#!/usr/bin/env python3
"""Strip painted letterbox bars from a delivered render and file it as a panel.

    tools/debar.py <file> <panel-id>

Image models asked for a "letterbox" or "widescreen" frame tend to paint the black
bars into the image rather than return a wide canvas -- gpt-image-2 caps native output
at a 3:1 edge ratio, so anything wider can only arrive this way. This finds the live
band, crops to it, writes images/<panel-id>.png, and reports the true aspect ratio so
the panel's slot can be shaped to match.

Needs Pillow: python3 -m pip install Pillow
"""
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
THRESH = 3.0     # mean row/col brightness counted as "pure black bar"
INSET = 1        # skip one live row/col at each edge to avoid a soft fringe


def live_span(vals):
    live = [i for i, v in enumerate(vals) if v > THRESH]
    if not live:
        sys.exit("image is entirely black")
    return live[0] + INSET, live[-1] - INSET


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src, pid = Path(sys.argv[1]), sys.argv[2]
    im = Image.open(src)
    W, H = im.size
    g = im.convert("L")
    px = g.load()
    rows = [sum(px[x, y] for x in range(0, W, 7)) / len(range(0, W, 7)) for y in range(H)]
    cols = [sum(px[x, y] for y in range(0, H, 7)) / len(range(0, H, 7)) for x in range(W)]
    t, b = live_span(rows)
    l, r = live_span(cols)
    out = im.crop((l, t, r + 1, b + 1))
    w, h = out.size
    dest = ROOT / "images" / f"{pid}.png"
    out.save(dest)
    dropped = (1 - (w * h) / (W * H)) * 100
    print(f"{src.name}  {W}x{H}")
    print(f"  -> images/{pid}.png  {w}x{h}  ({w/h:.4f}:1)")
    print(f"  dropped {dropped:.0f}% painted bars")
    if max(w / h, h / w) > 3.0:
        print(f"  note: {max(w/h,h/w):.2f}:1 exceeds gpt-image-2's native 3:1 cap --"
              " shape this panel's slot to the art, it cannot be re-ordered natively")


if __name__ == "__main__":
    main()
