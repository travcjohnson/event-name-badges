#!/usr/bin/env bash
# render_pdf.sh <badges.html> [out.pdf]
# Chrome headless -> PDF at true 8.5x11 with no browser headers, then a PNG proof
# of sheet 1. Chrome is the renderer that was used for the proofed 74541 file;
# wkhtmltopdf and weasyprint shift the grid, so do not substitute them.
set -euo pipefail

SRC="${1:?usage: render_pdf.sh <badges.html> [out.pdf]}"
SRC="$(cd "$(dirname "$SRC")" && pwd)/$(basename "$SRC")"
OUT="${2:-$(dirname "$SRC")/badges-print.pdf}"
PROOF="$(dirname "$OUT")/PROOF-$(basename "${OUT%.pdf}")-sheet1.png"

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
[ -x "$CHROME" ] || CHROME="$(command -v google-chrome || command -v chromium || true)"
[ -n "$CHROME" ] || { echo "ERROR: Chrome not found. Install Google Chrome."; exit 1; }

"$CHROME" --headless=new --disable-gpu --no-pdf-header-footer \
  --allow-file-access-from-files --virtual-time-budget=10000 \
  --print-to-pdf="$OUT" "file://$SRC" 2>/dev/null

echo "PDF   -> $OUT"

if command -v pdftoppm >/dev/null 2>&1; then
  pdftoppm -f 1 -l 1 -r 110 -png -singlefile "$OUT" "${PROOF%.png}"
  echo "PROOF -> $PROOF"
else
  echo "NOTE: pdftoppm not found (brew install poppler) — no PNG proof generated."
fi
