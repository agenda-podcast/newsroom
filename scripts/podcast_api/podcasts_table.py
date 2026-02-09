from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from typing import Dict, Optional


DEFAULT_PODCASTS_PATH = os.path.join("data", "video-data", "podcasts.csv")


@dataclass
class PodcastConfig:
    podcast_id: str
    podcast_name: str
    site_url: str
    feed_home_url: str
    language: str
    author: str
    owner_name: str
    owner_email: str
    category: str
    subcategory: str
    explicit: str
    summary: str
    description: str
    keywords: str
    copyright: str
    managing_editor: str
    webmaster: str
    artwork_square_path: str
    image_url: str
    googleplay_author: str
    googleplay_email: str
    googleplay_category: str
    yt_channel_id: str
    yt_playlist_id: str
    yt_category_id: str
    yt_privacy: str
    audio_rss_path: str
    gcp_project_id: str
    notebooklm_length: str
    atom_self_url: str
    atom_hub_url: str
    itunes_type: str
    itunes_new_feed_url: str
    itunes_block: str
    itunes_complete: str
    podcast_locked: str
    podcast_guid: str
    podcast_medium: str

    @staticmethod
    def from_row(row: Dict[str, str]) -> "PodcastConfig":
        def g(k: str) -> str:
            return (row.get(k) or "").strip()

        return PodcastConfig(
            podcast_id=g("podcast_id"),
            podcast_name=g("podcast_name"),
            site_url=g("site_url"),
            feed_home_url=g("feed_home_url"),
            language=g("language"),
            author=g("author"),
            owner_name=g("owner_name"),
            owner_email=g("owner_email"),
            category=g("category"),
            subcategory=g("subcategory"),
            explicit=g("explicit"),
            summary=g("summary"),
            description=g("description"),
            keywords=g("keywords"),
            copyright=g("copyright"),
            managing_editor=g("managing_editor"),
            webmaster=g("webmaster"),
            artwork_square_path=g("artwork_square_path"),
            image_url=g("image_url"),
            googleplay_author=g("googleplay_author"),
            googleplay_email=g("googleplay_email"),
            googleplay_category=g("googleplay_category"),
            yt_channel_id=g("yt_channel_id"),
            yt_playlist_id=g("yt_playlist_id"),
            yt_category_id=g("yt_category_id"),
            yt_privacy=g("yt_privacy"),
            audio_rss_path=g("audio_rss_path"),
            gcp_project_id=g("gcp_project_id"),
            notebooklm_length=g("notebooklm_length") or "STANDARD",
            atom_self_url=g("atom_self_url"),
            atom_hub_url=g("atom_hub_url"),
            itunes_type=g("itunes_type") or "episodic",
            itunes_new_feed_url=g("itunes_new_feed_url"),
            itunes_block=g("itunes_block"),
            itunes_complete=g("itunes_complete"),
            podcast_locked=g("podcast_locked"),
            podcast_guid=g("podcast_guid"),
            podcast_medium=g("podcast_medium"),
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
