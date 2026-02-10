from __future__ import annotations

import argparse
import csv
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .episodes_requests import EpisodesRequestsTable, EpisodeRequest

NS_ATOM = "http://www.w3.org/2005/Atom"
NS_ITUNES = "http://www.itunes.com/dtds/podcast-1.0.dtd"
NS_GOOGLEPLAY = "http://www.google.com/schemas/play-podcasts/1.0"
NS_PODCAST = "https://podcastindex.org/namespace/1.0"
NS_CONTENT = "http://purl.org/rss/1.0/modules/content/"


def _utc_now_rfc822() -> str:
    # Example: "Mon, 09 Feb 2026 02:10:00 +0000"
    return datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")


def _iso_to_rfc822(s: str) -> Optional[str]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        # Accept: 2026-02-08T19:00:00Z or with offset
        if s.endswith("Z"):
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")
    except Exception:
        return None


def _read_podcasts_table(path: str) -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        if not r.fieldnames or "podcast_id" not in r.fieldnames:
            raise SystemExit(f"podcasts table missing podcast_id: {path}")
        for row in r:
            pid = (row.get("podcast_id") or "").strip()
            if not pid:
                continue
            out[pid] = {k: (v or "").strip() for k, v in row.items()}
    return out


def _t(parent: ET.Element, tag: str, text: str) -> None:
    if not text:
        return
    el = ET.SubElement(parent, tag)
    el.text = text


def _t_ns(parent: ET.Element, ns: str, tag: str, text: str, attrib: Optional[dict] = None) -> None:
    if not text:
        return
    el = ET.SubElement(parent, f"{{{ns}}}{tag}", attrib=attrib or {})
    el.text = text


def _set_channel_metadata(channel: ET.Element, pcfg: Dict[str, str]) -> None:
    # Core RSS 2.0
    _t(channel, "title", pcfg.get("show_title", ""))
    _t(channel, "link", pcfg.get("show_website_url", ""))
    _t(channel, "description", pcfg.get("show_description", ""))
    _t(channel, "language", pcfg.get("language", ""))
    _t(channel, "copyright", pcfg.get("copyright", ""))

    lbd = pcfg.get("last_build_date", "")
    _t(channel, "lastBuildDate", _iso_to_rfc822(lbd) or _utc_now_rfc822())

    # Atom self link (helps aggregators)
    self_url = pcfg.get("feed_self_url", "")
    if self_url:
        ET.SubElement(
            channel,
            f"{{{NS_ATOM}}}link",
            attrib={"href": self_url, "rel": "self", "type": "application/rss+xml"},
        )

    # RSS image
    art = pcfg.get("show_artwork_url_or_path", "")
    if art:
        img = ET.SubElement(channel, "image")
        _t(img, "url", art)
        _t(img, "title", pcfg.get("show_title", ""))
        _t(img, "link", pcfg.get("show_website_url", ""))

    # iTunes show-level tags
    _t_ns(channel, NS_ITUNES, "author", pcfg.get("author_name", ""))
    # Many platforms map summary/subtitle from description if not provided separately.
    _t_ns(channel, NS_ITUNES, "summary", pcfg.get("show_description", ""))
    _t_ns(channel, NS_ITUNES, "subtitle", pcfg.get("show_title", ""))

    owner_name = pcfg.get("owner_name", "")
    owner_email = pcfg.get("owner_email", "")
    if owner_name or owner_email:
        owner = ET.SubElement(channel, f"{{{NS_ITUNES}}}owner")
        _t(owner, f"{{{NS_ITUNES}}}name", owner_name)
        _t(owner, f"{{{NS_ITUNES}}}email", owner_email)

    if art:
        ET.SubElement(channel, f"{{{NS_ITUNES}}}image", attrib={"href": art})

    _t_ns(channel, NS_ITUNES, "explicit", pcfg.get("explicit", ""))
    _t_ns(channel, NS_ITUNES, "type", pcfg.get("podcast_type", ""))
    _t_ns(channel, NS_ITUNES, "complete", pcfg.get("is_complete", ""))
    _t_ns(channel, NS_ITUNES, "block", pcfg.get("is_blocked", ""))
    _t_ns(channel, NS_ITUNES, "new-feed-url", pcfg.get("new_feed_url", ""))
    _t_ns(channel, NS_ITUNES, "keywords", pcfg.get("keywords", ""))

    for k in ("category_1", "category_2", "category_3"):
        cat = pcfg.get(k, "")
        if cat:
            ET.SubElement(channel, f"{{{NS_ITUNES}}}category", attrib={"text": cat})

    # Google Podcasts (a.k.a. Google Play podcasts schema)
    _t_ns(channel, NS_GOOGLEPLAY, "author", pcfg.get("author_name", ""))
    _t_ns(channel, NS_GOOGLEPLAY, "description", pcfg.get("show_description", ""))
    if art:
        _t_ns(channel, NS_GOOGLEPLAY, "image", art)
    _t_ns(channel, NS_GOOGLEPLAY, "explicit", pcfg.get("explicit", ""))
    _t_ns(channel, NS_GOOGLEPLAY, "block", pcfg.get("is_blocked", ""))
    for k in ("category_1", "category_2", "category_3"):
        cat = pcfg.get(k, "")
        if cat:
            _t_ns(channel, NS_GOOGLEPLAY, "category", cat)

    # Podcast Namespace (PodcastIndex)
    _t_ns(channel, NS_PODCAST, "guid", pcfg.get("global_guid", ""))

    locked = pcfg.get("locked", "").lower()
    if locked in ("yes", "true", "1"):
        owner = pcfg.get("owner_email", "")
        ET.SubElement(channel, f"{{{NS_PODCAST}}}locked", attrib={"owner": owner}).text = "yes"

    for idx in ("1", "2"):
        url = pcfg.get(f"funding_url_{idx}", "")
        text = pcfg.get(f"funding_text_{idx}", "")
        if url:
            _t_ns(channel, NS_PODCAST, "funding", text or url, attrib={"url": url})

    loc = pcfg.get("location", "")
    if loc:
        _t_ns(channel, NS_PODCAST, "location", loc)

    trailer = pcfg.get("trailer_url", "")
    if trailer:
        ET.SubElement(channel, f"{{{NS_PODCAST}}}trailer", attrib={"url": trailer})


def _add_item(channel: ET.Element, r: EpisodeRequest, pcfg: Dict[str, str]) -> None:
    item = ET.SubElement(channel, "item")
    _t(item, "title", r.title)
    if r.task_id:
        ET.SubElement(item, "guid", attrib={"isPermaLink": "false"}).text = r.task_id

    pub = _iso_to_rfc822(r.downloaded_at_utc) or _iso_to_rfc822(r.requested_at_utc) or _utc_now_rfc822()
    _t(item, "pubDate", pub)

    # Enclosure
    if r.audio_url:
        ET.SubElement(
            item,
            "enclosure",
            attrib={"url": r.audio_url, "length": "0", "type": "audio/mpeg"},
        )

    # Descriptions: plain + content:encoded for maximum compatibility.
    _t(item, "description", r.description)
    if r.description:
        _t_ns(item, NS_CONTENT, "encoded", r.description)

    # Platform-specific episode tags
    _t_ns(item, NS_ITUNES, "author", pcfg.get("author_name", ""))
    _t_ns(item, NS_ITUNES, "explicit", pcfg.get("explicit", ""))

    _t_ns(item, NS_GOOGLEPLAY, "author", pcfg.get("author_name", ""))
    _t_ns(item, NS_GOOGLEPLAY, "explicit", pcfg.get("explicit", ""))


def _write_xml(path: Path, root: ET.Element) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(root)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build RSS feeds from completed Podcast API audio requests")
    ap.add_argument("--requests", default=os.environ.get("EPISODES_REQUESTS", "data/video-data/episodes_requests.csv"))
    ap.add_argument("--podcasts", default=os.environ.get("PODCASTS_TABLE", "data/video-data/podcasts.csv"))
    args = ap.parse_args()

    # Register namespaces so ElementTree emits stable prefixes.
    ET.register_namespace("atom", NS_ATOM)
    ET.register_namespace("itunes", NS_ITUNES)
    ET.register_namespace("googleplay", NS_GOOGLEPLAY)
    ET.register_namespace("podcast", NS_PODCAST)
    ET.register_namespace("content", NS_CONTENT)

    podcasts = _read_podcasts_table(args.podcasts)
    table = EpisodesRequestsTable(args.requests)
    reqs = table.load()

    by_podcast: Dict[str, List[EpisodeRequest]] = {}
    for r in reqs:
        if r.status != "DOWNLOADED":
            continue
        if not r.podcast_id:
            continue
        by_podcast.setdefault(r.podcast_id, []).append(r)

    for pid, items in by_podcast.items():
        pcfg = podcasts.get(pid)
        if not pcfg:
            print(f"[build_rss][warn] missing podcasts.csv row for podcast_id={pid}")
            continue

        rss_path = (pcfg.get("audio_rss_path") or "").strip()
        if not rss_path:
            # Default if missing.
            rss_path = f"feed/audio_{pid}.xml"

        rss = ET.Element(
            "rss",
            attrib={
                "version": "2.0",
                f"xmlns:atom": NS_ATOM,
                f"xmlns:itunes": NS_ITUNES,
                f"xmlns:googleplay": NS_GOOGLEPLAY,
                f"xmlns:podcast": NS_PODCAST,
                f"xmlns:content": NS_CONTENT,
            },
        )
        channel = ET.SubElement(rss, "channel")
        _set_channel_metadata(channel, pcfg)

        # Determinism: order by downloaded_at then task_id.
        items_sorted = sorted(
            items,
            key=lambda x: (
                x.downloaded_at_utc or x.requested_at_utc or "",
                x.task_id,
            ),
        )
        for r in items_sorted:
            _add_item(channel, r, pcfg)

        _write_xml(Path(rss_path), rss)
        print(f"[build_rss] wrote {rss_path} items={len(items_sorted)} podcast_id={pid}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
