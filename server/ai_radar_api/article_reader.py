from __future__ import annotations

import html
import ipaddress
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup, Comment

from .db import connect_db
from .radar_data import item_identity, load_latest_items, normalize_public_url


BLOCK_TAGS = ("h2", "h3", "p", "blockquote", "pre", "ul", "ol")
DROP_SELECTORS = (
    "script",
    "style",
    "noscript",
    "svg",
    "canvas",
    "iframe",
    "header",
    "footer",
    "nav",
    "aside",
    "form",
    "button",
    "[aria-hidden='true']",
    ".ad",
    ".ads",
    ".advertisement",
    ".social",
    ".share",
    ".comments",
    ".related",
    ".signup",
    ".login",
    ".subscribe",
    ".newsletter",
    ".paywall",
    "[id='signup']",
    "[id='login']",
    "[id='subscribe']",
    "[id='newsletter']",
    "[id='paywall']",
)
ARTICLE_SELECTORS = (
    "article",
    "main",
    "[role='main']",
    ".post-content",
    ".entry-content",
    ".article-content",
    ".article__content",
    ".content",
    "body",
)
CTA_PATTERNS = (
    r"\bsign\s*up\b",
    r"\blog\s*in\b",
    r"\bcreate an account\b",
    r"\bsubscribe\b",
    r"\bnewsletter\b",
    r"\baccept cookies\b",
    r"\bprivacy policy\b",
    r"\balready have an account\b",
    r"注册",
    r"登录",
    r"订阅",
    r"会员",
)
RESTRICTED_PATTERNS = (
    r"\bsubscribe to continue\b",
    r"\bcontinue reading\b",
    r"\bmembers-only\b",
    r"\bpremium\b",
    r"\bpaywall\b",
    r"\bsign in to continue\b",
    r"登录后.*阅读",
    r"订阅.*继续阅读",
    r"会员.*阅读",
)
NEGATIVE_RE = re.compile(
    r"ad-|agegate|banner|combx|comment|community|cookie|disqus|extra|foot|header|login|menu|modal|"
    r"newsletter|pager|pagination|popup|promo|related|remark|rss|share|shoutbox|sidebar|signin|"
    r"sponsor|subscribe|widget",
    flags=re.I,
)
POSITIVE_RE = re.compile(r"article|body|content|entry|hentry|main|page|post|story|text", flags=re.I)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _absolute_link(url: str, base_url: str) -> str:
    href = urljoin(base_url, str(url or "").strip())
    parsed = urlsplit(href)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return href


def _is_safe_public_url(url: str) -> bool:
    parsed = urlsplit(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.strip().lower()
    if host in {"localhost", "0.0.0.0"} or host.endswith(".local"):
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast)


def _meta_content(soup: BeautifulSoup, *selectors: str) -> str:
    for selector in selectors:
        node = soup.select_one(selector)
        value = node.get("content") if node else ""
        if value:
            return _compact_text(value)
    return ""


def _title(soup: BeautifulSoup, fallback_title: str) -> str:
    return (
        _meta_content(soup, "meta[property='og:title']", "meta[name='twitter:title']")
        or _compact_text(soup.h1.get_text(" ", strip=True) if soup.h1 else "")
        or _compact_text(soup.title.get_text(" ", strip=True) if soup.title else "")
        or _compact_text(fallback_title)
        or "未命名文章"
    )


def _clean_soup(html_text: str) -> BeautifulSoup:
    soup = BeautifulSoup(html_text or "", "html.parser")
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    for selector in DROP_SELECTORS:
        for node in soup.select(selector):
            node.decompose()
    for node in list(soup.find_all(True)):
        if getattr(node, "attrs", None) is None:
            continue
        signature = " ".join(
            [
                str(node.get("id") or ""),
                " ".join(str(value) for value in node.get("class", []) if value),
            ]
        )
        if signature and NEGATIVE_RE.search(signature) and not POSITIVE_RE.search(signature):
            node.decompose()
    return soup


def _looks_boilerplate(text: str) -> bool:
    compact = _compact_text(text).lower()
    if not compact:
        return True
    if len(compact) > 420:
        return False
    return any(re.search(pattern, compact, flags=re.I) for pattern in CTA_PATTERNS)


def _access_status(text: str) -> tuple[str, str]:
    compact = _compact_text(text).lower()
    if any(re.search(pattern, compact, flags=re.I) for pattern in RESTRICTED_PATTERNS):
        return "restricted", "可能需要登录/订阅"
    return "open", ""


def _detect_language(soup: BeautifulSoup, text: str) -> str:
    html_lang = _compact_text((soup.html or {}).get("lang", "") if soup.html else "").lower()
    if html_lang:
        return html_lang.split("-")[0]
    compact = _compact_text(text)
    cjk = len(re.findall(r"[\u4e00-\u9fff]", compact))
    latin = len(re.findall(r"[A-Za-z]", compact))
    if cjk >= max(12, latin * 0.18):
        return "zh"
    if latin >= 24:
        return "en"
    return "unknown"


def _article_metadata(soup: BeautifulSoup, raw_text: str, article_text: str) -> dict:
    access_status, access_label = _access_status(raw_text)
    language = _detect_language(soup, article_text or raw_text)
    return {
        "access_status": access_status,
        "access_label": access_label,
        "language": language,
        "translation_available": language not in {"", "unknown", "zh", "zh-cn", "zh-tw"},
    }


def _candidate_score(node) -> float:
    paragraphs = node.find_all("p")
    text_len = len(_compact_text(node.get_text(" ", strip=True)))
    paragraph_len = sum(len(_compact_text(p.get_text(" ", strip=True))) for p in paragraphs)
    link_len = sum(len(_compact_text(a.get_text(" ", strip=True))) for a in node.find_all("a"))
    link_density = link_len / max(text_len, 1)
    signature = " ".join(
        [
            str(node.get("id") or ""),
            " ".join(str(value) for value in node.get("class", []) if value),
        ]
    )
    class_weight = 0
    if POSITIVE_RE.search(signature):
        class_weight += 180
    if NEGATIVE_RE.search(signature):
        class_weight -= 260
    return paragraph_len + min(len(paragraphs), 12) * 80 + class_weight - link_density * 420


def _best_container(soup: BeautifulSoup):
    candidates = []
    for selector in ARTICLE_SELECTORS:
        candidates.extend(soup.select(selector))
    for paragraph in soup.find_all("p"):
        text = _compact_text(paragraph.get_text(" ", strip=True))
        if len(text) < 60:
            continue
        if paragraph.parent:
            candidates.append(paragraph.parent)
        if paragraph.parent and paragraph.parent.parent:
            candidates.append(paragraph.parent.parent)
    if not candidates:
        return soup.body or soup
    return max(candidates, key=_candidate_score)


def _inline_html(node, base_url: str) -> str:
    parts: list[str] = []
    for child in node.children:
        name = getattr(child, "name", None)
        if not name:
            parts.append(html.escape(str(child), quote=False))
            continue
        if name == "br":
            parts.append("<br>")
            continue
        if name == "a":
            text = _compact_text(child.get_text(" ", strip=True))
            href = _absolute_link(child.get("href", ""), base_url)
            if text and href:
                parts.append(f'<a href="{html.escape(href, quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(text)}</a>')
            elif text:
                parts.append(html.escape(text))
            continue
        text = _compact_text(child.get_text(" ", strip=True))
        if text:
            parts.append(html.escape(text))
    return _compact_text("".join(parts))


def _block_html(node, base_url: str) -> tuple[str, str]:
    name = getattr(node, "name", "")
    if name in {"h2", "h3", "p", "blockquote", "pre"}:
        inner = _inline_html(node, base_url) if name != "pre" else html.escape(node.get_text("\n", strip=True))
        text = _compact_text(node.get_text(" ", strip=True))
        if not text:
            return "", ""
        return f"<{name}>{inner}</{name}>", text
    if name in {"ul", "ol"}:
        items = []
        texts = []
        for li in node.find_all("li", recursive=False):
            text = _compact_text(li.get_text(" ", strip=True))
            if not text:
                continue
            items.append(f"<li>{_inline_html(li, base_url)}</li>")
            texts.append(text)
        if not items:
            return "", ""
        return f"<{name}>{''.join(items)}</{name}>", "\n".join(texts)
    return "", ""


def extract_article_from_html(html_text: str, *, url: str, fallback_title: str = "") -> dict:
    soup = _clean_soup(html_text)
    container = _best_container(soup)
    raw_text = _compact_text(container.get_text(" ", strip=True))
    blocks = []
    texts = []
    seen = set()
    for node in container.find_all(BLOCK_TAGS):
        block_html, text = _block_html(node, url)
        if not text or text in seen:
            continue
        if _looks_boilerplate(text):
            continue
        if node.name == "p" and len(text) < 24:
            continue
        seen.add(text)
        blocks.append(block_html)
        texts.append(text)
        if sum(len(part) for part in texts) >= 15000 or len(blocks) >= 80:
            break
    article_text = "\n\n".join(texts)
    return {
        "title": _title(soup, fallback_title),
        "byline": _meta_content(soup, "meta[name='author']", "meta[property='article:author']"),
        "published_at": _meta_content(soup, "meta[property='article:published_time']", "meta[name='date']"),
        "excerpt": article_text[:260],
        "text": article_text,
        "content_html": "\n".join(blocks),
        **_article_metadata(soup, raw_text, article_text),
    }


def cached_article(db_path: str | Path, item_id: str) -> dict | None:
    with connect_db(db_path) as conn:
        row = conn.execute(
            """
            select item_id, url, final_url, title, site_name, byline, published_at, language,
                   access_status, access_label, excerpt, text, content_html, fetched_at
            from article_cache
            where item_id = ?
            """,
            (item_id,),
        ).fetchone()
    if not row:
        return None
    article = {
        "item_id": row["item_id"],
        "url": row["url"],
        "final_url": row["final_url"],
        "title": row["title"],
        "site_name": row["site_name"],
        "byline": row["byline"],
        "published_at": row["published_at"],
        "language": row["language"],
        "access_status": row["access_status"],
        "access_label": row["access_label"],
        "excerpt": row["excerpt"],
        "text": row["text"],
        "content_html": row["content_html"],
        "fetched_at": row["fetched_at"],
        "cache_status": "hit",
    }
    article["translation_available"] = article["language"] not in {"", "unknown", "zh", "zh-cn", "zh-tw"}
    return article


def store_article(db_path: str | Path, article: dict) -> None:
    with connect_db(db_path) as conn:
        conn.execute(
            """
            insert into article_cache(
              item_id, url, final_url, title, site_name, byline, published_at, language,
              access_status, access_label,
              excerpt, text, content_html, fetched_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(item_id) do update set
              url = excluded.url,
              final_url = excluded.final_url,
              title = excluded.title,
              site_name = excluded.site_name,
              byline = excluded.byline,
              published_at = excluded.published_at,
              language = excluded.language,
              access_status = excluded.access_status,
              access_label = excluded.access_label,
              excerpt = excluded.excerpt,
              text = excluded.text,
              content_html = excluded.content_html,
              fetched_at = excluded.fetched_at
            """,
            (
                article["item_id"],
                article["url"],
                article["final_url"],
                article["title"],
                article["site_name"],
                article.get("byline", ""),
                article.get("published_at", ""),
                article.get("language", "unknown"),
                article.get("access_status", "open"),
                article.get("access_label", ""),
                article.get("excerpt", ""),
                article.get("text", ""),
                article.get("content_html", ""),
                article["fetched_at"],
            ),
        )


def _fallback_article(item: dict, *, url: str, final_url: str, reason: str, status_code: int | None = None) -> dict:
    item_id = item_identity(item)
    restricted = status_code in {401, 402, 403}
    access_label = "原站限制抓取，可能需要登录/订阅" if restricted else "暂时无法清洗原文"
    title = str(item.get("title") or item.get("title_zh") or item.get("title_en") or "未命名文章")
    text = f"{title}\n\n{access_label}。可打开原文查看。"
    return {
        "item_id": item_id,
        "url": url,
        "final_url": final_url or url,
        "title": title,
        "site_name": str(item.get("site_name") or item.get("source") or ""),
        "byline": "",
        "published_at": str(item.get("published_at") or item.get("first_seen_at") or ""),
        "language": "zh",
        "access_status": "restricted" if restricted else "unavailable",
        "access_label": access_label,
        "translation_available": False,
        "excerpt": text[:260],
        "text": text,
        "content_html": (
            f"<p>{html.escape(access_label)}。</p>"
            f"<p>这类页面通常由原站反爬、登录墙、会员墙或网络限制导致。请使用上方原文入口查看。</p>"
        ),
        "fetched_at": _now(),
        "cache_status": "miss",
        "item": item,
        "fetch_error": reason[:320],
    }


def find_news_item(config, requested_id: str) -> dict | None:
    for mode in ("ai", "all"):
        try:
            items = load_latest_items(config, mode=mode)
        except Exception:
            items = []
        for item in items:
            identity = item_identity(item)
            candidates = {identity, str(item.get("id") or ""), normalize_public_url(str(item.get("url") or ""))}
            if requested_id in candidates:
                return item
    return None


def fetch_clean_article(config, item: dict, timeout_seconds: int = 6) -> dict:
    item_id = item_identity(item)
    cached = cached_article(config.db_path, item_id)
    if cached:
        return {**cached, "item": item}

    url = normalize_public_url(str(item.get("url") or ""))
    if not _is_safe_public_url(url):
        raise ValueError("Unsupported article URL")

    try:
        response = httpx.get(
            url,
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": "AI-News-Radar/1.0 (+https://withyouda.github.io/ai-news-radar-enhance)",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        response.raise_for_status()
    except Exception as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        final_url = str(getattr(getattr(exc, "response", None), "url", "") or url)
        article = _fallback_article(item, url=url, final_url=final_url, reason=str(exc), status_code=status_code)
        store_article(config.db_path, article)
        return article
    extracted = extract_article_from_html(response.text, url=str(response.url), fallback_title=str(item.get("title") or ""))
    if not extracted["text"]:
        article = _fallback_article(item, url=url, final_url=str(response.url), reason="No readable article body found")
        store_article(config.db_path, article)
        return article

    article = {
        **extracted,
        "item_id": item_id,
        "url": url,
        "final_url": normalize_public_url(str(response.url)),
        "site_name": str(item.get("site_name") or item.get("source") or ""),
        "fetched_at": _now(),
        "cache_status": "miss",
        "item": item,
    }
    store_article(config.db_path, article)
    return article
