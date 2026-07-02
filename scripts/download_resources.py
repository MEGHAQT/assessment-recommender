from __future__ import annotations

import urllib.request
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SAMPLE_DIR = ROOT / "sample_conversations"

CATALOG_URL = "https://tcp-us-prod-rnd.shl.com/voiceRater/shl-ai-hiring/shl_product_catalog.json"
CONVERSATIONS_URL = "https://tcp-us-prod-rnd.shl.com/voiceRater/shl-ai-hiring/sample_conversations.zip"


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=30) as response:
        destination.write_bytes(response.read())


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    download(CATALOG_URL, DATA_DIR / "catalog_raw.json")
    download(CONVERSATIONS_URL, DATA_DIR / "sample_conversations.zip")
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(DATA_DIR / "sample_conversations.zip") as archive:
        archive.extractall(SAMPLE_DIR)
    print("Downloaded official SHL catalog and public sample conversations.")


if __name__ == "__main__":
    main()

