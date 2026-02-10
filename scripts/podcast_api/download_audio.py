from __future__ import annotations

import argparse
import os
from pathlib import Path

from .episodes_requests import (
    EpisodesRequestsTable,
    find_next_for_download,
    mark_downloaded,
    mark_failed_download,
)
from .podcasts_table import load_podcasts_table
from .podcast_api_client import PodcastApiClient
from .github_release import get_or_create_release, upload_asset


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Download Podcast API audio for REQUESTED tasks")
    ap.add_argument("--table", default=os.environ.get("EPISODES_REQUESTS", "data/video-data/episodes_requests.csv"))
    ap.add_argument("--podcasts", default=os.environ.get("PODCASTS_TABLE", "data/video-data/podcasts.csv"))
    ap.add_argument("--out_dir", default=os.environ.get("AUDIO_OUT_DIR", "work/podcast-api-audio"))
    ap.add_argument("--release_tag", default=os.environ.get("AUDIO_RELEASE_TAG", "audio-archive"))
    ap.add_argument("--max", type=int, default=int(os.environ.get("MAX_TASKS", "10")))
    args = ap.parse_args()

    podcasts = load_podcasts_table(args.podcasts)
    gcp_project = os.environ.get("GCP_PROJECT_ID", "").strip()
    token = os.environ.get("GOOGLE_ACCESS_TOKEN", "").strip()
    if not gcp_project:
        # optional: can be specified in podcasts.csv per podcast
        # if any row has it.
        for p in podcasts.values():
            if p.gcp_project_id:
                gcp_project = p.gcp_project_id
                break
    if not gcp_project:
        raise SystemExit("GCP_PROJECT_ID is required (env or podcasts.csv gcp_project_id)")
    if not token:
        raise SystemExit("GOOGLE_ACCESS_TOKEN is required (workflow should provide it)")

    client = PodcastApiClient(project_id=gcp_project, access_token=token)
    table = EpisodesRequestsTable(args.table)
    reqs = table.load()

    out_dir = Path(args.out_dir)
    _ensure_dir(out_dir)

    processed = 0
    while processed < args.max:
        r = find_next_for_download(reqs)
        if not r:
            break
        if not r.operation_name:
            mark_failed_download(r, "missing operation_name")
            processed += 1
            continue

        try:
            dest = out_dir / f"{r.task_id}.mp3"
            client.download_operation_audio(operation_name=r.operation_name, out_path=str(dest))

            # Upload to a GitHub release tag for durable storage.
            release = get_or_create_release(tag=args.release_tag)
            asset_name = f"{r.task_id}.mp3"
            download_url = upload_asset(release=release, file_path=str(dest), asset_name=asset_name)
            mark_downloaded(r, tag=args.release_tag, asset_name=asset_name, audio_url=download_url)
        except Exception as e:
            mark_failed_download(r, str(e))
        processed += 1

    table.save(reqs)
    print(f"[download_audio] processed={processed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
