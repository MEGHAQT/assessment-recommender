from __future__ import annotations

import math
import re
from functools import lru_cache

from app.catalog import CatalogItem, load_catalog, normalize_name, normalize_text, unique_items
from app.config import MAX_RECOMMENDATIONS

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except Exception:  # pragma: no cover - exercised only when optional deps are absent
    TfidfVectorizer = None
    cosine_similarity = None


ALIASES: dict[str, str] = {
    "opq": "Occupational Personality Questionnaire OPQ32r",
    "opq32r": "Occupational Personality Questionnaire OPQ32r",
    "gsa": "Global Skills Assessment",
    "verify g+": "SHL Verify Interactive G+",
    "g+": "SHL Verify Interactive G+",
    "dsi": "Dependability and Safety Instrument (DSI)",
    "safety and dependability 8.0": "Manufac. & Indust. - Safety & Dependability 8.0",
    "safety & dependability 8.0": "Manufac. & Indust. - Safety & Dependability 8.0",
    "excel simulation": "Microsoft Excel 365 (New)",
    "word simulation": "Microsoft Word 365 (New)",
}


class AssessmentRetriever:
    def __init__(self, catalog: tuple[CatalogItem, ...] | None = None) -> None:
        self.catalog = catalog or load_catalog()
        self._by_name = {normalize_name(item.name): item for item in self.catalog}
        self._alias_lookup = {
            normalize_text(alias): self._by_name[normalize_name(target)]
            for alias, target in ALIASES.items()
            if normalize_name(target) in self._by_name
        }
        self._documents = [item.search_text for item in self.catalog]
        self._vectorizer = None
        self._matrix = None
        if TfidfVectorizer is not None:
            self._vectorizer = TfidfVectorizer(
                ngram_range=(1, 2),
                min_df=1,
                stop_words="english",
                sublinear_tf=True,
            )
            self._matrix = self._vectorizer.fit_transform(self._documents)

    def item_by_name(self, name: str) -> CatalogItem | None:
        normalized = normalize_name(name)
        if normalized in self._by_name:
            return self._by_name[normalized]
        alias = self._alias_lookup.get(normalize_text(name))
        if alias:
            return alias
        for item_name, item in self._by_name.items():
            if normalized and (normalized in item_name or item_name in normalized):
                return item
        return None

    def items_by_names(self, names: list[str]) -> list[CatalogItem]:
        return unique_items(item for name in names if (item := self.item_by_name(name)))

    def mentioned_items(self, text: str) -> list[CatalogItem]:
        normalized = normalize_text(text)
        found: list[tuple[int, CatalogItem]] = []
        for alias, item in self._alias_lookup.items():
            pos = normalized.find(alias)
            if pos >= 0:
                found.append((pos, item))
        for item in self.catalog:
            item_name = normalize_text(item.name)
            if len(item_name) < 4:
                continue
            pos = normalized.find(item_name)
            if pos >= 0:
                found.append((pos, item))
        return unique_items(item for _, item in sorted(found, key=lambda pair: pair[0]))

    def search(
        self,
        query: str,
        *,
        include_names: list[str] | None = None,
        exclude_names: list[str] | None = None,
        limit: int = MAX_RECOMMENDATIONS,
    ) -> list[CatalogItem]:
        include_items = self.items_by_names(include_names or [])
        excluded = {item.url for item in self.items_by_names(exclude_names or [])}
        scored = self._score(query)
        ranked = [self.catalog[index] for index, _score in scored if self.catalog[index].url not in excluded]
        results = unique_items([*include_items, *ranked])
        return [item for item in results if item.url not in excluded][:limit]

    def _score(self, query: str) -> list[tuple[int, float]]:
        if self._vectorizer is not None and self._matrix is not None and cosine_similarity is not None:
            query_vector = self._vectorizer.transform([query])
            sims = cosine_similarity(query_vector, self._matrix).ravel()
            return sorted(
                ((idx, float(score) + self._rule_boost(query, self.catalog[idx])) for idx, score in enumerate(sims)),
                key=lambda pair: pair[1],
                reverse=True,
            )
        return self._fallback_score(query)

    def _fallback_score(self, query: str) -> list[tuple[int, float]]:
        terms = set(normalize_text(query).split())
        scored: list[tuple[int, float]] = []
        for idx, item in enumerate(self.catalog):
            doc_terms = set(normalize_text(item.search_text).split())
            overlap = len(terms & doc_terms) / math.sqrt(max(len(doc_terms), 1))
            scored.append((idx, overlap + self._rule_boost(query, item)))
        return sorted(scored, key=lambda pair: pair[1], reverse=True)

    def _rule_boost(self, query: str, item: CatalogItem) -> float:
        text = normalize_text(query)
        name = normalize_text(item.name)
        boost = 0.0
        if name in text:
            boost += 8.0
        for term in name.split():
            if len(term) > 2 and term in text:
                boost += 0.15
        if "senior" in text and "advanced" in name:
            boost += 1.4
        if "entry" in text and "entry" in name:
            boost += 1.1
        if "graduate" in text and "Graduate" in item.job_levels:
            boost += 0.8
        if "quick" in text or "short" in text:
            minutes = _duration_minutes(item.duration or "")
            if minutes is not None and minutes <= 10:
                boost += 0.7
        if "simulation" in text and "Simulations" in item.keys:
            boost += 0.9
        if ("personality" in text or "behavior" in text or "behaviour" in text) and "Personality & Behavior" in item.keys:
            boost += 0.8
        if ("cognitive" in text or "reasoning" in text or "ability" in text) and "Ability & Aptitude" in item.keys:
            boost += 0.8
        if ("situational" in text or "judgement" in text or "judgment" in text) and "Biodata & Situational Judgment" in item.keys:
            boost += 0.9
        if "adaptive" in text and item.adaptive == "yes":
            boost += 0.6
        return boost


def _duration_minutes(duration: str) -> int | None:
    match = re.search(r"(\d+)", duration)
    return int(match.group(1)) if match else None


@lru_cache(maxsize=1)
def get_retriever() -> AssessmentRetriever:
    return AssessmentRetriever()

