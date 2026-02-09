from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

import requests


DISCOVERYENGINE_BASE = "https://discoveryengine.googleapis.com"


@dataclass
class PodcastOperation:
    name: str


class PodcastApiError(RuntimeError):
    pass


def _require_env(name: str) -> str:
    val = (os.environ.get(name) or "").strip()
    if not val:
        raise PodcastApiError(f"Missing required environment variable: {name}")
    return val


def _clean_text(s: str) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s


def _truncate_utf8(s: str, max_chars: int) -> str:
    s = s or ""
    if len(s) <= max_chars:
        return s
    return s[:max_chars]


def create_podcast(
    *,
    project_id: str,
    access_token: str,
    title: str,
    description: str,
    focus: str,
    length: str = "STANDARD",
    language_code: str = "en-us",
    contexts: Optional[List[str]] = None,
    timeout_sec: int = 60,
) -> PodcastOperation:
    url = f"{DISCOVERYENGINE_BASE}/v1/projects/{project_id}/locations/global/podcasts"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    req_contexts = []
    for c in (contexts or []):
        c = _clean_text(c)
        if not c:
            continue
        req_contexts.append({"text": _truncate_utf8(c, 20000)})

    payload = {
        "podcastConfig": {
            "focus": _truncate_utf8(focus, 2000),
            "length": length or "STANDARD",
            "languageCode": language_code or "en-us",
            "contexts": req_contexts,
            "title": _truncate_utf8(title, 200),
            "description": _truncate_utf8(description, 2000),
        }
    }

    r = requests.post(url, headers=headers, json=payload, timeout=timeout_sec)
    if r.status_code >= 300:
        raise PodcastApiError(f"create_podcast failed: http={r.status_code} body={r.text}")

    data = r.json() if r.text else {}
    name = (data.get("name") or "").strip()
    if not name:
        raise PodcastApiError(f"create_podcast returned no operation name: {data}")
    return PodcastOperation(name=name)


def download_podcast_audio(
    *,
    operation_name: str,
    access_token: str,
    timeout_sec: int = 600,
    poll_until_done: bool = True,
    poll_interval_sec: int = 10,
    poll_timeout_sec: int = 3600,
) -> bytes:
    op_name = operation_name.strip()
    if not op_name:
        raise PodcastApiError("operation_name is empty")

    headers = {"Authorization": f"Bearer {access_token}"}

    if poll_until_done:
        op_url = f"{DISCOVERYENGINE_BASE}/v1/{op_name}"
        start = time.time()
        while True:
            r = requests.get(op_url, headers=headers, timeout=60)
            if r.status_code >= 300:
                raise PodcastApiError(f"poll operation failed: http={r.status_code} body={r.text}")
            op = r.json() if r.text else {}
            if op.get("done") is True:
                break
            if time.time() - start > poll_timeout_sec:
                raise PodcastApiError("poll timeout exceeded")
            time.sleep(poll_interval_sec)

        if "error" in op:
            raise PodcastApiError(f"operation error: {op.get('error')}")

    dl_url = f"{DISCOVERYENGINE_BASE}/v1/{op_name}:download?alt=media"
    r = requests.get(dl_url, headers=headers, timeout=timeout_sec)
    if r.status_code >= 300:
        raise PodcastApiError(f"download failed: http={r.status_code} body={r.text}")
    return r.content


def require_access_token() -> str:
    return _require_env("GOOGLE_ACCESS_TOKEN")
