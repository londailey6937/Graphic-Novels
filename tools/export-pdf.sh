#!/usr/bin/env bash
# Export the built book to a print-ready PDF, one comic page per PDF page.
set -euo pipefail
cd "$(dirname "$0")/.."
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
python3 tools/build.py --embed
"$CHROME" --headless --disable-gpu --no-pdf-header-footer \
  --print-to-pdf="build/what-the-forest-kept-act1.pdf" \
  "file://$PWD/build/index-embedded.html" 2>/dev/null
echo "→ build/what-the-forest-kept-act1.pdf"
