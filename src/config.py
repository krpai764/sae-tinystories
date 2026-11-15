"""Load config.yaml and provide small helpers (seeding, device choice)."""
from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_config(path: str | Path | None = None) -> dict:
    path = Path(path) if path else ROOT / "config.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def set_seed(seed: int) -> None:
    """Seed python, numpy and torch so runs are repeatable."""
    import torch

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def get_device(cfg: dict | None = None) -> str:
    """Return 'cpu' or 'mps' according to config (auto = mps if available)."""
    import torch

    cfg = cfg or load_config()
    pref = cfg["device"]["preferred"]
    if pref == "auto":
        return "mps" if torch.backends.mps.is_available() else "cpu"
    if pref == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("config asks for mps but it is not available")
    return pref
