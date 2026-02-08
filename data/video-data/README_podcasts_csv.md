# podcasts.csv

This CSV defines per-podcast configuration for the video podcast pipeline.
Each row represents one podcast show.

The file combines:
- Pipeline config (search prefix, clip orientation policy, thumbnail defaults).
- YouTube publishing config (category, privacy, playlist, credentials reference).
- Show-level podcast metadata (RSS <channel> fields, plus common podcast namespaces).

## Conventions

- Empty string means: not provided / use system default.
- Colors use hex RGB: #RRGGBB.
- Dates for RSS should be RFC 2822 when written into RSS (example: `Sun, 08 Feb 2026 21:00:00 -0500`).
- URLs should be absolute (https://...). File paths are relative to your repo root unless your pipeline states otherwise.

## Column reference

### podcast_id
- Type: string
- Required: yes
- Example: `agenda_podcast`
- Description: Stable identifier for this podcast row. Must be unique.
- Used by: Your pipeline and any registries that reference a podcast config.

### video_rss_path
- Type: string (path)
- Required: yes
- Example: `feed/agenda_video_podcast.xml`
- Description: Path to the generated video RSS XML file for this show.
- Used by: YouTube RSS ingestion (you provide the RSS URL that serves this file).

### search_prefix
- Type: string
- Required: no
- Example: `AGENDA`
- Description: Optional prefix used by your internal search/indexing logic for clips or episodes.
- Used by: Your internal pipeline (search/discovery).

### clip_orientation_policy
- Type: enum
- Required: yes
- Allowed values: horizontal|vertical|auto
- Example: `horizontal`
- Description: How your pipeline should treat clip orientation for video generation.
- Used by: Your clip rendering pipeline (cropping/letterboxing).

### min_aspect_ratio
- Type: number
- Required: no
- Example: `1.0`
- Description: Minimum aspect ratio allowed by your pipeline for source clips (width/height).
- Used by: Your clip selection/validation logic.

### thumb_square_path
- Type: string (path)
- Required: no
- Example: `data/thumbs/agenda_left.png`
- Description: Default square thumbnail template/image used to compose final thumbnails.
- Used by: Thumbnail generator step.

### thumb_bg_color
- Type: string (hex color)
- Required: no
- Example: `#0B0F1A`
- Description: Default background color used by the thumbnail generator.
- Used by: Thumbnail generator step.

### thumb_title_color
- Type: string (hex color)
- Required: no
- Example: `#FFFFFF`
- Description: Default title/text color used by the thumbnail generator.
- Used by: Thumbnail generator step.

### yt_category_id
- Type: integer
- Required: no
- Example: `25`
- Description: YouTube video category ID used at upload time.
- Used by: YouTube upload/publish step.

### yt_privacy
- Type: enum
- Required: no
- Allowed values: public|unlisted|private
- Example: `public`
- Description: YouTube privacy setting for uploaded videos.
- Used by: YouTube upload/publish step.

### yt_playlist_id
- Type: string
- Required: no
- Example: `PLxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
- Description: Target YouTube playlist ID where uploaded videos should be added. If empty, do not auto-add.
- Used by: YouTube playlist management step.

### yt_credentials_ref
- Type: string
- Required: yes
- Example: `yt_main`
- Description: Reference/key to locate YouTube API credentials in your secrets store.
- Used by: YouTube upload/publish step (auth).

### show_title
- Type: string
- Required: yes
- Example: `Agenda Podcast`
- Description: Show title (RSS <channel><title>).
- Used by: RSS output; directories; YouTube may display series title based on feed/channel mapping.

### show_description
- Type: string
- Required: yes
- Example: `Fast, focused, insightful analysis of politics, culture, and public safety.`
- Description: Show description (RSS <channel><description> / iTunes summary).
- Used by: RSS output; directories; YouTube feed surfaces.

### show_website_url
- Type: string (url)
- Required: no
- Example: `https://agenda-podcasts.com`
- Description: Primary website for the show (RSS <channel><link>).
- Used by: RSS output; directories.

### feed_self_url
- Type: string (url)
- Required: no
- Example: `https://agenda-podcasts.com/feed/agenda_video_podcast.xml`
- Description: Canonical URL of this feed (Atom <atom:link rel="self">).
- Used by: RSS/Atom output; feed validators and directories.

### language
- Type: string
- Required: no
- Example: `en-us`
- Description: Show language tag (RSS <channel><language>).
- Used by: RSS output; directories.

### author_name
- Type: string
- Required: no
- Example: `Agenda Podcast`
- Description: Publisher/author name (commonly iTunes and/or Google Play author).
- Used by: RSS namespaces for Apple/Google; directory display.

### owner_name
- Type: string
- Required: no
- Example: `Gregory Timofeev`
- Description: Owner name (iTunes <itunes:owner><itunes:name>).
- Used by: RSS output; directory contact metadata.

### owner_email
- Type: string (email)
- Required: no
- Example: `gr.timofeev@usa.com`
- Description: Owner email (iTunes <itunes:owner><itunes:email>, and often required for feed verification in some systems).
- Used by: RSS output; YouTube RSS verification workflows; directory contact metadata.

### show_artwork_url_or_path
- Type: string (url or path)
- Required: no
- Example: `data/artwork/agenda_podcast_3000.jpg`
- Description: Show artwork (RSS <image> and/or <itunes:image href="...">). Prefer >= 1400x1400, typically 3000x3000 JPEG/PNG.
- Used by: RSS output; directories; YouTube static episode video art.

### category_1
- Type: string
- Required: no
- Example: `News`
- Description: Primary category/genre for the show.
- Used by: RSS output (iTunes categories / directory categories).

### category_2
- Type: string
- Required: no
- Example: `Politics`
- Description: Secondary category/genre for the show.
- Used by: RSS output (optional).

### category_3
- Type: string
- Required: no
- Example: `Culture`
- Description: Tertiary category/genre for the show.
- Used by: RSS output (optional).

### explicit
- Type: enum
- Required: no
- Allowed values: yes|no|clean
- Example: `no`
- Description: Explicit-content indicator.
- Used by: RSS output (iTunes/Google Play style explicit flags); directory compliance.

### podcast_type
- Type: enum
- Required: no
- Allowed values: episodic|serial
- Example: `episodic`
- Description: Show type. Episodic: any order. Serial: intended to be consumed in sequence.
- Used by: RSS output (iTunes type) and some directory ordering behavior.

### is_complete
- Type: enum
- Required: no
- Allowed values: yes|no
- Example: `no`
- Description: Whether the show is complete/ended.
- Used by: RSS output (iTunes complete).

### is_blocked
- Type: enum
- Required: no
- Allowed values: yes|no
- Example: `no`
- Description: Whether the show should be blocked from directory listings.
- Used by: RSS output (iTunes/Google Play block).

### new_feed_url
- Type: string (url)
- Required: no
- Example: (empty)
- Description: If the feed moved, provide the new feed URL.
- Used by: RSS output (iTunes/Google Play feed relocation).

### copyright
- Type: string
- Required: no
- Example: `Copyright 2026 Agenda Podcast`
- Description: Copyright statement (RSS <copyright>).
- Used by: RSS output; directory display.

### last_build_date
- Type: string (rfc2822 datetime)
- Required: no
- Example: `Sun, 08 Feb 2026 21:00:00 -0500`
- Description: Feed last build date (RSS <lastBuildDate>).
- Used by: RSS output; feed caching behavior.

### global_guid
- Type: string (uuid)
- Required: no
- Example: `3f2c5f2b-7a3b-4d6c-9b2e-1a6a0d3e9c10`
- Description: Globally unique show ID (Podcasting 2.0 <podcast:guid>).
- Used by: RSS output (Podcasting 2.0); modern indexers.

### locked
- Type: enum
- Required: no
- Allowed values: yes|no
- Example: `yes`
- Description: Lock the feed to prevent unauthorized imports (Podcasting 2.0 <podcast:locked>).
- Used by: RSS output (Podcasting 2.0).

### funding_url_1
- Type: string (url)
- Required: no
- Example: `https://buymeacoffee.com/agendapodcast`
- Description: Funding/support link #1 (Podcasting 2.0 <podcast:funding url="...">).
- Used by: RSS output (Podcasting 2.0) and apps that show support buttons.

### funding_text_1
- Type: string
- Required: no
- Example: `Support the show`
- Description: Label for funding/support link #1.
- Used by: RSS output (Podcasting 2.0).

### funding_url_2
- Type: string (url)
- Required: no
- Example: `https://patreon.com/agendapodcast`
- Description: Funding/support link #2.
- Used by: RSS output (Podcasting 2.0).

### funding_text_2
- Type: string
- Required: no
- Example: `Become a member`
- Description: Label for funding/support link #2.
- Used by: RSS output (Podcasting 2.0).

### location
- Type: string
- Required: no
- Example: `New York, NY, USA`
- Description: Show location (Podcasting 2.0 <podcast:location>).
- Used by: RSS output (Podcasting 2.0).

### trailer_url
- Type: string (url)
- Required: no
- Example: `https://cdn.agenda-podcasts.com/trailer.mp3`
- Description: Trailer URL (Podcasting 2.0 <podcast:trailer>), if you publish a trailer.
- Used by: RSS output (Podcasting 2.0) and podcast apps that support trailers.

### keywords
- Type: string
- Required: no
- Example: `politics,culture,public safety,news`
- Description: Comma-separated keywords. Legacy in iTunes; still useful for internal search.
- Used by: RSS output (legacy) and internal search/indexing.
