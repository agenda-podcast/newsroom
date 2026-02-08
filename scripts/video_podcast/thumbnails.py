from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class ThumbnailSpec:
    w: int = 1280
    h: int = 720
    # Left panel is w-h wide; right panel is square (h x h).
    left_pad: int = 0


def _load_font(paths: List[str], size: int):
    try:
        from PIL import ImageFont  # type: ignore
    except Exception as e:
        raise RuntimeError("Pillow is required for thumbnail generation") from e

    for p in paths:
        try:
            return ImageFont.truetype(p, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _wrap_text(draw, text: str, font, max_w: int):
    words = [w for w in text.replace("\n", " ").split(" ") if w]
    if not words:
        return []
    lines = []
    cur = words[0]
    for w in words[1:]:
        test = cur + " " + w
        if draw.textlength(test, font=font) <= max_w:
            cur = test
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def _fit_text(
    draw,
    text: str,
    *,
    box_w: int,
    box_h: int,
    bold: bool,
    max_size: int = 160,
):
    if bold:
        font_paths = (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        )
    else:
        font_paths = (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        )

    for size in range(max_size, 14, -2):
        font = _load_font(font_paths, size=size)
        lines = _wrap_text(draw, text, font, box_w)
        if not lines:
            return font, []
        line_h = int(size * 1.2)
        total_h = line_h * len(lines)
        if total_h <= box_h:
            return font, lines
    font = _load_font(font_paths, size=14)
    return font, _wrap_text(draw, text, font, box_w)


def _hex_to_rgb(s: str, default: Tuple[int, int, int]) -> Tuple[int, int, int]:
    t = (s or "").strip()
    if t.startswith("#"):
        t = t[1:]
    if len(t) == 3:
        t = "".join([c + c for c in t])
    if len(t) != 6:
        return default
    try:
        r = int(t[0:2], 16)
        g = int(t[2:4], 16)
        b = int(t[4:6], 16)
        return (r, g, b)
    except Exception:
        return default


def ensure_thumbnail_template(
    *,
    left_image_path: Optional[Path] = None,
    template_path: Optional[Path] = None,
    left_img_path: Optional[Path] = None,
    template_png: Optional[Path] = None,
    spec: ThumbnailSpec = ThumbnailSpec(),
) -> None:
    """Create a 16:9 template with a square image on the right.

    The left panel is initialized as black. Per-episode rendering can recolor it.
    """

    try:
        from PIL import Image, ImageDraw  # type: ignore
    except Exception as e:
        raise RuntimeError("Pillow is required for thumbnail generation") from e

    if left_image_path is None:
        left_image_path = left_img_path
    if template_path is None:
        template_path = template_png
    if left_image_path is None or template_path is None:
        raise ValueError("left_image_path and template_path are required")

    w, h = spec.w, spec.h
    square = h
    img_x0 = w - square

    canvas = Image.new("RGB", (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    if left_image_path.exists():
        src = Image.open(left_image_path).convert("RGB")
        sw, sh = src.size
        s = min(sw, sh)
        x0 = (sw - s) // 2
        y0 = (sh - s) // 2
        src_sq = src.crop((x0, y0, x0 + s, y0 + s)).resize((square, square))
        canvas.paste(src_sq, (img_x0, 0))
    else:
        draw.rectangle((img_x0, 0, w, square), fill=(25, 25, 25))
        f = _load_font(("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",), size=36)
        msg = "PLACEHOLDER"
        tw = draw.textlength(msg, font=f)
        draw.text((img_x0 + (square - tw) / 2, h * 0.45), msg, font=f, fill=(200, 200, 200))

    template_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(template_path)


def render_episode_thumbnail(
    *,
    template_path: Optional[Path] = None,
    out_path: Optional[Path] = None,
    title: Optional[str] = None,
    bg_color_hex: str = "#000000",
    title_color_hex: str = "#FFFFFF",
    template_png: Optional[Path] = None,
    out_png: Optional[Path] = None,
    episode_title: Optional[str] = None,
    spec: ThumbnailSpec = ThumbnailSpec(),
) -> None:
    """Render a per-episode thumbnail.

    Layout:
      - right: square image from template
      - left: solid background color (podcast-configured)
      - left: title only (bold, large), auto-sized to fill the panel
    """

    try:
        from PIL import Image, ImageDraw  # type: ignore
    except Exception as e:
        raise RuntimeError("Pillow is required for thumbnail generation") from e

    if template_path is None:
        template_path = template_png
    if out_path is None:
        out_path = out_png
    if title is None:
        title = episode_title or ""
    if template_path is None or out_path is None:
        raise ValueError("template_path and out_path are required")

    img = Image.open(template_path).convert("RGB")
    w, h = spec.w, spec.h
    if img.size != (w, h):
        img = img.resize((w, h))

    square = h
    img_x0 = w - square

    bg_rgb = _hex_to_rgb(bg_color_hex, (0, 0, 0))
    title_rgb = _hex_to_rgb(title_color_hex, (255, 255, 255))

    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, img_x0, h), fill=bg_rgb)

    pad = 32
    title_w = img_x0
    box_x0 = pad
    box_x1 = title_w - pad
    title_box = (box_x0, pad, box_x1, h - pad)
    box_w = title_box[2] - title_box[0]
    box_h = title_box[3] - title_box[1]

    font_t, lines_t = _fit_text(
        draw,
        title,
        box_w=box_w,
        box_h=box_h,
        bold=True,
        max_size=220,
    )

    line_h = int(getattr(font_t, "size", 32) * 1.18)
    total_h = max(1, len(lines_t)) * line_h
    y = title_box[1] + max(0, (box_h - total_h) // 2)
    for line in lines_t:
        tw = draw.textlength(line, font=font_t)
        x = title_box[0] + max(0, int((box_w - tw) // 2))
        draw.text((x, y), line, font=font_t, fill=title_rgb)
        y += line_h

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
