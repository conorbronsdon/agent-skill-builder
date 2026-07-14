#!/usr/bin/env python3
"""Deterministic terminal-style demo GIF renderer (Pillow, no external tools).

This is the fallback renderer used when `vhs`/`ttyd`/`ffmpeg` are unavailable.
The CANONICAL regeneration path is `demo.tape` (vhs) — see this repo's demo.tape.
This script exists so the GIF can be rebuilt reproducibly with only Pillow +
the DejaVu fonts, and so the frame content stays committed and reviewable.

Usage:
    python3 scripts/render_demo.py            # -> docs/demo.gif
    python3 scripts/render_demo.py out.gif

Frames are defined in scripts/demo_frames.py (FRAMES, TITLE). See that file for
the step format. Colors, sizing, and pacing are configured below.
"""
from __future__ import annotations

import os
import sys

from PIL import Image, ImageDraw, ImageFont

# --- Terminal look -----------------------------------------------------------
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
FONT_SIZE = 18
COLS = 100
MAX_ROWS = 26
PAD_X = 22
TITLE_H = 36
PAD_TOP = 12
PAD_BOTTOM = 14
LINE_H = 26

COLORS = {
    "bg": (26, 26, 46),          # #1a1a2e
    "titlebar": (18, 18, 38),
    "fg": (214, 214, 224),
    "dim": (122, 122, 144),
    "prompt": (110, 231, 160),   # green
    "cmd": (240, 240, 245),
    "green": (110, 231, 160),
    "red": (255, 107, 107),
    "yellow": (255, 203, 107),
    "cyan": (87, 199, 255),
    "magenta": (199, 146, 234),
    "blue": (130, 170, 255),
    "white": (255, 255, 255),
    "cursor": (110, 231, 160),
}
DOTS = [(255, 95, 86), (255, 189, 46), (39, 201, 63)]

PROMPT = "❯"  # ❯

# --- Pacing (ms) -------------------------------------------------------------
TYPE_MS = 45          # per typing frame
TYPE_CHUNK = 2        # chars typed per frame
CMD_HOLD_MS = 450     # pause after a command finishes typing, before output
DEFAULT_HOLD_MS = 1500

FONT = ImageFont.truetype(FONT_PATH, FONT_SIZE)
FONTB = ImageFont.truetype(FONT_BOLD, FONT_SIZE)
CHAR_W = FONT.getlength("M")


def _seg(line):
    """Normalize a line into a list of (text, colorkey) segments."""
    if isinstance(line, str):
        return [(line, "fg")]
    if isinstance(line, tuple) and len(line) == 2 and isinstance(line[0], str):
        return [line]
    # already a list of segments
    return list(line)


def _wrap(segs, width=COLS, indent=4):
    """Soft-wrap a segment list to `width` cols (terminal-style), preserving
    per-char color. Continuation lines get a hanging indent."""
    chars = [(ch, ck) for text, ck in segs for ch in text]
    if len(chars) <= width:
        return [segs]
    out, cur = [], []
    limit = width
    while chars:
        if len(chars) <= limit:
            cur.extend(chars)
            chars = []
            break
        # find break point: last space within limit
        brk = None
        for i in range(min(limit, len(chars)) - 1, max(0, limit - 24), -1):
            if chars[i][0] == " ":
                brk = i
                break
        if brk is None:
            brk = limit
        cur.extend(chars[:brk])
        out.append(cur)
        # skip the break space
        rest = chars[brk:]
        while rest and rest[0][0] == " ":
            rest = rest[1:]
        chars = [(" ", "fg")] * indent + rest
        cur = []
        limit = width
    if cur:
        out.append(cur)
    # recombine each row's chars into segments
    rows = []
    for row in out:
        segs2, buf, cck = [], "", None
        for ch, ck in row:
            if ck != cck and buf:
                segs2.append((buf, cck))
                buf = ""
            buf, cck = buf + ch, ck
        if buf:
            segs2.append((buf, cck))
        rows.append(segs2)
    return rows


class Screen:
    """A mutable scrollback the steps mutate; emits (lines, cursor, dur) frames."""

    def __init__(self):
        self.lines = []          # committed lines (list of segment-lists)
        self.frames = []         # (lines_copy, cursor_pos_or_None, dur_ms)

    def _emit(self, cursor=None, dur=DEFAULT_HOLD_MS):
        self.frames.append(([list(l) for l in self.lines], cursor, dur))

    def type_cmd(self, text):
        # append a new prompt line and type into it
        base = [(PROMPT + " ", "prompt")]
        self.lines.append(list(base))
        idx = len(self.lines) - 1
        n = len(text)
        i = 0
        while i < n:
            i = min(n, i + TYPE_CHUNK)
            self.lines[idx] = base + [(text[:i], "cmd")]
            col = 2 + i
            self._emit(cursor=(idx, col), dur=TYPE_MS)
        # settle: solid line + short hold with cursor
        self.lines[idx] = base + [(text, "cmd")]
        self._emit(cursor=(idx, 2 + n), dur=CMD_HOLD_MS)

    def out(self, lines, hold=DEFAULT_HOLD_MS):
        for l in lines:
            for row in _wrap(_seg(l)):
                self.lines.append(row)
        self._emit(cursor=None, dur=hold)

    def hold(self, dur=DEFAULT_HOLD_MS):
        self._emit(cursor=None, dur=dur)

    def clear(self):
        self.lines = []


def build_frames(steps):
    s = Screen()
    for st in steps:
        kind = st[0]
        if kind == "cmd":
            s.type_cmd(st[1])
        elif kind == "out":
            hold = st[2] if len(st) > 2 else DEFAULT_HOLD_MS
            s.out(st[1], hold)
        elif kind == "hold":
            s.hold(st[1])
        elif kind == "clear":
            s.clear()
        else:
            raise ValueError(f"unknown step: {kind}")
    return s.frames


def _term_rows(frames):
    m = 1
    for lines, _, _ in frames:
        m = max(m, len(lines))
    return min(max(m, 3), MAX_ROWS)


def render_rgb(lines, cursor, rows, title):
    width = int(PAD_X * 2 + CHAR_W * COLS)
    height = int(TITLE_H + PAD_TOP + rows * LINE_H + PAD_BOTTOM)
    img = Image.new("RGB", (width, height), COLORS["bg"])
    d = ImageDraw.Draw(img)
    # title bar
    d.rectangle([0, 0, width, TITLE_H], fill=COLORS["titlebar"])
    for i, c in enumerate(DOTS):
        cx = PAD_X + i * 22
        d.ellipse([cx, TITLE_H // 2 - 6, cx + 12, TITLE_H // 2 + 6], fill=c)
    tw = FONT.getlength(title)
    d.text(((width - tw) / 2, (TITLE_H - FONT_SIZE) / 2 - 2), title,
           font=FONT, fill=COLORS["dim"])
    # content: show last `rows` lines
    visible = lines[-rows:]
    y = TITLE_H + PAD_TOP
    base_index = len(lines) - len(visible)
    for ri, segs in enumerate(visible):
        x = PAD_X
        for text, ckey in segs:
            font = FONTB if ckey in ("prompt",) else FONT
            d.text((x, y), text, font=font, fill=COLORS.get(ckey, COLORS["fg"]))
            x += FONT.getlength(text)
        # cursor block
        if cursor is not None and cursor[0] == base_index + ri:
            cx = PAD_X + cursor[1] * CHAR_W
            d.rectangle([cx, y + 2, cx + CHAR_W - 1, y + FONT_SIZE + 4],
                        fill=COLORS["cursor"])
        y += LINE_H
    return img


def _calibration(rows, title):
    """A frame containing every color so the global palette captures all ramps."""
    lines = []
    for key in COLORS:
        if key in ("bg", "titlebar", "cursor"):
            continue
        lines.append([(f"{key}: PASS FAIL DRIFTED file.py:42 {PROMPT} 0123", key)])
    return render_rgb(lines, (0, 40), rows, title)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, here)
    import demo_frames

    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(here), "docs", "demo.gif")
    if os.path.dirname(out):
        os.makedirs(os.path.dirname(out), exist_ok=True)

    frames = build_frames(demo_frames.FRAMES)
    rows = _term_rows(frames)
    title = getattr(demo_frames, "TITLE", "demo")

    rgb = [render_rgb(lines, cur, rows, title) for lines, cur, _ in frames]
    durs = [dur for _, _, dur in frames]

    # global palette from a calibration swatch (captures every color's AA ramp)
    master = _calibration(rows, title).quantize(
        colors=64, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = [f.quantize(palette=master, dither=Image.Dither.NONE) for f in rgb]

    pal[0].save(out, save_all=True, append_images=pal[1:], loop=0,
                duration=durs, disposal=2, optimize=True)
    size = os.path.getsize(out)
    print(f"wrote {out}")
    print(f"frames={len(pal)} size={size} bytes ({size/1024/1024:.2f} MB) "
          f"dims={rgb[0].size[0]}x{rgb[0].size[1]}")
    if size > 8 * 1024 * 1024:
        print("WARNING: over 8 MB budget", file=sys.stderr)


if __name__ == "__main__":
    main()
