# ASCII-only. No ellipses. Keep <= 500 lines.

from __future__ import annotations

import time
from typing import Any, Dict, List


def search_assets_page(
    pexels_key: str,
    pixabay_key: str,
    q: str,
    *,
    tier: int = 1,
    page: int = 1,
    pexels_per_page: int = 10,
    pixabay_per_page: int = 15,
) -> List[Dict[str, Any]]:
    """Fetch one page of assets for a query."""
    # Local import to avoid import cycles.
    from . import sources as _sources

    qq = _sources._normalize_spaces(str(q or ""))
    if not qq:
        return []

    assets: List[Dict[str, Any]] = []

    time.sleep(0.2)
    try:
        for a in _sources.pexels_search(pexels_key, qq, per_page=int(pexels_per_page), page=int(page)):
            a["tier"] = int(tier)
            a["query"] = qq
            assets.append(a)
    except Exception:
        pass

    time.sleep(0.2)
    try:
        for a in _sources.pixabay_search(pixabay_key, qq, per_page=int(pixabay_per_page), page=int(page)):
            a["tier"] = int(tier)
            a["query"] = qq
            assets.append(a)
    except Exception:
        pass

    out = _sources.dedupe_assets(assets)
    out.sort(key=lambda a: (str(a.get("source") or ""), str(a.get("asset_id") or "")))
    return out
