# ASCII-only. No ellipses. Keep <= 500 lines.

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List


def youtube_err_text(exc: Exception) -> str:
    try:
        content = getattr(exc, "content", None)
        if content:
            if isinstance(content, (bytes, bytearray)):
                return content.decode("utf-8", errors="replace")
            return str(content)
    except Exception:
        pass
    return str(exc)


def best_effort_add_to_playlist(service: Any, video_id: str, playlist_id: str, guid: str) -> bool | None:
    """Best-effort playlist insert.

    Returns:
      - None if playlist_id is empty (skipped)
      - True if added successfully
      - False if attempted but failed (warning already printed)
    """
    pid = str(playlist_id or "").strip()
    if not pid:
        return None
    try:
        service.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": pid,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id},
                }
            },
        ).execute()
        print("[youtube][playlist] added videoId=%s guid=%s playlist=%s" % (video_id, guid, pid))
        return True
    except Exception as e:
        print(
            "[youtube][playlist][warn] failed to add videoId=%s guid=%s playlist=%s err=%s"
            % (video_id, guid, pid, youtube_err_text(e).replace("\n", " "))
        )
        print("[youtube][playlist][warn] continuing_without_playlist videoId=%s guid=%s" % (video_id, guid))
        return False


def gh_delete_release_asset(tag: str, asset_name: str) -> None:
    """Delete an asset from a GitHub release tag using `gh`."""
    gh_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not gh_token:
        raise RuntimeError("GH_TOKEN (or GITHUB_TOKEN) is required to delete release assets")

    env = dict(os.environ)
    env["GH_TOKEN"] = gh_token

    cmd = ["gh", "release", "delete-asset", tag, asset_name, "--yes"]
    print("[cleanup][release] deleting asset tag=%s asset=%s" % (tag, asset_name))
    proc = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        raise RuntimeError("failed to delete release asset: %s" % proc.stdout.strip())


def youtube_url(video_id: str) -> str:
    return "https://www.youtube.com/watch?v=%s" % video_id


def clean_tags(tags: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for t in tags:
        tt = (t or "").strip()
        if not tt:
            continue
        if tt in seen:
            continue
        seen.add(tt)
        out.append(tt)
        if len(out) >= 20:
            break
    return out
