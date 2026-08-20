#!/usr/bin/env python3
"""Write the ChatGPT-ready anchored story, or read one back.

    python3 tools/anchored.py export script/what-the-forest-kept.json
    python3 tools/anchored.py check  stories/what-the-forest-kept.anchored.md

Anchor line, on its own line immediately before the paragraph it belongs to:

    [IMAGE p07 | quad | dawn, the band on the dead wrist]

id verbatim as the filename, role is splash or quad, intent optional. The same
format both builders and ChatGPT read, so a file can go out to be drawn and come
back without anyone retyping anything.
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANCHOR = re.compile(r"^\[IMAGE\s+([A-Za-z0-9_-]+)\s*\|\s*(splash|quad)\s*(?:\|\s*(.*?))?\]\s*$")


def export(script_path):
    d = json.loads(Path(script_path).read_text())
    m, panels = d["meta"], d["panels"]
    out = [f"# {m['title']}", ""]
    if m.get("byline"):
        out += [f"*{m['byline']}*", ""]

    cast = d.get("characters", {})
    marks = d.get("fixed_marks", [])
    out += ["## How to draw this file", "",
            "Anchor lines read `[IMAGE id | role | intent]`. Work them in order, top to",
            "bottom. Never skip, add or reorder one. For each: write the order "
            "(SHOT / CAMERA / LIGHT-TIME / STATE / CONTINUITY / NEW / SIZE), then draw it.",
            "", "**Standing constraints — true for every image in this file:**", "",
            "- **One continuous photographic image.** No panels, no gutters, no borders,",
            "  no insets, no composed page. One frame of film, one moment.",
            "- **No text of any kind** in the image — no captions, balloons, letters,",
            "  numbers, logos or signatures.",
            "- **2432x3040, 4:5 portrait, filled edge to edge.** No letterbox bars.",
            "- **Setting:** " + (m.get("setting") or "as described in the prose") ,
            "- Never restyle, idealize or clean up a character.", ""]
    if cast:
        out += ["## Cast", ""]
        out += [f"- **{k.upper()}** — {v}" for k, v in cast.items()]
        out += [""]
    if marks:
        out += ["## Fixed marks", "", *[f"- {x}" for x in marks], ""]
    out += ["## Story", ""]

    n = 0
    for sec in d["sections"]:
        out += [f"### {sec['n']}", ""]
        for b in sec["blocks"]:
            pid = b.get("art")
            if pid:
                p = panels.get(pid, {})
                intent = p.get("intent") or first_clause(p.get("prompt", ""))
                out.append(f"[IMAGE {pid} | {p.get('role','quad')}"
                           + (f" | {intent}]" if intent else "]"))
                n += 1
            out += [b["text"], ""]

    dest = ROOT / "stories" / f"{m['slug']}.anchored.md"
    dest.write_text("\n".join(out).rstrip() + "\n")
    print(f"exported {dest.relative_to(ROOT)} · {n} anchors · "
          f"{sum(len(b['text'].split()) for s in d['sections'] for b in s['blocks'])} words")
    return dest


def first_clause(prompt):
    """A short hint, not the description — the model writes the description."""
    s = re.split(r"(?<=[.!?]) ", prompt)[0]
    s = re.sub(r"^(THE |INSIDE: )", "", s)
    return (s[:70].rstrip(" ,.;:") + "…") if len(s) > 70 else s.rstrip(".")


def check(md_path):
    text = Path(md_path).read_text().split("\n")
    ids, bad, orphan = [], [], 0
    for i, line in enumerate(text):
        if line.strip().startswith("[IMAGE"):
            mm = ANCHOR.match(line.strip())
            if not mm:
                bad.append((i + 1, line.strip()[:70]))
                continue
            ids.append(mm.group(1))
            nxt = next((t for t in text[i + 1:] if t.strip()), "")
            if not nxt or nxt.startswith(("#", "[IMAGE")):
                orphan += 1
    dupes = [x for x in set(ids) if ids.count(x) > 1]
    print(f"{Path(md_path).name}: {len(ids)} anchors")
    print(f"  malformed        : {len(bad)}" + (f" -> {bad[:3]}" if bad else ""))
    print(f"  duplicate ids    : {sorted(dupes) or 'none'}")
    print(f"  anchors with no following paragraph: {orphan}")
    return 1 if (bad or dupes or orphan) else 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    mode, target = sys.argv[1], sys.argv[2]
    if mode == "export":
        sys.exit(check(export(target)))
    elif mode == "check":
        sys.exit(check(target))
    sys.exit(__doc__)
