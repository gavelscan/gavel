"""Verdict card renderer — the shareable artifact.

Trust rules, same discipline as the judge:

- Every string on the card is OURS (templates, finding details written by
  gavel/checks.py) or a SANITIZED, boxed identifier. Token and currency
  names are attacker-controlled; they are stripped of control/bidi
  characters, length-capped, and rendered in fixed data type — never as
  display copy. The big stamp is always ours.
- Every number comes from the factsheet. The model contributes only
  enums, and enums are rendered through our label tables.
- Colours are the locked brand; verdict colours appear only on the stamp
  and the state line.
"""

import os
import unicodedata
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

W, H = 1600, 900

SLATE = (14, 17, 19, 255)
SLATE_DEEP = (10, 13, 15, 255)
BONE = (236, 232, 223, 255)
MUTED = (139, 144, 152, 255)
FAINT = (95, 101, 108, 255)
BRASS = (185, 141, 43, 255)
BRASS_DIM = (185, 141, 43, 90)
HAIR = (42, 46, 51, 255)

VERDICT_TONE = {
    "PASS": (46, 125, 79, 255),
    "FLAG": (138, 143, 152, 255),
    "FAIL": (179, 55, 47, 255),
}

ASSESSMENT_LABEL = {
    "none": "no hook",
    "benign": "hook: judged benign",
    "suspicious": "hook: suspicious",
    "hostile": "hook: hostile",
    "unknown": "unresolved",
    "native_eth": "native ETH",
    "verified_official": "verified official",
    "plausible": "plausible",
    "unverified": "unverified",
    "likely_impostor": "likely impostor",
    "contract": "contract",
    "delegated_wallet": "wallet (EIP-7702)",
    "established_eoa": "EOA with history",
    "fresh_eoa": "fresh EOA",
}

_FONT_DIRS = [
    "/System/Library/Fonts/Supplemental",
    "/System/Library/Fonts",
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/truetype/jetbrains-mono",
]


def _font(names: List[str], size: int) -> ImageFont.FreeTypeFont:
    for name in names:
        for d in _FONT_DIRS:
            path = os.path.join(d, name)
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)  # last resort, never crash the daemon


def font_display(size: int):
    return _font(["DIN Alternate Bold.ttf", "DejaVuSans-Bold.ttf"], size)


def font_mono(size: int):
    return _font(["SFNSMono.ttf", "Menlo.ttc", "JetBrainsMono-Regular.ttf",
                  "DejaVuSansMono.ttf"], size)


# --- untrusted strings -------------------------------------------------------

def safe_label(value: Optional[str], max_len: int = 26) -> str:
    """Sanitize an attacker-controlled identifier for display.

    Strips every control/format codepoint (kills bidi overrides and
    zero-width tricks), collapses whitespace, caps length. The result is
    still untrusted CONTENT — callers must render it in data type inside
    our own framing, never as headline copy.
    """
    if not value:
        return "?"
    cleaned = "".join(
        ch if not unicodedata.category(ch).startswith("C") and ch.isprintable()
        else " "
        for ch in value
    )
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 1] + "…"
    return cleaned or "?"


def short_addr(addr: Optional[str]) -> str:
    if not addr or len(addr) < 12:
        return addr or "?"
    return addr[:6] + "…" + addr[-4:]


def fmt_pct(x: Optional[float]) -> str:
    if x is None:
        return "—"
    return ("%.2f" % (x * 100)).rstrip("0").rstrip(".") + "%"


def fmt_int(n: int) -> str:
    return f"{n:,}"


# --- drawing helpers ---------------------------------------------------------

def _atmosphere() -> Image.Image:
    """Slate with a brass horizon glow — same room as the site hero."""
    im = Image.new("RGBA", (W, H), SLATE)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)
    cx, cy, r = W * 0.78, H * 1.25, W * 0.75
    for i in range(46, 0, -1):
        alpha = int(0.55 * i)
        g.ellipse(
            [cx - r * i / 46, cy - r * i / 46 * 0.62,
             cx + r * i / 46, cy + r * i / 46 * 0.62],
            fill=(185, 141, 43, alpha),
        )
    im.alpha_composite(glow)
    d = ImageDraw.Draw(im)
    # top fade to deep slate so the header sits in shadow
    for y in range(0, 130):
        a = int(120 * (1 - y / 130))
        d.line([(0, y), (W, y)], fill=(10, 13, 15, a))
    return im


def _stamp(verdict: str) -> Image.Image:
    """The rubber stamp: our voice, and the only loud thing on the card."""
    tone = VERDICT_TONE[verdict]
    pad = 60
    f = font_display(150)
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    tw = int(probe.textlength(verdict, font=f))
    w, h = tw + pad * 2, 150 + pad + 10
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w - 1, h - 1], outline=tone, width=7)
    d.rectangle([14, 14, w - 15, h - 15], outline=tone, width=2)
    d.text((pad, pad // 2 + 6), verdict, font=f, fill=tone)
    return im.rotate(6, expand=True, resample=Image.BICUBIC)


def _tracked(d, text, f, x, y, fill, tr=3):
    for ch in text:
        d.text((x, y), ch, font=f, fill=fill)
        x += d.textlength(ch, font=f) + tr
    return x


# --- the card ----------------------------------------------------------------

def render_card(
    verdict: dict,
    factsheet: dict,
    token_symbol: Optional[str],
    currency_symbol: Optional[str],
    out_path: str,
    mark_path: Optional[str] = None,
) -> str:
    """Render one verdict card PNG. Returns out_path."""
    v = verdict["verdict"]
    if v not in VERDICT_TONE:  # closed domain, enforced again at the edge
        raise ValueError("unknown verdict %r" % v)
    p = factsheet["launch"]["params"]

    im = _atmosphere()
    d = ImageDraw.Draw(im)

    margin = 84
    # header ------------------------------------------------------------------
    y = 64
    x = margin
    if mark_path and os.path.exists(mark_path):
        mark = Image.open(mark_path).convert("RGBA").resize((56, 56), Image.LANCZOS)
        im.alpha_composite(mark, (x, y - 8))
        x += 76
    _tracked(d, "GAVELSCAN", font_mono(21), x, y + 2, BRASS, 6)
    right_label = "ROBINHOOD CHAIN · LIQUIDITY LAUNCHER"
    f_r = font_mono(17)
    rw = sum(d.textlength(c, font=f_r) + 3 for c in right_label)
    _tracked(d, right_label, f_r, W - margin - rw, y + 5, FAINT, 3)
    d.line([(margin, y + 62), (W - margin, y + 62)], fill=HAIR, width=1)

    # token identity — sanitized, boxed, data type ------------------------------
    y = 190
    d.text((margin, y), "token", font=font_mono(19), fill=FAINT)
    token_line = safe_label(token_symbol) if token_symbol else short_addr(p["token"])
    d.text((margin, y + 34), token_line, font=font_display(84), fill=BONE)
    cur_line = "auction priced in %s" % (
        safe_label(currency_symbol) if currency_symbol else short_addr(p["currency"])
    )
    d.text((margin, y + 142), cur_line, font=font_mono(24), fill=MUTED)

    # stamp ---------------------------------------------------------------------
    stamp = _stamp(v)
    im.alpha_composite(stamp, (W - margin - stamp.width, 160))
    d = ImageDraw.Draw(im)

    # facts grid — figures from the factsheet only ------------------------------
    y = 420
    d.line([(margin, y - 24), (W - margin, y - 24)], fill=HAIR, width=1)
    sched = p["lpAllocationSchedule"]
    terminal = sched[-1]["rate"] / 1e7 if sched else None
    cur_assess = ASSESSMENT_LABEL.get(verdict["currency_assessment"], "unresolved")
    rec_assess = ASSESSMENT_LABEL.get(verdict["recipient_assessment"], "unresolved")
    hook_assess = ASSESSMENT_LABEL.get(verdict["hook_assessment"], "unresolved")

    facts: List[Tuple[str, str]] = [
        ("currency", cur_assess),
        ("recipient", "%s · %s" % (short_addr(p["recipient"]), rec_assess)),
        ("LP reserve", "%s of supply" % fmt_pct(factsheet.get("reserved_lp_ratio"))),
        ("raise → LP", "%s at the top bracket" % fmt_pct(terminal)),
        ("hook", hook_assess),
        ("migration", "block %s" % fmt_int(p["migrationBlock"])),
    ]
    col_w = (W - 2 * margin) // 3
    f_k, f_v = font_mono(18), font_mono(25)
    for i, (k, val) in enumerate(facts):
        cx = margin + (i % 3) * col_w
        cy = y + (i // 3) * 108
        d.text((cx, cy), k, font=f_k, fill=BRASS)
        d.text((cx, cy + 32), val, font=f_v, fill=BONE)

    # findings — our own deterministic detail strings ---------------------------
    y = 660
    d.line([(margin, y - 20), (W - margin, y - 20)], fill=HAIR, width=1)
    shown = 0
    details = {name: detail for name, _sev, detail in factsheet["findings"]}
    for key in verdict.get("key_findings", []):
        if key in details and shown < 2:
            d.text((margin, y + shown * 42), "· " + details[key][:96],
                   font=font_mono(22), fill=MUTED)
            shown += 1
    if shown == 0:
        d.text((margin, y), "· no deterministic findings — see full factsheet",
               font=font_mono(22), fill=MUTED)
        shown = 1

    if verdict.get("manipulation_detected"):
        d.text((margin, y + shown * 42), "· manipulation signals present",
               font=font_mono(22), fill=BRASS)

    # footer --------------------------------------------------------------------
    fy = H - 74
    d.line([(margin, fy - 26), (W - margin, fy - 26)], fill=HAIR, width=1)
    d.text((margin, fy), "tx %s" % short_addr(factsheet["launch"]["tx"]),
           font=font_mono(19), fill=FAINT)
    site = "gavelscan.xyz"
    f_s = font_mono(19)
    d.text((W - margin - d.textlength(site, font=f_s), fy), site,
           font=f_s, fill=BRASS)

    im.convert("RGB").save(out_path, "PNG")
    return out_path
