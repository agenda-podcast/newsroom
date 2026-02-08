# ASCII-only. No ellipses. Keep <= 500 lines.

from __future__ import annotations

import select
import subprocess
import threading
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Tuple


def run_ffmpeg_with_progress(
    cmd: List[str],
    segment_plan: List[Dict[str, Any]],
    expected_total_sec: float,
    target_fps: int,
    timeout_sec: int = 7200,
) -> None:
    """Run ffmpeg with structured progress logs.

    segment_plan items:
      - kind: intro|clip|outro
      - idx: int (for clip only)
      - file: str (for clip only)
      - abs_start: float
      - abs_end: float
      - dur: float
      - src_start: float (for clip only)
      - src_dur: float (for clip only)

    This function enforces a hard-fail guard if ffmpeg output time exceeds expected_total_sec
    by a wide margin, to prevent runaway runs on Actions.
    """
    # Ensure progress output is enabled. Keep stderr so ffmpeg still prints codec details.
    cmd2 = list(cmd)
    if "-progress" not in cmd2:
        cmd2.insert(1, "-progress")
        cmd2.insert(2, "pipe:1")
    if "-nostats" not in cmd2:
        cmd2.insert(1, "-nostats")
    start_ts = time.time()
    last_out_ms = -1
    last_seg_key = ""
    backward_jumps = 0

    last_progress_ts = time.time()
    last_advance_ts = time.time()
    last_hb_ts = time.time()
    last_out_sec = -1.0

    def _seg_for_out_sec(t: float) -> Dict[str, Any]:
        for s in segment_plan:
            if t >= float(s.get("abs_start") or 0.0) and t < float(s.get("abs_end") or 0.0):
                return s
        return {"kind": "unknown", "abs_start": 0.0, "abs_end": float(expected_total_sec), "dur": float(expected_total_sec)}

    def _fmt_sec(s: float) -> str:
        if s < 0:
            s = 0.0
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        sec = s - (h * 3600) - (m * 60)
        return "%02d:%02d:%06.3f" % (h, m, sec)

    print("[ffmpeg][plan] segments=%d expected_total_sec=%.3f target_fps=%d" % (
        len(segment_plan), float(expected_total_sec), int(target_fps)
    ), flush=True)
    for s in segment_plan:
        kind = str(s.get("kind") or "unknown")
        if kind == "clip":
            print("[ffmpeg][plan_segment] kind=clip idx=%s file=%s abs_start=%s abs_end=%s src_start=%.3f src_dur=%.3f" % (
                str(s.get("idx")),
                str(s.get("file")),
                _fmt_sec(float(s.get("abs_start") or 0.0)),
                _fmt_sec(float(s.get("abs_end") or 0.0)),
                float(s.get("src_start") or 0.0),
                float(s.get("src_dur") or 0.0),
            ), flush=True)
        else:
            print("[ffmpeg][plan_segment] kind=%s abs_start=%s abs_end=%s dur=%.3f" % (
                kind,
                _fmt_sec(float(s.get("abs_start") or 0.0)),
                _fmt_sec(float(s.get("abs_end") or 0.0)),
                float(s.get("dur") or 0.0),
            ), flush=True)
    print("[ffmpeg][cmd] %s" % (" ".join(cmd2)), flush=True)

    p = subprocess.Popen(
        cmd2,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )

    stderr_tail: Deque[str] = deque(maxlen=200)
    last_stderr_ts = time.time()
    stderr_lines = 0
    stderr_stop_evt = threading.Event()

    def _stderr_reader() -> None:
        nonlocal last_stderr_ts, stderr_lines
        try:
            assert p.stderr is not None
            for line in p.stderr:
                if stderr_stop_evt.is_set():
                    break
                line = line.rstrip("\n")
                if not line:
                    continue
                stderr_tail.append(line)
                last_stderr_ts = time.time()
                stderr_lines += 1
                # Keep logs useful but bounded: print early lines, then periodically.
                if stderr_lines <= 50 or (stderr_lines % 200) == 0:
                    print("[ffmpeg][stderr] %s" % line, flush=True)
        except Exception:
            return

    th = None
    try:
        th = threading.Thread(target=_stderr_reader)
        th.start()

        assert p.stdout is not None
        progress_kv: Dict[str, str] = {}
        last_print_sec = -1.0
        progress_events = 0

        while True:
            if time.time() - start_ts > float(timeout_sec):
                try:
                    p.terminate()
                except Exception:
                    pass
                raise RuntimeError("ffmpeg timeout exceeded")

            # Use select() so we can emit heartbeat logs even if ffmpeg is not producing output.
            rlist, _, _ = select.select([p.stdout], [], [], 1.0)
            now = time.time()

            # Always emit a wall-clock heartbeat, even if ffmpeg is chatty but not advancing time.
            if now - last_hb_ts >= 30.0:
                age_adv = now - last_advance_ts
                age_prog = now - last_progress_ts
                age_stderr = now - last_stderr_ts
                wall = now - start_ts
                print("[ffmpeg][heartbeat] wall_sec=%.1f out_time=%s seg=%s prog_age_sec=%.1f adv_age_sec=%.1f stderr_age_sec=%.1f stderr_lines=%d" % (
                    float(wall),
                    _fmt_sec(float(last_out_sec)),
                    str(last_seg_key),
                    float(age_prog),
                    float(age_adv),
                    float(age_stderr),
                    int(stderr_lines),
                ), flush=True)
                progress_events = 0
                last_hb_ts = now

            # Stall detection should be based on timeline advance, not just progress events.
            # Some ffmpeg states can emit progress=continue repeatedly while out_time_ms stays fixed.
            near_end = False
            if expected_total_sec is not None and last_out_sec is not None:
                near_end = last_out_sec >= float(expected_total_sec) - 0.25
            if (not near_end) and now - last_advance_ts >= 240.0 and now - start_ts >= 60.0:
                print("[ffmpeg][stall] no_out_time_advance_for_sec=%.1f seg=%s out_time=%s expected_total=%s terminating=1" % (
                    float(now - last_advance_ts),
                    str(last_seg_key),
                    _fmt_sec(float(last_out_sec)),
                    _fmt_sec(float(expected_total_sec)),
                ), flush=True)
                try:
                    p.terminate()
                except Exception:
                    pass
                raise RuntimeError("ffmpeg stalled: out_time not advancing")
            if not rlist:
                if p.poll() is not None:
                    break
                continue

            line = p.stdout.readline()
            if line == "" and p.poll() is not None:
                break
            if not line:
                continue
            line = line.strip()
            if "=" in line:
                k, v = line.split("=", 1)
                progress_kv[k.strip()] = v.strip()

            if progress_kv.get("progress") in ("continue", "end"):
                last_progress_ts = time.time()
                progress_events += 1
                out_ms_s = progress_kv.get("out_time_ms", "")
                out_sec = None
                if out_ms_s.isdigit():
                    out_ms = int(out_ms_s)
                    out_sec = float(out_ms) / 1000000.0
                    if last_out_ms >= 0 and out_ms + 2000000 < last_out_ms:
                        backward_jumps += 1
                        print("[ffmpeg][warn] out_time_ms moved backward from %d to %d jumps=%d" % (
                            int(last_out_ms), int(out_ms), int(backward_jumps)
                        ), flush=True)
                    last_out_ms = out_ms
                    if out_sec > last_out_sec + 0.001:
                        last_advance_ts = time.time()
                    last_out_sec = out_sec

                if out_sec is not None:
                    # Segment switch logs.
                    seg = _seg_for_out_sec(out_sec)
                    kind = str(seg.get("kind") or "unknown")
                    seg_key = kind
                    if kind == "clip":
                        seg_key = "clip:%s:%s" % (str(seg.get("idx")), str(seg.get("file")))
                    if seg_key != last_seg_key:
                        last_seg_key = seg_key
                        local = out_sec - float(seg.get("abs_start") or 0.0)
                        if kind == "clip":
                            print("[ffmpeg][segment] kind=clip idx=%s file=%s abs=%s local=%s src_start=%.3f src_dur=%.3f" % (
                                str(seg.get("idx")),
                                str(seg.get("file")),
                                _fmt_sec(out_sec),
                                _fmt_sec(local),
                                float(seg.get("src_start") or 0.0),
                                float(seg.get("src_dur") or 0.0),
                            ), flush=True)
                        else:
                            print("[ffmpeg][segment] kind=%s abs=%s local=%s dur=%.3f" % (
                                kind,
                                _fmt_sec(out_sec),
                                _fmt_sec(local),
                                float(seg.get("dur") or 0.0),
                            ), flush=True)

                    # Periodic progress log (once per ~15 seconds of output time).
                    if out_sec - last_print_sec >= 15.0:
                        last_print_sec = out_sec
                        print("[ffmpeg][progress] abs=%s seg=%s" % (_fmt_sec(out_sec), seg_key), flush=True)

                    # Near-end marker to distinguish "done encoding" vs "finalizing".
                    if out_sec >= float(expected_total_sec) - (2.0 / float(max(1, int(target_fps)))):
                        print("[ffmpeg][phase] nearing_end abs=%s expected_total=%s" % (
                            _fmt_sec(out_sec), _fmt_sec(float(expected_total_sec))
                        ), flush=True)

                    # Hard-fail guard: output time must not exceed expected total by more than 2 seconds + 2 frames.
                    guard = float(expected_total_sec) + 2.0 + (2.0 / float(max(1, int(target_fps))))
                    if out_sec > guard:
                        print("[ffmpeg][guard] out_time_exceeds_expected abs=%s expected_total=%s" % (
                            _fmt_sec(out_sec), _fmt_sec(float(expected_total_sec))
                        ), flush=True)
                        try:
                            p.terminate()
                        except Exception:
                            pass
                        raise RuntimeError("ffmpeg runaway duration detected")

                pr = progress_kv.get("progress")
                progress_kv = {}
                if pr == "end":
                    break

        rc = p.wait()
        if rc != 0:
            tail = "\n".join(stderr_tail[-50:])
            raise RuntimeError("ffmpeg failed rc=%d tail=%s" % (int(rc), tail))
    finally:
        try:
            if p.poll() is None:
                p.terminate()
        except Exception:
            pass
        try:
            stderr_stop_evt.set()
            if p.stderr is not None:
                try:
                    p.stderr.close()
                except Exception:
                    pass
            if th is not None:
                th.join(timeout=5.0)
        except Exception:
            pass

