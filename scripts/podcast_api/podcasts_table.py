from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from typing import Dict


DEFAULT_PODCASTS_PATH = os.path.join("data", "video-data", "podcasts.csv")


@dataclass
class PodcastConfig:
    # Primary
    podcast_id: str

    # Podcast API inputs
    language: str
    gcp_project_id: str
    podcast_api_length: str  # STANDARD|LONG|SHORT (server enum)
    notebooklm_length: str  # backward-compatible alias
    audio_rss_path: str

    # Optional metadata (kept for future RSS work; safe if empty)
    podcast_name: str
    site_url: str
    summary: str
    description: str
    owner_name: str
    owner_email: str
    explicit: str
    keywords: str
    copyright: str
    yt_playlist_id: str
    yt_category_id: str
    yt_privacy: str

    @staticmethod
    def from_row(row: Dict[str, str]) -> "PodcastConfig":
        def g(k: str) -> str:
            return (row.get(k) or "").strip()

        # Support two schemas:
        # - normalized podcasts.csv (show_title, show_description, ...)
        # - older schema (podcast_name, summary, description, ...)
        podcast_name = g("podcast_name") or g("show_title")
        site_url = g("site_url") or g("show_website_url")

        summary = g("summary") or g("show_description")
        description = g("description") or g("show_description")

        owner_name = g("owner_name")
        owner_email = g("owner_email")

        language = g("language") or "en-us"

        yt_playlist_id = g("yt_playlist_id")
        yt_category_id = g("yt_category_id")
        yt_privacy = g("yt_privacy") or "public"

        explicit = g("explicit") or "no"
        keywords = g("keywords")
        copyright = g("copyright")

        audio_rss_path = g("audio_rss_path") or "feed/audio_podcast.xml"
        gcp_project_id = g("gcp_project_id") or os.environ.get("GCP_PROJECT_ID", "").strip()
        length = g("podcast_api_length") or g("notebooklm_length") or "STANDARD"

        return PodcastConfig(
            podcast_id=g("podcast_id"),
            language=language,
            gcp_project_id=gcp_project_id,
            podcast_api_length=length,
            notebooklm_length=length,
            audio_rss_path=audio_rss_path,
            podcast_name=podcast_name,
            site_url=site_url,
            summary=summary,
            description=description,
            owner_name=owner_name,
            owner_email=owner_email,
            explicit=explicit,
            keywords=keywords,
            copyright=copyright,
            yt_playlist_id=yt_playlist_id,
            yt_category_id=yt_category_id,
            yt_privacy=yt_privacy,
        )


def load_podcasts(path: str = DEFAULT_PODCASTS_PATH) -> Dict[str, PodcastConfig]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"podcasts table not found: {path}")
    out: Dict[str, PodcastConfig] = {}
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pid = (row.get("podcast_id") or "").strip()
            if not pid or pid.startswith("#"):
                continue
            out[pid] = PodcastConfig.from_row(row)
    return out


# Backward-compatible name used by workflows/scripts.
def load_podcasts_table(path: str = DEFAULT_PODCASTS_PATH) -> Dict[str, PodcastConfig]:
    return load_podcasts(path)


def get_podcast(podcast_id: str, path: str = DEFAULT_PODCASTS_PATH) -> PodcastConfig:
    tbl = load_podcasts(path)
    if podcast_id not in tbl:
        raise KeyError(f"podcast_id not found in podcasts table: {podcast_id}")
    return tbl[podcast_id]
