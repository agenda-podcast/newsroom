# ASCII-only. No ellipses. Keep <= 500 lines.
import os
import re
from typing import Dict, Any


def _norm_name(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def load_podcast_reg(csv_path: str) -> Dict[str, str]:
    if not csv_path:
        return {}
    if not os.path.exists(csv_path):
        return {}
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            lines = [ln.strip() for ln in f.read().splitlines() if ln.strip()]
        if not lines:
            return {}
        header = [h.strip() for h in lines[0].split(",")]
        if "podcast_name" not in header or "podcast_id" not in header:
            return {}
        name_idx = header.index("podcast_name")
        id_idx = header.index("podcast_id")
        out: Dict[str, str] = {}
        for ln in lines[1:]:
            parts = [c.strip() for c in ln.split(",")]
            if len(parts) <= max(name_idx, id_idx):
                continue
            nm = _norm_name(parts[name_idx])
            pid = (parts[id_idx] or "").strip()
            if nm and pid:
                out[nm] = pid
        return out
    except Exception:
        return {}


def _get_dict(obj: Any) -> Dict[str, Any]:
    return obj if isinstance(obj, dict) else {}


def derive_podcast_id(entry: Any, feed_obj: Any, podcast_name: str, reg: Dict[str, str], env_title: str = "", default_pid: str = "default") -> str:
    # Prefer explicit RSS field if present (supports typo pidcast_id).
    pid = ""
    try:
        pid = str(_get_dict(entry).get("podcast_id") or _get_dict(entry).get("pidcast_id") or "").strip()
    except Exception:
        pid = ""
    if not pid:
        try:
            feed_d = _get_dict(feed_obj)
            pid = str(feed_d.get("podcast_id") or feed_d.get("pidcast_id") or "").strip()
        except Exception:
            pid = ""

    if pid:
        return pid

    nm = _norm_name(podcast_name)
    if nm and nm in reg:
        return reg[nm]

    env_nm = _norm_name(env_title)
    if env_nm and env_nm in reg:
        return reg[env_nm]

    return default_pid
