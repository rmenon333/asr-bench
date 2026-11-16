"""A crashed run resumes without redoing or losing finished rows."""

import pytest


@pytest.mark.skip(reason="build step 5")
def test_placeholder():
    """Rows already in results.csv are skipped on restart."""
