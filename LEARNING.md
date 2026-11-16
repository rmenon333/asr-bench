# LEARNING.md — running notes for a non-Python reader

## Step 1 — Scaffold (2026-11-16)

**New files**
- `pyproject.toml` — the project's "manifest": its name, the Python version, its dependencies, and the `asr-bench` command it installs. `uv` reads it.
- `uv.lock` — the exact version of every installed package, so a fresh clone gets an identical environment. Generated; don't edit by hand.
- `.python-version` — tells uv to use Python 3.12.
- `src/asr_bench/cli.py` — the command line. `asr-bench run` and `asr-bench report` exist but only print "not implemented yet".
- `src/asr_bench/{data,conditions,transcribe,metrics,run,report}.py` — empty modules, one per job, each saying which build step fills it in.
- `config.yaml` — every knob for a run: models, datasets, conditions, sample size, seed, cost assumptions. Not read by code yet.
- `Makefile` — short aliases (`make test`, `make smoke`, ...) for longer `uv run ...` commands.
- `tests/` — `test_cli.py` really runs. The others are placeholders marked "skip" until their build step.
- `.gitignore`, `.env.example`, `results/.gitkeep` — hygiene: keeps audio, weights, data and secrets out of git.

**Concept: the virtual environment and the lockfile**
Every Python project needs particular versions of particular libraries. Installing them for the whole computer causes projects to clash, so `uv sync` creates a private folder (`.venv/`) for this project only. The lockfile pins exact versions, so the benchmark gives the same environment on any machine. That is part of what makes results reproducible.

**Interview question**
"Why separate configuration (`config.yaml`) from code?" Suggested answer: the decisions a PM wants to change (which models, how many samples, price assumptions) can be changed and reviewed without touching logic. A results file can also be traced back to the exact config that produced it.
