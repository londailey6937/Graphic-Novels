#!/usr/bin/env python3
"""Find the story's art gaps and write the requests.

    python3 tools/coverage.py script/what-the-forest-kept.json

Four questions, in order of how badly a wrong answer hurts:

  1. Is any stretch of prose running without a picture?      -> requests art
  2. Does every section have at least one picture?           -> requests art
  3. Could a child follow the story from the pictures alone? -> lints the orders
  4. Which orders are still unrendered?                      -> the worklist

(3) is the one that needs saying out loud: a picture sequence only carries a story if
each frame has somebody in it doing something. An order naming no actor is an
establishing shot, which is fine on its own and fatal in a run -- two in a row and the
thread drops. That is what gets flagged.

Exit code is 1 if anything blocking is found, so this can gate a build.
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_UNCOVERED = 150      # words of prose allowed between pictures
GRAMMAR = (1, 4, 9)      # panels per page the template permits

ALIASES = {
    "walt": ["walt", "he ", "his ", "him "],
    "visitor": ["visitor", "alien"],
    "band": ["band", "bracelet"],
    "keeper": ["keeper", "presence"],
    "kept": ["the kept", "beings"],
    "ship": ["ship"],
    "agents": ["agents", "men ", "vehicles"],
}
ACTIONS = re.compile(
    r"\b(kneel\w*|walk\w*|sit\w*|stand\w*|build\w*|open\w*|clos\w*|lift\w*|look\w*|"
    r"weep\w*|wept|step\w*|watch\w*|crouch\w*|drink\w*|thrown|spill\w*|spring\w*|"
    r"search\w*|driv\w*|ris\w*|hold\w*|reach\w*|lie|lies|lying|fold\w*|carr\w*|"
    r"keep\w*|arriv\w*|fill\w*|surround\w*|enter\w*|leav\w*|turn\w*|point\w*)\b", re.I)


def actors(prompt, chars):
    low = prompt.lower()
    found = [k for k in chars if any(a in low for a in ALIASES.get(k, [k]))]
    return found


def paginate(panels_in_order):
    """Group panels into pages of 1 / 4 / 9. A splash claims a page alone."""
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
                pages.append(run); run = []
    if run:
        pages.append(run)
    return pages


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    doc = json.loads(Path(sys.argv[1]).read_text())
    secs, panels, chars = doc["sections"], doc["panels"], doc.get("characters", {})
    out, blocking = [], 0
    title = doc["meta"]["title"]
    out += [f"# Coverage — {title}", ""]

    # flatten prose with anchor positions
    flat = []
    for s in secs:
        for b in s["blocks"]:
            flat.append({"sec": s["n"], "words": len(b["text"].split()),
                         "art": b.get("art"), "text": b["text"]})
    total_words = sum(b["words"] for b in flat)
    anchored = [i for i, b in enumerate(flat) if b["art"]]

    # ---- 1. uncovered stretches ------------------------------------------------
    out += ["## 1. Prose running without a picture", ""]
    gaps, run_words, run_start = [], 0, 0
    for i, b in enumerate(flat):
        if b["art"]:
            if run_words > MAX_UNCOVERED:
                gaps.append((run_start, i - 1, run_words))
            run_words, run_start = 0, i + 1
        else:
            run_words += b["words"]
    if run_words > MAX_UNCOVERED:
        gaps.append((run_start, len(flat) - 1, run_words))
    if gaps:
        blocking += len(gaps)
        for lo, hi, w in gaps:
            out += [f"- **REQUEST ART** — {w} words uncovered, {flat[lo]['sec']} "
                    f"paragraphs {lo}–{hi}: *“{flat[lo]['text'][:90]}…”*"]
    else:
        out += [f"None. Longest uncovered run is under {MAX_UNCOVERED} words."]
    out += [""]

    # ---- 2. sections without a picture ----------------------------------------
    out += ["## 2. Sections without a picture", ""]
    bare = [s["n"] for s in secs if not any(b.get("art") for b in s["blocks"])]
    if bare:
        blocking += len(bare)
        out += [f"- **REQUEST ART** — section {n} has no picture at all" for n in bare]
    else:
        out += [f"None. All {len(secs)} sections carry at least one."]
    out += [""]

    # ---- 3. can a child follow the pictures? -----------------------------------
    out += ["## 3. Could a child follow the pictures alone?", ""]
    order = [(b["art"], panels[b["art"]]) for b in flat if b["art"] and b["art"] in panels]
    rows, no_actor_run, worst_run = [], 0, 0
    for pid, p in order:
        who = actors(p["prompt"], chars)
        act = ACTIONS.search(p["prompt"])
        if who:
            no_actor_run = 0
        else:
            no_actor_run += 1
            worst_run = max(worst_run, no_actor_run)
        rows.append((pid, who, bool(act), no_actor_run))
    silent = [r for r in rows if not r[1]]
    still = [r for r in rows if not r[2]]
    if worst_run >= 2:
        blocking += 1
        out += [f"- **REQUEST ART** — {worst_run} pictures in a row with no actor in them; "
                "the thread drops for a reader following only the pictures"]
    if silent:
        out += [f"- {len(silent)} establishing shot(s) with no actor (fine alone): "
                + ", ".join(f"`{r[0]}`" for r in silent)]
    if still:
        out += [f"- {len(still)} order(s) name no action: "
                + ", ".join(f"`{r[0]}`" for r in still)]
    if not silent and not still and worst_run < 2:
        out += ["Every picture has somebody in it doing something."]
    out += ["", "**The story as pictures only:**", ""]
    for i, (pid, p) in enumerate(order, 1):
        first = re.split(r"(?<=[.!?]) ", p["prompt"])[0]
        mark = "" if actors(p["prompt"], chars) else "  ← no actor"
        out += [f"{i:>2}. `{pid}` {first}{mark}"]
    out += [""]

    # ---- 4. the worklist -------------------------------------------------------
    out += ["## 4. Art still to make", ""]
    todo = [(pid, p) for pid, p in order if not p.get("image")]
    done = [(pid, p) for pid, p in order if p.get("image")]
    out += [f"{len(done)} rendered · **{len(todo)} outstanding**", ""]
    for pid, p in todo:
        out += [f"- `{pid}` ({p['sec']}, {p.get('role','quad')}) — {p['prompt'][:100]}…"]
    out += [""]

    # ---- pagination ------------------------------------------------------------
    pages = paginate(order)
    bad = [i + 1 for i, pg in enumerate(pages) if len(pg) not in GRAMMAR]
    out += ["## Pagination under the 1 / 4 / 9 grammar", "",
            f"{len(order)} panels -> **{len(pages)} pages** "
            f"({sum(1 for p in pages if len(p)==1)} splash, "
            f"{sum(1 for p in pages if len(p)==4)} quad"
            + (f", {len(bad)} short" if bad else "") + ")", ""]
    for i, pg in enumerate(pages, 1):
        flag = "  ⚠ short page — pad to 4 or promote to splash" if len(pg) not in GRAMMAR else ""
        out += [f"- page {i:>2}: {' '.join('`'+x+'`' for x in pg)}{flag}"]
    if bad:
        out += ["", f"{len(bad)} page(s) hold a count the grammar does not allow."]
    out += [""]

    dest = ROOT / "build" / "coverage.md"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text("\n".join(out) + "\n")
    print(f"{title}: {total_words} words · {len(flat)} paragraphs · {len(order)} panels")
    print(f"  uncovered stretches : {len(gaps)}")
    print(f"  bare sections       : {len(bare)}")
    print(f"  actorless runs >=2  : {'yes' if worst_run >= 2 else 'no'}")
    print(f"  art outstanding     : {len(todo)} of {len(order)}")
    print(f"  pages               : {len(pages)}" + (f" ({len(bad)} off-grammar)" if bad else ""))
    print(f"  -> {dest.relative_to(ROOT)}")
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
