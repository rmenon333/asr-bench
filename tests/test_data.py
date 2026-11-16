"""Loader tests. They use tiny fake datasets built in a temp folder, so they
run in a second without downloading anything."""

from pathlib import Path

from asr_bench.config import load_config
from asr_bench.data import (
    read_fleurs,
    read_librispeech,
    sample_utterances,
)
from fakes import make_fake_fleurs, make_fake_librispeech


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
