from __future__ import annotations

import argparse
import os
from typing import List

from .episodes_requests import EpisodesRequestsTable, TaskStatus
from .podcasts_table import load_podcasts_table
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
    ap.add_argument("--table", default=None, help="Path to episodes_requests.csv")
    ap.add_argument("--podcasts", default=None, help="Path to podcasts.csv")
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

    requested = 0
    for t in table.iter_pending_requests():
        if requested >= args.max_tasks:
            break

        pc = podcasts.get(t.podcast_id)
        project_id = args.project_id or (pc.gcp_project_id if pc else "")
        if not project_id:
            table.update_task(t.task_id, status=TaskStatus.REQUEST_FAILED, last_error="Missing gcp_project_id")
            continue

        length = (pc.notebooklm_length if pc and pc.notebooklm_length else "STANDARD").strip() or "STANDARD"

        urls = _split_urls(t.source_urls)
        contexts_text = fetch_contexts_from_urls(urls, max_chars_per_url=args.max_chars_per_url)
        if not contexts_text:
            contexts_text = ["No external sources were provided."]

        client = PodcastApiClient(project_id=project_id, access_token=token)
        op = client.create_podcast(
            title=t.title or f"Task {t.task_id}",
            description=t.description or "",
            language_code=(pc.language if pc and pc.language else "en-US"),
            focus=t.custom_prompt,
            length=length,
            contexts=contexts_text,
        )

        table.update_task(
            t.task_id,
            status=TaskStatus.REQUESTED,
            operation_name=op.name,
            requested_at_utc=table.utc_now_iso(),
            last_error="",
        )
        requested += 1
        print(f"[podcast_api] requested task_id={t.task_id} op={op.name}")

    print(f"[podcast_api] requested_count={requested}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
