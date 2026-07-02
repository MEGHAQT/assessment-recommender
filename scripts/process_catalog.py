from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "catalog_raw.json"
OUT_PATH = ROOT / "data" / "catalog_processed.json"

KEY_TO_CODE = {
    "Ability & Aptitude": "A",
    "Assessment Exercises": "E",
    "Biodata & Situational Judgment": "B",
    "Competencies": "C",
    "Development & 360": "D",
    "Knowledge & Skills": "K",
    "Personality & Behavior": "P",
    "Simulations": "S",
}


def clean_spaces(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_name(name: str, link: str) -> str:
    name = clean_spaces(name)
    if link.endswith("/microsoft-excel-365-new/") and name == "Microsoft 365 (New)":
        return "Microsoft Excel 365 (New)"
    return name


def test_type(keys: list[str]) -> str:
    codes = [KEY_TO_CODE[key] for key in keys if key in KEY_TO_CODE]
    return ",".join(codes)


def process_row(row: dict) -> dict:
    keys = [clean_spaces(key) for key in row.get("keys") or [] if clean_spaces(key)]
    name = normalize_name(row.get("name", ""), row.get("link", ""))
    job_levels = [clean_spaces(level) for level in row.get("job_levels") or [] if clean_spaces(level)]
    languages = [clean_spaces(language) for language in row.get("languages") or [] if clean_spaces(language)]
    duration = clean_spaces(row.get("duration"))
    description = clean_spaces(row.get("description"))
    remote = clean_spaces(row.get("remote")).lower() or None
    adaptive = clean_spaces(row.get("adaptive")).lower() or None
    search_parts = [
        name,
        description,
        " ".join(keys),
        " ".join(job_levels),
        " ".join(languages),
        duration,
        f"remote {remote or ''}",
        f"adaptive {adaptive or ''}",
        row.get("link", ""),
    ]
    return {
        "entity_id": clean_spaces(row.get("entity_id")),
        "name": name,
        "url": clean_spaces(row.get("link")),
        "test_type": test_type(keys),
        "keys": keys,
        "job_levels": job_levels,
        "languages": languages,
        "duration": duration or None,
        "remote": remote,
        "adaptive": adaptive,
        "description": description,
        "search_text": clean_spaces(" ".join(search_parts)),
    }


def main() -> None:
    raw_text = RAW_PATH.read_text(encoding="utf-8")
    raw_rows = json.JSONDecoder(strict=False).decode(raw_text)
    processed = [process_row(row) for row in raw_rows if row.get("status") == "ok"]
    processed = [row for row in processed if row["name"] and row["url"]]
    OUT_PATH.write_text(json.dumps(processed, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(processed)} processed catalog entries to {OUT_PATH}")


if __name__ == "__main__":
    main()
