"""WER on known reference/hypothesis pairs, normaliser behaviour, and RTF."""

import pytest

from asr_bench.metrics import normalise, real_time_factor, word_errors


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
