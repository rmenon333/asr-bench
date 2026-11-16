"""Command-line entry point: `uv run asr-bench run` and `uv run asr-bench report`.

Uses argparse from the standard library, so no extra dependency is needed.
The commands are stubs for now; later build steps fill them in.
"""

import argparse


def cmd_run(smoke: bool) -> int:
    """Run the benchmark. With --smoke, run a tiny 5-utterance version."""
    mode = "smoke (5 utterances)" if smoke else "full"
    print(f"asr-bench run [{mode}]: not implemented yet (build steps 2-5).")
    return 0


def cmd_report() -> int:
    """Build results/report.md and charts from results/results.csv."""
    print("asr-bench report: not implemented yet (build step 6).")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse the command line and dispatch to the right command."""
    parser = argparse.ArgumentParser(prog="asr-bench", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="run the benchmark")
    run_parser.add_argument("--smoke", action="store_true", help="tiny 5-utterance run")
    sub.add_parser("report", help="build the report from results.csv")

    args = parser.parse_args(argv)
    if args.command == "run":
        return cmd_run(args.smoke)
    return cmd_report()


if __name__ == "__main__":
    raise SystemExit(main())
