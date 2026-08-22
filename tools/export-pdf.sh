#!/usr/bin/env bash
# Export the built book to a print-ready PDF, one comic page per PDF page.
#
#   tools/export-pdf.sh                                  # the current script
#   tools/export-pdf.sh script/what-the-forest-kept.json
#   tools/export-pdf.sh script/act1.json                 # an earlier draft
#
# The embedded build inlines full-size plates on purpose: this is the print path,
# and 2432x3040 is 304dpi on the 8x10in trim. It is a large file and Chrome takes
# its time with it. build/board.html is the one that got thumbnails, not this.
set -euo pipefail
cd "$(dirname "$0")/.."
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SCRIPT="${1:-script/what-the-forest-kept.json}"

if [ ! -f "$SCRIPT" ]; then
  echo "no such script: $SCRIPT" >&2
  exit 1
fi
if [ ! -x "$CHROME" ]; then
  echo "Chrome not found at $CHROME — needed to render the PDF" >&2
  exit 1
fi

SLUG=$(python3 -c 'import json,sys,pathlib
d=json.load(open(sys.argv[1]))
print(d.get("meta",{}).get("slug") or pathlib.Path(sys.argv[1]).stem)' "$SCRIPT")
OUT="build/${SLUG}.pdf"

python3 tools/build.py "$SCRIPT" --embed
"$CHROME" --headless --disable-gpu --no-pdf-header-footer \
  --print-to-pdf="$OUT" \
  "file://$PWD/build/index-embedded.html" 2>/dev/null
echo "→ $OUT"
