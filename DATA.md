# DATA.md — datasets, sources and licences

Public data only. Audio is downloaded by script into `data/` (git-ignored) and never committed.
Licence and availability are checked live at build step 2 and recorded below with the date checked.

| Dataset | Used for | Source | Licence | Checked on |
|---|---|---|---|---|
| LibriSpeech test-clean | English read speech, clean | OpenSLR SLR12 | _to verify (step 2)_ | — |
| LibriSpeech test-other | English read speech, harder speakers | OpenSLR SLR12 | _to verify (step 2)_ | — |
| FLEURS en / es / de | Multilingual read speech | Hugging Face `google/fleurs` | _to verify (step 2)_ | — |
| Whisper models (faster-whisper / CTranslate2 conversions) | Models under test | Hugging Face | _to verify (step 4)_ | — |
