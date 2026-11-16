"""WER on known pairs, normaliser behaviour, speed, and report statistics
(pooled WER, bootstrap intervals, cost)."""

import numpy as np
import pytest

from asr_bench.metrics import (
    bootstrap_indices,
    confidence_interval,
    hosted_api_cost_per_1000_min,
    normalise,
    pooled_wer,
    real_time_factor,
    self_hosted_cost_per_1000_min,
    word_errors,
)


# ---------- WER on known pairs ----------


def test_one_wrong_word_in_three():
    errors, words = word_errors("the cat sat", "the cat sit")
    assert (errors, words) == (1, 3)  # WER = 1/3


def test_perfect_transcript_has_no_errors():
    assert word_errors("good morning", "good morning") == (0, 2)


def test_empty_transcript_counts_every_word_as_missed():
    assert word_errors("good morning everyone", "") == (3, 3)  # WER = 100%


def test_extra_and_missing_words_both_count():
    # "very" inserted, "now" deleted: 2 errors over 4 reference words
    assert word_errors("please call me now", "please call me very") == (1, 4)
    assert word_errors("please call me now", "please very call me") == (2, 4)


def test_wer_can_exceed_100_percent():
    """A model that hallucinates many extra words can have more errors than words."""
    errors, words = word_errors("yes", "yes yes yes yes")
    assert errors > words


def test_empty_reference_is_rejected():
    with pytest.raises(ValueError):
        word_errors("", "anything")


# ---------- Normaliser ----------


def test_english_ignores_case_and_punctuation():
    assert normalise("Hello, World!", "en") == "hello world"


def test_english_treats_spelled_and_digit_numbers_the_same():
    assert normalise("twenty five", "en") == normalise("25", "en")


def test_english_expands_titles():
    assert normalise("Dr. Jones", "en") == "doctor jones"


@pytest.mark.parametrize(
    ("language", "text", "expected"),
    [
        ("de", "Über die Brücke, bitte!", "über die brücke bitte"),
        ("es", "«Si bien», dijo él.", "si bien dijo él"),
    ],
)
def test_other_languages_keep_accents_drop_punctuation(language, text, expected):
    assert normalise(text, language) == expected


def test_other_languages_do_not_convert_numbers():
    """A known limitation: "2017" and a spelled-out year don't match outside
    English, so number formatting can count as an error."""
    assert normalise("2017", "es") != normalise("dos mil diecisiete", "es")


def test_normalised_text_has_single_spaces():
    assert normalise("  «Hola»,   amigo  ", "es") == "hola amigo"


# ---------- Speed ----------


def test_real_time_factor():
    assert real_time_factor(latency_s=1.0, duration_s=10.0) == pytest.approx(0.1)


# ---------- Report statistics (step 6) ----------

def test_pooled_wer_weights_long_sentences_more():
    # 1 error in 3 words + 0 errors in 30 words = 1/33, not the average of 33% and 0%
    assert pooled_wer(np.array([1, 0]), np.array([3, 30])) == pytest.approx(1 / 33)


def test_bootstrap_indices_are_repeatable_and_in_range():
    a = bootstrap_indices(n_items=7, n_boot=100, seed=3)
    b = bootstrap_indices(n_items=7, n_boot=100, seed=3)
    assert a.shape == (100, 7)
    assert np.array_equal(a, b)
    assert a.min() >= 0 and a.max() <= 6


def test_interval_contains_the_estimate():
    rng = np.random.default_rng(0)
    errors = rng.integers(0, 5, size=40)
    words = rng.integers(5, 20, size=40)
    idx = bootstrap_indices(40, 2000, seed=0)
    samples = errors[idx].sum(axis=1) / words[idx].sum(axis=1)
    low, high = confidence_interval(samples)
    assert low <= pooled_wer(errors, words) <= high
    assert low < high


def test_interval_has_zero_width_when_every_sentence_scores_the_same():
    words = np.array([10, 20, 5, 15])
    errors = words // 5  # every sentence at exactly 20% WER
    idx = bootstrap_indices(4, 500, seed=0)
    low, high = confidence_interval(errors[idx].sum(axis=1) / words[idx].sum(axis=1))
    assert low == pytest.approx(0.2) and high == pytest.approx(0.2)


def test_self_hosted_cost():
    # RTF 0.6 -> 1,000 audio minutes take 600 minutes = 10 hours; at $0.50/h = $5
    assert self_hosted_cost_per_1000_min(rtf=0.6, usd_per_hour=0.5) == pytest.approx(5.0)


def test_hosted_api_cost():
    assert hosted_api_cost_per_1000_min(usd_per_minute=0.006) == pytest.approx(6.0)


def test_costs_are_none_when_price_not_set():
    assert self_hosted_cost_per_1000_min(rtf=0.6, usd_per_hour=None) is None
    assert hosted_api_cost_per_1000_min(usd_per_minute=None) is None
