"""Benchmark loop over models x datasets x conditions, writing one CSV row per clip.

For each model: load it, warm it up on one clip (untimed), then for each
dataset's sampled sentences, apply every condition, transcribe, score, and
write a row. Rows are written and flushed one at a time, so a crash keeps
everything finished so far. (Skipping finished rows on restart is step 5.)
"""

import csv
from collections.abc import Callable
from pathlib import Path

from asr_bench.conditions import apply_condition, load_audio
from asr_bench.data import load_sample
from asr_bench.metrics import normalise, real_time_factor, word_errors
from asr_bench.transcribe import Transcriber

CSV_COLUMNS = [
    "model", "dataset", "language", "condition", "utt_id", "duration_s", "snr_db",
    "reference", "hypothesis", "reference_norm", "hypothesis_norm",
    "ref_words", "errors", "wer", "latency_s", "rtf",
    "compute_type", "cpu_threads", "beam_size",
]  # fmt: skip


def run_benchmark(
    config: dict,
    models: list[str],
    sample_size: int,
    out_csv: Path,
    transcriber_factory: Callable[[str], Transcriber],
) -> int:
    """Run every (model, dataset, condition, sentence) and write results to out_csv.

    transcriber_factory turns a model name into a transcribe function. The
    real one loads Whisper; tests pass a fake one. Returns the number of rows.
    """
    runtime = config["runtime"]
    data_dir = Path(config["data_dir"])
    samples = {d["name"]: load_sample(d, data_dir, sample_size, config["seed"]) for d in config["datasets"]}

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    rows_written = 0
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for model_name in models:
            print(f"model {model_name}: loading")
            transcribe = transcriber_factory(model_name)
            warm_up(transcribe, samples)
            for dataset in config["datasets"]:
                print(f"  {dataset['name']}")
                for utt in samples[dataset["name"]]:
                    clean_audio = load_audio(utt.audio_path)
                    for condition in config["conditions"]:
                        audio, snr = apply_condition(clean_audio, condition, config["seed"], utt.utt_id)
                        hypothesis, latency = transcribe(audio, utt.language)
                        ref_norm = normalise(utt.reference, utt.language)
                        hyp_norm = normalise(hypothesis, utt.language)
                        errors, ref_words = word_errors(ref_norm, hyp_norm)
                        writer.writerow({
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
                            "compute_type": runtime["compute_type"],
                            "cpu_threads": runtime["cpu_threads"],
                            "beam_size": runtime["beam_size"],
                        })  # fmt: skip
                        f.flush()  # on disk now, in case of a crash
                        rows_written += 1
    return rows_written


def warm_up(transcribe: Transcriber, samples: dict) -> None:
    """Transcribe one clip without recording it. The first call is always
    slower (memory set-up), which would unfairly inflate the first latency."""
    first = next(utt for utts in samples.values() for utt in utts)
    transcribe(load_audio(first.audio_path), first.language)
