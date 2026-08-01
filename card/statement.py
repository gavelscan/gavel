"""Statement cards — the announcement template.

One fixed frame, reused for every post: same room, same lockup, same
corner mark. Only the sentence changes. That is the whole point — a
timeline reader should recognise a GAVEL card before they read a word of
it, and the way you earn that is by never redesigning it.

Deliberately shares _atmosphere(), the palette and the fonts with the
verdict card in card/render.py, so the marketing artifact and the product
artifact are visibly the same object. If those two ever drift, the cards
stop vouching for the product.

Trust rule carried over from the verdict card: every string on a
statement card is OURS. These are not generated from chain data and must
never interpolate an attacker-controlled symbol — if a card needs to name
a token, render it through card.render.safe_label first.
"""

import os
from typing import List, Optional

from PIL import Image, ImageDraw, ImageFont

from .render import (
    BONE,
    BRASS,
    FAINT,
    MUTED,
    W,
    H,
    _tracked,
    font_mono,
)

# The site's dark section, not the verdict card's. brand/README still
# records slate as #0E1113, which is blue-black; when the site moved to a
# parchment palette its dark end warmed to #17130e so it could sit beside
# aged paper without looking like a different product. The cards never
# followed, and side by side the two really do read as two brands.
SLATE = (23, 19, 14, 255)

# Display face. The site sets its headlines in Newsreader, a serif; the
# verdict card was set in DIN, a geometric sans. Same words, two voices.
# Nothing here is downloaded — these are faces already on the machine,
# chosen for how close they sit to Newsreader's transitional serif.
FACES = {
    "charter":   ("/System/Library/Fonts/Supplemental/Charter.ttc", 3),
    "baskerville": ("/System/Library/Fonts/Supplemental/Baskerville.ttc", 1),
    "iowan":     ("/System/Library/Fonts/Supplemental/Iowan Old Style.ttc", 1),
    "clarendon": ("/System/Library/Fonts/Supplemental/SuperClarendon.ttc", 5),
    "ptserif":   ("/System/Library/Fonts/Supplemental/PTSerif.ttc", 3),
    "din":       ("/System/Library/Fonts/Supplemental/DIN Alternate Bold.ttf", 0),
}
# Locked: Charter. It is a transitional serif like the site's Newsreader,
# and Carter drew it to survive coarse rendering — which is exactly what
# X's image pipeline does to a card before anyone sees it. The wider
# old-style faces (Iowan, PT Serif, Clarendon) wrap this deck's headlines
# onto a third line, and a third line breaks the bone/brass split that
# carries the sentence.
FACE = "charter"


def font_display(size: int):
    """The display face, resolved from FACE. Falls back to the verdict
    card's own resolver so a missing system font can never crash a
    render."""
    from .render import font_display as fallback
    path, index = FACES.get(FACE, FACES["charter"])
    if os.path.exists(path):
        try:
            return ImageFont.truetype(path, size, index=index)
        except OSError:
            pass
    return fallback(size)


def _room(w: int = W, h: int = H) -> Image.Image:
    """Slate lit by a brass horizon — the site's dark section, as a card.

    Built by upscaling a tiny gradient rather than stacking concentric
    ellipses the way the verdict card does. Same palette and the same
    light direction, but the ellipse stack leaves faint contour rings and
    a hard seam where its header shade stops, and on a card that is
    ninety percent flat background those artefacts are the first thing
    you see. Bicubic upscaling of a 80x45 field cannot band.
    """
    # A field ~80px on the long side; the ratio must follow the target so
    # the light does not stretch into an ellipse on a wider canvas.
    sw = 80
    sh = max(8, round(sw * h / w))
    small = Image.new("RGB", (sw, sh), SLATE[:3])
    px = small.load()
    # Light source below the bottom-right corner, matching .bg-slate-glow.
    lx, ly = sw * 0.80, sh * 1.18
    # Two radii, each tied to its own axis. Deriving the vertical reach
    # from the horizontal one works by accident at 16:9 and floods a 5:2
    # banner, because the same absolute reach covers far more of a
    # shallower frame.
    rx, ry = sw * 0.92, sh * 1.01
    for y in range(sh):
        for x in range(sw):
            dx, dy = (x - lx) / rx, (y - ly) / ry
            d = (dx * dx + dy * dy) ** 0.5
            k = max(0.0, 1.0 - d) ** 2.4
            r, g, b = SLATE[:3]
            px[x, y] = (
                min(255, int(r + 126 * k)),
                min(255, int(g + 94 * k)),
                min(255, int(b + 26 * k)),
            )
    return small.resize((w, h), Image.BICUBIC).convert("RGBA")

MARK = os.path.join(os.path.dirname(__file__), "..", "brand",
                    "gavel-mark-tight.png")

MARGIN = 96
DOMAIN = "gavelscan.xyz"


def _wrap(draw, text: str, font, max_w: int) -> List[str]:
    """Greedy wrap. Kept simple on purpose: a headline that needs clever
    typesetting is a headline that is too long."""
    words, lines, cur = text.split(), [], ""
    for word in words:
        trial = (cur + " " + word).strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


class CopyTooLong(Exception):
    """The sentence will not sit on two lines at a readable size."""


def _fit(draw, halves: List[str], max_w: int, max_h: int,
         start: int = 108, floor: int = 62):
    """Largest size at which each half sits on exactly one line.

    Not merely "fits in the box". The template's whole grammar is one bone
    line and one brass line: the colour break IS the sentence break. Let a
    half wrap and the reader sees three lines in two colours with the
    split landing mid-clause, which reads as a typesetting accident.

    So a half that will not fit on one line is a copy problem, and it is
    raised as one. Shrinking to fit would hide the defect in every card
    that follows.
    """
    size = start
    while size >= floor:
        f = font_display(size)
        line_h = int(size * 1.14)
        if (all(draw.textlength(t, font=f) <= max_w for t in halves)
                and len(halves) * line_h <= max_h):
            return f, list(halves), line_h
        size -= 2
    f = font_display(floor)
    over = [t for t in halves if draw.textlength(t, font=f) > max_w]
    raise CopyTooLong(
        "will not fit on one line even at %dpx: %s. Shorten it — the bone "
        "half and the brass half must each be a single line."
        % (floor, "; ".join('"%s"' % t for t in over)))


def _corner_mark(im: Image.Image, mark_path: str, opacity: int = 26,
                 scale: float = 0.72):
    """The mark, huge and nearly invisible, bleeding off the bottom-right.

    It is watermark-faint by design: it should register as texture at
    thumbnail size and only resolve into the logo when someone stops to
    look. A loud one competes with the sentence, which is the only thing
    on the card that matters.
    """
    if not os.path.exists(mark_path):
        return
    w, h = im.size
    mark = Image.open(mark_path).convert("RGBA")
    size = int(h * scale)
    mark = mark.resize((size, size), Image.LANCZOS)
    alpha = mark.getchannel("A").point(lambda a: int(a * opacity / 255))
    mark.putalpha(alpha)
    # Cropped by both edges, but far enough in that the ring and the bars
    # still read as the mark rather than as a stray arc.
    im.alpha_composite(mark, (w - int(size * 0.84), h - int(size * 0.80)))


def _domain_pill(d: ImageDraw.ImageDraw, x: int, y: int) -> None:
    f = font_mono(26)
    text_w = int(d.textlength(DOMAIN, font=f))
    pad_x, h = 26, 54
    w = text_w + pad_x * 2 + 30
    d.rounded_rectangle([x, y, x + w, y + h], radius=h // 2,
                        outline=(185, 141, 43, 110), width=2)
    # A small ring standing in for the globe glyph, which no system mono
    # font can be relied on to have.
    cy = y + h // 2
    d.ellipse([x + pad_x - 2, cy - 9, x + pad_x + 16, cy + 9],
              outline=(185, 141, 43, 150), width=2)
    d.line([x + pad_x - 2, cy, x + pad_x + 16, cy], fill=(185, 141, 43, 150), width=2)
    d.text((x + pad_x + 30, cy - 15), DOMAIN, font=f, fill=(206, 170, 92, 255))


def render_statement(
    headline: str,
    accent: str,
    subline: str,
    out_path: str,
    eyebrow: str = "LAUNCH VETTING · ROBINHOOD CHAIN",
    mark_path: Optional[str] = None,
) -> str:
    """Render one statement card.

    headline / accent are the two halves of the sentence: the first sits
    in bone, the second in brass. Splitting them is not decoration — the
    brass half is the claim, and putting the claim in the brand colour is
    how the card says which words to keep.
    """
    im = _room()
    d = ImageDraw.Draw(im)
    mark_path = mark_path or MARK
    _corner_mark(im, mark_path)

    # -- lockup ---------------------------------------------------------------
    y = 72
    x = MARGIN
    if os.path.exists(mark_path):
        m = Image.open(mark_path).convert("RGBA").resize((62, 62), Image.LANCZOS)
        im.alpha_composite(m, (x, y))
        x += 62 + 22
    d.text((x, y + 4), "GAVEL", font=font_display(40), fill=BONE)
    wm = d.textlength("GAVEL", font=font_display(40))
    d.text((x + wm, y + 4), "SCAN", font=font_display(40), fill=BRASS)
    _tracked(d, eyebrow, font_mono(19), x + 2, y + 48, FAINT, tr=2.2)

    # -- the sentence ---------------------------------------------------------
    body_top = 250
    body_bottom = H - MARGIN - 120
    f, laid, line_h = _fit(d, [headline, accent], W - MARGIN * 2,
                           body_bottom - body_top)
    ty = body_top
    for i, line in enumerate(laid):
        d.text((MARGIN, ty), line, font=f, fill=BRASS if i else BONE)
        ty += line_h

    if subline:
        fs = font_mono(27)
        sy = ty + 34
        for line in _wrap(d, subline, fs, int((W - MARGIN * 2) * 0.66)):
            d.text((MARGIN, sy), line, font=fs, fill=MUTED)
            sy += 40

    _domain_pill(d, MARGIN, H - MARGIN - 54)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    im.convert("RGB").save(out_path, "PNG", optimize=True)
    return out_path


# -- article banner -----------------------------------------------------------

BANNER_W, BANNER_H = 2000, 800  # 5:2


def render_banner(
    headline: str,
    accent: str,
    out_path: str,
    kicker: str = "GAVELSCAN · ROBINHOOD CHAIN",
    mark_path: Optional[str] = None,
) -> str:
    """The article header, 5:2.

    Same room, same face, same mark as the statement cards — a banner that
    looked like a different designer made it would undo the only thing the
    fixed template buys us. What changes is the proportion: at 5:2 there is
    no vertical room for a subline, so the sentence carries the whole
    frame and is set larger, and the lockup shrinks to a kicker rule so it
    does not crowd the headline in a band this shallow.
    """
    w, h = BANNER_W, BANNER_H
    im = _room(w, h)
    mark_path = mark_path or MARK
    # The field replaces the watermark mark: instead of the logo, the
    # banner's right side carries the record itself — one bar per launch,
    # colours from the same feed the site renders. Data as the ornament.
    try:
        from .field3d import render_field, states_from_feed
        render_field(im, states_from_feed(),
                     (int(w * 0.40), -int(h * 0.10), int(w * 0.66), int(h * 1.18)),
                     cols=30)
    except Exception:
        # No feed on disk (fresh clone): fall back to the quiet mark.
        _corner_mark(im, mark_path, opacity=24, scale=1.15)
    d = ImageDraw.Draw(im)
    margin = 104

    # Kicker: a rule, then tracked mono. No wordmark — at this height the
    # lockup and the headline fight, and the headline should win.
    ky = 92
    d.line([(margin, ky), (margin + 54, ky)], fill=BRASS, width=3)
    _tracked(d, kicker, font_mono(20), margin + 74, ky - 12, FAINT, tr=2.4)

    # The sentence, vertically centred in what is left.
    top, bottom = 190, h - 150
    # The sentence gets 72% of the width, not all of it. The field owns the
    # right of the frame, and a headline that runs into it forces a fight
    # between the two things the banner exists to show.
    f, laid, line_h = _fit(d, [headline, accent], int(w * 0.72) - margin,
                           bottom - top, start=132, floor=68)
    ty = top + max(0, (bottom - top - line_h * len(laid)) // 2)
    for i, line in enumerate(laid):
        d.text((margin, ty), line, font=f, fill=BRASS if i else BONE)
        ty += line_h

    _domain_pill(d, margin, h - 92 - 54)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    im.convert("RGB").save(out_path, "PNG", optimize=True)
    return out_path
