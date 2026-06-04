"""Tiny JSON file store for weekly picks and the paper-trading portfolio.

State lives under <repo>/data/ and persists across restarts *within* a host.
In an ephemeral container it resets when the container is reclaimed, which is
fine for a demo; deploy to a persistent host to keep history.
"""
import json
import threading
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

_lock = threading.Lock()


def _path(name: str) -> Path:
    return DATA_DIR / f"{name}.json"


def load(name: str, default=None):
    p = _path(name)
    if not p.exists():
        return default
    try:
        with open(p) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def save(name: str, data) -> None:
    with _lock:
        p = _path(name)
        tmp = p.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2, default=str)
        tmp.replace(p)
