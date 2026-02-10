from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional


DEFAULT_TABLE_PATH = os.path.join("data", "video-data", "episodes_requests.csv")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class TaskStatus:
    PENDING_REQUEST = "PENDING_REQUEST"
    REQUESTED = "REQUESTED"
    REQUEST_FAILED = "REQUEST_FAILED"
    DONE = "DONE"
    DOWNLOAD_FAILED = "DOWNLOAD_FAILED"


@dataclass
class EpisodeRequest:
    task_id: str
    podcast_id: str
    source_urls: str
    custom_prompt: str
    title: str
    description: str
    status: str
    operation_name: str
    requested_at_utc: str
    downloaded_at_utc: str
    audio_release_tag: str
    audio_asset_name: str
    audio_url: str
    last_error: str

    @staticmethod
    def from_row(row: Dict[str, str]) -> "EpisodeRequest":
        def g(k: str) -> str:
            return (row.get(k) or "").strip()

        return EpisodeRequest(
            task_id=g("task_id"),
            podcast_id=g("podcast_id"),
            source_urls=g("source_urls"),
            custom_prompt=g("custom_prompt"),
            title=g("title"),
            description=g("description"),
            status=g("status"),
            operation_name=g("operation_name"),
            requested_at_utc=g("requested_at_utc"),
            downloaded_at_utc=g("downloaded_at_utc"),
            audio_release_tag=g("audio_release_tag"),
            audio_asset_name=g("audio_asset_name"),
            audio_url=g("audio_url"),
            last_error=g("last_error"),
        )

    def to_row(self) -> Dict[str, str]:
        return {
            "task_id": self.task_id,
            "podcast_id": self.podcast_id,
            "source_urls": self.source_urls,
            "custom_prompt": self.custom_prompt,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "operation_name": self.operation_name,
            "requested_at_utc": self.requested_at_utc,
            "downloaded_at_utc": self.downloaded_at_utc,
            "audio_release_tag": self.audio_release_tag,
            "audio_asset_name": self.audio_asset_name,
            "audio_url": self.audio_url,
            "last_error": self.last_error,
        }


def load_requests(path: str = DEFAULT_TABLE_PATH) -> List[EpisodeRequest]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"episodes_requests table not found: {path}")

    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            # Allow comment rows (starting with '#')
            tid = (row.get("task_id") or "").strip()
            if not tid or tid.startswith("#"):
                continue
            rows.append(EpisodeRequest.from_row(row))
        return rows


def save_requests(reqs: List[EpisodeRequest], path: str = DEFAULT_TABLE_PATH) -> None:
    if not reqs:
        return

    fieldnames = list(reqs[0].to_row().keys())
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in reqs:
            writer.writerow(r.to_row())
    os.replace(tmp_path, path)


def find_next_for_request(reqs: List[EpisodeRequest]) -> Optional[EpisodeRequest]:
    for r in reqs:
        if r.status.strip().upper() == "PENDING_REQUEST":
            return r
    return None


def find_next_for_download(reqs: List[EpisodeRequest]) -> Optional[EpisodeRequest]:
    for r in reqs:
        if r.status.strip().upper() == "REQUESTED":
            return r
    return None


def mark_requested(r: EpisodeRequest, operation_name: str) -> None:
    r.operation_name = operation_name
    r.status = "REQUESTED"
    r.requested_at_utc = _utc_now_iso()
    r.last_error = ""


def mark_failed_request(r: EpisodeRequest, err: str) -> None:
    r.last_error = err
    r.status = "REQUEST_FAILED"


def mark_downloaded(r: EpisodeRequest, tag: str, asset_name: str, audio_url: str) -> None:
    r.audio_release_tag = tag
    r.audio_asset_name = asset_name
    r.audio_url = audio_url
    r.status = "DONE"
    r.downloaded_at_utc = _utc_now_iso()
    r.last_error = ""


def mark_failed_download(r: EpisodeRequest, err: str) -> None:
    r.last_error = err
    r.status = "DOWNLOAD_FAILED"


class EpisodesRequestsTable:
    def __init__(self, path: str = DEFAULT_TABLE_PATH):
        self.path = path

    @staticmethod
    def utc_now_iso() -> str:
        return _utc_now_iso()

    def load(self) -> List[EpisodeRequest]:
        return load_requests(self.path)

    def save(self, reqs: List[EpisodeRequest]) -> None:
        # save_requests signature is (reqs, path=...).
        save_requests(reqs, self.path)

    def iter_pending_requests(self, reqs: List[EpisodeRequest]) -> List[EpisodeRequest]:
        return [r for r in reqs if r.status.strip().upper() == TaskStatus.PENDING_REQUEST]

    def update_task(self, reqs: List[EpisodeRequest], task_id: str, patch: Dict[str, str]) -> None:
        for r in reqs:
            if r.task_id == task_id:
                for k, v in patch.items():
                    if hasattr(r, k):
                        setattr(r, k, v)
                return
        raise KeyError(f"task_id not found: {task_id}")
