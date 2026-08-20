#!/usr/bin/env python3
"""Emit Flux-ready prompts for every panel.

    python3 tools/flux-prompts.py script/what-the-forest-kept.json

Flux takes one descriptive prompt. There is no project, no system message and no
attachment convention, so everything that lived in ChatGPT's project instructions —
style, cast, fixed marks — is inlined into every prompt here. Identity comes from a
LoRA trigger token instead of an attached sheet.
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRIGGER = "<TRIGGER>"      # replace with your LoRA's token, e.g. w4ltman


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    d = json.loads(Path(args[0] if args else ROOT / "script" / "what-the-forest-kept.json").read_text())
    m, panels = d["meta"], d["panels"]
    style = d["style_bible"].replace("Fill the entire frame edge to edge at the stated "
        "size: no letterbox bars, no black borders, no matte.", "").strip()
    marks = d.get("fixed_marks", [])
    ordered = sorted(panels.items(), key=lambda kv: kv[1]["board_no"])

    out = [f"# Flux prompts — {m['title']}", "",
      f"{len(ordered)} panels. Replace `{TRIGGER}` with your character LoRA's trigger "
      "token once it is trained; until then the prompts still work, they just will not "
      "hold one face.", "",
      "**Settings** — 1024x1280 (4:5, screen edition) · Flux dev, 28–32 steps, guidance "
      "3.0–3.5 · Flux schnell, 4 steps, for composition proofs. **Record the seed of every "
      "keeper** and put it in the script; a kept seed makes a frame reproducible, which is "
      "the whole reason for moving off a chat interface.", "",
      "**Standing style** (already inlined below, repeated here for reference):", "",
      f"> {style}", ""]
    if marks:
        out += ["**Fixed marks** — check every delivery:", ""] + [f"- {x}" for x in marks] + [""]
    out += ["---", ""]

    for pid, p in ordered:
        n = p["board_no"]
        who = TRIGGER + " " if "man" in p["prompt"].lower() else ""
        body = p["prompt"]
        if who and body.lower().startswith(("a gaunt", "the man", "seen from behind")):
            body = body[0].lower() + body[1:]
            body = f"{TRIGGER}, {body}"
        prompt = f"{body} {style}"
        out += [f"## {n:02d} · `{pid}` — {p['sec']}", "",
                f"*{p['intent']}*", "", "```",
                " ".join(prompt.split()), "```", "",
                f"`size 1024x1280` · `steps 28` · `guidance 3.2` · `seed ______` "
                f"→ save as `images/{pid}.png`", ""]

    dest = ROOT / "build" / "flux-prompts.md"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text("\n".join(out) + "\n")
    print(f"wrote {dest.relative_to(ROOT)} · {len(ordered)} prompts")


if __name__ == "__main__":
    main()
