#!/usr/bin/env python3
"""
make_badges.py — roster CSV -> print-ready badge HTML (then render_pdf.sh -> PDF).

Absolute-positioned cells computed from real stock geometry, so the badges land
on the perforations instead of "close enough". Fonts and the spark logo are
base64-embedded, so the HTML is portable and Chrome's file:// sandbox can't
break it.

Example:
  python3 make_badges.py \
      --roster ../data/roster-approved.csv \
      --stock 74541 \
      --event "Claude Conversation" \
      --location "Los Angeles · Jul 24" \
      --tables ../data/table-assignments.csv \
      --blanks 9 \
      --outdir .

Run with --list-stocks to see supported badge stock.
"""
import argparse, base64, csv, html, os, re, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(os.path.dirname(HERE), "assets")

# --------------------------------------------------------------------------
# Stock geometry. All values in INCHES on US Letter (8.5 x 11).
#   margin_top / margin_side = distance from sheet edge to the FIRST cell
#   gutter_x / gutter_y      = gap between cells
#   verified                 = has this geometry been printed and checked
#                              against physical stock?
# Self-check: margin_side*2 + cols*cell_w + (cols-1)*gutter_x should == 8.5
# --------------------------------------------------------------------------
STOCKS = {
    "74541": dict(
        label="Avery 74541 clip-style name badge insert (4\" x 3\", 6/sheet)",
        cell_w=4.0, cell_h=3.0, cols=2, rows=3,
        margin_top=1.0, margin_side=0.25, gutter_x=0.0, gutter_y=0.0,
        crop_marks=False,
        verified="printed 2026-07-23, LA Claude Conversation, landed clean on perfs",
    ),
    "5395": dict(
        label="Avery 5395 / 8395 / 45395 adhesive name badge (3-3/8\" x 2-1/3\", 8/sheet)",
        cell_w=3.375, cell_h=2.3333, cols=2, rows=4,
        margin_top=0.8333, margin_side=0.75, gutter_x=0.25, gutter_y=0.0,
        crop_marks=False,
        verified=None,  # derived from Avery published template, NOT yet proofed
    ),
    "cardstock": dict(
        label="Plain 65-80lb cardstock fallback, 4\" x 3\" with crop marks, 6/sheet",
        cell_w=4.0, cell_h=3.0, cols=2, rows=3,
        margin_top=1.0, margin_side=0.25, gutter_x=0.0, gutter_y=0.0,
        crop_marks=True,
        verified=None,
    ),
}

# Roster header aliases -> canonical field. Covers Luma exports, Google Forms,
# and hand-built rosters.
ALIASES = {
    "name": ["name", "full name", "full_name", "attendee", "guest", "guest name"],
    "first": ["first_name", "first name", "firstname", "given name"],
    "last": ["last_name", "last name", "lastname", "surname", "family name"],
    "status": ["approval_status", "approval status", "status", "rsvp status",
               "registration status", "ticket status"],
    "email": ["email", "email address", "e-mail"],
}
APPROVED_VALUES = {"approved", "going", "yes", "attending", "confirmed", "accepted"}


def fmt_date(d):
    """ISO dates become 'Jul 24'. Anything else is passed through verbatim."""
    d = (d or "").strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", d)
    if not m:
        return d
    from datetime import date
    y, mo, dy = (int(x) for x in m.groups())
    return date(y, mo, dy).strftime("%b %-d")


def norm(s):
    return re.sub(r"[^a-z ]", " ", (s or "").strip().lower()).strip()


def map_columns(fieldnames):
    """Return {canonical: actual_header} for whatever the CSV happens to use."""
    found = {}
    lookup = {norm(f): f for f in fieldnames}
    for canon, options in ALIASES.items():
        for opt in options:
            if opt in lookup:
                found[canon] = lookup[opt]
                break
    return found


def split_name(full, first, last):
    first = (first or "").strip()
    last = (last or "").strip()
    if not first:
        parts = (full or "").strip().split()
        first = parts[0] if parts else (full or "").strip()
        last = " ".join(parts[1:]) if len(parts) > 1 else ""
    return first, last


def load_roster(path, only_approved):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        sys.exit(f"ERROR: {path} has no rows.")
    cols = map_columns(rows[0].keys())
    if "name" not in cols and "first" not in cols:
        sys.exit(f"ERROR: no name column in {path}. Headers: {list(rows[0].keys())}\n"
                 "Rename a column to 'name' (or 'first_name'/'last_name') and re-run.")
    people, skipped = [], 0
    for r in rows:
        if only_approved and "status" in cols:
            if norm(r.get(cols["status"], "")) not in APPROVED_VALUES:
                skipped += 1
                continue
        full = r.get(cols.get("name", ""), "") or ""
        first, last = split_name(full, r.get(cols.get("first", "")), r.get(cols.get("last", "")))
        if not first:
            skipped += 1
            continue
        key = (full.strip() or f"{first} {last}".strip())
        people.append({"key": key, "first": first, "last": last, "table": ""})
    return people, skipped, cols


def apply_tables(people, path):
    """Attach table numbers by exact name match; report both directions of mismatch."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    cols = map_columns(rows[0].keys())
    namecol = cols.get("name") or list(rows[0].keys())[0]
    tablecol = next((f for f in rows[0].keys() if norm(f) in ("table", "table number", "table no", "seat")), None)
    if not tablecol:
        sys.exit(f"ERROR: no 'table' column in {path}. Headers: {list(rows[0].keys())}")
    assign = {r[namecol].strip(): str(r[tablecol]).strip() for r in rows if r.get(namecol)}
    by_name = {p["key"]: p for p in people}
    unmatched_assign = [n for n in assign if n not in by_name]
    for name, t in assign.items():
        if name in by_name:
            by_name[name]["table"] = t
    no_table = [p["key"] for p in people if not p["table"]]
    return unmatched_assign, no_table


def build(args):
    stock = STOCKS[args.stock]
    per_sheet = stock["cols"] * stock["rows"]

    # --- geometry sanity (catches a bad custom stock before it wastes paper)
    w_used = stock["margin_side"] * 2 + stock["cols"] * stock["cell_w"] \
        + (stock["cols"] - 1) * stock["gutter_x"]
    h_used = stock["margin_top"] * 2 + stock["rows"] * stock["cell_h"] \
        + (stock["rows"] - 1) * stock["gutter_y"]
    if abs(w_used - 8.5) > 0.02:
        print(f"WARNING: columns span {w_used:.3f}in, expected 8.500in on Letter.")
    if h_used - 11.0 > 0.02:
        print(f"WARNING: rows span {h_used:.3f}in, taller than 11.000in Letter.")

    people, skipped, cols = load_roster(args.roster, args.only_approved)
    people.sort(key=lambda p: p["key"].lower())

    unmatched_assign, no_table = [], []
    if args.tables:
        unmatched_assign, no_table = apply_tables(people, args.tables)
        people.sort(key=lambda p: (int(p["table"]) if p["table"].isdigit() else 9999,
                                   p["key"].lower()))

    n_named = len(people)
    if args.fill_sheet:
        n_blank = (-n_named) % per_sheet
        if n_blank == 0 and args.blanks:
            n_blank = args.blanks
    else:
        n_blank = args.blanks
        n_blank += (-(n_named + n_blank)) % per_sheet  # never print a ragged sheet

    # --- brand assets, embedded
    spark = open(os.path.join(ASSETS, "Claude-Spark-Logo.svg")).read()
    spark = spark.replace("<svg ", '<svg role="img" aria-label="Claude Spark Logo" ', 1)
    if args.accent:
        spark = re.sub(r'fill="rgb\([^)]*\)"', f'fill="{args.accent}"', spark)
    if args.no_logo:
        spark = ""
    fontfile = "Copernicus-Medium.woff2" if args.font == "copernicus" else "Lora-var.ttf"
    fmt = "woff2" if args.font == "copernicus" else "truetype"
    fb64 = base64.b64encode(open(os.path.join(ASSETS, fontfile), "rb").read()).decode()

    # --- type scale: tuned at 4in cell width, scaled linearly for other stock
    k = stock["cell_w"] / 4.0

    def pt(v):
        return round(v * k, 1)

    def name_class(first):
        n = len(first)
        return "xl" if n <= 6 else "lg" if n <= 9 else "md" if n <= 12 else "sm"

    ev = html.escape(args.event)
    loc = html.escape(args.location)

    def cell(inner, i, j):
        left = stock["margin_side"] + i * (stock["cell_w"] + stock["gutter_x"])
        top = stock["margin_top"] + j * (stock["cell_h"] + stock["gutter_y"])
        marks = ""
        if stock["crop_marks"]:
            marks = ('<span class="cm tl"></span><span class="cm tr"></span>'
                     '<span class="cm bl"></span><span class="cm br"></span>')
        return (f'<div class="badge" style="left:{left}in;top:{top}in">{marks}{inner}</div>')

    def named(p):
        first = html.escape(p["first"])
        last = f'<div class="last">{html.escape(p["last"])}</div>' if p["last"] else ""
        tnum = (f'<span class="tnum">{html.escape(p["table"])}</span>'
                if p["table"] else '<span class="tnum">&nbsp;</span>')
        return (f'<div class="top"><span class="label">{ev}</span>'
                f'<span class="spark">{spark}</span></div>'
                f'<div class="mid"><div class="first {name_class(p["first"])}">{first}</div>{last}</div>'
                f'<div class="bot"><span class="loc">{loc}</span>{tnum}</div>')

    def blank():
        slot = ('<span class="tnum tnum-empty">&nbsp;</span>' if args.tables
                else '<span class="tnum">&nbsp;</span>')
        return (f'<div class="top"><span class="label">{ev}</span>'
                f'<span class="spark">{spark}</span></div>'
                f'<div class="mid"><div class="writeline"></div>'
                f'<div class="hint">your name</div></div>'
                f'<div class="bot"><span class="loc">{loc}</span>{slot}</div>')

    items = [named(p) for p in people] + [blank() for _ in range(n_blank)]

    def paginate(cells_list):
        out = []
        for s in range(0, len(cells_list), per_sheet):
            chunk = cells_list[s:s + per_sheet]
            out.append('<div class="sheet">' + "".join(
                cell(c, idx % stock["cols"], idx // stock["cols"])
                for idx, c in enumerate(chunk)) + "</div>")
        return out

    sheets = paginate(items)
    blank_sheets = paginate([blank() for _ in range(per_sheet * args.blank_sheets)]) \
        if args.blank_sheets else []

    css = f"""
@font-face{{font-family:'BadgeSerif';font-weight:400 700;font-style:normal;
  src:url(data:font/{fmt};base64,{fb64}) format('{fmt}');}}
:root{{--fg:#241F1B;--mut:#6B625A;--line:#E2D9CC;--serif:'BadgeSerif',Georgia,serif}}
*{{box-sizing:border-box;margin:0;padding:0}}
@page{{size:8.5in 11in;margin:0}}
html,body{{background:#fff}}
body{{font-family:Arial,'Liberation Sans',Helvetica,sans-serif;color:var(--fg)}}
.sheet{{position:relative;width:8.5in;height:11in;background:#fff;
  page-break-after:always;overflow:hidden}}
.sheet:last-child{{page-break-after:auto}}
.badge{{position:absolute;width:{stock['cell_w']}in;height:{stock['cell_h']}in;
  background:#fff;overflow:hidden;padding:{round(0.30*k,3)}in {round(0.36*k,3)}in;
  display:flex;flex-direction:column;justify-content:space-between;
  outline:{'0.5px solid var(--line)' if args.cut_guides else 'none'};outline-offset:-0.5px}}
.cm{{position:absolute;background:#999}}
.cm.tl,.cm.tr,.cm.bl,.cm.br{{width:0.12in;height:0.5pt}}
.cm.tl{{left:0;top:0}}.cm.tr{{right:0;top:0}}.cm.bl{{left:0;bottom:0}}.cm.br{{right:0;bottom:0}}
.top{{display:flex;justify-content:space-between;align-items:flex-start}}
.label{{font-family:var(--serif);font-size:{pt(12)}pt;font-weight:500;color:var(--fg)}}
.spark{{width:{round(0.6*k,3)}in;height:{round(0.6*k,3)}in;
  margin:{round(-0.05*k,3)}in {round(-0.06*k,3)}in 0 0;flex:none;display:block}}
.spark svg{{width:100%;height:100%;display:block}}
.mid{{flex:1;display:flex;flex-direction:column;justify-content:center;padding:.02in 0}}
.first{{font-family:var(--serif);font-weight:500;line-height:.98;color:var(--fg);
  letter-spacing:-.01em}}
.first.xl{{font-size:{pt(52)}pt}}.first.lg{{font-size:{pt(44)}pt}}
.first.md{{font-size:{pt(36)}pt}}.first.sm{{font-size:{pt(29)}pt}}
.last{{font-family:var(--serif);font-weight:400;font-size:{pt(18)}pt;
  color:var(--mut);margin-top:.05in}}
.bot{{display:flex;justify-content:space-between;align-items:flex-end}}
.loc{{font-size:{pt(9.5)}pt;color:var(--mut);letter-spacing:.03em}}
.tnum{{font-family:var(--serif);font-weight:500;font-size:{pt(30)}pt;
  line-height:.8;color:var(--fg)}}
.writeline{{border-bottom:1.5px solid var(--fg);height:{round(0.6*k,3)}in;
  margin:0 .1in .04in 0}}
.hint{{font-size:{pt(9.5)}pt;color:var(--mut);font-style:italic}}
.tnum-empty{{border-bottom:1.5px solid var(--fg);width:{round(0.5*k,3)}in;
  height:{round(0.36*k,3)}in}}
"""
    def doc(title, body_sheets):
        return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
                f'<title>{title}</title><style>{css}</style></head>'
                f'<body>{"".join(body_sheets)}</body></html>')

    os.makedirs(args.outdir, exist_ok=True)
    out = os.path.join(args.outdir, "badges.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(doc(f"{ev} — badges ({args.stock})", sheets))

    blank_out = None
    if blank_sheets:
        blank_out = os.path.join(args.outdir, "badges-blank.html")
        with open(blank_out, "w", encoding="utf-8") as fh:
            fh.write(doc(f"{ev} — blank write-on badges ({args.stock})", blank_sheets))

    # ---------------- confirmation report (read this out loud to the user) ----
    print(f"\nWROTE {out}")
    print("--- printed on every badge, read this back to the user ---")
    print(f"title      : {args.event}")
    print(f"city+date  : {args.location}")
    print("----------------------------------------------------------")
    print(f"stock      : {args.stock} — {stock['label']}")
    print(f"verified   : {stock['verified'] or 'NOT PROOFED — test sheet is mandatory'}")
    print(f"font       : {fontfile}")
    print(f"named      : {n_named}")
    if skipped:
        print(f"skipped    : {skipped} row(s) (unapproved or nameless)")
    pad = n_blank - args.blanks
    print(f"blank      : {n_blank} mixed in"
          + (f" ({args.blanks} requested + {pad} to finish the last sheet)" if pad > 0 else ""))
    print(f"total      : {len(items)} badges on {len(sheets)} sheet(s) @ {per_sheet}/sheet")
    if blank_out:
        print(f"\nWROTE {blank_out}")
        print(f"blank-only : {args.blank_sheets} spare sheet(s) = "
              f"{args.blank_sheets * per_sheet} write-on badges, print as many as you want")
    if args.tables:
        c = Counter(p["table"] for p in people if p["table"])
        print(f"\ntables     : {len(c)} table(s)")
        for t in sorted(c, key=lambda x: int(x) if x.isdigit() else 9999):
            print(f"  table {t:>3} -> {c[t]}")
        if no_table:
            print(f"  !! {len(no_table)} guest(s) with NO table: {', '.join(no_table[:10])}"
                  + (" ..." if len(no_table) > 10 else ""))
        if unmatched_assign:
            print(f"  !! {len(unmatched_assign)} assignment name(s) not in roster: "
                  f"{', '.join(unmatched_assign[:10])}"
                  + (" ..." if len(unmatched_assign) > 10 else ""))
    dupes = [n for n, ct in Counter(p["key"] for p in people).items() if ct > 1]
    if dupes:
        print(f"\n!! duplicate name(s): {', '.join(dupes)}")
    long_first = [p["first"] for p in people if len(p["first"]) > 14]
    if long_first:
        print(f"!! very long first name(s), eyeball the proof: {', '.join(long_first)}")
    print()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list-stocks", action="store_true")
    ap.add_argument("--roster", help="CSV of attendees")
    ap.add_argument("--stock", default="74541", choices=list(STOCKS))
    ap.add_argument("--event", help="EVENT TITLE — small label, top-left. Required.")
    ap.add_argument("--city", help="CITY — e.g. 'Los Angeles'. Required.")
    ap.add_argument("--date", help="DATE — ISO (2026-07-24) or free text ('Jul 24'). Required.")
    ap.add_argument("--location", help="override: replaces the composed 'City · Date' line")
    ap.add_argument("--tables", help="CSV with name,table — omit for no table numbers")
    ap.add_argument("--blanks", type=int, default=0,
                    help="write-on badges mixed into the main file, for walk-ups")
    ap.add_argument("--blank-sheets", type=int, default=1,
                    help="extra standalone sheets of write-on badges (badges-blank.html). "
                         "Default 1. Use 0 to skip.")
    ap.add_argument("--fill-sheet", action="store_true",
                    help="pad blanks only to finish the last sheet")
    ap.add_argument("--only-approved", action="store_true",
                    help="keep rows whose status column reads approved/going/confirmed")
    ap.add_argument("--font", default="copernicus", choices=["copernicus", "lora"])
    ap.add_argument("--accent", help="hex for the spark logo, e.g. #D97757")
    ap.add_argument("--no-logo", action="store_true")
    ap.add_argument("--cut-guides", action="store_true",
                    help="hairline outline per badge (helpful on cardstock)")
    ap.add_argument("--outdir", default=".")
    args = ap.parse_args()

    if args.list_stocks:
        for k, v in STOCKS.items():
            print(f"{k:12} {v['label']}")
            print(f"{'':12} cell {v['cell_w']}x{v['cell_h']}in  {v['cols']}x{v['rows']} "
                  f"= {v['cols']*v['rows']}/sheet  margins {v['margin_top']}/{v['margin_side']}in")
            print(f"{'':12} verified: {v['verified'] or 'NO — proof before printing'}\n")
        return
    if not args.roster:
        ap.error("--roster is required (or use --list-stocks)")

    # Event title, city, and date are what make a badge a keepsake instead of a
    # sticker. Never silently print a blank line where they belong.
    if not args.event:
        ap.error("--event (event title) is required — it prints top-left on every badge")
    if not args.location and not (args.city and args.date):
        ap.error("--city and --date are both required (or pass --location to override "
                 "the composed line). They print bottom-left on every badge.")
    if not args.location:
        args.location = f"{args.city.strip()} · {fmt_date(args.date)}"
    build(args)


if __name__ == "__main__":
    main()
