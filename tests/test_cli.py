"""The CLI skeleton works: both commands exist and exit cleanly."""

from asr_bench.cli import main


def test_run_smoke_exits_ok(capsys):
    assert main(["run", "--smoke"]) == 0
    assert "smoke" in capsys.readouterr().out


def test_report_exits_ok():
    assert main(["report"]) == 0
