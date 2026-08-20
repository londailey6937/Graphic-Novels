#!/usr/bin/env python3
"""Render the contact sheet from the script. Deterministic — same input, same sheet.

    python3 tools/board.py script/what-the-forest-kept.json          -> build/board.html
    python3 tools/board.py script/what-the-forest-kept.json --png    -> + build/board.png

Frames come out in board order (board_no), captions come from the script, and a panel
with no art yet renders as a numbered slot holding its caption. Nothing is recalled,
so nothing drifts: to change the sheet, change the script.
"""
import base64, json, mimetypes, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COLS = 6
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def data_uri(rel):
    p = ROOT / rel
    if not p.exists():
        return None
    mime = mimetypes.guess_type(p.name)[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


CSS = """
*{box-sizing:border-box}
body{margin:0;background:#fff;color:#111;font:400 13px/1.45 -apple-system,
  "Helvetica Neue",Arial,sans-serif;padding:0}
.sheet{display:grid;grid-template-columns:repeat(%d,1fr);gap:0}
.cell{border-right:1px solid #e6e6e6;border-bottom:1px solid #e6e6e6;
  display:flex;flex-direction:column}
.cell:nth-child(%dn){border-right:none}
.art{aspect-ratio:4/5;background:#0b0d0e;overflow:hidden;position:relative}
.art img{width:100%%;height:100%%;object-fit:cover;display:block}
.slot{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
  background:repeating-linear-gradient(45deg,#12161a 0 10px,#0e1114 10px 20px);
  color:#5d6a66;font:600 30px/1 ui-monospace,Menlo,monospace;letter-spacing:.06em}
.cap{padding:12px 14px 20px}
.no{font:700 14px/1 -apple-system,Helvetica,Arial,sans-serif;letter-spacing:.02em;
  margin-bottom:7px}
.cap p{margin:0;font-size:12.5px;line-height:1.42;color:#1a1a1a;text-wrap:pretty}
.meta{margin-top:7px;font:500 9.5px/1 ui-monospace,Menlo,monospace;letter-spacing:.1em;
  text-transform:uppercase;color:#9b9b9b}
""" % (COLS, COLS)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    spath = Path(args[0]) if args else ROOT / "script" / "what-the-forest-kept.json"
    d = json.loads(spath.read_text())
    panels = sorted(d["panels"].items(), key=lambda kv: kv[1].get("board_no", 0))

    cells, drawn = [], 0
    for pid, p in panels:
        n = p.get("board_no", 0)
        src = data_uri(p["image"]) if p.get("image") else None
        if src:
            drawn += 1
            art = f'<img src="{src}" alt="">'
        else:
            art = f'<div class="slot">{n:02d}</div>'
        cells.append(
            f'<div class="cell"><div class="art">{art}</div>'
            f'<div class="cap"><div class="no">{n:02d}</div>'
            f'<p>{esc(p.get("intent",""))}</p>'
            f'<div class="meta">{esc(pid)} · {esc(p.get("sec",""))} · '
            f'{esc(p.get("role","plate"))}</div></div></div>')

    html = (f'<!doctype html><meta charset="utf-8"><title>{esc(d["meta"]["title"])} — board'
            f'</title><style>{CSS}</style><div class="sheet">{"".join(cells)}</div>')
    out = ROOT / "build" / "board.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(html)
    print(f"built {out.relative_to(ROOT)} · {len(panels)} frames · {drawn} with art")

    if "--png" in sys.argv:
        png = ROOT / "build" / "board.png"
        w = 1020
        rows = (len(panels) + COLS - 1) // COLS
        cell_art = w / COLS * 1.25          # 4:5 art
        h = int(rows * (cell_art + 165)) + 40
        subprocess.run([CHROME, "--headless", "--disable-gpu", f"--window-size={w},{h}",
                        "--hide-scrollbars", f"--screenshot={png}", f"file://{out}"],
                       capture_output=True)
        print(f"built {png.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
