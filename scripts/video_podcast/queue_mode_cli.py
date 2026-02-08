# ASCII-only. No ellipses. Keep <= 500 lines.

from __future__ import annotations

import argparse
from pathlib import Path

from .tables import ensure_podcasts_csv, ensure_queue_mode, load_podcasts, load_queue_mode, save_queue_mode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--run-all-podcasts", required=True, help="true|false")
    ap.add_argument("--podcast-id", default="", help="used when run-all-podcasts=false")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    ensure_podcasts_csv(repo_root)
    ensure_queue_mode(repo_root)

    podcasts = load_podcasts(repo_root)
    mode = load_queue_mode(repo_root)

    rap = str(args.run_all_podcasts).strip().lower()
    if rap not in ["true", "false"]:
        raise SystemExit("run-all-podcasts must be true|false")
    mode.run_all_podcasts = (rap == "true")

    pid = str(args.podcast_id or "").strip()
    if not mode.run_all_podcasts:
        if pid and pid not in podcasts:
            raise SystemExit("unknown podcast_id: %s" % pid)
        mode.podcast_id = pid
    else:
        mode.podcast_id = ""

    save_queue_mode(repo_root, mode)
    print("[queue_mode] run_all_podcasts=%s podcast_id=%s" % ("true" if mode.run_all_podcasts else "false", mode.podcast_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
