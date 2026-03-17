import json
import re
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent  # scripts/book_pipeline/../../ → scripts/
OUTPUT_DIR = SCRIPTS_DIR / "output"

BOOK_LIST_PATH = OUTPUT_DIR / "book_list.json"
BOOK_LIST_MANUAL_ISBN_PATH = OUTPUT_DIR / "book_list_manual_isbn.json"
BOOK_DETAILS_PATH = OUTPUT_DIR / "book_details.json"
COVERS_DIR = SCRIPTS_DIR.parent / "public" / "covers"


def load_env_local() -> dict[str, str]:
    """Load key=value pairs from .env.local in the project root."""
    env_path = SCRIPTS_DIR.parent / ".env.local"
    result = {}
    if not env_path.exists():
        return result
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r'^([^=]+)=(.*)$', line)
        if match:
            key = match.group(1).strip()
            value = match.group(2).strip().strip('"').strip("'")
            result[key] = value
    return result


def sanitize_title(title: str) -> str:
    """Strip edition suffixes and separators from a title."""
    return re.sub(r'[,\s–_-]+\s*(second|third|fourth|fifth|sixth|\d+(st|nd|rd|th))\s+edition.*', '', title, flags=re.IGNORECASE).strip()


def load_json(path: Path, default):
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
