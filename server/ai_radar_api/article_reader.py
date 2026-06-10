from __future__ import annotations

import html
import ipaddress
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, unquote, urlencode, urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup, Comment
from readability import Document

from .db import connect_db
from .radar_data import item_identity, load_latest_items, normalize_public_url


BLOCK_TAGS = ("h2", "h3", "p", "blockquote", "pre", "ul", "ol", "figure", "img")
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
    ".article-info",
    ".article_info",
    ".avatar",
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
    r"newsletter|pager|pagination|popup|promo|recommend|related|remark|rss|share|shoutbox|sidebar|signin|"
    r"sponsor|subscribe|widget",
    flags=re.I,
)
POSITIVE_RE = re.compile(r"article|body|content|entry|hentry|main|page|post|story|text", flags=re.I)
READER_AUXILIARY_RE = re.compile(
    r"related|recommend|more[-_\s]*(stories|from|like)|read[-_\s]*next|you[-_\s]*might|popular|latest|"
    r"extension[-_\s]*reading|extended[-_\s]*reading|相关阅读|推荐阅读|延伸阅读|扩展阅读|更多故事|更多文章",
    flags=re.I,
)
YAHOO_STORY_CONTINUES_RE = re.compile(r"\bstory\s+continues\b", flags=re.I)
YAHOO_READ_MORE_SIGNATURE_RE = re.compile(r"\bread[-_\s]*more\b", flags=re.I)
YAHOO_FINANCE_PROMO_HEADING_RE = re.compile(r"^should you (?:buy|invest(?: in)?).*\bright now\??$", flags=re.I)
YAHOO_FINANCE_PROMO_LOOKAHEAD_RE = re.compile(
    r"\b(before you buy stock|motley fool stock advisor|10 best stocks|see the 10 stocks)\b",
    flags=re.I,
)
RECOMMENDATION_HEADING_RE = re.compile(
    r"^(recommended|related|also read|around the web|elsewhere|more from|more stories|read next|you might also like|popular|latest|"
    r"推荐|推荐阅读|相关阅读|延伸阅读|扩展阅读|更多|热门)",
    flags=re.I,
)
HTML_IMAGE_SRC_RE = re.compile(r'<img\b[^>]*\bsrc="([^"]+)"', flags=re.I)
PLACEHOLDER_IMAGE_RE = re.compile(
    r"(^|/)(image|placeholder|blank|spacer|transparent|pixel|loading|lazy|default)([-_.]?\d+)?\.(png|gif|jpe?g|webp|svg)(\?|$)|placehold\.co|1x1",
    flags=re.I,
)
READER_UI_IMAGE_SRC_RE = re.compile(
    r"(^|/)(wechat[-_]?share|share|arrow[-_]?grey|close|emoji|default|qr[-_][^/?#]*|code_production|jingzhun|krspace|kr\.)([-_.][^/?#]+)?\.(png|gif|jpe?g|webp|svg)(\?|$)|"
    r"/(general|common|resource/web|36kr-web/static)/.*(wechat[-_]?share|share|arrow|close|emoji|default|qr[-_])",
    flags=re.I,
)
READER_UI_IMAGE_SIGNATURE_RE = re.compile(r"分享到|分享|二维码|扫码|客户端|wechat|weixin|share|close|arrow|avatar", flags=re.I)
IMAGE_SIZE_QUERY_KEYS = {
    "auto",
    "crop",
    "dpr",
    "fit",
    "format",
    "h",
    "height",
    "name",
    "q",
    "quality",
    "resize",
    "size",
    "w",
    "width",
}
X_ERROR_SHELL_RE = re.compile(
    r"something went wrong,?\s+but don.?t fret.*give it another shot|this browser is no longer supported",
    flags=re.I,
)
LAZY_IMAGE_ATTRS = (
    "data-src",
    "data-original",
    "data-lazy-src",
    "data-hi-res-src",
    "data-url",
    "data-image",
    "data-image-src",
    "data-original-src",
    "data-canonical-src",
)
SRCSET_IMAGE_ATTRS = ("srcset", "data-srcset")
GOOGLE_NEWS_BATCH_URL = "https://news.google.com/_/DotsSplashUi/data/batchexecute"
MAX_FETCH_REDIRECTS = 4
GOOGLE_NEWS_TIMEOUT_SECONDS = 1.0
SHORT_OPEN_CACHE_RETRY_AFTER_SECONDS = 10 * 60
UNAVAILABLE_CACHE_RETRY_AFTER_SECONDS = 10 * 60


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


def _bounded_timeout(
    timeout_seconds: int | float,
    *,
    connect_limit: float = 2.0,
    read_limit: float = 5.0,
) -> httpx.Timeout:
    value = max(1.0, float(timeout_seconds or 6))
    return httpx.Timeout(
        timeout=value,
        connect=min(connect_limit, value),
        read=min(read_limit, value),
        write=min(2.0, value),
        pool=1.0,
    )


def _http_get(
    url: str,
    *,
    timeout_seconds: int | float = 6,
    follow_redirects: bool = True,
    headers: dict | None = None,
    max_redirects: int = MAX_FETCH_REDIRECTS,
    connect_timeout_seconds: float = 2.0,
    read_timeout_seconds: float = 5.0,
) -> httpx.Response:
    with httpx.Client(
        timeout=_bounded_timeout(
            timeout_seconds,
            connect_limit=connect_timeout_seconds,
            read_limit=read_timeout_seconds,
        ),
        max_redirects=max_redirects,
    ) as client:
        return client.get(url, follow_redirects=follow_redirects, headers=headers)


def _http_post(
    url: str,
    *,
    timeout_seconds: int | float = 6,
    params: dict | None = None,
    data: dict | None = None,
    headers: dict | None = None,
) -> httpx.Response:
    with httpx.Client(timeout=_bounded_timeout(timeout_seconds), max_redirects=2) as client:
        return client.post(url, params=params, data=data, headers=headers)


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


def _clean_soup(html_text: str, *, url: str = "") -> BeautifulSoup:
    soup = BeautifulSoup(html_text or "", "html.parser")
    is_yahoo_finance = _is_yahoo_finance_url(url)
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
                str(node.get("aria-label") or ""),
                " ".join(str(value) for key, value in node.attrs.items() if str(key).startswith("data-")),
            ]
        )
        if is_yahoo_finance and signature and YAHOO_READ_MORE_SIGNATURE_RE.search(signature):
            continue
        if signature and READER_AUXILIARY_RE.search(signature):
            node.decompose()
            continue
        if signature and NEGATIVE_RE.search(signature) and not POSITIVE_RE.search(signature):
            node.decompose()
    return soup


def _normalize_lazy_images(html_text: str) -> str:
    soup = BeautifulSoup(html_text or "", "html.parser")
    for img in soup.find_all("img"):
        current_src = str(img.get("src") or "").strip()
        if current_src and not _looks_placeholder_image_src(current_src):
            continue
        for value in _image_source_values(img, include_src=False):
            img["src"] = value
            break
    return str(soup)


def _readability_html(html_text: str) -> str:
    try:
        return str(Document(_normalize_lazy_images(html_text)).summary(html_partial=True) or "")
    except Exception:
        return ""


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


def _pre_text(node) -> str:
    source = node.find("code") or node
    text = str(source.get_text("", strip=False) or "")
    return text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")


def _srcset_url(value: str) -> str:
    candidates = []
    for part in str(value or "").split(","):
        url = part.strip().split(" ", 1)[0].strip()
        if url:
            candidates.append(url)
    return candidates[-1] if candidates else ""


def _looks_placeholder_image_src(value: str) -> bool:
    raw = str(value or "").strip()
    if not raw or raw in {"#", "about:blank"}:
        return True
    if raw.lower().startswith("data:"):
        return True
    return bool(PLACEHOLDER_IMAGE_RE.search(raw))


def _canonical_image_key(value: str) -> str:
    raw = html.unescape(str(value or "").strip())
    if not raw:
        return ""
    parsed = urlsplit(raw)
    path = parsed.path or ""
    if re.search(r"\.(avif|gif|jpe?g|png|svg|webp)$", path, flags=re.I):
        return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))
    query_items = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in IMAGE_SIZE_QUERY_KEYS
    ]
    return urlunsplit((parsed.scheme, parsed.netloc, path, urlencode(query_items), ""))


def _looks_reader_ui_image(node, src: str) -> bool:
    if READER_UI_IMAGE_SRC_RE.search(src):
        return True
    signature = " ".join(
        [
            str(node.get("alt") or ""),
            str(node.get("title") or ""),
            str(node.get("id") or ""),
            " ".join(str(value) for value in node.get("class", []) if value),
        ]
    )
    if not signature or not READER_UI_IMAGE_SIGNATURE_RE.search(signature):
        return False
    parsed = urlsplit(str(src or ""))
    asset_hint = " ".join([parsed.netloc, parsed.path])
    return bool(re.search(r"jrj|36kr|static|resource|common|general|assets?", asset_hint, flags=re.I))


def _append_image_source(values: list[str], value: str) -> None:
    raw = str(value or "").strip()
    if raw and not _looks_placeholder_image_src(raw):
        values.append(raw)


def _image_source_values(node, *, include_src: bool = True) -> list[str]:
    values: list[str] = []
    src = str(node.get("src") or "").strip()
    if include_src:
        _append_image_source(values, src)
    for attr in LAZY_IMAGE_ATTRS:
        _append_image_source(values, str(node.get(attr) or ""))
    for attr in SRCSET_IMAGE_ATTRS:
        value = _srcset_url(str(node.get(attr) or ""))
        _append_image_source(values, value)
    picture = node.find_parent("picture")
    if picture:
        for source in picture.find_all("source"):
            for attr in SRCSET_IMAGE_ATTRS:
                value = _srcset_url(str(source.get(attr) or ""))
                _append_image_source(values, value)
            for attr in LAZY_IMAGE_ATTRS:
                _append_image_source(values, str(source.get(attr) or ""))
    return values


def _image_url(node, base_url: str) -> str:
    for value in _image_source_values(node):
        href = _absolute_link(value, base_url)
        if href:
            return href
    return ""


def _image_figure_html(img, base_url: str, caption: str = "") -> tuple[str, str]:
    src = _image_url(img, base_url)
    if not src or _looks_reader_ui_image(img, src):
        return "", ""
    alt = _compact_text(img.get("alt", ""))
    image_html = f'<img src="{html.escape(src, quote=True)}"'
    if alt:
        image_html += f' alt="{html.escape(alt, quote=True)}"'
    image_html += ">"
    clean_caption = _compact_text(caption)
    caption_html = f"<figcaption>{html.escape(clean_caption)}</figcaption>" if clean_caption else ""
    return f"<figure>{image_html}{caption_html}</figure>", clean_caption or alt


def _image_text_for_article(text: str) -> str:
    clean = _compact_text(text)
    if not clean:
        return ""
    if _looks_placeholder_image_src(clean):
        return ""
    if clean.lower() in {"image", "photo", "picture", "screenshot", "thumbnail"}:
        return ""
    return clean


def _block_html(node, base_url: str) -> tuple[str, str]:
    name = getattr(node, "name", "")
    if name == "img":
        return _image_figure_html(node, base_url)
    if name in {"h2", "h3", "p", "blockquote", "pre"}:
        text = _compact_text(node.get_text(" ", strip=True))
        if name == "p" and not text:
            img = node.find("img")
            if img:
                return _image_figure_html(img, base_url)
        inner = _inline_html(node, base_url) if name != "pre" else html.escape(_pre_text(node))
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
    if name == "figure":
        img = node.find("img")
        if not img:
            return "", ""
        caption_node = node.find("figcaption")
        caption = _compact_text(caption_node.get_text(" ", strip=True) if caption_node else "")
        return _image_figure_html(img, base_url, caption)
    return "", ""


def _paragraph_blocks(text: str) -> tuple[str, str]:
    parts = [part.strip() for part in re.split(r"\n{2,}", str(text or "").strip()) if part.strip()]
    if not parts and str(text or "").strip():
        parts = [str(text).strip()]
    content_html = "\n".join(f"<p>{html.escape(part)}</p>" for part in parts)
    return content_html, "\n\n".join(_compact_text(part) for part in parts)


def _initial_state_json(html_text: str) -> dict:
    match = re.search(r"window\.initialState\s*=\s*(\{.*?\})\s*;?\s*</script>", html_text or "", flags=re.S)
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}


def _extract_36kr_newsflash(html_text: str, *, url: str, fallback_title: str = "") -> dict | None:
    host = (urlsplit(str(url or "")).hostname or "").lower()
    if not (host == "36kr.com" or host.endswith(".36kr.com")) or "/newsflashes/" not in str(url):
        return None

    soup = BeautifulSoup(html_text or "", "html.parser")
    state = _initial_state_json(html_text)
    detail = (
        state.get("newsflashDetail", {})
        .get("detailData", {})
        .get("data", {})
        if isinstance(state, dict)
        else {}
    )
    title = _compact_text(
        str(detail.get("widgetTitle") or "")
        or (soup.select_one(".item-title").get_text(" ", strip=True) if soup.select_one(".item-title") else "")
        or _title(soup, fallback_title)
    )
    content = _compact_text(
        str(detail.get("widgetContent") or "")
        or (soup.select_one(".pre-item-des").get_text(" ", strip=True) if soup.select_one(".pre-item-des") else "")
        or _meta_content(soup, "meta[name='description']", "meta[property='og:description']")
    )
    if not content:
        return None

    content_html, article_text = _paragraph_blocks(content)
    metadata_soup = BeautifulSoup(html_text or "", "html.parser")
    return {
        "title": title or _title(metadata_soup, fallback_title),
        "byline": "",
        "published_at": _meta_content(metadata_soup, "meta[property='article:published_time']", "meta[name='date']"),
        "excerpt": article_text[:260],
        "text": article_text,
        "content_html": content_html,
        **_article_metadata(metadata_soup, content, article_text),
    }


def _article_image_count(article: dict) -> int:
    keys = {
        _canonical_image_key(match.group(1))
        for match in HTML_IMAGE_SRC_RE.finditer(str(article.get("content_html") or ""))
    }
    keys.discard("")
    return len(keys)


def _is_yahoo_finance_url(url: str) -> bool:
    host = (urlsplit(str(url or "")).hostname or "").lower()
    return host == "finance.yahoo.com" or host.endswith(".finance.yahoo.com")


def _following_block_text(node, *, limit: int = 4) -> str:
    texts = []
    for sibling in node.find_next_siblings():
        candidates = [sibling] if getattr(sibling, "name", None) in BLOCK_TAGS else sibling.find_all(BLOCK_TAGS)
        for candidate in candidates:
            text = _compact_text(candidate.get_text(" ", strip=True))
            if not text:
                continue
            texts.append(text)
            if len(texts) >= limit:
                return " ".join(texts)
    return " ".join(texts)


def _looks_yahoo_finance_promo_heading(node, text: str, url: str) -> bool:
    if not _is_yahoo_finance_url(url) or getattr(node, "name", None) not in {"h2", "h3"}:
        return False
    if not YAHOO_FINANCE_PROMO_HEADING_RE.search(text):
        return False
    return bool(YAHOO_FINANCE_PROMO_LOOKAHEAD_RE.search(_following_block_text(node)))


def _image_key_from_block(block_html: str) -> str:
    match = HTML_IMAGE_SRC_RE.search(str(block_html or ""))
    return _canonical_image_key(match.group(1)) if match else ""


def _article_from_clean_soup(soup: BeautifulSoup, *, metadata_soup: BeautifulSoup, url: str, title: str) -> dict:
    container = _best_container(soup)
    raw_text = _compact_text(container.get_text(" ", strip=True))
    blocks = []
    texts = []
    seen = set()
    for node in container.find_all(BLOCK_TAGS):
        block_html, text = _block_html(node, url)
        is_media = block_html.startswith("<figure>")
        if not block_html or (not text and not is_media):
            continue
        image_key = _image_key_from_block(block_html) if is_media else ""
        seen_key = f"image:{image_key}" if image_key else block_html if is_media else text
        if seen_key in seen:
            continue
        if text and node.name in {"h2", "h3"}:
            if RECOMMENDATION_HEADING_RE.search(text):
                break
            if _looks_yahoo_finance_promo_heading(node, text, url):
                break
        if text and _looks_boilerplate(text):
            continue
        if node.name == "p" and len(text) < 24 and not block_html.startswith("<figure>"):
            continue
        seen.add(seen_key)
        blocks.append(block_html)
        if is_media:
            image_text = _image_text_for_article(text)
            if image_text:
                texts.append(image_text)
        elif text:
            texts.append(text)
        if sum(len(part) for part in texts) >= 15000 or len(blocks) >= 80:
            break
    article_text = "\n\n".join(texts)
    article = {
        "title": title,
        "byline": _meta_content(metadata_soup, "meta[name='author']", "meta[property='article:author']"),
        "published_at": _meta_content(metadata_soup, "meta[property='article:published_time']", "meta[name='date']"),
        "excerpt": article_text[:260],
        "text": article_text,
        "content_html": "\n".join(blocks),
        **_article_metadata(metadata_soup, raw_text, article_text),
    }
    return article


def _should_use_original_candidate(primary: dict, original: dict, *, html_text: str = "", url: str = "") -> bool:
    primary_images = _article_image_count(primary)
    original_images = _article_image_count(original)
    primary_len = len(_compact_text(str(primary.get("text") or "")))
    original_len = len(_compact_text(str(original.get("text") or "")))
    has_story_continues = _is_yahoo_finance_url(url) and bool(YAHOO_STORY_CONTINUES_RE.search(html_text or ""))

    if has_story_continues and original_len >= max(160, primary_len + 80):
        max_expected_len = max(primary_len * 8, primary_len + 5000)
        if not primary_len or original_len <= max_expected_len:
            return True

    if original_images > max(primary_images, 1):
        if original_len < max(160, int(primary_len * 0.65)):
            return False
        if primary_len and original_len > max(int(primary_len * 1.75), primary_len + 1200):
            return False
        return True

    return False


def extract_article_from_html(html_text: str, *, url: str, fallback_title: str = "") -> dict:
    site_specific = _extract_36kr_newsflash(html_text, url=url, fallback_title=fallback_title)
    if site_specific:
        return site_specific

    metadata_soup = BeautifulSoup(html_text or "", "html.parser")
    title = _title(metadata_soup, fallback_title)
    reader_html = _readability_html(html_text)
    article = _article_from_clean_soup(_clean_soup(reader_html or html_text, url=url), metadata_soup=metadata_soup, url=url, title=title)
    if reader_html:
        original_article = _article_from_clean_soup(_clean_soup(html_text, url=url), metadata_soup=metadata_soup, url=url, title=title)
        if _should_use_original_candidate(article, original_article, html_text=html_text, url=url):
            article = original_article
    return article


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


def _cached_article_age_seconds(article: dict) -> float | None:
    fetched_at = str(article.get("fetched_at") or "").strip()
    try:
        parsed = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return (datetime.now(UTC) - parsed.astimezone(UTC)).total_seconds()


def _should_retry_cached_article(article: dict) -> bool:
    status = str(article.get("access_status") or "").strip().lower()
    if status == "unavailable":
        age_seconds = _cached_article_age_seconds(article)
        return age_seconds is None or age_seconds >= UNAVAILABLE_CACHE_RETRY_AFTER_SECONDS
    if _is_x_error_shell(str(article.get("url") or article.get("final_url") or ""), article):
        return True
    if status == "open" and len(_compact_text(str(article.get("text") or ""))) < 50:
        age_seconds = _cached_article_age_seconds(article)
        return age_seconds is None or age_seconds >= SHORT_OPEN_CACHE_RETRY_AFTER_SECONDS
    return False


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


def _is_google_news_url(url: str) -> bool:
    host = (urlsplit(str(url or "")).hostname or "").lower()
    return host == "news.google.com" or host.endswith(".news.google.com")


def _is_x_status_url(url: str) -> bool:
    parsed = urlsplit(str(url or ""))
    host = (parsed.hostname or "").lower()
    return host in {"x.com", "twitter.com"} and "/status/" in parsed.path


def _is_x_error_shell(url: str, article: dict) -> bool:
    if not _is_x_status_url(url):
        return False
    text = _compact_text(str(article.get("text") or ""))
    return bool(text and X_ERROR_SHELL_RE.search(text))


def _google_news_locale(url: str) -> tuple[str, str, str]:
    query = parse_qs(urlsplit(url).query)
    hl = (query.get("hl") or ["en-US"])[0] or "en-US"
    gl = (query.get("gl") or ["US"])[0] or "US"
    ceid = (query.get("ceid") or [f"{gl}:en"])[0] or f"{gl}:en"
    return hl, gl, ceid


def _google_news_decode_request(article_id: str, timestamp: str, signature: str, url: str) -> str:
    hl, gl, ceid = _google_news_locale(url)
    ts_value: int | str = int(timestamp) if str(timestamp).isdigit() else timestamp
    inner = [
        "garturlreq",
        [
            [hl, gl, ["FINANCE_TOP_INDICES", "WEB_TEST_1_0_0"], None, None, 1, 1, ceid, None, 180, None, None, None, None, None, 0, None, None, [1608992183, 723341000]],
            hl,
            gl,
            1,
            [2, 3, 4, 8],
            1,
            0,
            "655000234",
            0,
            0,
            None,
            0,
        ],
        article_id,
        ts_value,
        signature,
    ]
    return json.dumps([[["Fbv4je", json.dumps(inner, separators=(",", ":")), None, "generic"]]], separators=(",", ":"))


def _walk_first_public_url(value) -> str:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("http://", "https://")) and _is_safe_public_url(stripped) and not _is_google_news_url(stripped):
            return unquote(stripped)
        if stripped.startswith(("[", "{")):
            try:
                nested = json.loads(stripped)
            except json.JSONDecodeError:
                nested = None
            if nested is not None:
                found = _walk_first_public_url(nested)
                if found:
                    return found
        for candidate in re.findall(r"https?://[^\"\\\s<>]+", stripped):
            candidate = unquote(candidate)
            if _is_safe_public_url(candidate) and not _is_google_news_url(candidate):
                return candidate
        return ""
    if isinstance(value, dict):
        values = value.values()
    elif isinstance(value, list):
        values = value
    else:
        return ""
    for item in values:
        found = _walk_first_public_url(item)
        if found:
            return found
    return ""


def _decoded_google_news_url(response_text: str) -> str:
    payload = re.sub(r"^\)\]\}'\s*", "", response_text or "").strip()
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return ""
    return _walk_first_public_url(data)


def resolve_google_news_url(url: str, timeout_seconds: int = 6) -> str:
    if not _is_google_news_url(url):
        return ""
    response = _http_get(
        url,
        timeout_seconds=min(timeout_seconds, GOOGLE_NEWS_TIMEOUT_SECONDS),
        follow_redirects=True,
        max_redirects=1,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html,application/xhtml+xml"},
    )
    response.raise_for_status()
    final_url = normalize_public_url(str(response.url))
    if final_url and not _is_google_news_url(final_url) and _is_safe_public_url(final_url):
        return final_url
    soup = BeautifulSoup(response.text or "", "html.parser")
    node = soup.select_one("[data-n-a-id][data-n-a-ts][data-n-a-sg]")
    if not node:
        return ""
    request_body = _google_news_decode_request(str(node.get("data-n-a-id") or ""), str(node.get("data-n-a-ts") or ""), str(node.get("data-n-a-sg") or ""), url)
    decode_response = _http_post(
        GOOGLE_NEWS_BATCH_URL,
        params={"rpcids": "Fbv4je"},
        data={"f.req": request_body},
        timeout_seconds=min(timeout_seconds, GOOGLE_NEWS_TIMEOUT_SECONDS),
        headers={
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "Referer": "https://news.google.com/",
        },
    )
    decode_response.raise_for_status()
    resolved = normalize_public_url(_decoded_google_news_url(decode_response.text))
    return resolved if resolved and _is_safe_public_url(resolved) else ""


def fetch_clean_article(config, item: dict, timeout_seconds: int = 6) -> dict:
    item_id = item_identity(item)
    cached = cached_article(config.db_path, item_id)
    if cached and not _should_retry_cached_article(cached):
        return {**cached, "item": item}

    url = normalize_public_url(str(item.get("url") or ""))
    if not _is_safe_public_url(url):
        raise ValueError("Unsupported article URL")

    fetch_url = url
    from_google_news = _is_google_news_url(url)
    if from_google_news:
        try:
            fetch_url = resolve_google_news_url(url, timeout_seconds=min(timeout_seconds, GOOGLE_NEWS_TIMEOUT_SECONDS))
        except Exception as exc:
            article = _fallback_article(item, url=url, final_url=url, reason=f"Google News resolution failed: {exc}")
            store_article(config.db_path, article)
            return article
        if not fetch_url or _is_google_news_url(fetch_url):
            article = _fallback_article(item, url=url, final_url=url, reason="Google News did not resolve to a publisher URL")
            store_article(config.db_path, article)
            return article

    fetch_headers = {
        "User-Agent": "AI-News-Radar/1.0 (+https://withyouda.github.io/ai-news-radar-enhance)",
        "Accept": "text/html,application/xhtml+xml",
    }
    try:
        try:
            response = _http_get(
                fetch_url,
                timeout_seconds=min(timeout_seconds, 3) if from_google_news else timeout_seconds,
                follow_redirects=True,
                headers=fetch_headers,
            )
        except httpx.TransportError:
            if from_google_news:
                raise
            response = _http_get(
                fetch_url,
                timeout_seconds=max(float(timeout_seconds or 6), 8.0),
                follow_redirects=True,
                headers={
                    **fetch_headers,
                    "User-Agent": "Mozilla/5.0 (compatible; AI News Radar Reader)",
                },
                connect_timeout_seconds=4.0,
                read_timeout_seconds=6.0,
            )
        response.raise_for_status()
    except Exception as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        final_url = str(getattr(getattr(exc, "response", None), "url", "") or url)
        article = _fallback_article(item, url=url, final_url=final_url, reason=str(exc), status_code=status_code)
        store_article(config.db_path, article)
        return article
    extracted = extract_article_from_html(response.text, url=str(response.url), fallback_title=str(item.get("title") or ""))
    x_error_shell = _is_x_error_shell(str(response.url), extracted)
    if not extracted["text"] or x_error_shell:
        reason = "Publisher returned an X client-side error shell" if x_error_shell else "No readable article body found"
        article = _fallback_article(item, url=url, final_url=str(response.url), reason=reason)
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
