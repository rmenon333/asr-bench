"""Audio conditions: clean, telephony (phone line), and pink noise at a target SNR.

Every function takes and returns audio as a numpy array of numbers between
about -1 and 1, at 16,000 samples per second (16 kHz), which is what Whisper
expects.

When a condition has both noise and telephony, the noise is in the caller's
room, so it goes through the phone line together with the voice, as on a real
call. Its loudness is set so the SNR is exact at the far end of the line.
See SPEC.md section 12.
"""

import hashlib
from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, resample_poly, sosfiltfilt

SAMPLE_RATE = 16000  # what Whisper expects
PHONE_RATE = 8000  # classic telephone sample rate
PHONE_BAND_HZ = (300.0, 3400.0)  # pitches a classic phone line lets through


# ---------- Loading and resampling ----------


def resample(audio: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
    """Change the sample rate (snapshots per second) of a signal."""
    if from_rate == to_rate:
        return audio
    divisor = gcd(from_rate, to_rate)
    return resample_poly(audio, to_rate // divisor, from_rate // divisor).astype(np.float32)


def load_audio(path: Path) -> np.ndarray:
    """Read an audio file as mono, 16 kHz, float32."""
    audio, rate = sf.read(path, dtype="float32", always_2d=True)
    mono = audio.mean(axis=1)  # average the channels if it is stereo
    return resample(mono, rate, SAMPLE_RATE)


# ---------- Telephony ----------


def telephony(audio: np.ndarray, rate: int = SAMPLE_RATE) -> np.ndarray:
    """Simulate a classic phone line.

    1. Drop to 8 kHz. This removes everything above 4 kHz.
    2. Band-pass filter to 300-3400 Hz. This removes the deep and the high pitches.
    3. Go back up to 16 kHz so the model gets its usual input format.
       (Going back up does not restore what was lost.)
    """
    narrow = resample(audio, rate, PHONE_RATE)
    band_filter = butter(4, PHONE_BAND_HZ, btype="bandpass", fs=PHONE_RATE, output="sos")
    filtered = sosfiltfilt(band_filter, narrow)
    back = resample(filtered, PHONE_RATE, rate)
    return fit_length(back, len(audio))


def fit_length(audio: np.ndarray, length: int) -> np.ndarray:
    """Trim or zero-pad to an exact length (resampling can be off by a sample)."""
    if len(audio) >= length:
        return audio[:length].astype(np.float32)
    return np.pad(audio, (0, length - len(audio))).astype(np.float32)


# ---------- Noise ----------


def noise_seed(seed: int, utt_id: str) -> int:
    """A stable number made from the run seed and the utterance ID.

    The same utterance always gets the same noise, so every model hears
    exactly the same noisy audio.
    """
    digest = hashlib.sha256(f"{seed}-{utt_id}".encode()).hexdigest()
    return int(digest[:16], 16)


def pink_noise(length: int, rng: np.random.Generator) -> np.ndarray:
    """Pink noise with average power 1.

    Start from white noise (equal energy at every pitch, like TV static) and
    turn down the higher pitches, so each octave gets equal energy. The result
    sounds deeper, like steady rain or an air-conditioner.
    """
    white = rng.standard_normal(length)
    spectrum = np.fft.rfft(white)
    freqs = np.fft.rfftfreq(length)
    freqs[0] = freqs[1]  # avoid dividing by zero at "0 Hz"
    pink = np.fft.irfft(spectrum / np.sqrt(freqs), n=length)
    return (pink / np.sqrt(np.mean(pink**2))).astype(np.float32)


def power(audio: np.ndarray) -> float:
    """Average power (loudness) of a signal."""
    return float(np.mean(audio.astype(np.float64) ** 2))


def scale_noise_to_snr(voice: np.ndarray, noise: np.ndarray, snr_db: float) -> np.ndarray:
    """Turn noise up or down so the voice is snr_db decibels louder than it.

    The voice loudness is the average over the whole clip, pauses included.
    """
    voice_power = power(voice)
    if voice_power == 0:
        raise ValueError("cannot set an SNR on silent audio")
    target_noise_power = voice_power / (10 ** (snr_db / 10))
    return noise * np.sqrt(target_noise_power / power(noise))


def add_noise_at_snr(clean: np.ndarray, snr_db: float, rng: np.random.Generator) -> np.ndarray:
    """Add pink noise so the voice is snr_db decibels louder than the noise."""
    noise = scale_noise_to_snr(clean, pink_noise(len(clean), rng), snr_db)
    return (clean + noise).astype(np.float32)


def measure_snr_db(clean: np.ndarray, noisy: np.ndarray) -> float:
    """Measure the actual SNR: voice loudness vs the loudness of (noisy - clean)."""
    return 10 * np.log10(power(clean) / power(noisy - clean))


# ---------- Applying a condition from config.yaml ----------


def apply_condition(
    audio: np.ndarray, condition: dict, seed: int, utt_id: str
) -> tuple[np.ndarray, float | None]:
    """Apply one condition from config.yaml to a clean 16 kHz clip.

    Returns (processed audio, measured SNR in dB). The SNR is None when no
    noise was added.

    Telephony + noise: the noise is in the caller's room, so voice and noise
    both go through the phone line. The line removes much of pink noise's deep
    rumble, so the room noise is set to whatever loudness gives exactly
    snr_db at the far end of the line (see SPEC.md section 12). The phone
    filter treats voice and noise independently, so filtering each and then
    adding them is the same as filtering the mix.
    """
    snr_db = condition.get("snr_db")
    on_phone = bool(condition.get("telephony"))

    voice = telephony(audio) if on_phone else audio
    if snr_db is None:
        return voice, None

    rng = np.random.default_rng(noise_seed(seed, utt_id))
    room_noise = pink_noise(len(audio), rng)
    heard_noise = telephony(room_noise) if on_phone else room_noise
    out = (voice + scale_noise_to_snr(voice, heard_noise, snr_db)).astype(np.float32)
    return out, measure_snr_db(voice, out)


def write_examples(
    audio: np.ndarray, conditions: list[dict], seed: int, utt_id: str, out_dir: Path
) -> list[Path]:
    """Save one clip in every condition as .wav files, for listening.

    If a clip would be too loud for a .wav file (above 1.0), it is turned down
    to fit. This is only for listening; the benchmark uses the unchanged audio.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for condition in conditions:
        processed, _ = apply_condition(audio, condition, seed, utt_id)
        peak = float(np.max(np.abs(processed)))
        if peak > 0.99:
            processed = processed * (0.99 / peak)
        path = out_dir / f"{utt_id}_{condition['name']}.wav"
        sf.write(path, processed, SAMPLE_RATE)
        paths.append(path)
    return paths
