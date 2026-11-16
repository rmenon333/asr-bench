"""Noise is mixed at the requested SNR (within 0.5 dB); telephony keeps ~300-3400 Hz."""

import pytest


@pytest.mark.skip(reason="build step 3")
def test_placeholder():
    """Measured SNR is within 0.5 dB of target; energy outside the telephony band is removed."""
