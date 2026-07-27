# Badge stock geometry

All numbers are inches on US Letter (8.5 × 11). `margin_top` / `margin_side` are
sheet edge → first cell. Cells are absolutely positioned from these, so the
layout is only ever as right as this table.

| key | stock | cell (w × h) | grid | per sheet | top margin | side margin | gutter x | proofed? |
|---|---|---|---|---|---|---|---|---|
| `74541` | Avery 74541 clip-style insert | 4.000 × 3.000 | 2 × 3 | 6 | 1.000 | 0.250 | 0 | **Yes** — printed 2026-07-23, LA Claude Conversation |
| `5395` | Avery 5395 / 8395 / 45395 adhesive | 3.375 × 2.333 | 2 × 4 | 8 | 0.833 | 0.750 | 0.250 | No — from Avery's published template |
| `cardstock` | Plain 65–80 lb, crop marks | 4.000 × 3.000 | 2 × 3 | 6 | 1.000 | 0.250 | 0 | No |

**Self-check any row:** `margin_side × 2 + cols × cell_w + (cols−1) × gutter_x` must equal 8.5.
`make_badges.py` runs this automatically and warns if it fails.

- 74541: `0.25 + 4 + 4 + 0.25 = 8.5` ✓ · `1 + 3+3+3 + 1 = 11` ✓
- 5395: `0.75 + 3.375 + 0.25 + 3.375 + 0.75 = 8.5` ✓ · `0.833 + 4×2.333 + 0.833 = 11` ✓

## Adding a stock

Add a dict entry to `STOCKS` in `scripts/make_badges.py`. Get the numbers from
the manufacturer's published template PDF, not from measuring a photo. Set
`verified=None` until a real sheet has been printed and checked, then record
what was proofed and when — that string is shown to the user on every run.

Type sizes scale linearly off the 4in-wide baseline (`k = cell_w / 4.0`), so a
new stock inherits a sane type scale automatically. Eyeball the proof anyway:
long names on small stock are where it breaks.

## Why Chrome

The proofed 74541 geometry was produced by Chrome headless. wkhtmltopdf and
WeasyPrint resolve `in` units and absolute positioning slightly differently and
shift the grid off the perforations. Do not substitute a different renderer
without re-proofing on physical stock.

## Fonts

- `Copernicus-Medium.woff2` — Anthropic's display serif. Correct for Claude
  Ambassador / Anthropic events. Embeds under the internal name
  "Copyright-Labor-and-Wait", which is expected and not a bug.
- `Lora-var.ttf` — SIL Open Font License. Use `--font lora` for non-Claude
  events, client work, or anything where Copernicus licensing does not apply.

Both embed as base64 in the HTML, so the file renders identically on any
machine and at any print shop.
