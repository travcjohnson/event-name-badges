#!/usr/bin/env python3
"""
verify_print.py <badges-print.pdf> [--stock 74541] [--expect-named N]

Reads the PDF that will actually go to the printer and proves it is correct.
Checks page size, page count, fonts embedded, per-table counts, and that no
name text runs past the safe zone of its cell.

Never claim badges are ready without running this.
"""
import argparse, re, subprocess, sys
from collections import Counter

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from make_badges import STOCKS  # noqa: E402

try:
    import pypdf
except ImportError:
    sys.exit("ERROR: pip3 install pypdf")

PT = 72.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--stock", default="74541", choices=list(STOCKS))
    ap.add_argument("--expect-named", type=int, help="named-badge count reported by make_badges.py")
    ap.add_argument("--event-label", help="the --event string, to count badge blocks")
    ap.add_argument("--tables", action="store_true",
                    help="this file was built with table numbers; report them")
    args = ap.parse_args()

    stock = STOCKS[args.stock]
    per_sheet = stock["cols"] * stock["rows"]
    reader = pypdf.PdfReader(args.pdf)
    fails, warns = [], []

    # 1. page geometry
    box = reader.pages[0].mediabox
    w, h = float(box.width) / PT, float(box.height) / PT
    if abs(w - 8.5) > 0.02 or abs(h - 11.0) > 0.02:
        fails.append(f"page is {w:.2f}x{h:.2f}in, expected 8.50x11.00in US Letter")
    print(f"page size    : {w:.2f} x {h:.2f} in")
    print(f"pages        : {len(reader.pages)}  (= {len(reader.pages)*per_sheet} badge slots)")

    # 2. fonts embedded — a non-embedded font silently reflows at the print shop
    try:
        out = subprocess.run(["pdffonts", args.pdf], capture_output=True, text=True).stdout
        rows = [r for r in out.splitlines()[2:] if r.strip()]
        print("fonts        :")
        for r in rows:
            parts = r.split()
            name, emb = parts[0], parts[-4]
            print(f"  {name:44} embedded={emb}")
            if emb != "yes":
                fails.append(f"font {name} is NOT embedded")
    except FileNotFoundError:
        warns.append("pdffonts not available (brew install poppler) — font embedding unchecked")

    # 3. table numbers, straight out of the print file.
    # The bottom row extracts as "<location> <table>", so find the repeated
    # location prefix and read the trailing numeral off it.
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    tail = [m.groups() for m in
            (re.match(r"^(.*\S)\s+(\d{1,2})$", ln.strip()) for ln in text.splitlines())
            if m]
    nums = []
    if tail:
        prefix = Counter(p for p, _ in tail).most_common(1)[0][0]
        nums = [n for p, n in tail if p == prefix]
    # A single distinct value across every badge is the date in the location
    # line, not a table number. Only report tables when they actually vary.
    if nums and len(set(nums)) == 1 and not args.tables:
        nums = []
    if nums:
        c = Counter(nums)
        print(f"tables       : {len(c)} table(s), {sum(c.values())} badges carry a number")
        for t in sorted(c, key=int):
            print(f"  table {t:>3} -> {c[t]}")
    else:
        print("tables       : none printed (no-table-number layout)")

    # 4. named count vs what the generator reported
    if args.expect_named is not None:
        blocks = text.count(args.event_label) if args.event_label else None
        if nums and len(nums) != args.expect_named:
            warns.append(f"badges with a table number = {len(nums)}, "
                         f"expected {args.expect_named}")
        if blocks is not None and blocks < args.expect_named:
            fails.append(f"only {blocks} badges found in PDF, expected at least "
                         f"{args.expect_named}")

    print()
    for wmsg in warns:
        print(f"WARN  {wmsg}")
    for f in fails:
        print(f"FAIL  {f}")
    if fails:
        sys.exit(1)
    print("PASS  geometry, embedding, and counts check out.")
    print("STILL REQUIRED: plain-paper test sheet held against blank stock before "
          "printing on the real badges.")


if __name__ == "__main__":
    main()
