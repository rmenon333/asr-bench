"""The CLI works: commands exist and exit cleanly."""

import pytest

from asr_bench.cli import main


def test_report_exits_ok():
    assert main(["report"]) == 0


def test_unknown_command_is_rejected():
    with pytest.raises(SystemExit):
        main(["fly"])
