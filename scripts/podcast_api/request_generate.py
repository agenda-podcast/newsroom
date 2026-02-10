from __future__ import annotations

import argparse
import os
from typing import List

from .episodes_requests import (
    DEFAULT_TABLE_PATH,
    EpisodesRequestsTable,
    find_next_for_request,
    mark_failed_request,
    mark_requested,
)
from .podcasts_table import DEFAULT_PODCASTS_PATH, load_podcasts_table
from .podcast_api_client import PodcastApiClient
from .url_sources import fetch_contexts_from_urls


def _split_urls(cell: str) -> List[str]:
    cell = (cell or "").strip()
    if not cell:
        return []
    # Use semicolon as the CSV-friendly separator.
    return [u.strip() for u in cell.split(";") if u.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description="Request Google Podcast API audio for all pending tasks")
    ap.add_argument(
        "--table",
        default=os.environ.get("EPISODES_REQUESTS", DEFAULT_TABLE_PATH),
        help="Path to episodes_requests.csv",
    )
    ap.add_argument(
        "--podcasts",
        default=os.environ.get("PODCASTS_TABLE", DEFAULT_PODCASTS_PATH),
        help="Path to podcasts.csv",
    )
    ap.add_argument("--max_tasks", type=int, default=50, help="Max tasks to request in one run")
    ap.add_argument("--max_chars_per_url", type=int, default=20000)
    ap.add_argument("--project_id", default=None, help="Override GCP project id")
    ap.add_argument("--token", default=None, help="Override access token")
    args = ap.parse_args()

    token = args.token or os.getenv("GOOGLE_ACCESS_TOKEN", "").strip()
    if not token:
        raise SystemExit("GOOGLE_ACCESS_TOKEN is required")

    podcasts = load_podcasts_table(args.podcasts)
    table = EpisodesRequestsTable(args.table)
    reqs = table.load()

    processed = 0
    while processed < args.max_tasks:
        r = find_next_for_request(reqs)
        if not r:
            break

        pc = podcasts.get(r.podcast_id)
        project_id = (args.project_id or (pc.gcp_project_id if pc else "")).strip()
        if not project_id:
            mark_failed_request(r, "Missing gcp_project_id")
            processed += 1
            continue

        length = (
            (pc.podcast_api_length if pc and pc.podcast_api_length else "STANDARD").strip() or "STANDARD"
        )

        urls = _split_urls(r.source_urls)
        contexts_text = fetch_contexts_from_urls(urls, max_chars_per_url=args.max_chars_per_url)
        if not contexts_text:
            contexts_text = ["No external sources were provided."]

        try:
            client = PodcastApiClient(project_id=project_id, access_token=token)
            op = client.create_podcast(
                title=r.title or f"Task {r.task_id}",
                description=r.description or "",
                language_code=(pc.language if pc and pc.language else "en-US"),
                focus=r.custom_prompt,
                length=length,
                contexts=contexts_text,
            )
            mark_requested(r, operation_name=op.name)
            print(f"[podcast_api] requested task_id={r.task_id} op={op.name}")
        except Exception as e:
            mark_failed_request(r, str(e))
            print(f"[podcast_api][warn] request failed task_id={r.task_id} err={e}")

        processed += 1

    table.save(reqs)
    print(f"[podcast_api] requested_count={processed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
