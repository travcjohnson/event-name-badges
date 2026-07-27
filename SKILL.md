---
name: event-name-badges
description: Use when making printable name tags, name badges, or badge inserts for an event from an attendee list (Luma export, RSVP CSV, Google Form, roster) — including Avery badge stock, blank write-on badges for walk-ups, and getting a print-ready PDF that lands on the perforations.
---

# Event Name Badges

Turns an attendee list into a print-ready badge PDF that lands on the perforations.
Brand assets travel with the skill, so there is nothing to hunt for.

**The failure this prevents:** a beautiful badge file printed on the wrong stock
at "Fit to Page", discovered at the venue an hour before doors.

## Deliverables

Every run produces, in the event's `badges/` folder:

| File | What it is |
|---|---|
| `badges-print.pdf` | **The file to print.** Named badges, padded to full sheets. |
| `badges-blank-print.pdf` | **Blank write-on badges.** Separate file so more can be run at the venue without reprinting names. Always produced. |
| `badges.html` / `badges-blank.html` | Sources. Re-render after any roster change. |
| `PROOF-badges-print-sheet1.png` | Sheet 1 proof to eyeball before printing. |
| `README.md` | Print settings + how to regenerate. Write this; the host prints from it. |

## Workflow

### 1. Confirm the four things, before generating anything

Ask together, in one message. Do not guess any of them.

1. **What stock is actually in hand?** The single biggest misprint cause. Ask for
   the Avery number on the box, or a photo of it. `--list-stocks` shows what is
   supported. Different stock = different geometry, not a scaling tweak.
   If they have no stock yet: recommend **Avery 74541** (4×3 clip-style, 6/sheet)
   — it is the proofed layout, and clip badges beat adhesive for a 2–4 hour event
   because they survive being taken off and put back on.
2. **Where is the attendee list, and is it final?** Luma export, RSVP CSV, form
   dump. Ask when it was pulled — a list from three days ago is a stale list.
   If a Luma export has an approval/status column, ask whether to filter to
   approved only (`--only-approved`).
3. **Event title, city, and date.** All three are required and all three print on
   every badge — title top-left, `City · Date` bottom-left. Get the exact strings;
   the badge is a keepsake and a conversation starter, so "Claude Conversation /
   Los Angeles · Jul 24" is the point, not decoration. The script refuses to run
   without them rather than printing a blank line. ISO dates (`2026-07-24`) are
   auto-formatted to `Jul 24`; any other string passes through verbatim.
4. **How many blanks?** Default: enough to finish the last sheet, plus one full
   spare sheet as a standalone file. Rule of thumb for walk-up-friendly events:
   10–15% of headcount.

**Do not ask about table numbers by default.** Assigned seating is uncommon.
Only offer it if the event is explicitly seated (dinner, structured discussion
groups) — see the optional section below.

### 2. Generate

```bash
S=~/.claude/skills/event-name-badges
python3 $S/scripts/make_badges.py \
  --roster path/to/attendees.csv \
  --stock 74541 \
  --event "Claude Conversation" \
  --city "Los Angeles" \
  --date 2026-07-24 \
  --blanks 8 \
  --blank-sheets 1 \
  --only-approved \
  --outdir badges/
```

The script auto-detects name columns across Luma / Forms / hand-built CSVs
(`name`, `full name`, `first_name`+`last_name`, etc.). If it cannot find one it
says so and lists the headers it saw — rename a column rather than reshaping the file.

Useful flags: `--font lora` (non-Claude events — see Fonts below), `--accent "#D97757"`,
`--no-logo`, `--cut-guides`, `--fill-sheet`, `--stock 5395|cardstock`.

### 3. Read the report back to the user

The generator prints a confirmation block. **Relay it — this is the check-in
moment, not a log.** It opens with the exact title and `City · Date` strings that
will appear on every badge (check these against the invite, not against memory),
then reports named count, skipped rows, blanks (and how many were padding),
sheet count, duplicate names, and names too long for the cell.

Resolve every `!!` line before rendering. A duplicate name usually means the
roster has a double registration; a long name means eyeball that badge on the proof.

### 4. Render and verify

```bash
bash $S/scripts/render_pdf.sh badges/badges.html
bash $S/scripts/render_pdf.sh badges/badges-blank.html badges/badges-blank-print.pdf
python3 $S/scripts/verify_print.py badges/badges-print.pdf --stock 74541 \
  --expect-named 69 --event-label "Claude Conversation"
```

`verify_print.py` reads the actual PDF and checks page size is true Letter, page
count matches, and **every font is embedded** — a non-embedded font silently
reflows at a print shop and ruins the sheet.

Then **look at the proof PNG** with Read. Automated checks do not catch a name
colliding with the logo.

### 5. Hand off

Show Travis the proof (`cmux browser open "file://…" --focus false`), state the
file path, sheet count, and stock. Write the `README.md` with print settings.

## The print settings that matter

Put these verbatim in the README and in the handoff message:

1. Load the badge stock in the correct tray, correct face-up orientation.
2. Print at **100% / "Actual Size"** — never "Fit to Page" or "Scale to Fit".
   Fit-to-page shrinks ~4% and walks every badge off the perforations.
3. **Single-sided**, US Letter, color.
4. **Run one plain-paper test sheet first.** Hold it against a blank badge sheet
   up to a light and confirm the cells land inside the perforations. Do this
   even on proofed stock — printer tray calibration varies.
5. Then print the real sheets, separate on the perforations, drop into holders.

Step 4 is not optional and not a nicety. It is the difference between a
misprint costing one sheet of paper and costing the whole box.

## Optional: table numbers (seated events only)

Only if the event has assigned seating. Pass a CSV with `name,table`:

```bash
python3 $S/scripts/make_badges.py ... --tables path/to/table-assignments.csv
```

Badges then sort by table (so they can be laid out table by table) and print
the number as a large serif numeral bottom-right. The report gains a per-table
breakdown and flags guests with no table plus assignment names missing from the
roster. Add `--tables` to `verify_print.py` so it reads them back out of the PDF.

Pair with table tents so guests can find the table the badge names.

## Fonts and logo

Both fonts and the Claude spark SVG ship in `assets/` and embed as base64 — the
HTML is self-contained and renders identically anywhere.

- **Copernicus** (default) — Anthropic's display serif. Correct for Claude
  Ambassador and Anthropic events. Embeds under the internal name
  "Copyright-Labor-and-Wait"; that is expected.
- **Lora** (`--font lora`) — SIL Open Font License. Use for non-Claude events,
  client work, or anywhere Copernicus licensing does not apply.

Never redraw the spark. Recolor it with `--accent` or drop it with `--no-logo`.

## Common mistakes

| Mistake | Consequence | Fix |
|---|---|---|
| Assuming the stock | Whole box misprints | Ask for the Avery number first |
| "Fit to Page" | Every badge off the perfs by ~4% | 100% / Actual Size |
| Skipping the paper test sheet | Tray offset ruins the real stock | Always test first |
| Building from a stale export | Missing walk-ins, wrong names | Confirm when the list was pulled |
| Wrong city or date on the badge | 78 keepsakes with the wrong event on them | Check title/city/date against the invite |
| Non-embedded font | Reflows at the print shop | `verify_print.py` catches it |
| No blanks | Walk-ups have no badge | Always print the spare blank sheet |
| Table numbers by default | Clutter on an unseated event | Only for assigned seating |
| Trusting counts without opening the PDF | Wrong file goes to print | Read the proof PNG |

## Reference

- `reference/stock-geometry.md` — exact geometry per stock, what is proofed vs
  derived, how to add a stock, why Chrome is the required renderer.
- Worked example: `~/AI_HOME/Claude_Ambassador/events/la-claude-conversation-2026-07/badges/`
  — 69 named + 9 blank on 74541, printed 2026-07-23.
