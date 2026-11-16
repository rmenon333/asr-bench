"""Transcribe audio with faster-whisper (CPU, int8) and time each call.

Model files are downloaded once from Hugging Face into data/models/
(git-ignored). The models are MIT-licensed (see DATA.md).
"""

import time
from collections.abc import Callable
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

# A transcriber takes (16 kHz audio, language code) and returns (text, seconds taken).
Transcriber = Callable[[np.ndarray, str], tuple[str, float]]


def load_model(model_name: str, runtime: dict, models_dir: Path) -> WhisperModel:
    """Load (and on first use, download) a Whisper model for CPU use."""
    return WhisperModel(
        model_name,
        device=runtime["device"],
        compute_type=runtime["compute_type"],
        cpu_threads=runtime["cpu_threads"],
        download_root=str(models_dir),
    )


def make_whisper_transcriber(model_name: str, runtime: dict, models_dir: Path) -> Transcriber:
    """Load a model and return a function that transcribes one clip and times it."""
    model = load_model(model_name, runtime, models_dir)

    def transcribe(audio: np.ndarray, language: str) -> tuple[str, float]:
        start = time.perf_counter()
        segments, _info = model.transcribe(
            audio,
            language=language,  # given, not detected (SPEC section 12)
            beam_size=runtime["beam_size"],
            condition_on_previous_text=False,  # each clip stands alone
            vad_filter=False,  # no silence trimming: keep audio identical across models
        )
        # faster-whisper does the work lazily, while we read the segments,
        # so joining them must happen INSIDE the timed section.
        text = " ".join(segment.text.strip() for segment in segments)
        return text, time.perf_counter() - start

    return transcribe
