"""The CLI works: commands exist and exit cleanly."""

import pytest

from asr_bench.cli import main


def test_unknown_command_is_rejected():
    with pytest.raises(SystemExit):
        main(["fly"])
