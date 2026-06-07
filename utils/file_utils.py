"""??????"""
import json
from pathlib import Path

def ensure_dir(path: str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p

def load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))

def save_json(data, path: str, indent=2):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=indent), encoding="utf-8")
