"""Tiny fake datasets for tests, built in a temp folder (no downloads)."""

from pathlib import Path

import numpy as np
import soundfile as sf


def write_tone(path: Path, seconds: float, sample_rate: int = 16000) -> None:
    """Write a quiet 440 Hz tone of the given length (not silence, so noise
    can be mixed at an SNR)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    t = np.arange(int(seconds * sample_rate)) / sample_rate
    sf.write(path, (0.1 * np.sin(2 * np.pi * 440 * t)).astype("float32"), sample_rate)


def make_fake_librispeech(root: Path) -> Path:
    """Two speakers, one chapter each, two utterances each (LibriSpeech layout)."""
    split_dir = root / "LibriSpeech" / "test-clean"
    for speaker, chapter in [("11", "100"), ("22", "200")]:
        chapter_dir = split_dir / speaker / chapter
        lines = []
        for n in range(2):
            utt_id = f"{speaker}-{chapter}-{n:04d}"
            write_tone(chapter_dir / f"{utt_id}.flac", 1.5)
            lines.append(f"{utt_id} HELLO WORLD NUMBER {n}")
        (chapter_dir / f"{speaker}-{chapter}.trans.txt").write_text("\n".join(lines) + "\n")
    return split_dir


def make_fake_fleurs(root: Path) -> Path:
    """Three sentences; sentence 1 is read by two speakers (as in real FLEURS)."""
    lang_dir = root / "fleurs" / "en_us"
    rows = [
        ("1", "b.wav", "Hello, world.", "hello world"),
        ("1", "a.wav", "Hello, world.", "hello world"),
        ("2", "c.wav", "Good morning!", "good morning"),
        ("3", "d.wav", "Thank you.", "thank you"),
    ]
    lines = []
    for sentence_id, filename, raw, normalised in rows:
        write_tone(lang_dir / "audio" / "test" / filename, 2.0)
        lines.append("\t".join([sentence_id, filename, raw, normalised, "x", "32000", "FEMALE"]))
    (lang_dir / "test.tsv").write_text("\n".join(lines) + "\n")
    return lang_dir
