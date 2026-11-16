"""The benchmark loop writes one correct CSV row per (model, dataset,
condition, utterance). A fake "model" stands in for Whisper, so this is fast."""

import csv

from asr_bench.run import CSV_COLUMNS, run_benchmark
from fakes import make_fake_fleurs


def fake_transcriber_factory(model_name: str):
    """Every clip is 'transcribed' as "hello world" in 0.5 seconds."""

    def transcribe(audio, language):
        return "Hello world.", 0.5

    return transcribe


def make_config(data_dir) -> dict:
    return {
        "seed": 42,
        "data_dir": str(data_dir),
        "runtime": {"compute_type": "int8", "cpu_threads": 4, "beam_size": 5},
        "datasets": [{"name": "fleurs_en", "source": "fleurs", "split": "test", "language": "en"}],
        "conditions": [
            {"name": "clean"},
            {"name": "telephony_noisy_10db", "telephony": True, "snr_db": 10},
        ],
    }


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_one_row_per_model_dataset_condition_utterance(tmp_path):
    make_fake_fleurs(tmp_path)  # 3 sentences
    out = tmp_path / "results.csv"
    run_benchmark(make_config(tmp_path), ["fake-a", "fake-b"], 2, out, fake_transcriber_factory)
    rows = read_rows(out)
    assert len(rows) == 2 * 1 * 2 * 2  # models x datasets x conditions x utterances
    assert list(rows[0].keys()) == CSV_COLUMNS


def test_row_contents(tmp_path):
    make_fake_fleurs(tmp_path)
    out = tmp_path / "results.csv"
    run_benchmark(make_config(tmp_path), ["fake"], 3, out, fake_transcriber_factory)
    rows = {(r["utt_id"], r["condition"]): r for r in read_rows(out)}

    row = rows[("a", "clean")]  # reference "Hello, world." vs hypothesis "Hello world."
    assert row["reference"] == "Hello, world."
    assert row["reference_norm"] == row["hypothesis_norm"] == "hello world"
    assert (row["errors"], row["ref_words"], row["wer"]) == ("0", "2", "0.0")
    assert float(row["rtf"]) == 0.5 / 2.0  # fake clips are 2 seconds long
    assert row["snr_db"] == ""  # no noise in the clean condition
    assert abs(float(rows[("a", "telephony_noisy_10db")]["snr_db"]) - 10) < 0.5
    assert row["beam_size"] == "5"
