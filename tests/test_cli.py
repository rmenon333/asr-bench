"""The CLI skeleton works: commands exist and exit cleanly."""

from asr_bench.cli import main


def test_report_exits_ok():
    assert main(["report"]) == 0


def test_full_run_is_not_yet_available(capsys):
    assert main(["run"]) == 0
    assert "step 5" in capsys.readouterr().out
