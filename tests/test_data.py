"""The loader returns the same seeded sample every time."""

import pytest


@pytest.mark.skip(reason="build step 2")
def test_placeholder():
    """Same seed gives the same utterance IDs."""
