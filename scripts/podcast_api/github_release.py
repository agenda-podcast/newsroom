from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

import requests


GITHUB_API = "https://api.github.com"


@dataclass
class ReleaseInfo:
    tag_name: str
    upload_url: str


def _repo() -> str:
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not repo:
        raise RuntimeError("GITHUB_REPOSITORY is not set")
    return repo


def _token() -> str:
    tok = os.environ.get("GITHUB_TOKEN", "").strip()
    if not tok:
        raise RuntimeError("GITHUB_TOKEN is not set")
    return tok


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_token()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_or_create_release(tag: str, name: Optional[str] = None) -> ReleaseInfo:
    repo = _repo()
    url = f"{GITHUB_API}/repos/{repo}/releases/tags/{tag}"
    r = requests.get(url, headers=_headers(), timeout=60)
    if r.status_code == 404:
        create_url = f"{GITHUB_API}/repos/{repo}/releases"
        payload = {
            "tag_name": tag,
            "name": name or tag,
            "draft": False,
            "prerelease": False,
        }
        cr = requests.post(create_url, headers=_headers(), json=payload, timeout=60)
        if cr.status_code >= 300:
            raise RuntimeError(f"create release failed: {cr.status_code} {cr.text}")
        data = cr.json()
        return ReleaseInfo(tag_name=tag, upload_url=data["upload_url"])

    if r.status_code >= 300:
        raise RuntimeError(f"get release failed: {r.status_code} {r.text}")
    data = r.json()
    return ReleaseInfo(tag_name=tag, upload_url=data["upload_url"])


def upload_asset(tag: str, file_path: str, asset_name: str, content_type: str = "audio/mpeg") -> str:
    rel = get_or_create_release(tag)
    upload_url = rel.upload_url.split("{")[0]
    url = f"{upload_url}?name={asset_name}"
    with open(file_path, "rb") as f:
        data = f.read()
    headers = _headers()
    headers["Content-Type"] = content_type
    r = requests.post(url, headers=headers, data=data, timeout=600)
    if r.status_code == 422 and "already_exists" in r.text:
        # Asset exists: fetch assets list and return matching browser_download_url.
        assets_url = f"{GITHUB_API}/repos/{_repo()}/releases/tags/{tag}"
        rr = requests.get(assets_url, headers=_headers(), timeout=60)
        if rr.status_code >= 300:
            raise RuntimeError(f"asset exists but release fetch failed: {rr.status_code} {rr.text}")
        assets = rr.json().get("assets", [])
        for a in assets:
            if a.get("name") == asset_name:
                return a.get("browser_download_url", "")
        raise RuntimeError("asset exists but browser_download_url not found")
    if r.status_code >= 300:
        raise RuntimeError(f"upload asset failed: {r.status_code} {r.text}")
    j = r.json()
    return j.get("browser_download_url", "")
