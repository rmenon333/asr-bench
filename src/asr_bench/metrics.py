"""Text normalisation, word error counting, speed, uncertainty and cost.

Normalisation (cleaning both texts the same way before comparing):
- English: Whisper's English normaliser. Lower case, no punctuation, spelled
  and digit numbers made equal ("twenty five" = "25"), titles expanded
  ("Dr." = "doctor"), British/American spellings unified.
- Other languages: Whisper's basic normaliser. Lower case, no punctuation,
  accents kept. Numbers are NOT converted, so "2017" vs a spelled-out year
  counts as an error. This is a known limitation (see SPEC hypothesis 4).

Both normalisers come from the `whisper-normalizer` package (MIT), a copy of
the rules in OpenAI's Whisper repository.
"""

import jiwer
import numpy as np
from whisper_normalizer.basic import BasicTextNormalizer
from whisper_normalizer.english import EnglishTextNormalizer

_english = EnglishTextNormalizer()
_basic = BasicTextNormalizer()


def normalise(text: str, language: str) -> str:
    """Clean text for scoring: the English rules for "en", basic rules otherwise."""
    cleaned = _english(text) if language == "en" else _basic(text)
    return " ".join(cleaned.split())  # collapse repeated spaces


def word_errors(reference: str, hypothesis: str) -> tuple[int, int]:
    """Count word errors between two already-normalised texts.

    Returns (errors, reference word count). Errors are the fewest word swaps,
    deletions and insertions needed to turn the hypothesis into the reference.
    WER = errors / reference words. We keep both numbers, so an overall WER
    can be computed as total errors / total words, and long sentences count
    for more than short ones.
    """
    if not reference.strip():
        raise ValueError("reference text is empty after normalisation")
    result = jiwer.process_words(reference, hypothesis)
    errors = result.substitutions + result.deletions + result.insertions
    return errors, len(reference.split())


def real_time_factor(latency_s: float, duration_s: float) -> float:
    """Processing time / audio length. 0.1 means a 10 s clip took 1 s."""
    return latency_s / duration_s


# ---------- Aggregating and uncertainty (used by the report) ----------


def pooled_wer(errors: np.ndarray, words: np.ndarray) -> float:
    """Overall WER of a group: total errors / total reference words."""
    return float(np.sum(errors) / np.sum(words))


def bootstrap_indices(n_items: int, n_boot: int, seed: int) -> np.ndarray:
    """Random re-draws of n_items with repeats allowed, n_boot times.

    Each row is one pretend "re-run" of the test on a similar set of
    sentences. Shape: (n_boot, n_items). A fixed seed makes it repeatable.
    """
    rng = np.random.default_rng(seed)
    return rng.integers(0, n_items, size=(n_boot, n_items))


def confidence_interval(samples: np.ndarray) -> tuple[float, float]:
    """The middle 95% of bootstrap results: the 2.5th and 97.5th percentiles."""
    low, high = np.percentile(samples, [2.5, 97.5])
    return float(low), float(high)


# ---------- Cost (prices come from config.yaml; never hard-coded) ----------


def self_hosted_cost_per_1000_min(rtf: float, usd_per_hour: float | None) -> float | None:
    """Server cost to transcribe 1,000 audio minutes on one machine.

    1,000 minutes x RTF = minutes of processing; / 60 = hours; x hourly price.
    Returns None if no price is set.
    """
    if usd_per_hour is None:
        return None
    return 1000 * rtf / 60 * usd_per_hour


def hosted_api_cost_per_1000_min(usd_per_minute: float | None) -> float | None:
    """Hosted speech API cost for 1,000 audio minutes. None if no price is set."""
    if usd_per_minute is None:
        return None
    return 1000 * usd_per_minute
