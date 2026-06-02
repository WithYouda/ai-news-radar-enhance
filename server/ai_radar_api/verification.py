from __future__ import annotations

import html
import re
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx


PRIMARY_DOMAINS = (
    "openai.com",
    "anthropic.com",
    "deepmind.google",
    "ai.googleblog.com",
    "huggingface.co",
    "github.com",
    "arxiv.org",
    "paperswithcode.com",
    "nvidia.com",
    "microsoft.com",
)


def extract_links(html_text: str) -> list[str]:
    seen = set()
    links = []
    for match in re.finditer(r"""href=["']([^"']+)["']""", html_text or "", flags=re.IGNORECASE):
        link = html.unescape(match.group(1)).strip()
        if link.startswith(("http://", "https://")) and link not in seen:
            seen.add(link)
            links.append(link)
    return links


def is_primary_evidence(url: str) -> bool:
    host = urlsplit(url).netloc.lower().split("@")[-1].split(":")[0]
    return any(host == domain or host.endswith(f".{domain}") for domain in PRIMARY_DOMAINS)


def _plain_text(html_text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html_text or "")
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


def _domain(url: str) -> str:
    return urlsplit(url).netloc.lower().split("@")[-1].split(":")[0]


def score_authority(item: dict, page_text: str, evidence_links: list[str], deep: bool) -> dict:
    item_url = str(item.get("url") or "")
    item_domain = _domain(item_url)
    source_text = f"{item.get('site_name', '')} {item.get('source', '')} {item_url}".lower()
    primary_links = [link for link in evidence_links if is_primary_evidence(link)]

    score = 42
    reasons = []
    if any(item_domain == domain or item_domain.endswith(f".{domain}") for domain in PRIMARY_DOMAINS):
        score += 35
        reasons.append("item is from a primary domain")
    if "official" in source_text or any(domain.split(".")[0] in source_text for domain in PRIMARY_DOMAINS):
        score += 10
        reasons.append("source label looks official")
    if primary_links:
        score += min(30, 14 * len(primary_links))
        reasons.append(f"found {len(primary_links)} primary evidence link(s)")
    if deep:
        score += 5
        reasons.append("deep verification requested")
    if not page_text and not primary_links:
        score -= 12
        reasons.append("no page text or primary evidence")

    score = max(0, min(95, score))
    if score >= 85:
        status = "verified"
    elif score >= 70:
        status = "likely_verified"
    elif score >= 50:
        status = "needs_review"
    else:
        status = "low_confidence"

    return {
        "status": status,
        "authority_score": score,
        "authority_reason": "; ".join(reasons) or "no strong primary evidence found",
        "evidence_links": primary_links,
        "deep_verified": bool(deep),
        "model": "rules-v1",
        "verified_at": datetime.now(UTC).isoformat(),
    }


def verify_from_page_text(item: dict, html: str, deep: bool = False) -> dict:
    links = extract_links(html)
    primary_links = [link for link in links if is_primary_evidence(link)]
    return score_authority(item, _plain_text(html), primary_links, deep)


def fetch_and_verify(item: dict, timeout_seconds: int = 12, deep: bool = False) -> dict:
    try:
        response = httpx.get(str(item.get("url") or ""), timeout=timeout_seconds, follow_redirects=True)
        response.raise_for_status()
    except Exception as exc:
        result = score_authority(item, "", [], deep)
        result["authority_reason"] = f"fetch failed: {exc}"
        return result
    return verify_from_page_text(item, response.text, deep=deep)
