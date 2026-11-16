# DATA.md — datasets, sources and licences

Public data only. `uv run asr-bench download` (or `make data`) fetches audio into `data/`, which git ignores. Audio is never committed.

| Dataset | Used for | Source | Licence | Download size | Checked on |
|---|---|---|---|---|---|
| LibriSpeech test-clean | English read speech, clean speakers | [OpenSLR 12](https://www.openslr.org/12) | CC BY 4.0 | 347 MB | 2026-11-16 |
| LibriSpeech test-other | English read speech, harder speakers | [OpenSLR 12](https://www.openslr.org/12) | CC BY 4.0 | 329 MB | 2026-11-16 |
| FLEURS `en_us` test | English read speech | [Hugging Face `google/fleurs`](https://huggingface.co/datasets/google/fleurs) | CC BY 4.0 (dataset card: `cc-by-4.0`) | 290 MB | 2026-11-16 |
| FLEURS `es_419` test | Spanish (Latin American) read speech | same | CC BY 4.0 | 582 MB | 2026-11-16 |
| FLEURS `de_de` test | German read speech | same | CC BY 4.0 | 569 MB | 2026-11-16 |
| Whisper `tiny` (faster-whisper / CTranslate2 conversion) | Model under test | [Hugging Face `Systran/faster-whisper-tiny`](https://huggingface.co/Systran/faster-whisper-tiny) | MIT | 75 MB | 2026-11-16 |
| Other Whisper sizes (base … large-v3-turbo) | Models under test | Hugging Face `Systran/…` | _to verify (step 5)_ | — | — |

Dataset download is about 2.1 GB, or roughly 4–5 GB on disk after unpacking. Model files are cached in `data/models/` (git-ignored).

Software used for scoring: `jiwer` (Apache-2.0) and `whisper-normalizer` (MIT, a copy of OpenAI Whisper's normalisation rules).

## Attribution (required by CC BY 4.0)
- LibriSpeech: V. Panayotov, G. Chen, D. Povey, S. Khudanpur, "LibriSpeech: an ASR corpus based on public domain audio books", ICASSP 2015.
- FLEURS: A. Conneau et al., "FLEURS: Few-shot Learning Evaluation of Universal Representations of Speech", IEEE SLT 2022.

## How the data is used
- **Reference text:** LibriSpeech transcripts (upper case, no punctuation). For FLEURS, the *raw* transcription (with case and punctuation), so both sides go through the same normaliser at scoring time (see SPEC §6).
- **One recording per sentence (FLEURS):** FLEURS has several speakers read the same sentence. We keep one recording per sentence, choosing the first filename alphabetically, so no sentence counts twice.
- **Sampling:** for each dataset, the utterances are sorted, shuffled with a fixed seed (`seed` in `config.yaml`), and the first N taken. A smaller sample is always the start of a bigger one.

## Known caveats
- Both datasets are *read* speech: clearer and more fluent than real customer calls.
- Whisper may have seen similar public data in training, which could flatter its accuracy on these sets.
