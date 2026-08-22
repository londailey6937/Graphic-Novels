#!/usr/bin/env python3
"""Turn a story script (sections + panels) into the pages the builders read.

    python3 tools/pages.py script/what-the-forest-kept.json     # show the pagination

The reading edition walks prose. The panel edition walks *pages*, and a page is a
layout plus slots. Two shapes, one story, and this is the only place the crossing
is made: which panels share a page, which layout holds them, which slot each takes,
and where the prose anchored to a panel lands as caption.

The grammar is the template's: 1, 4 or 9 panels to a page, because those are the
only subdivisions of 4:5 that stay 4:5. A splash claims a page alone. A run that
ends short is still emitted -- `coverage.py` is what tells you it is short, and a
book that refuses to build is worse than one that builds and reports its own flaw.

Captions are placed, never written: one caption per anchored block, in document
order, verbatim. Splitting a paragraph into shorter caption boxes is an editorial
act, so it belongs in the script -- split the block there and both editions follow.
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GRAMMAR = (1, 4, 9)
LAYOUT_FOR = {1: "splash", 2: "stack2", 3: "row3-tall", 4: "grid4", 9: "grid9"}
AREAS = "abcdefghi"


def paginate(panels_in_order):
    """Group (pid, panel) pairs into pages of 1 / 4 / 9. A splash claims a page."""
    pages, run = [], []
    for pid, p in panels_in_order:
        if p.get("role") == "splash":
            if run:
                pages += [run[i:i + 4] for i in range(0, len(run), 4)]
                run = []
            pages.append([pid])
        else:
            run.append(pid)
            if len(run) == 4:
                pages.append(run)
                run = []
    if run:
        pages.append(run)
    return pages


def blocks_by_panel(doc):
    """panel id -> the prose blocks anchored to it, in document order."""
    out = {}
    for sec in doc.get("sections", []):
        for b in sec.get("blocks", []):
            if b.get("art"):
                out.setdefault(b["art"], []).append(b)
    return out


def panel_order(doc):
    """Panels in the order the prose reaches them -- which is the order the book
    is read in, and the order `coverage.py` audits. `board_no` is the contact
    sheet's order, not the book's; the two differ wherever an anchor was moved
    against the prose, so paginating by board_no would silently disagree with the
    audit. Anything never anchored is appended in board order rather than dropped."""
    panels = doc["panels"]
    seen, order = set(), []
    for sec in doc.get("sections", []):
        for b in sec.get("blocks", []):
            pid = b.get("art")
            if pid and pid in panels and pid not in seen:
                seen.add(pid)
                order.append((pid, panels[pid]))
    for pid, p in sorted(panels.items(), key=lambda kv: kv[1].get("board_no", 0)):
        if pid not in seen:
            order.append((pid, p))
    return order


def captions_for(blocks, area, alone):
    """Anchored prose as caption boxes.

    Text is verbatim. The corner is the block's own `pos` when it has one --
    tools/edit.py writes that, and a corner chosen against the picture beats any
    rule -- and otherwise falls to a deterministic default, so a script that has
    never been through the editor still lays out sensibly."""
    caps = []
    for i, b in enumerate(blocks):
        text = b.get("text", "").strip()
        if not text:
            continue
        if b.get("pos"):
            pos = b["pos"]
        elif alone:
            pos = "bl" if i == 0 else "br"
        else:
            pos = "tl" if (area == "a" and i == 0) else "br"
        cap = {"pos": pos, "text": text}
        if b.get("emph"):
            cap["emph"] = True
        caps.append(cap)
    return caps


def build_pages(doc):
    """The script's panels, grouped into pages under the template's grammar."""
    panels = doc["panels"]
    order = panel_order(doc)
    anchored = blocks_by_panel(doc)
    pages = []
    for n, group in enumerate(paginate(order), 1):
        layout = LAYOUT_FOR.get(len(group))
        if layout is None:
            raise SystemExit(
                f"page {n} holds {len(group)} panels and no layout takes that count. "
                f"Layouts exist for {sorted(LAYOUT_FOR)}; the grammar allows {GRAMMAR}."
            )
        alone = len(group) == 1
        slots = []
        for i, pid in enumerate(group):
            p = panels[pid]
            area = AREAS[i]
            slot = {"id": pid, "area": area, "prompt": p.get("prompt", ""),
                    "focal": p.get("focal", "50% 50%"),
                    "captions": captions_for(anchored.get(pid, []), area, alone)}
            if p.get("image"):
                slot["image"] = p["image"]
            if p.get("black"):
                slot["black"] = True
            slots.append(slot)
        pages.append({"n": n, "act": panels[group[0]].get("sec", ""),
                      "layout": layout, "panels": slots})
    return pages


def adapt(doc, tpl):
    """A story script in the shape the page builders expect: meta + pages.

    Passed a doc that already carries `pages` (the earlier drafts do), it is
    returned untouched -- so both script generations build with one command."""
    if "pages" in doc:
        return doc
    page = tpl.get("page", {})
    meta = dict(doc.get("meta", {}))
    meta.setdefault("subtitle", doc.get("meta", {}).get("setting", "")[:0] or "")
    meta.setdefault("style_bible", doc.get("style_bible", ""))
    meta.setdefault("page_w", page.get("w", 1600))
    meta.setdefault("page_h", page.get("h", 2000))
    meta.setdefault("gutter", page.get("gutter", 14))
    return {**doc, "meta": meta, "pages": build_pages(doc)}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    src = Path(args[0]) if args else ROOT / "script" / "what-the-forest-kept.json"
    doc = json.loads(src.read_text())
    tpl = json.loads((ROOT / "script" / "template.json").read_text())
    out = adapt(doc, tpl)
    pages = out["pages"]
    counts = {}
    for pg in pages:
        counts[len(pg["panels"])] = counts.get(len(pg["panels"]), 0) + 1
    print(f"{len(doc.get('panels', out.get('pages')))} panels -> {len(pages)} pages")
    for pg in pages:
        n = len(pg["panels"])
        flag = "" if n in GRAMMAR else f"   <-- {n} panels, off-grammar"
        ids = " ".join(f"`{p['id']}`" for p in pg["panels"])
        caps = sum(len(p.get("captions", [])) for p in pg["panels"])
        print(f"  page {pg['n']:>2}  {pg['layout']:<10} {ids}  ({caps} caption(s)){flag}")
    off = [pg["n"] for pg in pages if len(pg["panels"]) not in GRAMMAR]
    if off:
        print(f"\n{len(off)} page(s) off-grammar: {off} — pad to 4 or promote to splash.")


if __name__ == "__main__":
    main()
