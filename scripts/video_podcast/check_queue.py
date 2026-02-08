# ASCII-only. No ellipses. Keep <= 500 lines.

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .tables import (
    ensure_podcasts_csv,
    ensure_queue_mode,
    ensure_videos_csv,
    load_podcasts,
    load_queue_mode,
    load_videos,
    pick_default_podcast_id,
)


@dataclass(frozen=True)
class QueueDecision:
    action: str  # render | upload | none
    podcast_id: str
    guid: Optional[str]
    title: Optional[str]
    reason: str


def _active_podcasts(repo_root: Path) -> List[str]:
    ensure_podcasts_csv(repo_root)
    ensure_queue_mode(repo_root)
    podcasts = load_podcasts(repo_root)
    mode = load_queue_mode(repo_root)
    if mode.run_all_podcasts:
        return sorted(podcasts.keys())
    pid = mode.podcast_id.strip()
    if pid and pid in podcasts:
        return [pid]
    return [pick_default_podcast_id(podcasts)]


def decide_next(repo_root: Path) -> QueueDecision:
    """Return what to do next.

    Deterministic rule:
      1) Determine active podcasts from queue_mode.json and podcasts.csv
      2) For active podcasts, sort videos by published_at then guid
      3) Render first: pick first row missing rendered_asset_name
      4) Only when all rendered: upload first row with empty youtube_id
    """
    ensure_videos_csv(repo_root)
    podcasts = load_podcasts(repo_root)
    active = _active_podcasts(repo_root)
    rows = load_videos(repo_root)

    active_set: Set[str] = set(active)
    rows = [r for r in rows if (r.get("podcast_id") or "").strip() in active_set]

    if not rows:
        return QueueDecision(action="none", podcast_id="", guid=None, title=None, reason="no_rows=1")

    # Render backlog first.
    for r in rows:
        if (r.get("rendered_asset_name") or "").strip() == "":
            pid = (r.get("podcast_id") or "").strip()
            guid = (r.get("episode_guid") or "").strip() or None
            title = (r.get("episode_title") or "").strip() or None
            return QueueDecision(
                action="render",
                podcast_id=pid,
                guid=guid,
                title=title,
                reason="pending_render=1",
            )

    # All rendered: upload next missing youtube_id.
    for r in rows:
        if (r.get("youtube_id") or "").strip() == "":
            pid = (r.get("podcast_id") or "").strip()
            guid = (r.get("episode_guid") or "").strip() or None
            title = (r.get("episode_title") or "").strip() or None
            return QueueDecision(
                action="upload",
                podcast_id=pid,
                guid=guid,
                title=title,
                reason="all_rendered=1 not_uploaded=1",
            )

    return QueueDecision(action="none", podcast_id="", guid=None, title=None, reason="all_done=1")


def _write_github_outputs(dec: QueueDecision) -> None:
    out_path = os.environ.get("GITHUB_OUTPUT")
    if not out_path:
        return
    p = Path(out_path)
    lines = [
        "action=%s" % dec.action,
        "podcast_id=%s" % (dec.podcast_id or ""),
        "guid=%s" % (dec.guid or ""),
        "title=%s" % (dec.title or ""),
        "reason=%s" % dec.reason,
    ]
    with p.open("a", encoding="utf-8") as f:
        for ln in lines:
            f.write(ln + "\n")


def main(argv: Optional[List[str]] = None) -> int:
    repo_root = Path(os.environ.get("GITHUB_WORKSPACE", ".")).resolve()
    dec = decide_next(repo_root)
    t = (dec.title or "").replace("\n", " ")
    if len(t) > 120:
        t = t[:120]
    print("[queue] action=%s podcast_id=%s guid=%s title=%s reason=%s" % (
        dec.action,
        dec.podcast_id,
        dec.guid or "",
        t,
        dec.reason,
    ))
    _write_github_outputs(dec)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
