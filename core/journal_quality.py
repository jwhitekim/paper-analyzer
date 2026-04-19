import csv
import json
import os
from functools import lru_cache
from typing import Optional

ALIAS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "venue_aliases.json")
CSV_PATH   = os.path.join(os.path.dirname(__file__), "..", "data", "scimagojr 2025.csv")

_cache: dict = {}


@lru_cache(maxsize=1)
def _load_aliases() -> dict:
    path = os.path.abspath(ALIAS_PATH)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_csv() -> list[dict]:
    path = os.path.abspath(CSV_PATH)
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        return list(reader)


def _words(s: str) -> set:
    return set(s.lower().split())


def _match(query: str) -> Optional[dict]:
    rows = _load_csv()
    if not rows:
        return None

    q_lower = query.lower()
    q_words = _words(query)
    best_row = None
    best_score = 0.0

    for row in rows:
        title = row.get("Title", "")
        t_lower = title.lower()

        # 정확히 일치하면 즉시 반환
        if q_lower == t_lower:
            best_row = row
            break

        # 단어 단위 Jaccard 유사도
        t_words = _words(title)
        if not t_words:
            continue
        intersection = len(q_words & t_words)
        union = len(q_words | t_words)
        score = intersection / union if union else 0

        # 최소 0.6 이상이고 지금까지 최고점일 때만 후보로
        if score > best_score and score >= 0.6:
            best_score = score
            best_row = row

    if not best_row:
        return None

    return {
        "matched_title": best_row.get("Title"),
        "sjr":           best_row.get("SJR"),
        "quartile":      best_row.get("SJR Best Quartile"),
        "issn":          best_row.get("Issn"),
        "type":          best_row.get("Type"),
        "country":       best_row.get("Country"),
    }


def lookup_venue(venue: str) -> dict:
    if not venue:
        return {}

    aliases = _load_aliases()
    resolved = venue
    for abbr, full in aliases.items():
        if abbr.lower() == venue.lower():
            resolved = full
            break

    cache_key = resolved.lower()
    if cache_key in _cache:
        return _cache[cache_key]

    result = _match(resolved) or {}
    if not result and resolved != venue:
        result = _match(venue) or {}

    _cache[cache_key] = result
    return result


def csv_loaded() -> bool:
    return bool(_load_csv())
