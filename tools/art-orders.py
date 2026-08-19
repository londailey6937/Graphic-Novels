#!/usr/bin/env python3
"""Emit build/art-orders.md: one paste-ready generation prompt per missing panel.

Every prompt is prefixed with the style bible and any character sheets it needs,
because consistency across panels comes from repeating those two blocks verbatim
-- not from remembering what you typed last time.
"""
import json, re, sys
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import grid_of

ROOT = Path(__file__).resolve().parent.parent
TPL = json.loads((ROOT / "script" / "template.json").read_text())
STD_W, STD_H = TPL["art"]["size"]
STD_R = TPL["art"]["ratio"][0] / TPL["art"]["ratio"][1]
TOL = TPL["tolerance"]
EXC = TPL["exceptions"]
data = json.loads((ROOT / "script" / "act1.json").read_text())
m, chars = data["meta"], data["characters"]
GUT = m.get("gutter", 14)


def fr(spec):
    return [float(x.rstrip("fr")) for x in spec.split()]


def slot_px(pg, area):
    """Pixel size of a panel's grid slot on the page -- so its art is generated
    at the shape it will actually occupy, instead of being cropped to fit."""
    rows, cols, areas, _ = grid_of(pg)
    r1, c1, r2, c2 = areas[area]
    R, C = fr(rows), fr(cols)
    aw = m["page_w"] - 2 * GUT - GUT * (len(C) - 1)
    ah = m["page_h"] - 2 * GUT - GUT * (len(R) - 1)
    cw = [aw * f / sum(C) for f in C]
    rh = [ah * f / sum(R) for f in R]
    w = sum(cw[c1 - 1:c2 - 1]) + GUT * (c2 - c1 - 1)
    h = sum(rh[r1 - 1:r2 - 1]) + GUT * (r2 - r1 - 1)
    return round(w), round(h)


# generators take arbitrary ratios, but a clean one is easier to trust and reuse
COMMON = [(1,4),(1,3),(1,2),(2,3),(3,4),(4,5),(1,1),(5,4),(4,3),(3,2),(16,9),(2,1),(21,9),(3,1)]


def gen_size(w, h, min_long=2400):
    """A slot size gpt-image-2 will actually accept: edges multiples of 16px,
    edge ratio <= 3:1, long edge >= 2400px so a print edition stays possible."""
    k = min_long / max(w, h)
    W, H = max(16, round(w * k / 16) * 16), max(16, round(h * k / 16) * 16)
    return W, H, max(W / H, H / W)


def ar(w, h):
    r = w / h
    for a, b in COMMON:
        if abs(r - a / b) / (a / b) < 0.015:      # within 1.5% -> call it the clean ratio
            return f"{a}:{b}"
    f = Fraction(w, h).limit_denominator(48)
    return f"{f.numerator}:{f.denominator}"

# which character sheets to append, by keyword in the prompt
KEYS = {"walt": r"\bWALT\b|Walt", "visitor": r"visitor|alien", "band": r"\bband\b"}

out = [f'# Art orders — {m["title"]}: {m["subtitle"]}', "",
       "**Style bible** (prepend to every prompt, unchanged):", "",
       f'> {m["style_bible"]}', "",
       f'**Every panel is {STD_W}x{STD_H}** ({TPL["art"]["ratio"][0]}:{TPL["art"]["ratio"][1]}). '
       "One ratio for the whole book: a 4:5 page subdivides into n x n cells that are also "
       "4:5, so 1, 4 or 9 panels per page is the entire grammar and any render drops into "
       "any slot with no crop. Pass the size as the `size` parameter (API) or state it in "
       "the prompt (ChatGPT).", "",
       "Panels whose slot is off-standard are flagged below; those are the ones to "
       "re-cut, not to re-render at an odd size.", "", "---", ""]

todo = 0
for pg in data["pages"]:
    rows = [p for p in pg["panels"] if not p.get("image") and not p.get("black")]
    if not rows:
        continue
    out.append(f'## Page {pg["n"]} — section {pg["act"]}  ({pg["layout"]})')
    for p in rows:
        todo += 1
        sheets = [f"- **{k}:** {chars[k]}" for k, rx in KEYS.items()
                  if re.search(rx, p["prompt"])]
        w, h = slot_px(pg, p["area"])
        off = abs(w / h - STD_R) / STD_R > TOL
        note = ""
        if off and p["id"] in EXC:
            note = f'  · exception: {EXC[p["id"]]}'
        elif off:
            note = f'  ⚠ slot is {ar(w, h)}, off-standard — re-cut the page, not the render'
        out += ["", f'### panel `{p["id"]}` — **{STD_W}×{STD_H}**{note}', ""]
        if off:
            W2, H2, edge = gen_size(w, h)
            out += [f'Slot is {w}×{h}px ({ar(w, h)}). If you keep the slot, render '
                    f'{W2}×{H2}' + (f' — but that is {edge:.2f}:1, past the 3:1 cap, so it '
                    'can only arrive as a painted letterbox (see tools/debar.py).'
                    if edge > 3.0 else '.'), ""]
        out += ["```", f'{m["style_bible"]} {p["prompt"]} Image size '
                + (f'{STD_W}x{STD_H}' if not off else f'{gen_size(w,h)[0]}x{gen_size(w,h)[1]}')
                + '.', "```"]
        if sheets:
            out += ["", "Consistency sheets in play:", *sheets]
        out.append("")
        out.append(f'Set `\"image\": \"images/{p["id"]}.png\"` on panel `{p["id"]}` '
                   "in `script/act1.json` when the render lands.")
    out.append("")

out += ["---", "", f"**{todo} panels outstanding.**"]
dest = ROOT / "build" / "art-orders.md"
dest.write_text("\n".join(out))
print(f"wrote {dest.relative_to(ROOT)} · {todo} outstanding panels")
