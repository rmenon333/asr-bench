"""Text normalisation, word error counting and speed metrics.

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
