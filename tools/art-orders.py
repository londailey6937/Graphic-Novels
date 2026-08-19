#!/usr/bin/env python3
"""Emit build/art-orders.md: one paste-ready generation prompt per missing panel.

Every prompt is prefixed with the style bible and any character sheets it needs,
because consistency across panels comes from repeating those two blocks verbatim
-- not from remembering what you typed last time.

Text sheets hold wardrobe and anatomy. They do not hold a *face*. So each order
also names the reference images to attach alongside the prompt: the character's
canonical sheet render, plus any earlier panel this one has to match. See
docs/likeness.md for the ChatGPT workflow those attachments assume.
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
PRINT = TPL.get("print", {})
SHEETS = TPL.get("reference_sheets", {})
MARKS = TPL.get("fixed_marks", [])
LONG_EDGE = max(STD_W, STD_H)
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


def gen_size(w, h, min_long=LONG_EDGE):
    """A slot size gpt-image-2 will actually accept: edges multiples of 16px,
    edge ratio <= 3:1, long edge >= the standard plate's so print stays possible."""
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


def subjects(prompt):
    return [k for k, rx in KEYS.items() if re.search(rx, prompt)]


def refs_for(p):
    """Reference images to attach to this order, most authoritative first:
    the canonical sheet for every subject named, then whatever earlier panels
    the script says this one has to match."""
    out = []
    for k in subjects(p["prompt"]):
        s = SHEETS.get(k)
        if s and s not in out:
            out.append((s, f"{k} — canonical likeness"
                           + ("" if (ROOT / s).exists() else "  ⚠ not rendered yet")))
    for r in p.get("refs", []):
        out.append((r, "continuity" + ("" if (ROOT / r).exists() else "  ⚠ missing file")))
    return out


def project_instructions():
    """The durable half of every prompt, assembled once. This goes in the ChatGPT
    Project's custom instructions, not in the message -- so a per-panel order is
    four lines instead of forty and cannot drift between panels by retyping."""
    cast = "\n".join(f'\u2022 {k.upper()} \u2014 {v}' for k, v in chars.items())
    marks = " \u00b7 ".join(MARKS) if MARKS else "(none declared)"
    return f"""This project generates panels for a photoreal graphic novel. Every image
request follows these rules.

STYLE (applies to every image, never varies):
{m["style_bible"]}

REFERENCE CONVENTION: when images are attached, Image 1 is the CHARACTER SHEET and
is the authority for identity \u2014 face, hairline, beard boundary, nose bridge, eye
spacing, ear shape, build, wardrobe. Image 2 is the PREVIOUS SHOT and is the
authority for state \u2014 light, wetness, dirt, wardrobe condition, object positions.
Do not average them.

CAST:
{cast}

FIXED MARKS, true in every image: {marks}

NEVER restyle, idealize, or clean up a character. Never make them younger, thinner
or more symmetrical. Never change hair length or beard shape.

Default size {STD_W}x{STD_H} unless the request states otherwise."""


def message_block(p, w, h, att):
    """The per-panel half: what actually goes in the chat message, assuming the
    project instructions above are loaded. Everything durable is already there."""
    lines = []
    if att:
        lines += ["Same shoot, minutes later, different camera position. Not a new "
                  "character.",
                  "Image 1 = identity. Image 2 = previous shot, match its state.", ""]
    if p.get("continuity"):
        lines += [f'CONTINUITY: {p["continuity"]}', ""]
    shot = p["prompt"]
    if p.get("camera"):
        shot = f'{p["camera"]} \u2014 {shot}'
    lines += [f'SHOT: {shot}', "", f'Image size {w}x{h}.']
    return "\n".join(lines)


def standalone_block(p, w, h):
    """Same order with the durable half inlined, for a chat with no project loaded."""
    marks = (" Fixed marks: " + " \u00b7 ".join(MARKS) + "." ) if MARKS else ""
    lead = ""
    if p.get("continuity"):
        c = p["continuity"]
        lead = (" Image 1 is the character sheet and is the authority for identity; "
                "image 2 is the previous shot and is the authority for state. "
                + c[0].upper() + c[1:] + ("" if c.rstrip().endswith(".") else "."))
    shot = f'{p["camera"]} \u2014 {p["prompt"]}' if p.get("camera") else p["prompt"]
    return (f'{m["style_bible"]}{lead}{marks} Do not restyle, idealize or clean up the '
            f'character. {shot} Image size {w}x{h}.')


dpi_line = ""
if PRINT:
    tw, th = PRINT["trim_in"]
    dpi_line = (f'That size is the print floor, not a preference: {STD_W}×{STD_H} on a '
                f'{tw}×{th}in trim is {PRINT["dpi"]}dpi, so a full-bleed splash survives '
                "the press. Screen builds downsample; nothing upsamples.")

out = [f'# Art orders — {m["title"]}: {m["subtitle"]}', "",
       "**Style bible** (prepend to every prompt, unchanged):", "",
       f'> {m["style_bible"]}', "",
       f'**Every panel is {STD_W}x{STD_H}** ({TPL["art"]["ratio"][0]}:{TPL["art"]["ratio"][1]}). '
       "One ratio for the whole book: a 4:5 page subdivides into n x n cells that are also "
       "4:5, so 1, 4 or 9 panels per page is the entire grammar and any render drops into "
       "any slot with no crop. Pass the size as the `size` parameter (API) or state it in "
       "the prompt (ChatGPT).", ""]
if dpi_line:
    out += [dpi_line, ""]
out += ["Panels whose slot is off-standard are flagged below; those are the ones to "
        "re-cut, not to re-render at an odd size.", ""]

out += ["---", "", "## Project instructions — paste once", "",
        "This is the durable half of every prompt. Paste it into the ChatGPT Project's "
        "custom instructions and drop the reference sheets into the project files. "
        "Every order below then needs only its own four lines, and the style, cast and "
        "fixed marks cannot drift between panels by being retyped.", "",
        "```", project_instructions(), "```", ""]

# --- reference sheets: the likeness anchors every other order attaches ---
if SHEETS:
    out += ["---", "", "## Reference sheets", "",
            "Attach these to every order that names their subject. A text description "
            "fixes wardrobe; only an image fixes a face. Generate each one once, at the "
            "standard plate size, and never regenerate it — if a sheet drifts, every "
            "panel made after it drifts with it. See [docs/likeness.md](../docs/likeness.md).", ""]
    for k, path in SHEETS.items():
        state = "**on file**" if (ROOT / path).exists() else "**not rendered**"
        out += [f'### sheet `{k}` — `{path}` — {state}', ""]
        if not (ROOT / path).exists():
            out += ["```",
                    f'{m["style_bible"]} Character reference sheet: {chars[k]} '
                    "Neutral standing pose against the forest, three views in one frame — "
                    "full front, three-quarter, and profile — even overcast light, no "
                    "dramatic shadow hiding the face, consistent scale across the three. "
                    f'Image size {STD_W}x{STD_H}.',
                    "```", ""]
    out += ["---", ""]
else:
    out += ["---", ""]

todo = 0
for pg in data["pages"]:
    rows = [p for p in pg["panels"] if not p.get("image") and not p.get("black")]
    if not rows:
        continue
    out.append(f'## Page {pg["n"]} — section {pg["act"]}  ({pg["layout"]})')
    for p in rows:
        todo += 1
        sheets = [f"- **{k}:** {chars[k]}" for k in subjects(p["prompt"])]
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
        gw, gh = (STD_W, STD_H) if not off else gen_size(w, h)[:2]
        att = refs_for(p)
        if att:
            out += ["Attach these images, in this order:",
                    *[f"- `{path}` — {why}" for path, why in att], ""]
        out += ["Paste into the message (project instructions carry the rest):", "",
                "```", message_block(p, gw, gh, att), "```"]
        if att and not p.get("camera"):
            out += ["", "> No `camera` on this panel. Add one — a shot phrased as a move "
                    "from the previous setup (\"camera now low at the waterline, facing "
                    "him\") holds a face where a fresh description of the subject "
                    "re-rolls it."]
        out += ["", "<details><summary>Without a project loaded — full prompt</summary>",
                "", "```", standalone_block(p, gw, gh), "```", "", "</details>"]
        if sheets:
            out += ["", "Consistency sheets in play:", *sheets]
        out.append("")
        out.append(f'Set `\"image\": \"images/{p["id"]}.png\"` on panel `{p["id"]}` '
                   "in `script/act1.json` when the render lands.")
    out.append("")

out += ["---", "", f"**{todo} panels outstanding.**"]
dest = ROOT / "build" / "art-orders.md"
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text("\n".join(out))
print(f"wrote {dest.relative_to(ROOT)} · {todo} outstanding panels")
