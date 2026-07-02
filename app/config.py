from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_CATALOG_PATH = DATA_DIR / "catalog_raw.json"
PROCESSED_CATALOG_PATH = DATA_DIR / "catalog_processed.json"

MAX_RECOMMENDATIONS = 10
