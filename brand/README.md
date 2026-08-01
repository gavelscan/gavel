# Brand assets

`gavel-mark-source.png` is the supplied artwork at its highest available
fidelity (1254×1254) and is the source of truth. Everything else here is
derived from it mechanically — nothing is redrawn.

| File | Use |
|---|---|
| `gavel-mark-source.png` | Master, as supplied (white background) |
| `gavel-mark.png` | Transparent background, original framing |
| `gavel-mark-tight.png` | Transparent, cropped to the ink — avatars, favicons |
| `gavel-mark-{512,256,128,64,48,32,16}.png` | Rasterised sizes from the tight crop |
| `favicon.ico` | Multi-resolution icon (16/32/48) |
| `preview.html` | Size and background test sheet |

Brass, read from the master's pixels: **`#B98D2B`**.
Slate `#0E1113`. Verdict colours: PASS `#2E7D4F`, FAIL `#B3372F`,
FLAG `#8A8F98`.

## Provenance note

The master was delivered as a `.svg`, but that file is a raster wrapped
in an SVG container (a single `<image>` element holding a base64 PNG),
not vector geometry. The embedded 1254×1254 bitmap was extracted and is
what lives here; the 1 MB wrapper is not committed, because it carries
no information the PNG does not.

## Known limitations

- **No true vector.** Scaling past 1254px softens the mark. That covers
  cards, web and icons comfortably; print or large-format merch would
  need a real vector redraw.
- **Thin bars close up below ~32px.** A small-size variant with fewer,
  thicker bars is still outstanding and should come from the brand
  owner, not be reconstructed here.
