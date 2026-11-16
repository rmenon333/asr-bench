"""Tests for the audio conditions: noise level (SNR), pink-noise shape,
telephony band, and the "room noise first, then phone line" order.

They use synthetic test signals (tones), so they need no downloaded data.
"""

import numpy as np
import pytest
import soundfile as sf

from asr_bench.conditions import (
    SAMPLE_RATE,
    add_noise_at_snr,
    apply_condition,
    load_audio,
    measure_snr_db,
    noise_seed,
    pink_noise,
    telephony,
)


def tone(freq_hz: float, seconds: float = 2.0, sr: int = SAMPLE_RATE) -> np.ndarray:
    """A pure tone (a single pitch) at the given frequency."""
    t = np.arange(int(seconds * sr)) / sr
    return (0.5 * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)


def speech_like(seconds: float = 3.0) -> np.ndarray:
    """A rough stand-in for speech: several pitches whose loudness rises and falls."""
    t = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    voice = sum(np.sin(2 * np.pi * f * t) for f in (180, 450, 900, 2200))
    syllables = 0.5 + 0.5 * np.sin(2 * np.pi * 4 * t)  # ~4 "syllables" per second
    return (0.2 * voice * syllables).astype(np.float32)


def level_db(audio: np.ndarray) -> float:
    """Loudness (average power) in dB, ignoring the first/last 10% (filter edges)."""
    edge = len(audio) // 10
    middle = audio[edge:-edge]
    return 10 * np.log10(np.mean(middle.astype(np.float64) ** 2))


# ---------- Noise ----------


@pytest.mark.parametrize("snr_db", [20, 10, 5])
def test_noise_is_mixed_at_requested_snr(snr_db):
    clean = speech_like()
    noisy = add_noise_at_snr(clean, snr_db, np.random.default_rng(0))
    assert abs(measure_snr_db(clean, noisy) - snr_db) < 0.5  # the spec's tolerance


def test_pink_noise_has_equal_energy_per_octave():
    """Pink noise: each octave (doubling of pitch) carries about the same energy."""
    noise = pink_noise(2**18, np.random.default_rng(1))
    spectrum = np.abs(np.fft.rfft(noise)) ** 2
    freqs = np.fft.rfftfreq(len(noise), d=1 / SAMPLE_RATE)
    octaves = [(250, 500), (500, 1000), (1000, 2000), (2000, 4000)]
    energies_db = [10 * np.log10(spectrum[(freqs >= lo) & (freqs < hi)].sum()) for lo, hi in octaves]
    assert max(energies_db) - min(energies_db) < 1.5


def test_same_utterance_gets_same_noise_and_different_utterances_differ():
    a1 = pink_noise(1000, np.random.default_rng(noise_seed(42, "utt-1")))
    a2 = pink_noise(1000, np.random.default_rng(noise_seed(42, "utt-1")))
    b = pink_noise(1000, np.random.default_rng(noise_seed(42, "utt-2")))
    assert np.array_equal(a1, a2)
    assert not np.array_equal(a1, b)


# ---------- Telephony ----------


def test_telephony_keeps_speech_band():
    original = tone(1000)
    assert abs(level_db(telephony(original)) - level_db(original)) < 1.0


@pytest.mark.parametrize("freq_hz", [100, 6000])
def test_telephony_removes_very_low_and_very_high_pitches(freq_hz):
    original = tone(freq_hz)
    assert level_db(original) - level_db(telephony(original)) > 20


def test_telephony_keeps_length():
    original = speech_like(2.37)
    assert len(telephony(original)) == len(original)


# ---------- Conditions from config ----------


def test_clean_condition_leaves_audio_unchanged():
    audio = speech_like()
    out, snr = apply_condition(audio, {"name": "clean"}, seed=42, utt_id="u")
    assert np.array_equal(out, audio)
    assert snr is None


def test_noisy_condition_reports_measured_snr():
    audio = speech_like()
    _, snr = apply_condition(audio, {"name": "noisy_10db", "snr_db": 10}, seed=42, utt_id="u")
    assert abs(snr - 10) < 0.5


def test_room_noise_goes_through_phone_line():
    """Noise is added in the room first, so the phone line also cuts the noise's
    high pitches. Almost nothing should be left above 3.4 kHz."""
    audio = speech_like()
    condition = {"name": "telephony_noisy_10db", "telephony": True, "snr_db": 10}
    out, snr = apply_condition(audio, condition, seed=42, utt_id="u")
    spectrum = np.abs(np.fft.rfft(out)) ** 2
    freqs = np.fft.rfftfreq(len(out), d=1 / SAMPLE_RATE)
    share_above_band = spectrum[freqs > 3600].sum() / spectrum.sum()
    assert share_above_band < 0.001


def test_phone_plus_noise_is_exactly_the_target_snr_after_the_line():
    """The room noise is tuned so the caller-to-agent SNR is the stated 10 dB."""
    audio = speech_like()
    condition = {"name": "telephony_noisy_10db", "telephony": True, "snr_db": 10}
    out, snr = apply_condition(audio, condition, seed=42, utt_id="u")
    assert abs(measure_snr_db(telephony(audio), out) - 10) < 0.5
    assert abs(snr - 10) < 0.5


def test_load_audio_returns_16k_mono(tmp_path):
    stereo_8k = np.stack([tone(440, sr=8000), tone(440, sr=8000)], axis=1)
    path = tmp_path / "x.wav"
    sf.write(path, stereo_8k, 8000)
    audio = load_audio(path)
    assert audio.ndim == 1
    assert len(audio) == 2 * SAMPLE_RATE  # 2 seconds at 16 kHz
