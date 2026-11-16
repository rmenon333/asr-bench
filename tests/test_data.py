"""Loader tests. They use tiny fake datasets built in a temp folder, so they
run in a second without downloading anything."""

from pathlib import Path

import numpy as np
import soundfile as sf

from asr_bench.config import load_config
from asr_bench.data import (
    read_fleurs,
    read_librispeech,
    sample_utterances,
)


def write_silence(path: Path, seconds: float, sample_rate: int = 16000) -> None:
    """Write a silent audio file of the given length."""
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, np.zeros(int(seconds * sample_rate), dtype="float32"), sample_rate)


def make_fake_librispeech(root: Path) -> Path:
    """Two speakers, one chapter each, two utterances each (LibriSpeech layout)."""
    split_dir = root / "LibriSpeech" / "test-clean"
    for speaker, chapter in [("11", "100"), ("22", "200")]:
        chapter_dir = split_dir / speaker / chapter
        lines = []
        for n in range(2):
            utt_id = f"{speaker}-{chapter}-{n:04d}"
            write_silence(chapter_dir / f"{utt_id}.flac", 1.5)
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
        write_silence(lang_dir / "audio" / "test" / filename, 2.0)
        lines.append("\t".join([sentence_id, filename, raw, normalised, "x", "32000", "FEMALE"]))
    (lang_dir / "test.tsv").write_text("\n".join(lines) + "\n")
    return lang_dir


def test_librispeech_reads_ids_and_references(tmp_path):
    split_dir = make_fake_librispeech(tmp_path)
    utts = read_librispeech(split_dir, dataset="ls", language="en")
    assert len(utts) == 4
    first = sorted(utts, key=lambda u: u.utt_id)[0]
    assert first.utt_id == "11-100-0000"
    assert first.reference == "HELLO WORLD NUMBER 0"
    assert first.audio_path.exists()


def test_fleurs_keeps_raw_text_and_one_recording_per_sentence(tmp_path):
    lang_dir = make_fake_fleurs(tmp_path)
    utts = read_fleurs(lang_dir, dataset="fleurs_en", language="en")
    assert len(utts) == 3  # sentence 1 appears once, not twice
    by_id = {u.utt_id: u for u in utts}
    assert by_id["a"].reference == "Hello, world."  # raw text with punctuation
    assert "b" not in by_id  # the alphabetically-first file wins, deterministically


def test_same_seed_same_sample(tmp_path):
    utts = read_librispeech(make_fake_librispeech(tmp_path), dataset="ls", language="en")
    a = [u.utt_id for u in sample_utterances(utts, n=3, seed=42, dataset="ls")]
    b = [u.utt_id for u in sample_utterances(list(reversed(utts)), n=3, seed=42, dataset="ls")]
    assert a == b  # input order doesn't matter, only the seed


def test_smaller_sample_is_prefix_of_larger(tmp_path):
    """So a smoke run's utterances are also in the full run's sample."""
    utts = read_librispeech(make_fake_librispeech(tmp_path), dataset="ls", language="en")
    small = sample_utterances(utts, n=2, seed=7, dataset="ls")
    large = sample_utterances(utts, n=4, seed=7, dataset="ls")
    assert [u.utt_id for u in small] == [u.utt_id for u in large[:2]]


def test_sample_adds_duration(tmp_path):
    utts = read_librispeech(make_fake_librispeech(tmp_path), dataset="ls", language="en")
    sample = sample_utterances(utts, n=2, seed=1, dataset="ls")
    assert all(abs(u.duration_s - 1.5) < 0.01 for u in sample)


def test_sample_larger_than_dataset_returns_everything(tmp_path):
    utts = read_librispeech(make_fake_librispeech(tmp_path), dataset="ls", language="en")
    assert len(sample_utterances(utts, n=99, seed=1, dataset="ls")) == 4


def test_project_config_loads():
    config = load_config(Path(__file__).parent.parent / "config.yaml")
    assert config["smoke_sample_size"] == 5
    assert {d["language"] for d in config["datasets"]} == {"en", "es", "de"}
