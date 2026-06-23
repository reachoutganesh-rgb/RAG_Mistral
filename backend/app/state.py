import json
from pathlib import Path
from typing import Any

from .config import get_settings


def data_root() -> Path:
    root = Path(get_settings().data_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def state_path() -> Path:
    return data_root() / "rag_state.json"


def read_state() -> dict[str, Any]:
    path = state_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_state(values: dict[str, Any]) -> dict[str, Any]:
    current = read_state()
    current.update(values)
    state_path().write_text(json.dumps(current, indent=2), encoding="utf-8")
    return current
