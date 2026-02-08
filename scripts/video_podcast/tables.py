# ASCII-only. No ellipses. Keep <= 500 lines.

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .model import Episode, parse_episodes
from .repo_state import load_state
from .util import now_iso


PODCASTS_FIELDS = [
    "podcast_id",
    "video_rss_path",
    "search_prefix",
    "clip_orientation_policy",
    "min_aspect_ratio",
    "thumb_square_path",
    "thumb_bg_color",
    "thumb_title_color",
    "yt_category_id",
    "yt_privacy",
    "yt_playlist_id",
    "yt_credentials_ref",
]

VIDEOS_FIELDS = [
    "podcast_id",
    "episode_guid",
    "episode_title",
    "published_at_rfc822",
    "audio_url",
    "rendered_asset_name",
    "manifest_asset_name",
    "rendered_at",
    "youtube_id",
    "youtube_uploaded_at",
    "youtube_privacy_status",
    "youtube_playlist_id",
    "youtube_playlist_added",
    "youtube_playlist_add_failed",
]

QUEUE_MODE_DEFAULT = {
    "run_all_podcasts": True,
    "podcast_id": "",
    "updated_at": "",
}


@dataclass(frozen=True)
class QueueMode:
    run_all_podcasts: bool
    podcast_id: str
    updated_at: str


def _read_csv(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        fields = list(r.fieldnames or [])
        rows: List[Dict[str, str]] = []
        for row in r:
            rows.append({k: (row.get(k) or "").strip() for k in fields})
    return fields, rows


def _write_csv(path: Path, fields: List[str], rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: (row.get(k) or "") for k in fields})


def podcasts_csv_path(repo_root: Path) -> Path:
    return repo_root / "data" / "video-data" / "podcasts.csv"


def videos_csv_path(repo_root: Path) -> Path:
    return repo_root / "data" / "video-data" / "videos.csv"


def queue_mode_path(repo_root: Path) -> Path:
    return repo_root / "data" / "video-data" / "queue_mode.json"


def _default_podcast_row(podcast_id: str) -> Dict[str, str]:
    return {
        "podcast_id": podcast_id,
        "video_rss_path": "feed/video_podcast.xml",
        "search_prefix": "",
        "clip_orientation_policy": "horizontal",
        "min_aspect_ratio": "1.0",
        "thumb_square_path": "data/thumbnail_left.png",
        "thumb_bg_color": "#000000",
        "thumb_title_color": "#FFFFFF",
        "yt_category_id": "25",
        "yt_privacy": "private",
        "yt_playlist_id": "",
        "yt_credentials_ref": "ENV:%s" % podcast_id,
    }


def ensure_podcasts_csv(repo_root: Path, default_podcast_id: str = "default") -> Path:
    p = podcasts_csv_path(repo_root)
    fields, rows = _read_csv(p)
    if rows and "podcast_id" in fields:
        return p
    row = _default_podcast_row(default_podcast_id)
    _write_csv(p, PODCASTS_FIELDS, [row])
    return p


def load_podcasts(repo_root: Path) -> Dict[str, Dict[str, str]]:
    ensure_podcasts_csv(repo_root)
    _, rows = _read_csv(podcasts_csv_path(repo_root))
    out: Dict[str, Dict[str, str]] = {}
    for r in rows:
        pid = (r.get("podcast_id") or "").strip()
        if not pid:
            continue
        out[pid] = {k: (r.get(k) or "").strip() for k in PODCASTS_FIELDS}
    if not out:
        ensure_podcasts_csv(repo_root)
        _, rows2 = _read_csv(podcasts_csv_path(repo_root))
        for r in rows2:
            pid = (r.get("podcast_id") or "").strip()
            if pid:
                out[pid] = {k: (r.get(k) or "").strip() for k in PODCASTS_FIELDS}
    return out


def pick_default_podcast_id(podcasts: Dict[str, Dict[str, str]]) -> str:
    if podcasts:
        return sorted(podcasts.keys())[0]
    return "default"


def _rfc822_ts(s: str) -> float:
    try:
        return parsedate_to_datetime(s).timestamp()
    except Exception:
        return 0.0


def ensure_queue_mode(repo_root: Path) -> Path:
    p = queue_mode_path(repo_root)
    if p.exists():
        return p
    d = dict(QUEUE_MODE_DEFAULT)
    d["updated_at"] = now_iso()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return p


def load_queue_mode(repo_root: Path) -> QueueMode:
    ensure_queue_mode(repo_root)
    p = queue_mode_path(repo_root)
    j = json.loads(p.read_text(encoding="utf-8"))
    run_all = bool(j.get("run_all_podcasts", True))
    pid = str(j.get("podcast_id") or "").strip()
    updated = str(j.get("updated_at") or "").strip()
    return QueueMode(run_all_podcasts=run_all, podcast_id=pid, updated_at=updated)


def save_queue_mode(repo_root: Path, mode: QueueMode) -> None:
    p = queue_mode_path(repo_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    from .util import now_iso

    j = {
        "run_all_podcasts": bool(mode.run_all_podcasts),
        "podcast_id": str(mode.podcast_id or "").strip(),
        "updated_at": now_iso(),
    }
    p.write_text(json.dumps(j, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_queue_mode(repo_root: Path, *, run_all_podcasts: bool, podcast_id: str) -> None:
    p = queue_mode_path(repo_root)
    d = {
        "run_all_podcasts": bool(run_all_podcasts),
        "podcast_id": str(podcast_id or "").strip(),
        "updated_at": now_iso(),
    }
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _videos_row_for_episode(ep: Episode, default_podcast_id: str) -> Dict[str, str]:
    pid = (getattr(ep, "podcast_id", "") or "").strip()
    if not pid:
        pid = (default_podcast_id or "").strip()
    return {
        "podcast_id": pid,
        "episode_guid": ep.guid,
        "episode_title": ep.title,
        "published_at_rfc822": ep.pub_rfc822,
        "audio_url": ep.audio_url,
        "rendered_asset_name": "",
        "manifest_asset_name": "",
        "rendered_at": "",
        "youtube_id": "",
        "youtube_uploaded_at": "",
        "youtube_privacy_status": "",
        "youtube_playlist_id": "",
        "youtube_playlist_added": "",
        "youtube_playlist_add_failed": "",
    }


def _apply_state_to_videos_rows(rows_by_guid: Dict[str, Dict[str, str]], state: Dict[str, Any]) -> None:
    processed = state.get("processed") or {}
    if not isinstance(processed, dict):
        return
    for guid, rec in processed.items():
        if not isinstance(rec, dict):
            continue
        g = str(guid or "").strip()
        if not g:
            continue
        row = rows_by_guid.get(g)
        if row is None:
            row = {
                "podcast_id": "",
                "episode_guid": g,
                "episode_title": g,
                "published_at_rfc822": "",
                "audio_url": "",
                "rendered_asset_name": "",
                "manifest_asset_name": "",
                "rendered_at": "",
                "youtube_id": "",
                "youtube_uploaded_at": "",
                "youtube_privacy_status": "",
                "youtube_playlist_id": "",
                "youtube_playlist_added": "",
                "youtube_playlist_add_failed": "",
            }
            rows_by_guid[g] = row
        row["rendered_asset_name"] = str(rec.get("video_asset_name") or row.get("rendered_asset_name") or "")
        row["manifest_asset_name"] = str(rec.get("manifest_asset_name") or row.get("manifest_asset_name") or "")
        row["rendered_at"] = str(rec.get("processed_at") or row.get("rendered_at") or "")
        yt = rec.get("youtube")
        if isinstance(yt, dict):
            row["youtube_id"] = str(yt.get("video_id") or row.get("youtube_id") or "")
            row["youtube_uploaded_at"] = str(yt.get("uploaded_at") or row.get("youtube_uploaded_at") or "")
            row["youtube_privacy_status"] = str(yt.get("privacy_status") or row.get("youtube_privacy_status") or "")
            row["youtube_playlist_id"] = str(yt.get("playlist_id") or row.get("youtube_playlist_id") or "")
            row["youtube_playlist_added"] = str(yt.get("playlist_added") or row.get("youtube_playlist_added") or "")
            row["youtube_playlist_add_failed"] = str(yt.get("playlist_add_failed") or row.get("youtube_playlist_add_failed") or "")


def ensure_videos_csv(
    repo_root: Path,
    episodes_json_rel: str = "data/episodes.json",
    state_rel: str = "data/video-data/state.json",
) -> Path:
    ensure_podcasts_csv(repo_root)
    podcasts = load_podcasts(repo_root)
    default_pid = pick_default_podcast_id(podcasts)

    p = videos_csv_path(repo_root)
    if p.exists():
        # Normalize schema and opportunistically backfill podcast_id from episodes.json if available.
        fields, rows = _read_csv(p)

        episodes_path = (repo_root / episodes_json_rel).resolve()
        ep_pid_by_guid: Dict[str, str] = {}
        if episodes_path.exists():
            try:
                eps = parse_episodes(episodes_path)
                for ep in eps:
                    g = (ep.guid or "").strip()
                    pid = (getattr(ep, "podcast_id", "") or "").strip()
                    if g and pid:
                        ep_pid_by_guid[g] = pid
            except Exception:
                # Keep deterministic behavior even if episodes parsing fails.
                ep_pid_by_guid = {}

        def _pick_pid(existing_pid: str, guid: str) -> str:
            cur = (existing_pid or "").strip()
            ep_pid = (ep_pid_by_guid.get((guid or "").strip()) or "").strip()

            # If cur is empty, prefer episodes.json, else default.
            if not cur:
                return ep_pid or default_pid

            # If episodes.json now has a non-empty pid and current is default, upgrade to episode pid.
            if ep_pid and cur == default_pid and ep_pid != cur:
                return ep_pid

            return cur

        changed = False
        rows2: List[Dict[str, str]] = []

        if fields == VIDEOS_FIELDS:
            for r in rows:
                nr = {k: (r.get(k) or "").strip() for k in VIDEOS_FIELDS}
                guid = (nr.get("episode_guid") or "").strip()
                new_pid = _pick_pid(nr.get("podcast_id") or "", guid)
                if new_pid != (nr.get("podcast_id") or "").strip():
                    nr["podcast_id"] = new_pid
                    changed = True
                rows2.append(nr)

            if changed:
                _write_csv(p, VIDEOS_FIELDS, _sort_videos(rows2))
            return p

        # If schema differs, normalize and also pick podcast ids.
        for r in rows:
            nr = {k: (r.get(k) or "").strip() for k in VIDEOS_FIELDS}
            guid = (nr.get("episode_guid") or "").strip()
            nr["podcast_id"] = _pick_pid(nr.get("podcast_id") or "", guid)
            if not nr["podcast_id"]:
                nr["podcast_id"] = default_pid
            rows2.append(nr)

        _write_csv(p, VIDEOS_FIELDS, _sort_videos(rows2))
        return p

    episodes_path = (repo_root / episodes_json_rel).resolve()
    eps: List[Episode] = []
    if episodes_path.exists():
        eps = parse_episodes(episodes_path)

    rows_by_guid: Dict[str, Dict[str, str]] = {}
    for ep in eps:
        rows_by_guid[ep.guid] = _videos_row_for_episode(ep, default_pid)

    state_path = (repo_root / state_rel).resolve()
    if state_path.exists():
        st = load_state(state_path)
        _apply_state_to_videos_rows(rows_by_guid, st)

    rows = list(rows_by_guid.values())
    for r in rows:
        if not (r.get("podcast_id") or "").strip():
            r["podcast_id"] = default_pid
    _write_csv(p, VIDEOS_FIELDS, _sort_videos(rows))
    return p


def _sort_videos(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    def key(r: Dict[str, str]):
        pid = (r.get("podcast_id") or "").strip()
        ts = _rfc822_ts((r.get("published_at_rfc822") or "").strip())
        guid = (r.get("episode_guid") or "").strip()
        return (pid, ts, guid)
    return sorted(rows, key=key)


def load_videos(repo_root: Path) -> List[Dict[str, str]]:
    ensure_videos_csv(repo_root)
    _, rows = _read_csv(videos_csv_path(repo_root))
    out: List[Dict[str, str]] = []
    for r in rows:
        out.append({k: (r.get(k) or "").strip() for k in VIDEOS_FIELDS})
    return _sort_videos(out)


def write_videos(repo_root: Path, rows: List[Dict[str, str]]) -> None:
    fixed: List[Dict[str, str]] = []
    for r in rows:
        nr = {k: (r.get(k) or "").strip() for k in VIDEOS_FIELDS}
        fixed.append(nr)
    _write_csv(videos_csv_path(repo_root), VIDEOS_FIELDS, _sort_videos(fixed))


def upsert_video_row(repo_root: Path, row: Dict[str, str]) -> None:
    rows = load_videos(repo_root)
    guid = (row.get("episode_guid") or "").strip()
    pid = (row.get("podcast_id") or "").strip()
    if not guid or not pid:
        raise ValueError("upsert requires podcast_id and episode_guid")
    out: List[Dict[str, str]] = []
    replaced = False
    for r in rows:
        if (r.get("podcast_id") or "").strip() == pid and (r.get("episode_guid") or "").strip() == guid:
            out.append({**r, **row})
            replaced = True
        else:
            out.append(r)
    if not replaced:
        out.append(row)
    write_videos(repo_root, out)


def episodes_by_guid(repo_root: Path, episodes_json_rel: str = "data/episodes.json") -> Dict[str, Episode]:
    p = (repo_root / episodes_json_rel).resolve()
    eps = parse_episodes(p) if p.exists() else []
    return {e.guid: e for e in eps}
