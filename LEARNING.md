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

## Step 3 — Audio conditions (2026-11-16)

**New and changed files**
- `src/asr_bench/conditions.py` — turns a clean clip into each test condition:
  - `load_audio` — reads any audio file as one channel at 16 kHz.
  - `telephony` — drops to 8 kHz, keeps only 300–3400 Hz, then returns to 16 kHz.
  - `pink_noise` — makes pink noise (white noise with the high pitches turned down).
  - `scale_noise_to_snr` / `add_noise_at_snr` — set the noise loudness for an exact SNR.
  - `measure_snr_db` — checks the SNR actually achieved.
  - `apply_condition` — reads a condition from `config.yaml` and applies it. It returns the audio plus the measured SNR.
  - `noise_seed` — makes the noise for each sentence identical across models.
  - `write_examples` — saves .wav files for listening.
- `src/asr_bench/cli.py` — new `asr-bench listen [--dataset fleurs_es]` command. It writes one clip in all 6 conditions to `data/examples/`.
- `tests/test_conditions.py` — 14 tests using synthetic tones: SNR accuracy, pink-noise shape, phone band, the room-noise-through-phone order, same-noise-per-sentence, and loading.
- `config.yaml` — the `telephony` condition now has `telephony: true`.
- `CONCEPTS.md` — new plain-English revision sheet with analogies.
- New dependency: `scipy` (standard library of scientific maths: resampling and filters).

**What we found while building**
Pink noise has a lot of deep rumble, and the phone line removes it. With "room noise at 10 dB", the caller-to-agent SNR came out at 12–15 dB instead of 10, so it was easier than its label. We now tune the room noise so the far end is exactly 10 dB. On the 100 sampled real clips, every noisy condition measures exactly on target.

**Concept: why test with synthetic tones instead of real speech?**
With a pure 1,000 Hz tone, we *know* the right answer: the phone line should keep it, and should remove a 100 Hz or 6,000 Hz tone. Real speech mixes everything together, so a test on it couldn't say exactly what "correct" looks like. Known inputs give unambiguous checks.

**Interview question**
"Your benchmark adds noise at 10 dB SNR. Is that the SNR the model actually sees on a phone call?" Suggested answer: not automatically. If the noise is in the caller's room, the phone line filters it along with the voice and changes the ratio. We measured this (12–15 dB instead of 10), calibrated the noise so the far-end SNR is the stated value, and wrote a test to keep it that way.

## Step 4 — Transcribe with one model, compute WER, write CSV (2026-11-16)

**New and changed files**
- `src/asr_bench/metrics.py` — `normalise` (cleans text with Whisper's rules: English rules for English, basic rules otherwise), `word_errors` (counts substitutions, deletions and insertions with `jiwer`), and `real_time_factor`.
- `src/asr_bench/transcribe.py` — loads a Whisper model with faster-whisper (CPU, int8, 4 threads, beam 5) and returns a `transcribe(audio, language)` function that also times itself.
- `src/asr_bench/run.py` — the main loop: model → dataset → sentence → condition → transcribe → score → one CSV row (19 columns, including raw and cleaned text). Each row is saved to disk immediately.
- `src/asr_bench/cli.py` — `asr-bench run --smoke` now really runs: `tiny`, 5 sentences × 5 datasets × 6 conditions = 150 transcripts → `results/smoke.csv`.
- `config.yaml` — new `models_dir`, `cpu_threads`, `beam_size`, `smoke_models`.
- `tests/test_metrics.py` (15 tests), `tests/test_run.py` (2 tests with a fake model), `tests/fakes.py` (shared fake datasets).
- New dependencies: `faster-whisper` (MIT), `jiwer` (Apache-2.0), `whisper-normalizer` (MIT).

**First smoke run (tiny model, 5 sentences per cell: far too small to conclude anything)**
- 150 transcripts in 88 s (including the 75 MB model download). The spec target is under 5 minutes.
- `tiny` processed about 1,600 s of audio in about 80 s (average RTF 0.05).
- The pattern looks plausible: clean LibriSpeech is easiest. German and phone + noise are hardest. Some noisy clips have WER above 100% because the model repeated itself.

**Concept: "lazy" work and where to put the stopwatch**
faster-whisper doesn't transcribe when you call it. It hands back a "to-do list" (a generator), and the real work happens as you read the results. If the stopwatch stopped right after the call, every model would look almost instantly fast. So we stop the clock only after the full text has been read. That's a classic benchmarking trap.

**Interview question**
"Why do you store both the raw and the normalised transcript instead of just the WER?" Suggested answer: the WER depends on the cleaning rules. Keeping the raw text means we can re-score with different rules, or audit a surprising number, without re-running hours of transcription. That's how we can test whether normalisation alone flips a model ranking.

## Step 5 — Resume, all models, full run (2026-11-16)

**New and changed files**
- `src/asr_bench/run.py`:
  - Now **resumable**. `read_finished` reads the existing results, `drop_partial_last_line` removes a row cut off by a crash, and only missing (model, dataset, condition, sentence) combinations are run. New rows are appended.
  - Refuses to mix rows made with different settings.
  - Skips loading a model that has nothing left to do.
  - Prints progress every 50 rows.
  - `score_row` now builds each row, which keeps the loop short.
- `src/asr_bench/cli.py` — `run` gained options: `--n` (sentences), `--models`, `--out`, `--fresh` (start over). `--smoke` always starts fresh.
- `tests/test_resume.py` — 6 tests with a fake model that "crashes" on purpose: restart after a crash, a finished run does nothing, a half-written line is redone, changed settings are refused, a bigger sample only adds new sentences, and `--fresh` starts over.
- `config.yaml` — `sample_size: 10`, chosen from the speed probe. `large-v3-turbo` was removed earlier by your decision.
- `results/results.csv` — the full run: 4 models × 5 datasets × 6 conditions × 10 sentences = 1,200 rows.

**Concept: "idempotent" (safe to re-run)**
A command is *idempotent* if running it twice gives the same result as running it once. `asr-bench run` is now idempotent: a second run on a finished file does nothing, and on a half-finished file it only completes the missing part. This matters for long jobs on laptops that sleep, crash or get closed.

**Interview question**
"Your full benchmark takes an hour. What happens if it dies at minute 50?" Suggested answer: every row is saved the moment it finishes, so we lose at most the one clip in progress. On restart, the run reads what's done, drops any half-written row, and continues. It also refuses to mix in rows produced with different settings, so a resumed run can't silently become an inconsistent one.

**Full run (2026-11-16): what actually happened**
- 1,200 rows in **59.7 min**, against an estimate of ~52 min from the probe. `medium` ran slower than in the probe (RTF 0.87 vs 0.78), and the estimate left out model loading and warm-up. The budget still held, but with no spare.
- Every row is unique and every model has 300 rows.
- The analysis (margins of error, charts, the hypotheses) is step 6. Until then these are raw numbers only.

## Step 6 — Report and charts (2026-11-16)

**New and changed files**
- `src/asr_bench/report.py` — reads `results/results.csv` (no models run) and writes `results/report.md` plus three charts in `results/charts/`. Main pieces:
  - `load_results` — turns the CSV rows into arrays indexed [model, condition, sentence]. It fails clearly if any result is missing.
  - `estimate` — any statistic plus its 95% bootstrap interval.
  - `section_*` / `hypothesis_1..4` — each builds one part of the report, with its rule written in.
  - `rescore` / `ranking_changed` — hypothesis 4: re-mark the saved raw text with other cleaning rules, and count real (non-tie) ranking swaps.
  - `chart_*` — the three matplotlib charts. Model sizes use one blue hue, light → dark, checked for colour-blind safety.
- `src/asr_bench/metrics.py` — new `pooled_wer`, `bootstrap_indices`, `confidence_interval`, and the two cost formulas.
- `config.yaml` — owner-approved AWS prices (with sources) and a `machine` description.
- `tests/test_metrics.py` (+7 tests), `tests/test_report.py` (4 tests, building a full report from a fake results file).
- New dependency: `matplotlib` (charts).

**What we caught while checking the output**
- Prices were displayed rounded ($0.145 showed as $0.14, and $0.006 as $0.01). They're now shown exactly.
- Hypothesis 4 first counted *ties* as ranking flips, which inflated the result from 3 to 11 cells. Now only real swaps count.
- The H2 verdict said "Mixed" when every condition was actually inconclusive. It now says "Unclear".

**Concept: why the report is generated, not written by hand**
Every number in `report.md` comes from code reading the CSV. If we re-run with more sentences, `make report` rebuilds everything consistently. A hand-written report goes stale, and invites "rounding in our favour". Interpretation and recommendations stay human-written (README and RECOMMENDATIONS.md), on top of the generated numbers.

**Interview question**
"Medium beats small by 3 WER points on clean audio. Is that real?" Suggested answer: it depends on the uncertainty, not the size of the gap. We ran a paired bootstrap on the same 50 sentences, and the difference's 95% interval is 1.1–5.5 points, entirely above zero. So with this data it's a clear difference, but the true gap could be as small as 1 point or as large as 5.5.

## Step 7 — README, recommendations skeleton, wrap-up (2026-11-16)

**New files**
- `README.md` — the project as a mini-PRD: problem, method, results (copied from `results/report.md`), limitations, what to do next in production, quick start, how to extend, and a repository map.
- `RECOMMENDATIONS.md` — a skeleton for the owner. The evidence for each use case is filled in; the recommended model and one-sentence trade-off are left blank.
- `LICENSE` — MIT, for the code only. The datasets keep their own CC BY 4.0 terms.

**Clean-clone check:** cloning into a temporary folder and running `make install`, `make test`, `make smoke` and `make report` all worked. The rebuilt report and charts were byte-for-byte identical to the committed ones, so the report is fully reproducible. The dataset download step was not repeated; it was verified in step 2.

### The whole codebase on one page

```
config.yaml ──► cli.py  (the commands: download, sample, listen, run, report)
                 │
   download ──► data.py         fetch LibriSpeech + FLEURS into data/; pick a seeded sample
   run      ──► run.py          for each model × dataset × sentence × condition:
                 ├─ conditions.py   clean / phone line / pink noise at an exact SNR
                 ├─ transcribe.py   faster-whisper on CPU, timed
                 └─ metrics.py      normalise text, count word errors, RTF
                 └─► results/results.csv   (one row per clip; resumable)
   report   ──► report.py       bootstrap intervals, hypothesis rules, cost, 3 charts
                 └─► results/report.md + results/charts/*.png
```

### Acceptance criteria (SPEC §9)
| Criterion | Status |
|---|---|
| Fresh clone to report in documented steps, macOS Apple Silicon | Met (clean-clone check above; README §6) |
| Unit tests: WER on known pairs, normaliser, noise SNR, telephony band, resume | Met (55 tests pass) |
| 5-utterance smoke run under 5 minutes | Met (~1.5 min for 150 clips) |
| Every chart states sample size and conditions | Met (in each chart's title) |
| Limitations name read speech, synthetic noise, single speaker, no diarisation, CPU timings | Met (README §4 and the report) |
| Deliverable: `RECOMMENDATIONS.md` written by the owner | **Open:** skeleton ready for the owner to fill in |

**Concept: reproducibility**
Anyone with this repo can get the *same* report, and we checked that. Three things make it work: a lockfile (exact package versions), fixed seeds (the same sentences, the same noise, the same bootstrap re-draws), and a report generated from data rather than written by hand. Reproducibility is what turns a one-off experiment into evidence other people can check and build on.

### Five interview questions worth practising
1. "Why not just pick the model with the best leaderboard score?" (Clean audio hides how much worse models get on phone + noise: tiny went from 17.7% to 59.9% WER, medium from 4.3% to 17.3%.)
2. "How do you know a difference between two models is real?" (A paired bootstrap on the same sentences; it's clear only if the 95% interval excludes zero.)
3. "What would change your recommendation?" (Real call audio, GPU timings, streaming delay, the hosted API's accuracy, a larger sample.)
4. "One hypothesis didn't hold. What did you do?" (Spanish did not degrade more than English, and sometimes less. We reported it as found, and noted that absolute points favour languages that start with low WER.)
5. "Why is self-hosting cheaper per minute here, and what's missing from that number?" (The compute floor is $0.61–$2.10 vs $6 per 1,000 minutes, but it excludes idle capacity, engineering, redundancy and monitoring.)
