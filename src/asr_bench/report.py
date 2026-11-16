"""Build results/report.md and PNG charts from results/results.csv.

Reads the results file only: no models are run. Every number in the report is
computed here from the CSV. Hypothesis verdicts follow rules written into the
report, so a reader can check them.

Uncertainty: every WER comes with a 95% bootstrap interval. We re-draw the
sentences with repeats allowed, thousands of times, and see how much the WER
moves. Comparisons between models re-draw the SAME sentences for both models
("paired"), because every model was tested on identical sentences.
"""

from dataclasses import dataclass
from pathlib import Path

import csv

import matplotlib
import matplotlib.ticker

matplotlib.use("Agg")  # draw to files, no window
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from whisper_normalizer.basic import BasicTextNormalizer  # noqa: E402

from asr_bench.metrics import (  # noqa: E402
    bootstrap_indices,
    confidence_interval,
    hosted_api_cost_per_1000_min,
    normalise,
    self_hosted_cost_per_1000_min,
    word_errors,
)

N_BOOT = 2000  # bootstrap re-draws
BOOT_SEED = 0

# Hypothesis 2 thresholds (a product judgement; change here if you disagree):
H2_SHARE_THRESHOLD = 0.80  # "most of the accuracy": >= 80% of the tiny -> largest WER improvement
H2_LATENCY_THRESHOLD = 0.50  # "a fraction of the latency": <= half the largest model's p50

# Chart styling. Model sizes are ordered, so they get one blue hue from light
# (smallest) to dark (largest). Palette checked for colour-blind safety.
MODEL_COLORS = ["#6da7ec", "#3987e5", "#256abf", "#104281"]
SURFACE, INK, INK_MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"

CONDITION_LABELS = {
    "clean": "Clean",
    "telephony": "Phone line",
    "noisy_20db": "Noise 20 dB",
    "noisy_10db": "Noise 10 dB",
    "noisy_5db": "Noise 5 dB",
    "telephony_noisy_10db": "Phone + noise 10 dB",
}
LANGUAGE_LABELS = {"en": "English", "es": "Spanish", "de": "German"}
WORST_CONDITION = "telephony_noisy_10db"  # used in side-by-side charts


# ---------- Loading results into arrays ----------


@dataclass
class Results:
    """The results file as arrays, indexed [model, condition, sentence]."""

    models: list[str]
    conditions: list[str]
    sentences: list[tuple[str, str]]  # (dataset, utt_id)
    dataset_of: np.ndarray  # dataset name per sentence
    language_of: np.ndarray  # language per sentence
    errors: np.ndarray  # [model, condition, sentence]
    latency: np.ndarray  # [model, condition, sentence]
    words: np.ndarray  # reference words per sentence
    duration: np.ndarray  # audio seconds per sentence
    rows: list[dict]
    settings: dict[str, str]


def load_results(path: Path, config: dict) -> Results:
    """Read results.csv. Fails clearly if any (model, condition, sentence) is missing."""
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    present = {r["model"] for r in rows}
    models = [m for m in config["models"] if m in present]
    conditions = [c["name"] for c in config["conditions"]]
    sentences = sorted({(r["dataset"], r["utt_id"]) for r in rows})
    s_index = {s: i for i, s in enumerate(sentences)}
    m_index = {m: i for i, m in enumerate(models)}
    c_index = {c: i for i, c in enumerate(conditions)}

    shape = (len(models), len(conditions), len(sentences))
    errors = np.full(shape, np.nan)
    latency = np.full(shape, np.nan)
    words = np.zeros(len(sentences))
    duration = np.zeros(len(sentences))
    dataset_of = np.empty(len(sentences), dtype=object)
    language_of = np.empty(len(sentences), dtype=object)
    for r in rows:
        if r["model"] not in m_index or r["condition"] not in c_index:
            continue
        m, c, s = m_index[r["model"]], c_index[r["condition"]], s_index[(r["dataset"], r["utt_id"])]
        errors[m, c, s] = int(r["errors"])
        latency[m, c, s] = float(r["latency_s"])
        words[s] = int(r["ref_words"])
        duration[s] = float(r["duration_s"])
        dataset_of[s], language_of[s] = r["dataset"], r["language"]
    if np.isnan(errors).any():
        missing = int(np.isnan(errors).sum())
        raise ValueError(f"{missing} (model, condition, sentence) results are missing; finish the run first")
    settings = {k: rows[0][k] for k in ("compute_type", "cpu_threads", "beam_size", "seed")}
    return Results(models, conditions, sentences, dataset_of, language_of, errors.astype(int),
                   latency, words, duration, rows, settings)  # fmt: skip


# ---------- Statistics helpers ----------


def wer_of(errors_1d: np.ndarray, words: np.ndarray, idx: np.ndarray) -> np.ndarray:
    """Pooled WER over the sentences in idx. idx can be one draw or many (rows)."""
    return errors_1d[idx].sum(axis=-1) / words[idx].sum(axis=-1)


def estimate(stat, subset: np.ndarray, n_boot: int, seed: int = BOOT_SEED) -> tuple[float, float, float]:
    """Return (value, low, high): the statistic on the real sentences, and its
    95% interval from re-drawing those sentences n_boot times."""
    point = float(stat(subset))
    draws = subset[bootstrap_indices(len(subset), n_boot, seed)]
    low, high = confidence_interval(stat(draws))
    return point, low, high


def sentences_where(res: Results, dataset: str | None = None, language: str | None = None,
                    fleurs_only: bool = False) -> np.ndarray:  # fmt: skip
    """Indices of sentences matching a filter."""
    keep = np.ones(len(res.sentences), dtype=bool)
    if dataset is not None:
        keep &= res.dataset_of == dataset
    if language is not None:
        keep &= res.language_of == language
    if fleurs_only:
        keep &= np.array([d.startswith("fleurs") for d in res.dataset_of])
    return np.flatnonzero(keep)


def pct(x: float) -> str:
    return f"{100 * x:.1f}"


def interval(low: float, high: float) -> str:
    return f"[{pct(low)}–{pct(high)}]"


def rank_models(wer_by_model: dict[str, float]) -> list[str]:
    """Models from lowest WER (best) to highest."""
    return sorted(wer_by_model, key=wer_by_model.get)


def ranking_changed(before: dict[str, float], after: dict[str, float]) -> bool:
    """True if some pair of models swaps order: one was strictly better
    before and strictly worse after. Ties are not counted as a change,
    because the order of tied models is arbitrary."""
    models = list(before)
    for i, a in enumerate(models):
        for b in models[i + 1 :]:
            if (before[a] - before[b]) * (after[a] - after[b]) < 0:
                return True
    return False


# ---------- Hypothesis 4: re-scoring with other normalisation rules ----------

_basic = BasicTextNormalizer()
RULES = {
    "whisper": "Whisper rules (English rules for English, basic rules otherwise) — the main results",
    "basic_all": "Basic rules for every language (no English number/spelling handling)",
    "lowercase": "Lower-case only (punctuation kept)",
}


def rescore(row: dict, rule: str) -> tuple[int, int]:
    """Recount (errors, reference words) for one row under a normalisation rule."""
    ref, hyp = row["reference"], row["hypothesis"]
    if rule == "whisper":
        ref, hyp = normalise(ref, row["language"]), normalise(hyp, row["language"])
    elif rule == "basic_all":
        ref, hyp = " ".join(_basic(ref).split()), " ".join(_basic(hyp).split())
    elif rule == "lowercase":
        ref, hyp = " ".join(ref.lower().split()), " ".join(hyp.lower().split())
    else:
        raise ValueError(f"unknown rule {rule}")
    return word_errors(ref, hyp)


def rescored_arrays(res: Results, rule: str) -> tuple[np.ndarray, np.ndarray]:
    """Errors [model, condition, sentence] and words [sentence] under a rule."""
    s_index = {s: i for i, s in enumerate(res.sentences)}
    errors = np.zeros_like(res.errors)
    words = np.zeros_like(res.words)
    for r in res.rows:
        if r["model"] not in res.models or r["condition"] not in res.conditions:
            continue
        e, w = rescore(r, rule)
        s = s_index[(r["dataset"], r["utt_id"])]
        errors[res.models.index(r["model"]), res.conditions.index(r["condition"]), s] = e
        words[s] = w
    return errors, words


# ---------- Report sections ----------


def section_overview(res: Results, config: dict) -> str:
    n_sent = len(res.sentences)
    per_dataset = n_sent // len(set(res.dataset_of))
    datasets = ", ".join(sorted(set(res.dataset_of)))
    return f"""# asr-bench report

_Generated by `make report` from `results/results.csv`. Do not edit by hand; re-run to rebuild._

## What was tested
- **Models:** {", ".join(res.models)} (faster-whisper, {res.settings["compute_type"]}, CPU, \
{res.settings["cpu_threads"]} threads, beam size {res.settings["beam_size"]}; language given to the model).
- **Machine:** {config.get("machine", "not recorded")}.
- **Data:** {datasets}. **{per_dataset} sentences per dataset** (seed {res.settings["seed"]}), \
so **n = {n_sent} sentences** per model × condition.
- **Conditions:** {", ".join(CONDITION_LABELS.get(c, c) for c in res.conditions)}. Noise is synthetic pink noise; \
"Phone + noise" adds the noise in the caller's room, then sends it through the phone line, \
tuned to 10 dB at the far end.
- **Clips:** {len(res.rows)} transcriptions in total.

## How to read this report
- **WER** = word errors per 100 reference words. Lower is better.
- **[a–b]** = 95% bootstrap interval. With this many sentences, the true WER could plausibly be anywhere in that range.
  Where two models' comparison interval includes zero, **this data cannot tell them apart**.
- This is a **small sample**. Treat differences of a few points with caution unless the comparison table says they are clear.
"""


def section_accuracy(res: Results, n_boot: int) -> str:
    all_s = np.arange(len(res.sentences))
    lines = [f"## Accuracy\n\n### WER by model and condition (all datasets, n = {len(all_s)} sentences per cell)\n"]
    lines.append("| Model | " + " | ".join(CONDITION_LABELS.get(c, c) for c in res.conditions) + " |")
    lines.append("|---" * (len(res.conditions) + 1) + "|")
    for m, model in enumerate(res.models):
        cells = []
        for c in range(len(res.conditions)):
            point, low, high = estimate(lambda i: wer_of(res.errors[m, c], res.words, i), all_s, n_boot)
            cells.append(f"{pct(point)} {interval(low, high)}")
        lines.append(f"| {model} | " + " | ".join(cells) + " |")

    datasets = sorted(set(res.dataset_of))
    n_per = len(sentences_where(res, dataset=datasets[0]))
    lines.append(f"\n### WER by model and dataset (all conditions pooled, n = {n_per} sentences × "
                 f"{len(res.conditions)} conditions per cell)\n")  # fmt: skip
    lines.append("| Model | " + " | ".join(datasets) + " |")
    lines.append("|---" * (len(datasets) + 1) + "|")
    all_conditions = res.errors.sum(axis=1)  # [model, sentence]
    words_all = res.words * len(res.conditions)
    for m, model in enumerate(res.models):
        cells = []
        for d in datasets:
            subset = sentences_where(res, dataset=d)
            point, low, high = estimate(lambda i: wer_of(all_conditions[m], words_all, i), subset, n_boot)
            cells.append(f"{pct(point)} {interval(low, high)}")
        lines.append(f"| {model} | " + " | ".join(cells) + " |")
    lines.append("\n![WER by model and condition](charts/wer_by_model_condition.png)\n")
    lines.append("![WER by language](charts/wer_by_language.png)\n")
    return "\n".join(lines)


def speed_by_model(res: Results) -> dict[str, dict[str, float]]:
    """p50 / p95 latency and overall RTF per model, over every clip."""
    out = {}
    for m, model in enumerate(res.models):
        lat = res.latency[m].ravel()
        audio = res.duration.sum() * len(res.conditions)
        out[model] = {
            "p50": float(np.percentile(lat, 50)),
            "p95": float(np.percentile(lat, 95)),
            "rtf": float(lat.sum() / audio),
        }
    return out


def section_speed_cost(res: Results, config: dict) -> str:
    cost = config.get("cost", {})
    per_hour = cost.get("self_hosted_usd_per_hour")
    batch = cost.get("hosted_api_usd_per_minute")
    stream = cost.get("hosted_api_streaming_usd_per_minute")
    api = hosted_api_cost_per_1000_min(batch)
    speed = speed_by_model(res)

    def money(x: float | None) -> str:
        return "not set" if x is None else f"${x:,.2f}"

    def price(x: float | None) -> str:
        return "not set" if x is None else f"${x:g}"

    lines = [
        "## Speed and cost\n",
        f"Per clip, over all {res.latency.shape[1] * res.latency.shape[2]} clips per model. "
        "Latency is the time to transcribe a **whole clip** (batch), not live-caption delay. "
        "RTF = processing time ÷ audio length (below 1 = faster than real time).\n",
        "| Model | Latency p50 (s) | Latency p95 (s) | RTF | Self-hosted $ / 1,000 audio min | Hosted API $ / 1,000 audio min |",
        "|---|---|---|---|---|---|",
    ]
    for model, s in speed.items():
        own = self_hosted_cost_per_1000_min(s["rtf"], per_hour)
        lines.append(f"| {model} | {s['p50']:.2f} | {s['p95']:.2f} | {s['rtf']:.3f} | {money(own)} | {money(api)} |")
    lines.append(f"""
**Cost assumptions (from `config.yaml`; prices change, so check before relying on them):**
- *Self-hosted* = 1,000 × RTF ÷ 60 hours × {price(per_hour)}/hour. The server is AWS EC2 c7g.xlarge, \
on-demand, US East. This assumes the server runs as fast as the test machine and is fully used. \
Real deployments add idle time, redundancy and engineering cost.
- *Hosted API* = Amazon Transcribe standard **batch** at {price(batch)}/min. \
**Streaming** (needed for live captions) is {price(stream)}/min = \
{money(hosted_api_cost_per_1000_min(stream))} per 1,000 minutes.
- The hosted API's accuracy was **not** measured here; only its price is shown.

![Accuracy vs latency](charts/accuracy_vs_latency.png)
""")
    return "\n".join(lines)


def section_separability(res: Results, n_boot: int) -> str:
    all_s = np.arange(len(res.sentences))
    pairs = list(zip(res.models[:-1], res.models[1:]))
    lines = [
        "## Can we tell them apart?\n",
        "Each neighbouring pair of sizes, judged on the **same** sentences. The number is how many WER points the "
        "larger model saves, with its 95% interval. **Clear** = the interval is entirely above zero.\n",
        "| Condition | " + " | ".join(f"{a} → {b}" for a, b in pairs) + " |",
        "|---" * (len(pairs) + 1) + "|",
    ]
    for c, cond in enumerate(res.conditions):
        cells = []
        for a, b in pairs:
            ia, ib = res.models.index(a), res.models.index(b)
            point, low, high = estimate(
                lambda i: wer_of(res.errors[ia, c], res.words, i) - wer_of(res.errors[ib, c], res.words, i),
                all_s, n_boot)  # fmt: skip
            verdict = "**clear**" if low > 0 else ("larger is worse" if high < 0 else "can't separate")
            cells.append(f"{pct(point)} {interval(low, high)} {verdict}")
        lines.append(f"| {CONDITION_LABELS.get(cond, cond)} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def verdict_from_counts(n_yes: int, n_no: int, n_total: int) -> str:
    """Supported if every comparison is clearly in favour, partly if some are,
    not supported if clearly against, otherwise unclear."""
    if n_yes == n_total:
        return "**Supported**"
    if n_yes > 0:
        return f"**Partly supported** ({n_yes} of {n_total} comparisons clear)"
    if n_no > 0:
        return f"**Not supported** ({n_no} of {n_total} comparisons clearly the other way)"
    return "**Unclear** (no comparison is clear with this sample)"


def hypothesis_1(res: Results, n_boot: int) -> str:
    all_s = np.arange(len(res.sentences))
    clean = res.conditions.index("clean")
    largest = res.models[-1]
    pairs = [(res.models[0], largest), (res.models[-2], largest)]
    lines = [
        "### H1. Accuracy gaps between model sizes widen under telephony and noise\n",
        "**Test:** gap = WER(smaller) − WER(larger). For each degraded condition: how much bigger is the gap than on "
        "clean audio (WER points), on the same sentences. **Clear** = interval above zero.\n",
        "| Condition | " + " | ".join(f"Gap widening {a} vs {b}" for a, b in pairs) + " |",
        "|---" * (len(pairs) + 1) + "|",
    ]
    n_yes = n_no = n_total = 0
    for c, cond in enumerate(res.conditions):
        if c == clean:
            continue
        cells = []
        for a, b in pairs:
            ia, ib = res.models.index(a), res.models.index(b)

            def widening(i, ia=ia, ib=ib, c=c):
                gap = wer_of(res.errors[ia, c], res.words, i) - wer_of(res.errors[ib, c], res.words, i)
                gap_clean = wer_of(res.errors[ia, clean], res.words, i) - wer_of(res.errors[ib, clean], res.words, i)
                return gap - gap_clean

            point, low, high = estimate(widening, all_s, n_boot)
            n_total += 1
            n_yes += low > 0
            n_no += high < 0
            cells.append(f"{pct(point)} {interval(low, high)}" + (" **clear**" if low > 0 else ""))
        lines.append(f"| {CONDITION_LABELS.get(cond, cond)} | " + " | ".join(cells) + " |")
    lines.append(f"\n**Verdict:** {verdict_from_counts(n_yes, n_no, n_total)}.\n")
    return "\n".join(lines)


def hypothesis_2(res: Results, n_boot: int) -> str:
    all_s = np.arange(len(res.sentences))
    smallest, largest = res.models[0], res.models[-1]
    speed = speed_by_model(res)
    i0, iL = res.models.index(smallest), res.models.index(largest)
    lines = [
        f"### H2. A mid-size model gives most of the accuracy of the largest ({largest}) at a fraction of the latency\n",
        f"**Test:** accuracy share = how much of the {smallest} → {largest} WER improvement a model achieves "
        f"(100% = as good as {largest}). Latency share = its p50 latency ÷ {largest}'s. **Rule (a product judgement, "
        f"set in `report.py`):** supported if the share's interval stays ≥ {H2_SHARE_THRESHOLD:.0%} and latency is "
        f"≤ {H2_LATENCY_THRESHOLD:.0%} of {largest}'s.\n",
        f"Latency share (all clips): " + ", ".join(
            f"{m} {speed[m]['p50'] / speed[largest]['p50']:.0%}" for m in res.models[1:-1]) + ".\n",
        "| Condition | " + " | ".join(f"Accuracy share: {m}" for m in res.models[1:-1]) + " |",
        "|---" * (len(res.models) - 1) + "|",
    ]
    mid = res.models[-2]  # the model the verdict is about: the largest of the smaller ones
    im = res.models.index(mid)
    meets = fails = 0
    for c, cond in enumerate(res.conditions):
        cells = []
        for m in res.models[1:-1]:
            ix = res.models.index(m)

            def share(i, ix=ix, c=c):
                w0 = wer_of(res.errors[i0, c], res.words, i)
                return (w0 - wer_of(res.errors[ix, c], res.words, i)) / (w0 - wer_of(res.errors[iL, c], res.words, i))

            point, low, high = estimate(share, all_s, n_boot)
            cells.append(f"{point:.0%} [{low:.0%}–{high:.0%}]")
            if ix == im:
                meets += low >= H2_SHARE_THRESHOLD
                fails += high < H2_SHARE_THRESHOLD
        lines.append(f"| {CONDITION_LABELS.get(cond, cond)} | " + " | ".join(cells) + " |")
    fast_enough = speed[mid]["p50"] / speed[largest]["p50"] <= H2_LATENCY_THRESHOLD
    n = len(res.conditions)
    if not fast_enough:
        verdict = f"**Not supported** for {mid}: its latency is above {H2_LATENCY_THRESHOLD:.0%} of {largest}'s"
    elif meets == n:
        verdict = f"**Supported** for {mid} in every condition"
    elif fails == n:
        verdict = f"**Not supported** for {mid}: its accuracy share is clearly below {H2_SHARE_THRESHOLD:.0%} in every condition"
    elif meets == 0 and fails == 0:
        verdict = (f"**Unclear** for {mid}: its accuracy share is close to {H2_SHARE_THRESHOLD:.0%} and the "
                   "interval includes the threshold in every condition")  # fmt: skip
    else:
        verdict = (f"**Mixed** for {mid}: clearly ≥ {H2_SHARE_THRESHOLD:.0%} in {meets} of {n} conditions, "
                   f"clearly below in {fails}, unclear in {n - meets - fails}")  # fmt: skip
    lines.append(f"\n**Verdict:** {verdict}.\n")
    return "\n".join(lines)


def hypothesis_3(res: Results, n_boot: int) -> str:
    fleurs = sentences_where(res, fleurs_only=True)
    languages = [lang for lang in ("en", "es", "de") if lang in set(res.language_of[fleurs])]
    others = [lang for lang in languages if lang != "en"]
    clean = res.conditions.index("clean")
    subsets = {lang: sentences_where(res, language=lang, fleurs_only=True) for lang in languages}
    lines = [
        "### H3. Non-English languages degrade more than English under the same conditions\n",
        "**Test (FLEURS only, the same sentences translated into each language):** degradation = WER(condition) − "
        "WER(clean), in points. The table shows how much **more** a language degrades than English. Positive = "
        "degrades more. **Clear** = interval entirely on one side of zero. Languages have different sentence "
        f"samples, so they are re-drawn independently (n = {len(subsets['en'])} sentences per language).\n",
        "| Model | Condition | " + " | ".join(f"Extra degradation: {LANGUAGE_LABELS[o]} vs English" for o in others) + " |",
        "|---|---" + "|---" * len(others) + "|",
    ]
    counts = {o: [0, 0, 0] for o in others}  # more, less, total
    for m, model in enumerate(res.models):
        for c, cond in enumerate(res.conditions):
            if c == clean:
                continue
            cells = []
            for o in others:

                def degradation(i, m=m, c=c):
                    return wer_of(res.errors[m, c], res.words, i) - wer_of(res.errors[m, clean], res.words, i)

                point = degradation(subsets[o]) - degradation(subsets["en"])
                draws_o = subsets[o][bootstrap_indices(len(subsets[o]), n_boot, BOOT_SEED + 1)]
                draws_en = subsets["en"][bootstrap_indices(len(subsets["en"]), n_boot, BOOT_SEED + 2)]
                low, high = confidence_interval(degradation(draws_o) - degradation(draws_en))
                counts[o][0] += low > 0
                counts[o][1] += high < 0
                counts[o][2] += 1
                tag = " **more**" if low > 0 else (" **less**" if high < 0 else "")
                cells.append(f"{pct(point)} {interval(low, high)}{tag}")
            lines.append(f"| {model} | {CONDITION_LABELS.get(cond, cond)} | " + " | ".join(cells) + " |")
    lines.append("")
    for o in others:
        more, less, total = counts[o]
        lines.append(f"- **{LANGUAGE_LABELS[o]}:** clearly degrades more than English in {more} of {total} "
                     f"model × condition comparisons, clearly less in {less}, unclear in {total - more - less}.")  # fmt: skip
    total_more = sum(v[0] for v in counts.values())
    total_less = sum(v[1] for v in counts.values())
    total = sum(v[2] for v in counts.values())
    lines.append(f"\n**Verdict:** {verdict_from_counts(total_more, total_less, total)}. Absolute points are used; "
                 "a language that starts with a higher clean WER has more room to degrade.\n")  # fmt: skip
    return "\n".join(lines)


def hypothesis_4(res: Results) -> str:
    rescored = {rule: rescored_arrays(res, rule) for rule in RULES}
    lines = [
        "### H4. Normalisation choices can change WER enough to flip a model ranking\n",
        "**Test:** re-score the saved raw transcripts under three rules (no models re-run), then compare model "
        "rankings with the main (Whisper) rule.\n",
    ]
    lines += [f"- `{rule}`: {text}" for rule, text in RULES.items()]
    lines += ["", "**Overall WER by rule (all conditions and datasets):**\n",
              "| Model | " + " | ".join(f"`{rule}`" for rule in RULES) + " |", "|---" * (len(RULES) + 1) + "|"]
    for m, model in enumerate(res.models):
        cells = [pct(e[m].sum() / (w.sum() * len(res.conditions))) for e, w in rescored.values()]
        lines.append(f"| {model} | " + " | ".join(cells) + " |")

    base_e, base_w = rescored["whisper"]
    flips_condition, flips_cell, n_cells, examples = {}, {}, 0, []
    datasets = sorted(set(res.dataset_of))
    for rule in ("basic_all", "lowercase"):
        e, w = rescored[rule]
        flips_condition[rule] = flips_cell[rule] = 0
        for c, cond in enumerate(res.conditions):

            def wers(E, W, s, c=c):
                return {m: E[i, c, s].sum() / W[s].sum() for i, m in enumerate(res.models)}

            all_s = np.arange(len(res.sentences))
            if ranking_changed(wers(base_e, base_w, all_s), wers(e, w, all_s)):
                flips_condition[rule] += 1
            for d in datasets:
                s = sentences_where(res, dataset=d)
                before, after = wers(base_e, base_w, s), wers(e, w, s)
                if ranking_changed(before, after):
                    flips_cell[rule] += 1
                    if len(examples) < 5:
                        examples.append(f"{d} / {CONDITION_LABELS.get(cond, cond)} under `{rule}`: "
                                        f"{' < '.join(rank_models(before))} → {' < '.join(rank_models(after))}")  # fmt: skip
        n_cells = len(res.conditions) * len(datasets)
    lines.append("\n**Ranking changes vs the Whisper rule** (a change = two models swap order; ties don't count). "
                 "Examples are written best → worst:\n")
    for rule in ("basic_all", "lowercase"):
        lines.append(f"- `{rule}`: overall ranking changed in {flips_condition[rule]} of {len(res.conditions)} "
                     f"conditions; per dataset × condition cell (n = {len(sentences_where(res, dataset=datasets[0]))} "
                     f"sentences each) in {flips_cell[rule]} of {n_cells} cells.")  # fmt: skip
    if examples:
        lines.append("\nExamples: " + "; ".join(examples) + ".")
    any_condition = sum(flips_condition.values()) > 0
    any_cell = sum(flips_cell.values()) > 0
    verdict = ("**Supported**: a normalisation choice changed an overall model ranking" if any_condition else
               "**Partly supported**: rankings changed only in small per-dataset cells, not overall" if any_cell else
               "**Not supported**: no ranking changed, though WER levels did")  # fmt: skip
    lines.append(f"\n**Verdict:** {verdict}. Note that rankings in small cells can also differ by chance, "
                 "so cell-level flips mainly show how fragile small-sample rankings are.\n")  # fmt: skip
    return "\n".join(lines)


def section_limitations(res: Results) -> str:
    return f"""## Limitations
- **Read speech is easier than real calls.** LibriSpeech and FLEURS are people reading prepared text clearly: no \
hesitations, interruptions, accents under stress, or cross-talk.
- **Synthetic noise is not real noise.** Steady pink noise is easier to "see through" than babble, music or a TV.
- **Single-speaker audio, no diarisation.** Real calls have two or more speakers, and separating who said what is \
not measured.
- **CPU-only timings are not production timings.** Speeds were measured on one laptop CPU, with no GPU and no \
batching. A production server could be much faster or slower.
- **Small sample.** n = {len(res.sentences)} sentences per model × condition, and \
{len(sentences_where(res, dataset=sorted(set(res.dataset_of))[0]))} per dataset. Intervals are wide, and close \
models often cannot be separated.
- **Telephony is band-limiting only.** No phone codec compression, packet loss or echo.
- **Hosted-API accuracy not measured.** Only its price is compared.
- **Possible training overlap.** Whisper may have seen similar public audio in training, which could flatter its \
results on these datasets.
"""


# ---------- Charts ----------


def style_axes(ax) -> None:
    """Recessive axes: no top/right frame, light horizontal grid behind the marks."""
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK_MUTED)
    ax.tick_params(colors=INK_MUTED, labelcolor=INK)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def grouped_bars(ax, res: Results, groups: list[tuple[str, np.ndarray, int]], n_boot: int) -> None:
    """Draw bars: one group per (label, sentence subset, condition), one bar per model."""
    n_models = len(res.models)
    width = 0.8 / n_models
    for m, model in enumerate(res.models):
        values, lows, highs = [], [], []
        for _label, subset, c in groups:
            point, low, high = estimate(lambda i: wer_of(res.errors[m, c], res.words, i), subset, n_boot)
            values.append(100 * point)
            lows.append(100 * (point - low))
            highs.append(100 * (high - point))
        x = np.arange(len(groups)) + (m - (n_models - 1) / 2) * width
        ax.bar(x, values, width=width, color=MODEL_COLORS[m % len(MODEL_COLORS)], label=model,
               edgecolor=SURFACE, linewidth=1.5, zorder=2)  # fmt: skip
        ax.errorbar(x, values, yerr=[lows, highs], fmt="none", ecolor=INK_MUTED, elinewidth=1, capsize=0, zorder=3)
    ax.set_xticks(np.arange(len(groups)), [label for label, _, _ in groups])


def chart_wer_by_condition(res: Results, path: Path, n_boot: int) -> None:
    all_s = np.arange(len(res.sentences))
    fig, ax = plt.subplots(figsize=(11, 5.2), facecolor=SURFACE)
    style_axes(ax)
    groups = [(CONDITION_LABELS.get(c, c), all_s, i) for i, c in enumerate(res.conditions)]
    grouped_bars(ax, res, groups, n_boot)
    ax.set_ylabel("Word error rate (%)", color=INK)
    fig.suptitle("Word error rate by model and condition", x=0.06, ha="left", fontsize=14, color=INK)
    ax.set_title(f"n = {len(all_s)} sentences per bar ({len(set(res.dataset_of))} datasets pooled). "
                 "Whiskers: 95% bootstrap interval. Lower is better.",
                 loc="left", fontsize=10, color=INK_MUTED)  # fmt: skip
    ax.legend(title="Model", frameon=False, ncols=len(res.models), loc="upper left", alignment="left")
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def chart_accuracy_vs_latency(res: Results, path: Path, n_boot: int) -> None:
    all_s = np.arange(len(res.sentences))
    panels = [c for c in ("clean", WORST_CONDITION) if c in res.conditions]
    fig, axes = plt.subplots(1, len(panels), figsize=(11, 4.8), sharey=True, facecolor=SURFACE)
    axes = np.atleast_1d(axes)
    for ax, cond in zip(axes, panels):
        style_axes(ax)
        c = res.conditions.index(cond)
        for m, model in enumerate(res.models):
            p50 = float(np.median(res.latency[m, c]))
            point, low, high = estimate(lambda i: wer_of(res.errors[m, c], res.words, i), all_s, n_boot)
            ax.errorbar([p50], [100 * point], yerr=[[100 * (point - low)], [100 * (high - point)]], fmt="o",
                        color=MODEL_COLORS[m % len(MODEL_COLORS)], ecolor=INK_MUTED, elinewidth=1, markersize=9,
                        markeredgecolor=SURFACE, markeredgewidth=2, zorder=3)  # fmt: skip
            ax.annotate(model, (p50, 100 * point), xytext=(8, 4), textcoords="offset points", color=INK, fontsize=10)
        ax.set_xscale("log")
        ticks = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20]
        ax.xaxis.set_major_locator(matplotlib.ticker.FixedLocator(ticks))
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g} s"))
        ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
        ax.set_xlim(np.median(res.latency[0, c]) / 1.6, np.median(res.latency[-1, c]) * 2.2)
        ax.set_xlabel("Typical (p50) time to transcribe one clip (log scale)", color=INK)
        ax.set_title(CONDITION_LABELS.get(cond, cond), loc="left", color=INK, fontsize=11)
    axes[0].set_ylabel("Word error rate (%)", color=INK)
    axes[0].set_ylim(bottom=0)
    fig.suptitle(f"Accuracy vs speed: what you give up for a faster model (n = {len(all_s)} sentences per point; "
                 "whiskers: 95% interval)", x=0.06, ha="left", fontsize=12, color=INK)  # fmt: skip
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def chart_wer_by_language(res: Results, path: Path, n_boot: int) -> None:
    languages = [lang for lang in ("en", "es", "de") if len(sentences_where(res, language=lang, fleurs_only=True))]
    panels = [c for c in ("clean", WORST_CONDITION) if c in res.conditions]
    fig, axes = plt.subplots(1, len(panels), figsize=(11, 4.8), sharey=True, facecolor=SURFACE)
    axes = np.atleast_1d(axes)
    n_per = len(sentences_where(res, language=languages[0], fleurs_only=True))
    for ax, cond in zip(axes, panels):
        style_axes(ax)
        c = res.conditions.index(cond)
        groups = [(LANGUAGE_LABELS.get(lang, lang), sentences_where(res, language=lang, fleurs_only=True), c)
                  for lang in languages]  # fmt: skip
        grouped_bars(ax, res, groups, n_boot)
        ax.set_title(CONDITION_LABELS.get(cond, cond), loc="left", color=INK, fontsize=11)
    axes[0].set_ylabel("Word error rate (%)", color=INK)
    axes[0].legend(title="Model", frameon=False, loc="upper left", alignment="left")
    fig.suptitle(f"Word error rate by language (FLEURS, same sentences translated; n = {n_per} sentences per bar; "
                 "whiskers: 95% interval)", x=0.06, ha="left", fontsize=12, color=INK)  # fmt: skip
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


# ---------- Putting it together ----------


def build_report(results_csv: Path, config: dict, out_dir: Path, n_boot: int = N_BOOT) -> Path:
    """Write report.md and charts/*.png into out_dir. Returns the report path."""
    res = load_results(results_csv, config)
    charts = out_dir / "charts"
    charts.mkdir(parents=True, exist_ok=True)
    chart_wer_by_condition(res, charts / "wer_by_model_condition.png", n_boot)
    chart_accuracy_vs_latency(res, charts / "accuracy_vs_latency.png", n_boot)
    chart_wer_by_language(res, charts / "wer_by_language.png", n_boot)

    parts = [
        section_overview(res, config),
        section_accuracy(res, n_boot),
        section_speed_cost(res, config),
        section_separability(res, n_boot),
        "## Hypotheses\n\n_Verdicts follow the stated rules. They report what this sample shows, not what we expected._\n",
        hypothesis_1(res, n_boot),
        hypothesis_2(res, n_boot),
        hypothesis_3(res, n_boot),
        hypothesis_4(res),
        section_limitations(res),
    ]
    report = out_dir / "report.md"
    report.write_text("\n".join(parts), encoding="utf-8")
    return report
