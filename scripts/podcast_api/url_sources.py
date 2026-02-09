from __future__ import annotations

import re
from typing import List

import requests


def _strip_html(html: str) -> str:
    # Very small, deterministic HTML text extraction.
    # This is not a full HTML parser; it is intended to be "good enough" for
    # turning article pages into a plain-text context block.
    html = html or ""
    # Remove scripts/styles.
    html = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?>.*?</style>", " ", html)
    # Remove tags.
    text = re.sub(r"(?is)<[^>]+>", " ", html)
    # Decode common entities (minimal).
    text = text.replace("&nbsp;", " ")
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", "\"")
    text = text.replace("&#39;", "'")
    # Collapse whitespace.
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_contexts_from_urls(urls: List[str], *, max_chars_per_url: int = 20000, timeout_sec: int = 20) -> List[str]:
    contexts: List[str] = []
    for u in urls:
        u = (u or "").strip()
        if not u:
            continue
        try:
            r = requests.get(u, timeout=timeout_sec, headers={"User-Agent": "newsroom-bot/1.0"})
            if r.status_code >= 300:
                contexts.append(f"SOURCE URL: {u}\nHTTP {r.status_code}")
                continue
            ct = (r.headers.get("content-type") or "").lower()
            if "text/html" in ct:
                text = _strip_html(r.text)
            else:
                text = r.text if isinstance(r.text, str) else ""
            if len(text) > max_chars_per_url:
                text = text[:max_chars_per_url]
            contexts.append(f"SOURCE URL: {u}\n{text}")
        except Exception as e:
            contexts.append(f"SOURCE URL: {u}\nERROR: {type(e).__name__}: {e}")
    return contexts
