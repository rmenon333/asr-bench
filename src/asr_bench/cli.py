"""Command-line entry point.

    uv run asr-bench download         fetch the datasets into data/
    uv run asr-bench sample [--n 5]   show the seeded sample for each dataset
    uv run asr-bench listen           save one clip in every condition, to hear
    uv run asr-bench run [--smoke]    run the benchmark (stub until step 4)
    uv run asr-bench report           build the report (stub until step 6)

Uses argparse from the standard library, so no extra dependency is needed.
"""

import argparse
from pathlib import Path

from asr_bench.conditions import load_audio, write_examples
from asr_bench.config import DEFAULT_CONFIG_PATH, load_config
from asr_bench.data import download_dataset, load_sample


def cmd_download(config: dict) -> int:
    """Download and unpack every dataset listed in config.yaml."""
    data_dir = Path(config["data_dir"])
    for dataset in config["datasets"]:
        download_dataset(dataset, data_dir)
    print("done")
    return 0


def cmd_sample(config: dict, n: int) -> int:
    """Print the first n sampled utterances of each dataset, as a check."""
    data_dir = Path(config["data_dir"])
    for dataset in config["datasets"]:
        utts = load_sample(dataset, data_dir, n, config["seed"])
        print(f"\n{dataset['name']} ({len(utts)} utterances)")
        for u in utts:
            print(f"  {u.utt_id:<24} {u.duration_s:5.1f}s  {u.reference[:70]}")
    return 0


def cmd_listen(config: dict, dataset_name: str, out_dir: Path) -> int:
    """Save the first sampled clip of a dataset in every condition as .wav files."""
    matches = [d for d in config["datasets"] if d["name"] == dataset_name]
    if not matches:
        names = ", ".join(d["name"] for d in config["datasets"])
        print(f"unknown dataset {dataset_name!r}; choose one of: {names}")
        return 1
    utt = load_sample(matches[0], Path(config["data_dir"]), 1, config["seed"])[0]
    print(f"{utt.dataset} / {utt.utt_id}: {utt.reference}")
    paths = write_examples(load_audio(utt.audio_path), config["conditions"], config["seed"], utt.utt_id, out_dir)
    for path in paths:
        print(f"  {path}")
    return 0


def cmd_run(smoke: bool) -> int:
    """Run the benchmark. With --smoke, run a tiny 5-utterance version."""
    mode = "smoke (5 utterances)" if smoke else "full"
    print(f"asr-bench run [{mode}]: not implemented yet (build steps 4-5).")
    return 0


def cmd_report() -> int:
    """Build results/report.md and charts from results/results.csv."""
    print("asr-bench report: not implemented yet (build step 6).")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse the command line and dispatch to the right command."""
    parser = argparse.ArgumentParser(prog="asr-bench", description="ASR benchmark")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("download", help="download datasets into data/")
    sample_parser = sub.add_parser("sample", help="show the seeded sample per dataset")
    sample_parser.add_argument("--n", type=int, default=None, help="default: smoke_sample_size")
    listen_parser = sub.add_parser("listen", help="save one clip in every condition as .wav")
    listen_parser.add_argument("--dataset", default="fleurs_en")
    listen_parser.add_argument("--out", type=Path, default=Path("data/examples"))
    run_parser = sub.add_parser("run", help="run the benchmark")
    run_parser.add_argument("--smoke", action="store_true", help="tiny 5-utterance run")
    sub.add_parser("report", help="build the report from results.csv")

    args = parser.parse_args(argv)
    if args.command == "run":
        return cmd_run(args.smoke)
    if args.command == "report":
        return cmd_report()

    config = load_config(args.config)
    if args.command == "download":
        return cmd_download(config)
    if args.command == "listen":
        return cmd_listen(config, args.dataset, args.out)
    return cmd_sample(config, args.n or config["smoke_sample_size"])


if __name__ == "__main__":
    raise SystemExit(main())
