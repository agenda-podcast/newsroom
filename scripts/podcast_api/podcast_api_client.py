from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence

import requests


DISCOVERYENGINE_BASE = "https://discoveryengine.googleapis.com/v1"


@dataclass
class Operation:
    name: str
    done: bool = False
    error: Optional[Dict[str, Any]] = None


class PodcastApiClient:
    def __init__(self, *, project_id: str, access_token: str, location: str = "global") -> None:
        if not project_id:
            raise ValueError("project_id is required")
        if not access_token:
            raise ValueError("access_token is required")
        self.project_id = project_id
        self.location = location
        self.access_token = access_token

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    def create_podcast(
        self,
        *,
        contexts: Sequence[Any],
        focus: str,
        length: str = "STANDARD",
        language_code: str = "en-us",
        title: str = "",
        description: str = "",
    ) -> Operation:
        # Backward-compatible wrapper:
        # - contexts may be list[str] (already cleaned text) OR list[dict] (contexts objects)
        # - focus maps to the request "text" (custom prompt)
        ctx_objs: list[dict] = []
        for c in contexts:
            if isinstance(c, dict):
                ctx_objs.append(c)
            else:
                s = str(c).strip()
                if not s:
                    continue
                ctx_objs.append({"text": s})

        endpoint = f"{DISCOVERYENGINE_BASE}/projects/{self.project_id}/locations/{self.location}/podcasts"
        # Request schema (Generate podcasts API):
        # https://cloud.google.com/generative-ai-app-builder/docs/reference/rest/v1/projects.locations/podcasts
        payload: Dict[str, Any] = {
            "podcastConfig": {
                "focus": focus,
                "length": length,
                "languageCode": language_code,
            },
            "contexts": ctx_objs,
            "title": title or "",
            "description": description or "",
        }

        r = requests.post(endpoint, headers=self._headers(), data=json.dumps(payload), timeout=120)
        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            # Include response body to make API troubleshooting actionable.
            body = (r.text or "").strip()
            raise RuntimeError(f"podcast create failed: http={r.status_code} body={body}") from e
        data = r.json()
        name = (data.get("name") or "").strip()
        if not name:
            raise RuntimeError(f"podcast create response missing name: {data}")
        return Operation(name=name, done=False)

    def get_operation(self, name: str) -> Operation:
        if name.startswith("projects/"):
            op_url = f"{DISCOVERYENGINE_BASE}/{name}"
        else:
            op_url = f"{DISCOVERYENGINE_BASE}/{name.lstrip('/')}"
        r = requests.get(op_url, headers=self._headers(), timeout=60)
        r.raise_for_status()
        data = r.json()
        return Operation(
            name=data.get("name", name),
            done=bool(data.get("done")),
            error=data.get("error"),
        )

    def wait_operation_done(self, name: str, *, timeout_sec: int = 3600, poll_sec: int = 15) -> Operation:
        start = time.time()
        while True:
            op = self.get_operation(name)
            if op.done:
                return op
            if time.time() - start > timeout_sec:
                raise TimeoutError(f"operation not done after {timeout_sec}s: {name}")
            time.sleep(poll_sec)

    def download_operation_audio(self, operation_name: str, dst_path: str) -> None:
        # GET https://discoveryengine.googleapis.com/v1/OPERATION_NAME:download?alt=media
        if not operation_name.startswith("projects/"):
            operation_name = operation_name.lstrip("/")
        url = f"{DISCOVERYENGINE_BASE}/{operation_name}:download?alt=media"
        with requests.get(
            url,
            headers={"Authorization": f"Bearer {self.access_token}"},
            stream=True,
            timeout=300,
        ) as r:
            r.raise_for_status()
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            with open(dst_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
