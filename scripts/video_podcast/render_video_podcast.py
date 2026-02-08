#!/usr/bin/env python3
# ASCII-only. No ellipses. Keep <= 500 lines.

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .model import Episode, parse_episodes
from .repo_state import load_state, save_state, write_status_csv, write_video_rss
from .tables import (
    ensure_podcasts_csv,
    ensure_videos_csv,
    load_podcasts,
    pick_default_podcast_id,
    upsert_video_row,
)
from .util import now_iso
from .render_video_podcast_impl import render_episode


def _pick_podcast_row(repo_root: Path, podcast_id: str) -> Dict[str, str]:
    ensure_podcasts_csv(repo_root)
    podcasts = load_podcasts(repo_root)
    pid = str(podcast_id or "").strip()
    if pid and pid in podcasts:
        return podcasts[pid]
    return podcasts[pick_default_podcast_id(podcasts)]


def _needs_render(entry: Dict[str, Any]) -> bool:
    asset = str(entry.get("video_asset_name") or "").strip()
    return not bool(asset)


def render_all(
    *,
    repo_root: Path,
    episodes: List[Episode],
    state_path: Path,
    status_csv: Path,
    rss_path: Path,
    out_dir: Path,
    pexels_key: str,
    pixabay_key: str,
    gh_token: str,
    clips_tag: str,
    max_items: int,
    force_guid: str,
    render_one_pass: bool,
    dry_run: bool,
    podcast_id: str,
    search_prefix: str,
    min_aspect_ratio: float,
) -> int:
    ensure_videos_csv(repo_root)

    state = load_state(state_path)
    processed = state.get("processed")
    if not isinstance(processed, dict):
        print("state.processed must be a dict", file=sys.stderr)
        return 2

    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not repo:
        print("GITHUB_REPOSITORY is required", file=sys.stderr)
        return 2

    out_videos_dir = out_dir / "videos"
    out_manifests_dir = out_dir / "manifests"
    out_clips_root = out_dir / "clips"
    out_clips_release_dir = out_dir / "clips_release"
    run_root = out_dir / "run"

    force_guid = str(force_guid or "").strip()
    force_set = set([force_guid]) if force_guid else set()

    to_process: List[Episode] = []
    for ep in episodes:
        if force_set and ep.guid not in force_set:
            continue
        entry = processed.get(ep.guid)
        if not isinstance(entry, dict):
            entry = {}
        if force_set or _needs_render(entry):
            to_process.append(ep)

    if force_set and not to_process:
        print("[render] no episodes match force_guid=%s" % force_guid)
        return 0

    max_n = int(max_items) if int(max_items) >= 0 else 0
    rendered = 0

    for ep in to_process:
        entry = processed.get(ep.guid)
        if not isinstance(entry, dict):
            entry = {}

        # Pass search_prefix and min_aspect_ratio via env for deterministic wiring.
        os.environ["VP_SEARCH_PREFIX"] = str(search_prefix or "").strip()
        os.environ["VP_MIN_ASPECT_RATIO"] = str(min_aspect_ratio)

        v_asset, m_asset = render_episode(
            ep=ep,
            repo_root=repo_root,
            repo=repo,
            out_videos_dir=out_videos_dir,
            out_manifests_dir=out_manifests_dir,
            out_clips_root=out_clips_root,
            out_clips_release_dir=out_clips_release_dir,
            run_root=run_root,
            pexels_key=pexels_key,
            pixabay_key=pixabay_key,
            gh_token=gh_token,
            clips_tag=clips_tag,
            render_one_pass=render_one_pass,
            dry_run=dry_run,
        )

        if dry_run:
            continue

        if not v_asset or not m_asset:
            print("[render] skip guid=%s reason=no_output_assets" % ep.guid, file=sys.stderr)
            return 2

        entry["processed_at"] = now_iso()
        entry["video_asset_name"] = v_asset
        entry["manifest_asset_name"] = m_asset
        entry["video_tag"] = "video-podcast"
        processed[ep.guid] = entry
        save_state(state_path, state)

        upsert_video_row(
            repo_root,
            {
                "podcast_id": podcast_id,
                "episode_guid": ep.guid,
                "episode_title": ep.title,
                "published_at_rfc822": ep.pub_rfc822,
                "audio_url": ep.audio_url,
                "rendered_asset_name": v_asset,
                "manifest_asset_name": m_asset,
                "rendered_at": str(entry.get("processed_at") or ""),
            },
        )

        rendered += 1
        print("[render] ok guid=%s video=%s manifest=%s" % (ep.guid, v_asset, m_asset))

        if max_n and rendered >= max_n:
            print("[render] max-items reached=%d" % max_n)
            break

    # Rewrite derived outputs.
    write_status_csv(status_csv, episodes, state)
    write_video_rss(rss_path, repo, "video-podcast", episodes, state)
    print("[render] rendered_count=%d" % rendered)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--episodes-json", default="data/episodes.json")
    ap.add_argument("--state-path", default="data/video-data/state.json")
    ap.add_argument("--status-csv", default="data/video-data/status.csv")
    ap.add_argument("--out-dir", default="work/video-podcast")
    ap.add_argument("--podcast-id", default="", help="Podcast id (maps to data/video-data/podcasts.csv).")
    ap.add_argument("--max-items", default="0")
    ap.add_argument("--force-guid", default="")
    ap.add_argument("--clips-tag", default=os.environ.get("CLIPS_RELEASE_TAG", "video-podcast-clips"))
    ap.add_argument("--render-one-pass", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    episodes = parse_episodes((repo_root / args.episodes_json).resolve())
    state_path = (repo_root / args.state_path).resolve()
    status_csv = (repo_root / args.status_csv).resolve()
    out_dir = (repo_root / args.out_dir).resolve()

    row = _pick_podcast_row(repo_root, str(args.podcast_id or "").strip())
    pid = str(row.get("podcast_id") or "").strip()
    rss_rel = str(row.get("video_rss_path") or "feed/video_podcast.xml").strip()
    rss_path = (repo_root / rss_rel).resolve()

    search_prefix = str(row.get("search_prefix") or "").strip()
    try:
        min_ar = float(str(row.get("min_aspect_ratio") or "1.0").strip())
    except Exception:
        min_ar = 1.0

    pexels_key = os.environ.get("PEXELS_API_KEY", "").strip()
    pixabay_key = os.environ.get("PIXABAY_API_KEY", "").strip()
    gh_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""

    if not pexels_key and not args.dry_run:
        print("PEXELS_API_KEY is required", file=sys.stderr)
        return 2
    if not pixabay_key and not args.dry_run:
        print("PIXABAY_API_KEY is required", file=sys.stderr)
        return 2
    if not gh_token and not args.dry_run:
        print("GH_TOKEN (or GITHUB_TOKEN) is required", file=sys.stderr)
        return 2

    return render_all(
        repo_root=repo_root,
        episodes=episodes,
        state_path=state_path,
        status_csv=status_csv,
        rss_path=rss_path,
        out_dir=out_dir,
        pexels_key=pexels_key,
        pixabay_key=pixabay_key,
        gh_token=str(gh_token),
        clips_tag=str(args.clips_tag),
        max_items=int(str(args.max_items).strip() or "0"),
        force_guid=str(args.force_guid).strip(),
        render_one_pass=bool(args.render_one_pass),
        dry_run=bool(args.dry_run),
        podcast_id=pid,
        search_prefix=search_prefix,
        min_aspect_ratio=min_ar,
    )


if __name__ == "__main__":
    raise SystemExit(main())
