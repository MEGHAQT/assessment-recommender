from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from app.config import PROCESSED_CATALOG_PATH


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


@dataclass(frozen=True)
class CatalogItem:
    entity_id: str
    name: str
    url: str
    test_type: str
    keys: tuple[str, ...]
    job_levels: tuple[str, ...]
    languages: tuple[str, ...]
    duration: str | None
    remote: str | None
    adaptive: str | None
    description: str
    search_text: str

    def recommendation(self) -> dict[str, str]:
        return {"name": self.name, "url": self.url, "test_type": self.test_type}


def normalize_text(value: str) -> str:
    value = value.replace("\u2013", "-").replace("\u2014", "-")
    value = re.sub(r"[^a-z0-9+.#/&() -]+", " ", value.lower())
    return re.sub(r"\s+", " ", value).strip()


def normalize_name(value: str) -> str:
    return normalize_text(value).replace(" - ", " ")


def _as_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _load_items(path: Path = PROCESSED_CATALOG_PATH) -> list[CatalogItem]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        CatalogItem(
            entity_id=str(row.get("entity_id") or ""),
            name=str(row["name"]),
            url=str(row["url"]),
            test_type=str(row["test_type"]),
            keys=_as_tuple(row.get("keys")),
            job_levels=_as_tuple(row.get("job_levels")),
            languages=_as_tuple(row.get("languages")),
            duration=row.get("duration") or None,
            remote=row.get("remote") or None,
            adaptive=row.get("adaptive") or None,
            description=str(row.get("description") or ""),
            search_text=str(row.get("search_text") or ""),
        )
        for row in data
    ]


@lru_cache(maxsize=1)
def load_catalog() -> tuple[CatalogItem, ...]:
    return tuple(_load_items())


@lru_cache(maxsize=1)
def catalog_by_normalized_name() -> dict[str, CatalogItem]:
    return {normalize_name(item.name): item for item in load_catalog()}


@lru_cache(maxsize=1)
def catalog_by_url() -> dict[str, CatalogItem]:
    return {item.url: item for item in load_catalog()}


def unique_items(items: Iterable[CatalogItem]) -> list[CatalogItem]:
    seen: set[str] = set()
    result: list[CatalogItem] = []
    for item in items:
        if item.url in seen:
            continue
        seen.add(item.url)
        result.append(item)
    return result


def find_by_name(name: str) -> CatalogItem | None:
    normalized = normalize_name(name)
    direct = catalog_by_normalized_name().get(normalized)
    if direct:
        return direct
    for item in load_catalog():
        item_name = normalize_name(item.name)
        if normalized and (normalized in item_name or item_name in normalized):
            return item
    return None
