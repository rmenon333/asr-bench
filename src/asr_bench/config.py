"""Read config.yaml into a plain Python dictionary."""

from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path("config.yaml")


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """Load the YAML config file and return it as a dictionary."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)
