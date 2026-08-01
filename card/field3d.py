"""LAUNCH FIELD in three dimensions, drawn from the record.

The site's hero already stands one bar per launch in a 3D field; this is
the same object rendered offline so a banner can carry it. It is data, not
ornament: every bar is a real launch and its colour is that launch's real
outcome, read from the same feed the site reads.

Two rules carried over from the hero, both learned the hard way:

  - All bars stand at the same height. An earlier version scaled height by
    outcome, which made 105 successful launches tower over 386 failures
    and read as "most launches succeed" — the exact opposite of the truth.
    Colour carries the outcome; the field carries the proportion.
  - Nothing is invented to fill the grid. If the record has 511 launches
    the field has 511 bars, and the last row is short.

No dependency beyond PIL. The projection is a pitch-and-yaw rotation with
a perspective divide, and bars are painted far to near.
"""

import json
import math
import os
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw

# The hero's palette, byte for byte (site/src/components/LaunchField.tsx).
TONE = {
    "unfilled": (74, 68, 58),     # drew no bids at all — the bulk
    "pool": (185, 141, 43),       # brass: migrated, liquidity exists
    "failed": (179, 55, 47),
    "live": (239, 232, 218),      # still inside its auction window
    "silent": (110, 115, 122),
}
ORDER = ["unfilled", "pool", "failed", "live", "silent"]


def _shade(rgb: Tuple[int, int, int], k: float) -> Tuple[int, int, int]:
    return tuple(max(0, min(255, int(c * k))) for c in rgb)


class _Cam:
    """Pitch, yaw, perspective divide. Enough for a field of boxes."""

    def __init__(self, pitch, yaw, dist, focal, cx, cy):
        self.cp, self.sp = math.cos(pitch), math.sin(pitch)
        self.cy_, self.sy_ = math.cos(yaw), math.sin(yaw)
        self.dist, self.focal, self.cx, self.cy = dist, focal, cx, cy

    def __call__(self, x, y, z):
        x, z = x * self.cy_ - z * self.sy_, x * self.sy_ + z * self.cy_
        y, z = y * self.cp - z * self.sp, y * self.sp + z * self.cp
        z += self.dist
        if z < 0.1:
            z = 0.1
        f = self.focal / z
        return (self.cx + x * f, self.cy - y * f), z


def states_from_feed(path: str = "data/feed.json") -> List[str]:
    """Outcomes in chain order, oldest first, so the field reads as time."""
    rows = json.load(open(path))["rows"]
    rows.sort(key=lambda r: r["block"])
    return [r["state"] for r in rows]


def render_field(
    im: Image.Image,
    states: List[str],
    box: Tuple[int, int, int, int],
    cols: int = 34,
    pitch: float = -0.52,
    yaw: float = -0.35,
    fade_left: bool = True,
) -> None:
    """Draw the field into `box` = (x, y, w, h) of an existing image."""
    bx, by, bw, bh = box
    n = len(states)
    rows = max(1, math.ceil(n / cols))

    layer = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    pitch_span = max(cols, rows)
    cam = _Cam(pitch, yaw, dist=pitch_span * 0.98, focal=bw * 0.72,
               cx=bw * 0.44, cy=bh * 0.42)

    s = 0.33          # bar half-width in grid units
    height = 2.6      # every bar, identical, on purpose

    # Painter's algorithm: build every bar with its depth, sort, then draw.
    prisms = []
    for i, state in enumerate(states):
        gx = (i % cols) - cols / 2 + 0.5
        gz = (i // cols) - rows / 2 + 0.5
        (_, _), depth = cam(gx, 0, gz)
        prisms.append((depth, gx, gz, state))
    prisms.sort(key=lambda p: -p[0])

    for depth, gx, gz, state in prisms:
        rgb = TONE.get(state, TONE["unfilled"])
        # Corners: top face then the two faces a camera at this yaw sees.
        p = {}
        for key, (dx, dz) in {
            "a": (-s, -s), "b": (s, -s), "c": (s, s), "d": (-s, s),
        }.items():
            p[key + "t"], _ = cam(gx + dx, height, gz + dz)
            p[key + "b"], _ = cam(gx + dx, 0, gz + dz)

        # Front-right and front-left walls, shaded so the form reads.
        d.polygon([p["bt"], p["ct"], p["cb"], p["bb"]], fill=_shade(rgb, 0.58))
        d.polygon([p["ct"], p["dt"], p["db"], p["cb"]], fill=_shade(rgb, 0.40))
        d.polygon([p["at"], p["bt"], p["ct"], p["dt"]], fill=_shade(rgb, 1.0))

    if fade_left:
        # The headline sits over the left of the banner, so the field has
        # to give way to it. A hard crop would look like a cut-out; a ramp
        # reads as the field receding into the room's shadow.
        mask = Image.new("L", (bw, bh), 255)
        md = ImageDraw.Draw(mask)
        ramp = int(bw * 0.66)
        for x in range(ramp):
            md.line([(x, 0), (x, bh)], fill=int(255 * (x / ramp) ** 2.6))
        a = layer.getchannel("A")
        layer.putalpha(Image.composite(a, Image.new("L", (bw, bh), 0), mask))

    im.alpha_composite(layer, (bx, by))


def legend(states: List[str]) -> List[Tuple[str, int, Tuple[int, int, int]]]:
    counts = {}
    for s in states:
        counts[s] = counts.get(s, 0) + 1
    return [(k, counts[k], TONE[k]) for k in ORDER if counts.get(k)]
