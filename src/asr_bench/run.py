"""Benchmark loop over models x datasets x conditions, writing one CSV row per clip.

For each model: load it, warm it up on one clip (untimed), then for each
dataset's sampled sentences, apply every condition, transcribe, score, and
write a row. Rows are written and flushed one at a time.

Resume: if the results file already exists, finished rows are kept and only
missing (model, dataset, condition, sentence) combinations are run. A
half-written last line (from a crash) is dropped and redone. If a setting
that changes results differs from the existing rows, the run refuses to mix
them.
"""

import csv
import time
from collections.abc import Callable
from pathlib import Path

from asr_bench.conditions import apply_condition, load_audio
from asr_bench.data import Utterance, load_sample
from asr_bench.metrics import normalise, real_time_factor, word_errors
from asr_bench.transcribe import Transcriber

CSV_COLUMNS = [
    "model", "dataset", "language", "condition", "utt_id", "duration_s", "snr_db",
    "reference", "hypothesis", "reference_norm", "hypothesis_norm",
    "ref_words", "errors", "wer", "latency_s", "rtf",
    "compute_type", "cpu_threads", "beam_size", "seed",
]  # fmt: skip

# Settings that change results. Old and new rows must agree on all of them.
# (Sample size is not here: a smaller sample is the start of a larger one,
# so growing the sample keeps earlier rows valid.)
SETTINGS_COLUMNS = ["compute_type", "cpu_threads", "beam_size", "seed"]

RowKey = tuple[str, str, str, str]  # (model, dataset, condition, utt_id)


def run_settings(config: dict) -> dict[str, str]:
    """The settings for this run, as strings (the way they look in the CSV)."""
    runtime = config["runtime"]
    values = {
        "compute_type": runtime["compute_type"],
        "cpu_threads": runtime["cpu_threads"],
        "beam_size": runtime["beam_size"],
        "seed": config["seed"],
    }
    return {name: str(value) for name, value in values.items()}


def drop_partial_last_line(path: Path) -> None:
    """If the file doesn't end with a line break, the last row was cut off
    mid-write (a crash). Remove that partial row so it gets redone."""
    content = path.read_bytes()
    if content and not content.endswith(b"\n"):
        path.write_bytes(content[: content.rfind(b"\n") + 1])


def read_finished(path: Path, settings: dict[str, str]) -> set[RowKey]:
    """Return the keys of rows already in the results file.

    Raises ValueError if the file's columns or settings don't match this run.
    """
    if not path.exists() or path.stat().st_size == 0:
        return set()
    drop_partial_last_line(path)
    finished = set()
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != CSV_COLUMNS:
            raise ValueError(f"{path} has different columns; move it aside or use a fresh start")
        for row in reader:
            for name, value in settings.items():
                if row[name] != value:
                    raise ValueError(
                        f"{path} was made with {name}={row[name]}, this run uses {name}={value}. "
                        "Move the old file aside or use a fresh start; results with different "
                        "settings must not be mixed."
                    )
            finished.add((row["model"], row["dataset"], row["condition"], row["utt_id"]))
    return finished


def score_row(
    model_name: str, utt: Utterance, condition: dict, snr: float | None,
    hypothesis: str, latency: float, settings: dict[str, str],
) -> dict:  # fmt: skip
    """Normalise both texts, count errors, and build one CSV row."""
    ref_norm = normalise(utt.reference, utt.language)
    hyp_norm = normalise(hypothesis, utt.language)
    errors, ref_words = word_errors(ref_norm, hyp_norm)
    return {
        "model": model_name,
        "dataset": utt.dataset,
        "language": utt.language,
        "condition": condition["name"],
        "utt_id": utt.utt_id,
        "duration_s": round(utt.duration_s, 3),
        "snr_db": "" if snr is None else round(snr, 2),
        "reference": utt.reference,
        "hypothesis": hypothesis,
        "reference_norm": ref_norm,
        "hypothesis_norm": hyp_norm,
        "ref_words": ref_words,
        "errors": errors,
        "wer": round(errors / ref_words, 4),
        "latency_s": round(latency, 4),
        "rtf": round(real_time_factor(latency, utt.duration_s), 4),
        **settings,
    }


def run_benchmark(
    config: dict,
    models: list[str],
    sample_size: int,
    out_csv: Path,
    transcriber_factory: Callable[[str], Transcriber],
    fresh: bool = False,
) -> int:
    """Run every missing (model, dataset, condition, sentence) and append to out_csv.

    transcriber_factory turns a model name into a transcribe function. The
    real one loads Whisper; tests pass a fake one. fresh=True ignores and
    replaces any existing file. Returns the number of new rows written.
    """
    settings = run_settings(config)
    data_dir = Path(config["data_dir"])
    samples = {d["name"]: load_sample(d, data_dir, sample_size, config["seed"]) for d in config["datasets"]}

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    if fresh and out_csv.exists():
        out_csv.write_text("")
    finished = read_finished(out_csv, settings)

    # Everything this run should contain, minus what is already done.
    todo = [
        (model_name, dataset, utt, condition)
        for model_name in models
        for dataset in config["datasets"]
        for utt in samples[dataset["name"]]
        for condition in config["conditions"]
        if (model_name, dataset["name"], condition["name"], utt.utt_id) not in finished
    ]
    total_rows = len(todo) + len(finished)
    print(f"{len(finished)} rows already done, {len(todo)} to run")

    new_file = not out_csv.exists() or out_csv.stat().st_size == 0
    start = time.perf_counter()
    rows_written = 0
    with open(out_csv, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        if new_file:
            writer.writeheader()
        current_model = None
        audio_cache: dict[Path, object] = {}
        for model_name, dataset, utt, condition in todo:
            if model_name != current_model:
                print(f"model {model_name}: loading")
                transcribe = transcriber_factory(model_name)
                warm_up(transcribe, samples)
                current_model = model_name
                audio_cache.clear()
            if utt.audio_path not in audio_cache:
                audio_cache.clear()  # keep only the current sentence in memory
                audio_cache[utt.audio_path] = load_audio(utt.audio_path)
            audio, snr = apply_condition(audio_cache[utt.audio_path], condition, config["seed"], utt.utt_id)
            hypothesis, latency = transcribe(audio, utt.language)
            writer.writerow(score_row(model_name, utt, condition, snr, hypothesis, latency, settings))
            f.flush()  # on disk now, in case of a crash
            rows_written += 1
            if rows_written % 50 == 0 or rows_written == len(todo):
                done = len(finished) + rows_written
                minutes = (time.perf_counter() - start) / 60
                print(f"  {model_name} / {dataset['name']}: {done}/{total_rows} rows, {minutes:.1f} min")
    return rows_written


def warm_up(transcribe: Transcriber, samples: dict) -> None:
    """Transcribe one clip without recording it. The first call is always
    slower (memory set-up), which would unfairly inflate the first latency."""
    first = next(utt for utts in samples.values() for utt in utts)
    transcribe(load_audio(first.audio_path), first.language)
