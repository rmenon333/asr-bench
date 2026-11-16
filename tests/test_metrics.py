"""WER on known reference/hypothesis pairs, and normaliser behaviour."""

import pytest


@pytest.mark.skip(reason="build step 4")
def test_placeholder():
    """WER of known pairs matches hand-computed values; normaliser handles case, punctuation, numbers."""
