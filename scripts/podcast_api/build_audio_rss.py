from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from typing import List

from .episodes_requests import EpisodeRequest, load_requests
from .podcasts_table import PodcastConfig, load_podcasts_table


ATOM_NS = "http://www.w3.org/2005/Atom"
ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
GOOGLEPLAY_NS = "http://www.google.com/schemas/play-podcasts/1.0"
PODCAST_NS = "https://podcastindex.org/namespace/1.0"


def _xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _bool_str(v: str) -> str:
    v2 = (v or "").strip().lower()
    if v2 in ("yes", "true", "1"):
        return "yes"
    if v2 in ("no", "false", "0"):
        return "no"
    return v2 or "no"


def _rfc2822_now() -> str:
    return datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")


def _item_pubdate(req: EpisodeRequest) -> str:
    # Prefer downloaded timestamp, else requested timestamp.
    iso = req.downloaded_at_utc or req.requested_at_utc
    if not iso:
        return _rfc2822_now()
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")
    except Exception:
        return _rfc2822_now()


def build_rss_for_podcast(pcfg: PodcastConfig, requests: List[EpisodeRequest]) -> str:
    # Channel-level metadata.
    title = pcfg.podcast_name
    link = pcfg.site_url
    desc = pcfg.description or pcfg.summary or pcfg.podcast_name

    # Namespace declarations (max compatibility across podcast apps).
    hdr = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<rss version=\"2.0\"\n"
        f"  xmlns:atom=\"{ATOM_NS}\"\n"
        f"  xmlns:itunes=\"{ITUNES_NS}\"\n"
        f"  xmlns:googleplay=\"{GOOGLEPLAY_NS}\"\n"
        f"  xmlns:podcast=\"{PODCAST_NS}\"\n"
        ">\n"
        "<channel>\n"
    )

    parts: List[str] = [hdr]
    parts.append(f"  <title>{_xml_escape(title)}</title>\n")
    parts.append(f"  <link>{_xml_escape(link)}</link>\n")
    parts.append(f"  <description>{_xml_escape(desc)}</description>\n")
    if pcfg.language:
        parts.append(f"  <language>{_xml_escape(pcfg.language)}</language>\n")
    parts.append(f"  <lastBuildDate>{_rfc2822_now()}</lastBuildDate>\n")
    parts.append("  <generator>podcast-archive</generator>\n")

    # atom self link
    self_url = pcfg.atom_self_url or ""
    if self_url:
        parts.append(
            f"  <atom:link href=\"{_xml_escape(self_url)}\" rel=\"self\" type=\"application/rss+xml\" />\n"
        )

    # Image
    img_url = pcfg.image_url or ""
    if img_url:
        parts.append("  <image>\n")
        parts.append(f"    <url>{_xml_escape(img_url)}</url>\n")
        parts.append(f"    <title>{_xml_escape(title)}</title>\n")
        parts.append(f"    <link>{_xml_escape(link)}</link>\n")
        parts.append("  </image>\n")

    # iTunes tags
    if pcfg.author:
        parts.append(f"  <itunes:author>{_xml_escape(pcfg.author)}</itunes:author>\n")
    if pcfg.summary:
        parts.append(f"  <itunes:summary>{_xml_escape(pcfg.summary)}</itunes:summary>\n")
    parts.append(f"  <itunes:explicit>{_xml_escape(_bool_str(pcfg.explicit))}</itunes:explicit>\n")
    if img_url:
        parts.append(f"  <itunes:image href=\"{_xml_escape(img_url)}\" />\n")
    if pcfg.owner_name or pcfg.owner_email:
        parts.append("  <itunes:owner>\n")
        if pcfg.owner_name:
            parts.append(f"    <itunes:name>{_xml_escape(pcfg.owner_name)}</itunes:name>\n")
        if pcfg.owner_email:
            parts.append(f"    <itunes:email>{_xml_escape(pcfg.owner_email)}</itunes:email>\n")
        parts.append("  </itunes:owner>\n")
    if pcfg.keywords:
        parts.append(f"  <itunes:keywords>{_xml_escape(pcfg.keywords)}</itunes:keywords>\n")
    if pcfg.itunes_type:
        parts.append(f"  <itunes:type>{_xml_escape(pcfg.itunes_type)}</itunes:type>\n")
    if pcfg.itunes_new_feed_url:
        parts.append(f"  <itunes:new-feed-url>{_xml_escape(pcfg.itunes_new_feed_url)}</itunes:new-feed-url>\n")
    if pcfg.itunes_block:
        parts.append(f"  <itunes:block>{_xml_escape(_bool_str(pcfg.itunes_block))}</itunes:block>\n")
    if pcfg.itunes_complete:
        parts.append(f"  <itunes:complete>{_xml_escape(_bool_str(pcfg.itunes_complete))}</itunes:complete>\n")

    # iTunes categories (primary + optional secondary)
    if pcfg.category:
        parts.append(f"  <itunes:category text=\"{_xml_escape(pcfg.category)}\">")
        if pcfg.subcategory:
            parts.append(f"<itunes:category text=\"{_xml_escape(pcfg.subcategory)}\" />")
        parts.append("</itunes:category>\n")

    # Google Play tags
    if pcfg.googleplay_author:
        parts.append(
            f"  <googleplay:author>{_xml_escape(pcfg.googleplay_author)}</googleplay:author>\n"
        )
    if pcfg.googleplay_email:
        parts.append(
            f"  <googleplay:email>{_xml_escape(pcfg.googleplay_email)}</googleplay:email>\n"
        )
    if pcfg.googleplay_category:
        parts.append(
            f"  <googleplay:category text=\"{_xml_escape(pcfg.googleplay_category)}\" />\n"
        )
    if img_url:
        parts.append(
            f"  <googleplay:image href=\"{_xml_escape(img_url)}\" />\n"
        )
    parts.append(
        f"  <googleplay:explicit>{_xml_escape(_bool_str(pcfg.explicit))}</googleplay:explicit>\n"
    )
    if pcfg.description:
        parts.append(
            f"  <googleplay:description>{_xml_escape(pcfg.description)}</googleplay:description>\n"
        )

    # Podcasting 2.0 tags (best-effort)
    if pcfg.podcast_locked:
        parts.append(
            f"  <podcast:locked>{_xml_escape(_bool_str(pcfg.podcast_locked))}</podcast:locked>\n"
        )
    if pcfg.podcast_guid:
        parts.append(f"  <podcast:guid>{_xml_escape(pcfg.podcast_guid)}</podcast:guid>\n")
    if pcfg.podcast_medium:
        parts.append(
            f"  <podcast:medium>{_xml_escape(pcfg.podcast_medium)}</podcast:medium>\n"
        )

    # Items: DONE tasks only.
    done = [r for r in requests if (r.status or "").strip().upper() == "DONE" and r.audio_url]
    # Stable order: by downloaded timestamp then task_id
    done.sort(key=lambda r: (r.downloaded_at_utc or "", r.task_id))

    for r in done:
        guid = r.task_id or r.operation_name or r.audio_url
        item_title = r.title or f"Audio overview {r.task_id}"
        item_desc = r.description or r.custom_prompt or "Audio overview generated by Podcast API."
        enclosure_url = r.audio_url

        parts.append("  <item>\n")
        parts.append(f"    <title>{_xml_escape(item_title)}</title>\n")
        parts.append(f"    <description>{_xml_escape(item_desc)}</description>\n")
        parts.append(f"    <guid isPermaLink=\"false\">{_xml_escape(guid)}</guid>\n")
        parts.append(f"    <pubDate>{_item_pubdate(r)}</pubDate>\n")
        parts.append(
            f"    <enclosure url=\"{_xml_escape(enclosure_url)}\" type=\"audio/mpeg\" />\n"
        )
        # iTunes episode-level tags (best-effort)
        parts.append(f"    <itunes:explicit>{_xml_escape(_bool_str(pcfg.explicit))}</itunes:explicit>\n")
        parts.append("  </item>\n")

    parts.append("</channel>\n</rss>\n")
    return "".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build audio RSS per podcast_id from completed episode requests")
    ap.add_argument("--podcasts", default=os.path.join("data", "video-data", "podcasts.csv"))
    ap.add_argument("--requests", default=os.path.join("data", "video-data", "episodes_requests.csv"))
    args = ap.parse_args()

    podcasts = load_podcasts_table(args.podcasts)
    reqs = load_requests(args.requests)

    # Group by podcast_id
    by_pid = {}
    for r in reqs:
        pid = (r.podcast_id or "").strip()
        if not pid:
            continue
        by_pid.setdefault(pid, []).append(r)

    wrote_any = False
    for pid, pcfg in podcasts.items():
        out_path = pcfg.audio_rss_path
        if not out_path:
            continue
        rss = build_rss_for_podcast(pcfg, by_pid.get(pid, []))
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(rss)
        print(f"[rss] wrote {out_path} podcast_id={pid} items={len([r for r in by_pid.get(pid, []) if (r.status or '').upper()=='DONE'])}")
        wrote_any = True

    if not wrote_any:
        print("[rss] nothing to write (no podcasts with audio_rss_path)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
