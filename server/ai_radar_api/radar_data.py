from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import httpx

from .config import AppConfig


TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
}


def normalize_public_url(url: str) -> str:
    parsed = urlsplit(str(url or "").strip())
    if not parsed.scheme or not parsed.netloc:
        return str(url or "").strip()

    query_parts = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_QUERY_KEYS
    ]
    query = urlencode(query_parts, doseq=True)
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, query, ""))


def item_identity(item: dict) -> str:
    url = normalize_public_url(str(item.get("url") or ""))
    if url:
        return hashlib.sha1(url.encode("utf-8")).hexdigest()
    if item.get("id"):
        return str(item["id"])
    fallback = f"{item.get('site_id', '')}|{item.get('source', '')}|{item.get('title', '')}"
    return hashlib.sha1(fallback.encode("utf-8")).hexdigest()


def fetch_public_json(config: AppConfig, path: str) -> dict:
    url = path if path.startswith(("http://", "https://")) else urljoin(f"{config.public_base_url}/", path)
    response = httpx.get(url, timeout=20)
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def load_latest_items(config: AppConfig, mode: str = "ai") -> list[dict]:
    path = "data/latest-24h-all.json" if mode == "all" else "data/latest-24h.json"
    payload = fetch_public_json(config, path)
    items = payload.get("items_all") if mode == "all" else payload.get("items")
    if items is None:
        items = payload.get("items_ai") or payload.get("items") or []
    return [item for item in items if isinstance(item, dict)]


def _question_keywords(question: str) -> set[str]:
    return {part.lower() for part in re.findall(r"[\w\u4e00-\u9fff]+", question or "") if len(part) > 1}


def _item_text(item: dict) -> str:
    fields = (
        item.get("title"),
        item.get("title_zh"),
        item.get("title_en"),
        item.get("site_name"),
        item.get("source"),
    )
    return " ".join(str(field) for field in fields if field).lower()


def _timestamp(item: dict) -> float:
    value = item.get("published_at") or item.get("first_seen_at") or ""
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _rank_item(item: dict, keywords: set[str]) -> tuple[int, float, float]:
    text = _item_text(item)
    match_count = sum(1 for keyword in keywords if keyword in text)
    return (match_count, float(item.get("ai_score") or item.get("score") or 0), _timestamp(item))


def rank_context_items(items: list[dict], question: str) -> list[dict]:
    keywords = _question_keywords(question)
    return sorted(items, key=lambda item: _rank_item(item, keywords), reverse=True)


def build_context(items: list[dict], question: str, max_items: int = 40) -> str:
    ranked = rank_context_items(items, question)
    lines = []
    for index, item in enumerate(ranked[:max_items], start=1):
        title = item.get("title") or item.get("title_zh") or item.get("title_en") or "Untitled"
        source = item.get("site_name") or item.get("source") or "Unknown source"
        url = normalize_public_url(str(item.get("url") or ""))
        score = item.get("ai_score")
        when = item.get("published_at") or item.get("first_seen_at") or ""
        parts: list[Any] = [f"[{index}] {title}", source, url]
        if score is not None:
            parts.append(f"score={score}")
        if when:
            parts.append(f"time={when}")
        lines.append(" | ".join(str(part) for part in parts if part))
    return "\n".join(lines)


def merge_item_metadata(item: dict, classification: dict | None, verification: dict | None) -> dict:
    merged = dict(item)
    if classification:
        for key in ("top_category", "sub_category", "confidence", "reason", "taxonomy_version", "model"):
            if key in classification:
                merged[key] = classification[key]
    if verification:
        for key in (
            "authority_score",
            "authority_reason",
            "status",
            "evidence_links",
            "deep_verified",
            "verified_at",
        ):
            if key in verification:
                merged[key] = verification[key]
    return merged
