"""Resume: a crashed or stopped run continues where it left off, without
redoing finished clips, duplicating rows, or mixing incompatible settings."""

import csv

import pytest

from asr_bench.run import run_benchmark
from fakes import make_fake_fleurs
from test_run import make_config


class CountingTranscriber:
    """A fake model that counts its calls, and can 'crash' after N calls."""

    def __init__(self, crash_after: int | None = None):
        self.calls = 0
        self.crash_after = crash_after

    def factory(self, model_name: str):
        def transcribe(audio, language):
            self.calls += 1
            if self.crash_after is not None and self.calls > self.crash_after:
                raise RuntimeError("simulated crash")
            return "hello world", 0.1

        return transcribe


def row_keys(path) -> list[tuple]:
    with open(path, newline="", encoding="utf-8") as f:
        return [(r["model"], r["dataset"], r["condition"], r["utt_id"]) for r in csv.DictReader(f)]


# 2 models x 1 dataset x 2 conditions x 3 sentences = 12 rows.
# Each model also does 1 untimed warm-up call.
MODELS = ["fake-a", "fake-b"]
TOTAL_ROWS = 12


def test_restart_after_crash_finishes_without_duplicates(tmp_path):
    make_fake_fleurs(tmp_path)
    out = tmp_path / "results.csv"
    config = make_config(tmp_path)

    crashing = CountingTranscriber(crash_after=6)  # 1 warm-up + 5 rows, then crash
    with pytest.raises(RuntimeError):
        run_benchmark(config, MODELS, 3, out, crashing.factory)
    assert len(row_keys(out)) == 5  # finished rows were saved before the crash

    second = CountingTranscriber()
    run_benchmark(config, MODELS, 3, out, second.factory)
    keys = row_keys(out)
    assert len(keys) == TOTAL_ROWS
    assert len(set(keys)) == TOTAL_ROWS  # no duplicates
    assert second.calls == (TOTAL_ROWS - 5) + 2  # only missing rows, plus 2 warm-ups


def test_finished_run_does_no_work_when_restarted(tmp_path):
    make_fake_fleurs(tmp_path)
    out = tmp_path / "results.csv"
    run_benchmark(make_config(tmp_path), MODELS, 3, out, CountingTranscriber().factory)
    again = CountingTranscriber()
    run_benchmark(make_config(tmp_path), MODELS, 3, out, again.factory)
    assert again.calls == 0  # not even a warm-up
    assert len(row_keys(out)) == TOTAL_ROWS


def test_half_written_last_line_is_dropped_and_redone(tmp_path):
    make_fake_fleurs(tmp_path)
    out = tmp_path / "results.csv"
    run_benchmark(make_config(tmp_path), MODELS, 3, out, CountingTranscriber().factory)
    content = out.read_bytes()
    out.write_bytes(content[:-15])  # simulate power loss mid-write

    run_benchmark(make_config(tmp_path), MODELS, 3, out, CountingTranscriber().factory)
    keys = row_keys(out)
    assert len(keys) == TOTAL_ROWS and len(set(keys)) == TOTAL_ROWS


def test_changed_settings_are_refused(tmp_path):
    make_fake_fleurs(tmp_path)
    out = tmp_path / "results.csv"
    run_benchmark(make_config(tmp_path), MODELS, 3, out, CountingTranscriber().factory)
    changed = make_config(tmp_path)
    changed["runtime"]["beam_size"] = 1
    with pytest.raises(ValueError, match="beam_size"):
        run_benchmark(changed, MODELS, 3, out, CountingTranscriber().factory)


def test_larger_sample_later_only_adds_new_sentences(tmp_path):
    """Smaller samples are the start of larger ones, so growing the sample
    keeps earlier rows valid and only the new sentences are run."""
    make_fake_fleurs(tmp_path)
    out = tmp_path / "results.csv"
    run_benchmark(make_config(tmp_path), MODELS, 2, out, CountingTranscriber().factory)
    grow = CountingTranscriber()
    run_benchmark(make_config(tmp_path), MODELS, 3, out, grow.factory)
    assert grow.calls == 2 * 2 * 1 + 2  # 2 models x 2 conditions x 1 new sentence, + warm-ups
    assert len(row_keys(out)) == TOTAL_ROWS


def test_fresh_start_ignores_old_rows(tmp_path):
    make_fake_fleurs(tmp_path)
    out = tmp_path / "results.csv"
    run_benchmark(make_config(tmp_path), MODELS, 3, out, CountingTranscriber().factory)
    again = CountingTranscriber()
    run_benchmark(make_config(tmp_path), MODELS, 3, out, again.factory, fresh=True)
    assert again.calls == TOTAL_ROWS + 2
    assert len(row_keys(out)) == TOTAL_ROWS
