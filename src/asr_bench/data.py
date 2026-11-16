"""Download public datasets and load a fixed, seeded sample of utterances.

Two sources, both CC BY 4.0 (see DATA.md):
- LibriSpeech (OpenSLR 12): English audiobook speech, .flac files plus one
  transcript file per chapter.
- FLEURS (Google, Hugging Face): read speech in many languages, .wav files plus
  one tab-separated transcript file per language.

Everything is saved under data/, which git ignores.
"""

import random
import tarfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import soundfile as sf

LIBRISPEECH_URL = "https://www.openslr.org/resources/12/{split}.tar.gz"
FLEURS_URL = "https://huggingface.co/datasets/google/fleurs/resolve/main/data/{locale}/{file}"

# FLEURS names folders by locale. These are the variants we use per language.
FLEURS_LOCALES = {"en": "en_us", "es": "es_419", "de": "de_de"}


@dataclass
class Utterance:
    """One spoken sentence and its correct (reference) text."""

    dataset: str  # e.g. "fleurs_es"
    utt_id: str  # unique within the dataset
    language: str  # e.g. "es"; passed to the model
    reference: str  # what was actually said, before normalisation
    audio_path: Path
    duration_s: float = 0.0  # filled in for sampled utterances only


# ---------- Downloading ----------


def download_file(url: str, dest: Path) -> None:
    """Download url to dest, unless dest already exists.

    Writes to a ".part" file first and renames at the end, so an interrupted
    download never looks finished.
    """
    if dest.exists():
        print(f"  already have {dest}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    print(f"  downloading {url}")
    urllib.request.urlretrieve(url, part)
    part.rename(dest)


def extract_tar(archive: Path, dest_dir: Path) -> None:
    """Unpack a .tar.gz into dest_dir once. A marker file records completion.

    filter="data" refuses archive entries that try to write outside dest_dir.
    """
    marker = dest_dir / f".extracted-{archive.name}"
    if marker.exists():
        return
    print(f"  extracting {archive.name}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as tar:
        tar.extractall(dest_dir, filter="data")
    marker.touch()


def dataset_dir(dataset: dict, data_dir: Path) -> Path:
    """Where a dataset's transcripts and audio live once downloaded."""
    if dataset["source"] == "librispeech":
        return data_dir / "librispeech" / "LibriSpeech" / dataset["split"]
    return data_dir / "fleurs" / FLEURS_LOCALES[dataset["language"]]


def download_dataset(dataset: dict, data_dir: Path) -> None:
    """Download and unpack one dataset entry from config.yaml."""
    print(f"{dataset['name']}:")
    if dataset["source"] == "librispeech":
        split = dataset["split"]
        archive = data_dir / "downloads" / f"librispeech-{split}.tar.gz"
        download_file(LIBRISPEECH_URL.format(split=split), archive)
        extract_tar(archive, data_dir / "librispeech")
    elif dataset["source"] == "fleurs":
        locale = FLEURS_LOCALES[dataset["language"]]
        split = dataset["split"]
        lang_dir = data_dir / "fleurs" / locale
        download_file(FLEURS_URL.format(locale=locale, file=f"{split}.tsv"), lang_dir / f"{split}.tsv")
        archive = data_dir / "downloads" / f"fleurs-{locale}-{split}.tar.gz"
        download_file(FLEURS_URL.format(locale=locale, file=f"audio/{split}.tar.gz"), archive)
        extract_tar(archive, lang_dir / "audio")
    else:
        raise ValueError(f"unknown source: {dataset['source']}")


# ---------- Reading transcripts ----------


def read_librispeech(split_dir: Path, dataset: str, language: str) -> list[Utterance]:
    """Read every utterance in a LibriSpeech split.

    Layout: <speaker>/<chapter>/<speaker>-<chapter>.trans.txt, where each line
    is "<utterance-id> <TEXT IN CAPITALS>" and audio is <utterance-id>.flac.
    """
    utts = []
    for trans_file in sorted(split_dir.glob("*/*/*.trans.txt")):
        for line in trans_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            utt_id, text = line.split(" ", 1)
            audio = trans_file.parent / f"{utt_id}.flac"
            utts.append(Utterance(dataset, utt_id, language, text, audio))
    return utts


def read_fleurs(lang_dir: Path, dataset: str, language: str, split: str = "test") -> list[Utterance]:
    """Read a FLEURS language folder.

    test.tsv columns: sentence id, wav filename, raw text, lower-cased text,
    characters, sample count, speaker gender. FLEURS records each sentence
    with several speakers. We keep one recording per sentence (the first by
    filename) so no sentence is counted twice.
    """
    chosen: dict[str, tuple[str, str]] = {}  # sentence id -> (filename, raw text)
    for line in (lang_dir / f"{split}.tsv").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        cols = line.split("\t")
        sentence_id, filename, raw_text = cols[0], cols[1], cols[2]
        if sentence_id not in chosen or filename < chosen[sentence_id][0]:
            chosen[sentence_id] = (filename, raw_text)

    utts = []
    for filename, raw_text in chosen.values():
        audio = lang_dir / "audio" / split / filename
        utts.append(Utterance(dataset, Path(filename).stem, language, raw_text, audio))
    return utts


# ---------- Sampling ----------


def sample_utterances(utts: list[Utterance], n: int, seed: int, dataset: str) -> list[Utterance]:
    """Pick n utterances, the same ones every time for the same seed.

    The list is sorted, shuffled with a seeded random generator, and the
    first n are taken. That means a sample of 5 is always the first 5 of a
    sample of 20, so smoke-run utterances are also in the full run. The
    dataset name is mixed into the seed so each dataset gets its own shuffle.
    """
    ordered = sorted(utts, key=lambda u: u.utt_id)
    random.Random(f"{seed}-{dataset}").shuffle(ordered)
    sample = ordered[:n]
    for u in sample:
        u.duration_s = sf.info(u.audio_path).duration
    return sample


def load_sample(dataset: dict, data_dir: Path, n: int, seed: int) -> list[Utterance]:
    """Read one config.yaml dataset entry and return its seeded sample of n."""
    folder = dataset_dir(dataset, data_dir)
    if dataset["source"] == "librispeech":
        utts = read_librispeech(folder, dataset["name"], dataset["language"])
    else:
        utts = read_fleurs(folder, dataset["name"], dataset["language"], dataset["split"])
    if not utts:
        raise FileNotFoundError(f"no utterances in {folder}; run `asr-bench download` first")
    return sample_utterances(utts, n, seed, dataset["name"])
