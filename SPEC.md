# SPEC: asr-bench — Speech-to-text quality benchmark for contact-center conditions

Owner: Rohan Menon (product owner). Built with Claude Code. Spec-driven: nothing is built that is not in this file.

## 1. Why this exists
Contact-center speech AI (live captions, call transcripts, summaries, QA) is only as good as the transcription underneath it. Teams usually pick an ASR model from a leaderboard measured on clean audio, then are surprised in production. This project answers a product question with data:

> **Which Whisper model size should you ship for which contact-center use case, given accuracy, latency and cost, once audio is noisy, narrowband (telephone) and multilingual?**

It is a decision aid, not a model-training project.

## 2. Users and decisions it supports
- A product manager choosing a model for (a) live captions, (b) post-call transcripts, (c) analytics / summaries.
- An engineer who wants a reproducible harness to re-run when a new model ships.

Output the user should walk away with: a one-page recommendation table ("for use case X, ship model Y, because Z") backed by charts.

## 3. Non-goals
- No model training or fine-tuning.
- No real customer audio. Public datasets only (see 4).
- No claims about any employer's systems or numbers.
- No web UI. A CLI and a generated report are enough.

## 4. Data (public only)
Claude Code must verify each dataset's current availability and licence before using it, and record the licence in `DATA.md`.
- **LibriSpeech** `test-clean` and `test-other` (English, read speech).
- **FLEURS** (multilingual read speech): English, Spanish and German. (Hindi deferred; see 12.)
- Do not commit audio to git. Download scripts only. Cache under `data/` (git-ignored).

### Conditions (applied to the same utterances so comparisons are fair)
| Condition | How |
|---|---|
| `clean` | original audio, resampled to 16 kHz |
| `telephony` | downsample to 8 kHz, band-limit to ~300–3400 Hz, then back to 16 kHz for the model |
| `noisy_20db`, `noisy_10db`, `noisy_5db` | add synthetic pink noise at the stated SNR (pink is closer to real ambient noise than white; see 12) |
| `telephony_noisy_10db` | pink noise added in the caller's room, then voice and noise both go through the telephony line; noise loudness is set so the SNR after the line is 10 dB |

Noise mixing must be verified by a test that measures the actual SNR within 0.5 dB.

## 5. Models and runtime
- Runtime: `faster-whisper` on CPU with int8 (the baseline; must work on an Apple M-series Mac).
- Optional, only if time allows: `mlx-whisper` as a second runtime to compare speed on Apple Silicon.
- Models: `tiny`, `base`, `small`, `medium`. (`large-v3-turbo` deferred; see 12.) Model list lives in `config.yaml`.
- Default sample: small enough that the full run (all models × sets × conditions) finishes in about 1 hour on an Apple M4. The exact number per (set × condition) is set after measuring speed in step 4. Fixed random seed. Configurable.
- Language is given to the model (no automatic language detection).
- Runs must be resumable: a crash must not lose finished work.

## 6. Metrics
- **WER** with `jiwer`, after normalising both reference and hypothesis with the Whisper text normaliser (English) or a basic normaliser (other languages). Document the choice, because normalisation changes WER.
- **Latency:** per-utterance wall-clock time for a whole clip (batch, not streaming); report p50 and p95. Label it as clip processing time, not live-caption delay.
- **RTF** (real-time factor) = processing time / audio duration.
- **Cost per 1,000 audio minutes:** two columns, both driven by values in `config.yaml` that the user fills in (do not hard-code prices): (a) self-hosted compute estimate from RTF and an hourly machine price, (b) a hosted-API price per minute. Label these clearly as assumptions.
- Report confidence: bootstrap 95% interval for WER per cell, or state clearly if sample size is too small to separate two models.

## 7. Hypotheses to test (do not assume the answer; report what the data says)
1. Accuracy gaps between model sizes widen under telephony and noise compared with clean audio.
2. A mid-size model gives most of the accuracy of the largest at a fraction of the latency.
3. Non-English languages degrade more than English under the same conditions.
4. Normalisation choices can change WER enough to flip a model ranking.

## 8. Deliverables
1. `make bench` (or `uv run asr-bench run`) runs everything from a clean checkout; `make report` builds the report.
2. `results/results.csv`: one row per (model, language, condition, utterance) with reference, hypothesis, WER, latency.
3. `results/report.md` plus PNG charts: WER by model × condition; accuracy vs latency scatter; WER by language.
4. `RECOMMENDATIONS.md`: a table mapping use cases (live captions, post-call transcript, analytics) to a recommended model with the trade-off in one sentence each, written by the product owner, using the numbers.
5. `README.md` structured as a mini-PRD: problem, method, results, limitations, "what I would do next in production".
6. `LEARNING.md`: running notes on what the code does, written for a non-Python reader.

## 9. Acceptance criteria
- Fresh clone to report in documented steps, on macOS Apple Silicon.
- Unit tests pass for: WER calculation on known pairs, normaliser behaviour, noise SNR accuracy, telephony filter band, resume logic.
- A 5-utterance smoke run completes in under 5 minutes (`make smoke`).
- Every chart states sample size and conditions in its title or caption.
- Limitations section names at least: read speech is easier than real calls, synthetic noise is not real noise, single-speaker audio, no diarisation, CPU-only timings are not production timings.

## 10. Suggested repo layout
```
asr-bench/
  README.md  SPEC.md  CLAUDE.md  LEARNING.md  DATA.md  RECOMMENDATIONS.md
  config.yaml  Makefile  pyproject.toml
  src/asr_bench/   (data.py, conditions.py, transcribe.py, metrics.py, run.py, report.py)
  tests/
  results/         (committed: csv, report, charts)
  data/            (git-ignored)
```

## 11. Build order for Claude Code
1. Scaffold repo, tooling, empty tests, `make smoke` skeleton.
2. Data download + 5-utterance loader.
3. Conditions (telephony, noise) with tests.
4. Transcribe with one model; compute WER; write CSV.
5. Resume support; all models; all conditions.
6. Report and charts.
7. README, LEARNING.md, and a short "how to extend" section.
Stop after each step and show what changed so the product owner can review.

## 12. Decisions log
- 2026-11-16: Hindi removed from scope. Whisper's basic normaliser strips Devanagari vowel signs, so Hindi WER would be misleading without extra work.
- 2026-11-16: Noise is pink only (more production-like than white), which also keeps the number of conditions down.
- 2026-11-16: Language is passed to the model, so that WER isn't polluted by language-detection errors.
- 2026-11-16: Telephony = band-limiting only (no codec).
- 2026-11-16: Telephony + noise: the noise is added in the caller's room *before* the phone line (more production-like than the original "telephony, then noise"). The line removes much of pink noise's low rumble, which left the far-end SNR at 12–15 dB instead of 10. The room noise is therefore tuned so the SNR after the line is exactly 10 dB.
- 2026-11-16: Transcription settings, fixed for every model and recorded on every CSV row: beam size 5 (Whisper's standard), 4 CPU threads (the M4's performance cores), int8, no silence trimming (VAD off), each clip transcribed on its own. One untimed warm-up clip per model before timing starts.
- 2026-11-16: Normalisation: Whisper's English normaliser for English, and Whisper's basic normaliser (lower case, no punctuation, accents kept, numbers not converted) for Spanish and German. Both come from the `whisper-normalizer` package. Raw and normalised text are both saved, so scores can be recomputed with other rules (hypothesis 4).
- 2026-11-16: Overall WER for a group of clips = total word errors ÷ total reference words (not an average of per-clip WERs).
- 2026-11-16: `make smoke` writes to `results/smoke.csv` (git-ignored) so smoke output never mixes with real results.
- 2026-11-16: `large-v3-turbo` removed from scope for this exercise. The largest model tested is `medium`.
- 2026-11-16: Added `asr-bench listen`, which saves one clip in every condition as .wav (in git-ignored `data/examples/`) so a person can hear the conditions.
- 2026-11-16: The full benchmark must finish in about 1 hour, so the default sample is small. The report states the sample size and confidence intervals.

## 13. Future enhancement candidates (not in scope now)
- Hindi (and other non-Latin scripts), with character error rate (CER) and a script-aware normaliser.
- Automatic language detection, measured as its own error source.
- G.711 μ-law codec in the telephony condition.
- Real recorded noise (e.g. babble, call-centre ambience) instead of synthetic noise.
- Streaming simulation to measure true live-caption delay.
- Larger samples, for tighter confidence intervals.
- `large-v3-turbo` (and other newer large models), to check whether a distilled large model beats `medium` on accuracy per second.
- A fast mode (beam size 1, greedy) closer to how live captions are run.
- Number normalisation for Spanish and German ("2017" vs a spelled-out year currently counts as an error).
