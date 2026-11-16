# RECOMMENDATIONS.md: which model for which use case

_Owner-written. The evidence below is copied from [`results/report.md`](results/report.md) (n = 50 sentences per model × condition; Apple M4 CPU; prices from `config.yaml`). Fill in the **blank** lines. Keep each trade-off to one sentence, and cite the numbers you rely on._

## Summary table

| Use case | Recommended model | Trade-off in one sentence |
|---|---|---|
| Live captions | _____ | _____ |
| Post-call transcripts | _____ | _____ |
| Analytics / summaries | _____ | _____ |

---

## Evidence by use case

### 1. Live captions
**What matters most:** keeping up with speech as it happens (RTF well below 1, short slow-case latency) on phone audio, often with background noise.

| Model | RTF | p95 clip time | WER: Phone line | WER: Phone + noise 10 dB |
|---|---|---|---|---|
| tiny | 0.068 | 2.49 s | 23.8 | 59.9 [51.1–69.6] |
| base | 0.106 | 2.28 s | 16.8 | 43.1 [34.6–52.5] |
| small | 0.254 | 3.65 s | 9.0 | 25.4 [18.3–33.7] |
| medium | 0.871 | 13.70 s | 4.6 | 17.3 [12.2–23.4] |

- Hosted alternative: Amazon Transcribe streaming costs $10 per 1,000 minutes. Its accuracy was not measured.
- **Caveat:** we measured whole-clip processing, not streaming delay (see README §5). On this CPU, `medium` is barely real time.
- **Questions to decide:** What caption delay is acceptable? Is a GPU available in production?

**Recommended model:** _____
**Trade-off (one sentence):** _____

### 2. Post-call transcripts
**What matters most:** accuracy on phone audio. Speed only needs to keep up with call volume, and cost per 1,000 minutes matters at scale.

| Model | WER: Phone line | WER: Phone + noise 10 dB | Self-hosted $ / 1,000 min | Batch API $ / 1,000 min |
|---|---|---|---|---|
| tiny | 23.8 | 59.9 | $0.16 | $6 |
| base | 16.8 | 43.1 | $0.26 | $6 |
| small | 9.0 | 25.4 | $0.61 | $6 |
| medium | 4.6 | 17.3 | $2.10 | $6 |

- small → medium is a clear improvement: 4.4 points saved on the phone line [2.2–7.3], 8.1 on phone + noise [4.5–11.9].
- Self-hosted cost is a floor (a fully busy server, no engineering or redundancy).
- **Questions to decide:** How many errors per 100 words can downstream readers or QA tolerate? What is the monthly call volume?

**Recommended model:** _____
**Trade-off (one sentence):** _____

### 3. Analytics / summaries
**What matters most:** getting the gist and key terms right across many calls and languages, at low cost. Some word errors are tolerable if meaning survives.

| Model | WER: Clean | WER: Phone + noise 10 dB | German (FLEURS), all conditions | Spanish (FLEURS), all conditions | RTF |
|---|---|---|---|---|---|
| tiny | 17.7 | 59.9 | 61.6 | 24.7 | 0.068 |
| base | 12.4 | 43.1 | 43.8 | 16.0 | 0.106 |
| small | 7.4 | 25.4 | 26.2 | 6.9 | 0.254 |
| medium | 4.3 | 17.3 | 13.5 | 4.4 | 0.871 |

- H2 is **unclear**: `small` delivers 75–81% of the tiny → medium improvement at 28% of the latency, on the edge of "most".
- German degrades clearly more than English under noise (H3). Spanish does not.
- **Questions to decide:** Which languages matter? Do errors in names and numbers break your summaries?

**Recommended model:** _____
**Trade-off (one sentence):** _____

---

## Caveats to carry into any decision
Read speech, synthetic noise, single speaker, CPU-only timings, and small samples. See README §4. Before production, validate on real (consented) calls.
