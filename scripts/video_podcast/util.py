# ASCII-only. No ellipses. Keep <= 500 lines.

import hashlib
import json
import random
import re
import shutil
import select
import subprocess
import threading
import sys
import time
import urllib.request
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple


def ensure_png_canvas_16x9(
    *,
    src_png: Path,
    dst_png: Path,
    out_w: int,
    out_h: int,
) -> None:
    """Create a transparent out_w x out_h PNG with src centered.

    This is used to avoid filtergraph stretching / SAR incompatibility
    by ensuring the overlay frame asset is already 16:9.

    The original src is scaled by height to out_h (AR preserved), then
    pasted centered onto a transparent canvas.
    """

    dst_png.parent.mkdir(parents=True, exist_ok=True)

    # Fast path: if dst exists and is newer than src, keep it.
    try:
        if dst_png.exists() and dst_png.stat().st_mtime >= src_png.stat().st_mtime:
            return
    except Exception:
        pass

    # Prefer Pillow if available; otherwise fall back to a single-image ffmpeg pad.
    try:
        from PIL import Image

        im = Image.open(src_png).convert("RGBA")
        # Scale by height to out_h.
        if im.height != out_h:
            new_w = max(1, int(round(im.width * (out_h / float(im.height)))))
            im = im.resize((new_w, out_h), Image.LANCZOS)
        canvas = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
        x = max(0, (out_w - im.width) // 2)
        y = max(0, (out_h - im.height) // 2)
        canvas.paste(im, (x, y), im)
        canvas.save(dst_png)
        return
    except Exception as e:
        # Fall back to ffmpeg. This encodes only a PNG (not a video), and runs once.
        # Use a transparent pad background and force RGBA so ffmpeg does not lose alpha.
        # NOTE: This path is used on runners where Pillow is not installed.
        dst_png.parent.mkdir(parents=True, exist_ok=True)
        vf = (
            f"scale=-1:{out_h}:flags=lanczos,"
            f"format=rgba,"
            f"pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2:color=black@0.0,"
            f"format=rgba"
        )
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(src_png),
            "-vf",
            vf,
            "-frames:v",
            "1",
            str(dst_png),
        ]
        print(f"[frame][ffmpeg_fallback] err={type(e).__name__} cmd={' '.join(cmd)}")
        run(cmd)



USER_AGENT = "video-podcast-render/1.0"


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_slug(s: str, max_len: int = 80) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    if not s:
        s = "item"
    return s[:max_len]


def run(
    cmd: List[str],
    timeout_sec: int = 600,
    stream: bool = False,
) -> subprocess.CompletedProcess:
    """Run a subprocess with sane defaults for GitHub Actions.

    - By default, captures stdout/stderr for parsing.
    - For long-running processes (ffmpeg), pass stream=True to avoid "looks stuck".
    - A timeout guard prevents indefinite hangs.
    """
    try:
        if stream:
            return subprocess.run(cmd, text=True, check=True, timeout=timeout_sec)
        return subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired as e:
        print("[run][timeout] cmd=%s" % " ".join(cmd), file=sys.stderr)
        raise RuntimeError("command timed out") from e
    except subprocess.CalledProcessError as e:
        # Keep stderr reasonably small in exception messages.
        err = (e.stderr or "")
        err = err[-4000:] if len(err) > 4000 else err
        print("[run][fail] cmd=%s" % " ".join(cmd), file=sys.stderr)
        if err:
            print(err, file=sys.stderr)
        raise


def ffprobe_duration_sec(p: Path) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(p),
    ]
    out = run(cmd).stdout.strip()
    return float(out)


def ffprobe_video_dims(p: Path) -> Tuple[int, int]:
    """Return (width, height) for the first video stream. (0,0) on failure."""
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0:s=x",
            str(p),
        ]
        out = run(cmd).stdout.strip()
        if not out or "x" not in out:
            return 0, 0
        w_s, h_s = out.split("x", 1)
        return int(float(w_s)), int(float(h_s))
    except Exception:
        return 0, 0


def infer_asset_page_url(source: str, asset_id: str, fallback: str = "") -> str:
    """Return a stable public page URL for known stock-video sources.

    This is used for auditability (e.g. mapping "pexels-34056946.mp4" ->
    the public page). For unknown sources, we keep the provided fallback.
    """
    src = (source or "").strip().lower()
    aid = (asset_id or "").strip()
    if not aid:
        return fallback
    if src == "pexels":
        # Pexels supports a stable numeric id form.
        return f"https://www.pexels.com/video/{aid}/"
    if src == "pixabay":
        # Pixabay uses an id-* URL etc
        return f"https://pixabay.com/videos/id-{aid}/"
    return fallback


def make_timecoded_url(page_url: str, start_sec: float, end_sec: float) -> str:
    """Attach time information etc

    Not all providers support time anchors; we still record the numbers in a
    standard query string for human use.
    """
    if not page_url:
        return ""
    try:
        s = max(0.0, float(start_sec))
        e = max(s, float(end_sec))
    except Exception:
        return page_url
    # Use integer seconds etc
    return f"{page_url}?t={int(s)}&t_end={int(e)}"


def http_get_json(url: str, headers: Dict[str, str], timeout_sec: int = 30) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def download(url: str, dst: Path, timeout_sec: int = 90, headers: Dict[str, str] = None) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    h = {"User-Agent": USER_AGENT}
    if headers:
        for k, v in headers.items():
            if k and v:
                h[str(k)] = str(v)
    req = urllib.request.Request(url, headers=h, method="GET")
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        with open(dst, "wb") as f:
            shutil.copyfileobj(resp, f)


def load_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(p: Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def strip_html(s: str) -> str:
    s = s or ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def rand_for_guid(guid: str) -> random.Random:
    h = hashlib.sha256(guid.encode("utf-8")).digest()
    seed = int.from_bytes(h[:4], "big")
    return random.Random(seed)
