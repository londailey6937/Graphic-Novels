#!/usr/bin/env python3
"""Drop a story in, get a script skeleton out.

    python3 tools/ingest.py stories/what-the-forest-kept.md

Reads .md or .txt, takes the title from a leading '# ', splits on blank lines, and
writes script/<slug>.json with one block per paragraph and no art anchored yet.
Placing the art is a judgment call, not a parse -- tools/coverage.py reports every
stretch still missing one so nothing gets left uncovered by accident.

    --index   print numbered paragraphs instead of writing (for placing anchors)
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def parse(path):
    raw = path.read_text().strip()
    title, body = path.stem.replace("-", " ").title(), raw
    m = re.match(r"#\s+(.+?)\n", raw)
    if m:
        title, body = m.group(1).strip(), raw[m.end():]
    paras, cur, sections = [], [], []
    for line in body.split("\n"):
        h = re.match(r"##\s+(.+)", line.strip())
        if h:
            sections.append((len(paras), h.group(1).strip()))
            continue
        if line.strip():
            cur.append(line.strip())
        elif cur:
            paras.append(" ".join(cur)); cur = []
    if cur:
        paras.append(" ".join(cur))
    return title, paras, sections


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    src = Path(args[0])
    title, paras, secs = parse(src)

    if "--index" in sys.argv:
        for i, p in enumerate(paras):
            print(f"[{i:>2}] ({len(p.split()):>3}w) {p[:96]}{'…' if len(p) > 96 else ''}")
        print(f"\n{len(paras)} paragraphs · {sum(len(p.split()) for p in paras)} words")
        return

    # no explicit '##' breaks -> one section; the editorial pass splits it
    if not secs:
        secs = [(0, "I")]
    bounds = [s[0] for s in secs] + [len(paras)]
    sections = [{"n": name, "blocks": [{"text": t} for t in paras[bounds[i]:bounds[i + 1]]]}
                for i, (_, name) in enumerate(secs)]

    slug = slugify(title)
    dest = ROOT / "script" / f"{slug}.json"
    doc = {
        "meta": {"title": title, "byline": "", "source": str(src), "slug": slug},
        "style_bible": "",
        "characters": {},
        "sections": sections,
        "panels": {},
    }
    if dest.exists():                       # never clobber an authored script
        old = json.loads(dest.read_text())
        for k in ("meta", "style_bible", "characters", "panels"):
            if old.get(k):
                doc[k] = old[k]
        dest = dest.with_suffix(".reingest.json")
        print(f"note: script exists — writing {dest.name} instead, merge by hand")
    dest.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    words = sum(len(p.split()) for p in paras)
    print(f"ingested {src.name} -> {dest.relative_to(ROOT)}")
    print(f"  {title!r} · {len(sections)} section(s) · {len(paras)} paragraphs · {words} words")
    print(f"  0 art anchors — run tools/coverage.py to see what needs art")


if __name__ == "__main__":
    main()
