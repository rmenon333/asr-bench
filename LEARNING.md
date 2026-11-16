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

## Step 2 — Data download and loader (2026-11-16)

**New and changed files**
- `src/asr_bench/config.py` — reads `config.yaml` into a dictionary. It uses `pyyaml` (new dependency).
- `src/asr_bench/data.py` — downloads the datasets, reads their transcript files, and picks a fixed sample. Main pieces:
  - `Utterance` — one record: dataset, ID, language, reference text, audio file path, length in seconds.
  - `download_file` / `extract_tar` — fetch and unpack, skipping anything already done, so re-running is safe.
  - `read_librispeech` / `read_fleurs` — turn each dataset's own transcript format into a list of `Utterance`s.
  - `sample_utterances` — sorts, shuffles with the seed, and takes the first N.
- `src/asr_bench/cli.py` — new commands `asr-bench download` and `asr-bench sample --n 5`.
- `tests/test_data.py` — 7 tests that build tiny fake datasets on the fly, so they need no real download.
- `DATA.md` — licences, sizes, attribution, and how the data is used.
- New dependencies: `pyyaml` (config), `soundfile` (reads audio file length), `numpy` (needed by soundfile).

**Concept: a seeded random sample**
A computer's "random" numbers come from a formula started by a number called the *seed*. The same seed always gives the same "random" order. So we get a sample that is fair (not hand-picked) and also repeatable: anyone re-running the benchmark tests the exact same sentences. We shuffle once and take the first N, so a 5-utterance smoke test uses the same sentences as the start of the 20-utterance run.

**Interview question**
"Why test on a fixed random sample instead of the first 20 files?" Suggested answer: the first files in a dataset often come from one speaker or one chapter, which would bias results. A seeded sample spreads across speakers and is still reproducible, so different models and conditions are compared on the same sentences.
