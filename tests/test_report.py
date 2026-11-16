"""Report building: hypothesis-4 re-scoring, ranking changes, and a full
report from a small fake results file (charts and report.md are created)."""

import csv

import numpy as np

from asr_bench.report import build_report, rank_models, ranking_changed, rescore
from asr_bench.run import CSV_COLUMNS

MODELS = ["tiny", "base", "small", "medium"]
CONDITIONS = [{"name": "clean"}, {"name": "telephony_noisy_10db", "telephony": True, "snr_db": 10}]
DATASETS = [
    {"name": "fleurs_en", "source": "fleurs", "split": "test", "language": "en"},
    {"name": "fleurs_es", "source": "fleurs", "split": "test", "language": "es"},
]


def fake_config() -> dict:
    return {
        "models": MODELS,
        "datasets": DATASETS,
        "conditions": CONDITIONS,
        "cost": {
            "self_hosted_usd_per_hour": 0.145,
            "hosted_api_usd_per_minute": 0.006,
            "hosted_api_streaming_usd_per_minute": 0.01,
        },
    }


def write_fake_results(path, sentences_per_dataset: int = 6) -> None:
    """Bigger models make fewer mistakes; noise adds mistakes."""
    rng = np.random.default_rng(0)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for m_index, model in enumerate(MODELS):
            for d in DATASETS:
                for i in range(sentences_per_dataset):
                    for c in CONDITIONS:
                        words = 10
                        base_errors = 4 - m_index + (3 if c["name"] != "clean" else 0)
                        errors = max(0, base_errors + int(rng.integers(-1, 2)))
                        writer.writerow({
                            "model": model, "dataset": d["name"], "language": d["language"],
                            "condition": c["name"], "utt_id": f"u{i}", "duration_s": 5.0,
                            "snr_db": "", "reference": "Hello, World.", "hypothesis": "hello world",
                            "reference_norm": "hello world", "hypothesis_norm": "hello world",
                            "ref_words": words, "errors": errors, "wer": errors / words,
                            "latency_s": 0.1 * (m_index + 1), "rtf": 0.02 * (m_index + 1),
                            "compute_type": "int8", "cpu_threads": 4, "beam_size": 5, "seed": 42,
                        })  # fmt: skip


def test_rank_models_orders_best_first():
    assert rank_models({"a": 0.3, "b": 0.1, "c": 0.2}) == ["b", "c", "a"]


def test_ranking_change_needs_a_strict_swap():
    assert ranking_changed({"a": 0.1, "b": 0.2}, {"a": 0.3, "b": 0.2})  # a went from better to worse
    assert not ranking_changed({"a": 0.1, "b": 0.2}, {"a": 0.15, "b": 0.25})  # same order
    assert not ranking_changed({"a": 0.1, "b": 0.1}, {"a": 0.2, "b": 0.1})  # was a tie: not a flip


def test_rescore_with_lowercase_only_counts_punctuation():
    row = {"reference": "Hello, world.", "hypothesis": "hello world", "language": "en"}
    assert rescore(row, "whisper") == (0, 2)
    assert rescore(row, "lowercase") == (2, 2)  # "hello," and "world." differ


def test_report_builds_with_charts(tmp_path):
    results = tmp_path / "results.csv"
    write_fake_results(results)
    report_path = build_report(results, fake_config(), tmp_path / "out", n_boot=200)

    text = report_path.read_text()
    for section in ["Accuracy", "Speed and cost", "Can we tell them apart", "Hypotheses", "Limitations"]:
        assert section in text
    assert "n = 12 sentences" in text  # 6 sentences x 2 datasets per model x condition
    for chart in ["wer_by_model_condition.png", "accuracy_vs_latency.png", "wer_by_language.png"]:
        assert (tmp_path / "out" / "charts" / chart).stat().st_size > 1000
        assert f"charts/{chart}" in text
