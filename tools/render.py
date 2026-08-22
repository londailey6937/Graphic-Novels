#!/usr/bin/env python3
"""Render panels with FLUX.2 and file them as art.

    python3 tools/render.py p26                    # one panel
    python3 tools/render.py p26 p27 --model pro    # several, cheaper model
    python3 tools/render.py --missing              # every panel with no art
    python3 tools/render.py p26 --seed 41234       # reproduce an earlier frame
    python3 tools/render.py p26 --dry-run          # show the request, send nothing

Needs an API key:  export BFL_API_KEY=...

What this does that a chat window cannot: it sends the *same* prompt every time
(the panel's prompt with the style bible appended, exactly as `flux-prompts.py`
emits it), attaches the *same* reference images, and writes the seed back into
the script beside the panel. A frame you can regenerate is a frame you can
improve -- change one variable, hold everything else.

Two defaults are deliberate and worth knowing:

* **Seeds are always explicit.** If you do not pass one, a random seed is chosen
  here and recorded, rather than letting the server pick one we never learn.
  Otherwise the frame is unreproducible the moment it lands.
* **Prompt upsampling is off.** FLUX.2 [pro] and [max] rewrite your prompt before
  generating unless told not to. That rewrite is not deterministic, so it defeats
  the seed -- same seed, different prompt, different picture. `--upsample` turns
  it back on for when you want the model's help finding a composition.
"""
import argparse, base64, json, os, random, sys, time, urllib.error, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.bfl.ai/v1/"
MODELS = {"max": "flux-2-max", "pro": "flux-2-pro-preview", "flex": "flux-2-flex",
          "klein": "flux-2-klein-9b"}
MAX_REFS = 8                      # [pro] and [max] take eight via the API
SIZE = (1600, 2000)               # 4:5, 3.2MP -- under the 4MP cap, and the exact
                                  # page size, so a splash is pixel-for-pixel
TIMEOUT = 300


def die(msg):
    sys.exit(f"render: {msg}")


def api_key():
    """The key, from the environment or from a key file beside the script.

    The environment is the usual place, but a long-running process -- the editor,
    say -- only ever sees the environment it was started with, so changing the key
    would mean restarting it. A file is re-read on every render instead. Both
    `.env` and `.bfl-key` are in .gitignore; this repo is public, and a key
    committed to a public repo is scraped within minutes."""
    k = os.environ.get("BFL_API_KEY", "").strip()
    if k:
        return k
    plain = ROOT / ".bfl-key"
    if plain.exists():
        k = plain.read_text().strip()
        if k:
            return k
    dotenv = ROOT / ".env"
    if dotenv.exists():
        for line in dotenv.read_text().splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            name, _, val = line.partition("=")
            if name.strip() == "BFL_API_KEY":
                return val.strip().strip("'\"")
    return ""


def post(url, payload, key):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"accept": "application/json", "x-key": key,
                 "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:600]
        if e.code == 402:
            die("out of credits. Add them at https://app.bfl.ai — 1 credit = $0.01.\n"
                "    Check the balance any time:\n"
                "      curl -H \"x-key: $BFL_API_KEY\" https://api.bfl.ai/v1/credits")
        if e.code in (401, 403):
            die(f"the API key was rejected ({e.code}). Check .bfl-key or BFL_API_KEY.")
        die(f"{e.code} from {url}\n{body}")


def get(url, key):
    req = urllib.request.Request(url, headers={"accept": "application/json",
                                               "x-key": key})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


REF_EDGE = 1024           # a reference carries a likeness, not a plate


def b64(path):
    """A reference image, base64'd, downscaled first.

    The plates are 2432x3040, which is ~8MB of base64 each; eight of those is a
    40MB request body for information the model does not use. A likeness reads
    fine at 1024. Without Pillow the file goes as-is rather than not at all."""
    p = Path(path)
    try:
        import io
        from PIL import Image
        im = Image.open(p).convert("RGB")
        if max(im.size) > REF_EDGE:
            k = REF_EDGE / max(im.size)
            im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=88, optimize=True)
        return base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        return base64.b64encode(p.read_bytes()).decode()


ALIASES = {                       # kept in step with coverage.py
    "walt": ["walt", "the man", " he ", " his ", " him "],
    "visitor": ["visitor", "alien", "non-human"],
    "band": ["band", "bracelet", "cuff"],
    "keeper": ["keeper", "presence"],
    "kept": ["the kept", "beings"],
    "ship": ["ship"],
    "agents": ["agents", " men ", "vehicles", "rifles"],
}


def style_of(doc, panel=None):
    """The style bible for one panel: what is always true, plus what depends on
    which side of the hull it is on.

    One blob for every panel meant exterior frames carried the sentence about
    warm amber interiors, and a model told about warm amber light will find
    somewhere to put it -- a lit cabin in an empty forest, for instance. FLUX.2
    takes no negative prompt, so an absence has to be asserted, not withheld."""
    s = doc.get("style_bible", "")
    s = s.replace("Fill the entire frame edge to edge at the stated size: "
                  "no letterbox bars, no black borders, no matte.", "").strip()
    setting = (panel or {}).get("setting", "exterior")
    extra = (doc.get("style_by_setting") or {}).get(setting, "")
    return f"{extra} {s}".strip() if extra else s


def sheets_for(prompt, doc):
    """Character descriptions for whoever is in this panel.

    The reference images carry a likeness; they do not carry wardrobe, and they
    certainly do not carry three weeks of not washing. A studio turnaround shows
    a clean shirt, so without this the man arrives laundered."""
    chars = doc.get("characters") or {}
    low = f" {prompt.lower()} "
    out = []
    for name, desc in chars.items():
        keys = ALIASES.get(name, [name])
        if any(k in low for k in keys):
            out.append(desc.strip())
    return out


def continuity_for(panel, doc):
    """Assertions that depend on where in the story this panel sits.

    The band closes on Walt's wrist partway through, so a rule written as though
    it is always there is wrong for every frame before it arrives -- and wrong in
    the expensive direction, since asserting it puts it in the picture. Before the
    arrival the opposite is asserted, because an absence FLUX is not told about is
    an absence FLUX is free to fill."""
    out = []
    n = panel.get("board_no", 0)
    for rule in (doc.get("continuity") or {}).values():
        frm = rule.get("from_board")
        if frm is None:
            continue
        text = rule.get("mark") if n >= frm else rule.get("before")
        if text:
            out.append(text.strip())
    return out


def marks_for(prompt, doc):
    """The fixed marks that apply to this panel.

    These are the rules a finished frame is checked against -- and checking a
    delivery against a rule the generator was never told is a slow way to buy the
    same mistake twice. A mark naming a character travels only with that
    character; a mark naming none is global.

    They are phrased as exclusivity ("the only thing on either forearm") rather
    than prohibition, because FLUX.2 takes no negative prompt: saying "no watch"
    puts a watch in the frame as often as not."""
    low = f" {prompt.lower()} "
    present = set(sheets_names(prompt, doc))
    out = []
    for m in doc.get("fixed_marks", []):
        owner = None
        for name in (doc.get("characters") or {}):
            if name.lower() in m.lower():
                owner = name
                break
        if owner is None or owner in present:
            out.append(m.strip())
    return out


def sheets_names(prompt, doc):
    low = f" {prompt.lower()} "
    return [n for n in (doc.get("characters") or {})
            if any(k in low for k in ALIASES.get(n, [n]))]


def ref_clause(doc, n_refs, has_walt, panel=None):
    """Tell the model what the attached images are *for*.

    This is the difference between references as mood and references as
    instruction. FLUX.2 addresses inputs positionally -- "the man in image 1",
    "keep the pose of image 1" -- and BFL's own guide says to name them. Send
    eight pictures and mention none of them and you get a general impression of a
    weathered man; say "the same rucksack as image 1, carried the same way" and
    you get that rucksack. Continuity is not remembered between calls, because
    there are no calls between calls. It has to be pointed at, every time."""
    if not n_refs:
        return ""
    own = (panel or {}).get("ref_clause")
    if own:
        return own.replace("{last}", str(n_refs))
    if not has_walt:
        return ""
    tmpl = doc.get("reference_clause")
    if tmpl:
        return tmpl.replace("{last}", str(n_refs))
    return (f"Image 1 is the reference for this man and everything he carries. "
            f"He is the same man, wearing and carrying exactly what he wears and "
            f"carries in image 1: the same face, the same shirt, suspenders, "
            f"trousers, belt and boots, the same pack carried the same way on the "
            f"same shoulder, the same rope in the same place. Images 2 to "
            f"{n_refs} show the same man's face and head from other angles — match "
            f"that face. Do not redesign his clothing or his kit.")


def refs_for(pid, panel, doc):
    """Reference images for one panel: its own `refs`, else the script's
    `reference_set`. This is what holds a face across frames -- the text sheets
    describe wardrobe, they cannot describe a likeness.

    A panel that sets `refs` should set `ref_clause` too. Eight images the prompt
    never mentions are eight images the model averages into a mood; the whole
    point of swapping the set per panel is to then point at what you swapped in.
    A finished plate makes the best reference there is -- p04 and p08 are the
    visitor's only turnaround, and the first good band plate becomes the band's."""
    chosen = panel.get("refs") or doc.get("reference_set") or []
    out = []
    for r in chosen[:MAX_REFS]:
        p = ROOT / r
        if not p.exists():
            print(f"  ! reference missing, skipped: {r}")
            continue
        out.append(str(p))
    return out


def render(pid, doc, args, key):
    panel = doc["panels"][pid]
    body = panel.get("prompt", "").strip()
    if not body:
        die(f"{pid} has an empty prompt — write one before rendering it")
    sheets = sheets_for(body, doc)
    marks = marks_for(body, doc) + continuity_for(panel, doc)
    refs = refs_for(pid, panel, doc)
    clause = ref_clause(doc, len(refs), 'walt' in sheets_names(body, doc), panel)
    parts = [body] + sheets + ([clause] if clause else []) + [style_of(doc, panel)] + marks
    prompt = " ".join(" ".join(parts).split())

    seed = args.seed if args.seed is not None else random.randint(1, 2**31 - 1)
    w, h = args.size
    payload = {"prompt": prompt, "width": w, "height": h, "seed": seed,
               "output_format": "png", "safety_tolerance": args.safety,
               "disable_pup": not args.upsample}
    for i, r in enumerate(refs):
        payload["input_image" if i == 0 else f"input_image_{i+1}"] = b64(r)

    print(f"\n{pid} · {panel.get('intent','')}")
    print(f"  model {MODELS[args.model]} · {w}x{h} · seed {seed} · "
          f"{len(refs)} ref · {len(sheets)} sheet · {len(marks)} mark · "
          f"{panel.get("setting","exterior")}"
          + ("" if args.upsample else " · pup off"))
    if args.dry_run:
        shown = {k: (f"<{len(v)//1024}KB base64>" if k.startswith("input_image") else v)
                 for k, v in payload.items()}
        shown["prompt"] = shown["prompt"][:220] + "…"
        print("  DRY RUN, not sent:")
        print("   ", json.dumps(shown, indent=2).replace("\n", "\n    "))
        for r in refs:
            print(f"    ref: {Path(r).relative_to(ROOT)}")
        return None

    started = post(API + MODELS[args.model], payload, key)
    poll = started.get("polling_url")
    if not poll:
        die(f"no polling_url in response: {started}")
    if started.get("cost") is not None:
        print(f"  submitted · {started['cost']} credits")

    t0 = time.time()
    last = None
    while True:
        if time.time() - t0 > TIMEOUT:
            die(f"{pid} timed out after {TIMEOUT}s")
        time.sleep(1.0)
        res = get(poll, key)
        st = res.get("status")
        if st != last:
            print(f"  {st}")
            last = st
        if st == "Ready":
            break
        if st in ("Error", "Failed", "Task not found"):
            die(f"{pid} failed: {json.dumps(res)[:400]}")
        if st in ("Request Moderated", "Content Moderated"):
            die(f"{pid} was moderated ({st}). Raise --safety (0 strict … 5 least) "
                f"or rephrase the prompt.")

    url = (res.get("result") or {}).get("sample")
    if not url:
        die(f"{pid} ready but no image in result: {json.dumps(res)[:300]}")
    with urllib.request.urlopen(url, timeout=120) as r:
        data = r.read()
    dest = ROOT / "images" / f"{pid}.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        keep = ROOT / "images" / ".replaced"
        keep.mkdir(exist_ok=True)
        dest.replace(keep / f"{pid}-{time.strftime('%Y%m%d-%H%M%S')}.png")
    dest.write_bytes(data)
    print(f"  -> images/{pid}.png  ({len(data)//1024}KB)")
    return {"image": f"images/{pid}.png", "seed": seed,
            "model": MODELS[args.model], "size": [w, h]}


def main():
    ap = argparse.ArgumentParser(description="Render panels with FLUX.2.")
    ap.add_argument("panels", nargs="*", help="panel ids, e.g. p26 p27")
    ap.add_argument("--script", default=str(ROOT / "script" / "what-the-forest-kept.json"))
    ap.add_argument("--model", default="max", choices=sorted(MODELS))
    ap.add_argument("--missing", action="store_true", help="every panel with no art")
    ap.add_argument("--seed", type=int, help="reuse a seed to reproduce a frame")
    ap.add_argument("--size", type=int, nargs=2, default=list(SIZE), metavar=("W", "H"))
    ap.add_argument("--safety", type=int, default=4, choices=range(6),
                    help="0 strictest … 5 least strict (default 4)")
    ap.add_argument("--upsample", action="store_true",
                    help="let the model rewrite the prompt (breaks seed reproducibility)")
    ap.add_argument("--dry-run", action="store_true", help="print the request, send nothing")
    args = ap.parse_args()

    sp = Path(args.script)
    doc = json.loads(sp.read_text())
    ids = list(args.panels)
    if args.missing:
        ids += [p for p, v in sorted(doc["panels"].items()) if not v.get("image")]
    if not ids:
        die("name at least one panel, or pass --missing")
    unknown = [p for p in ids if p not in doc["panels"]]
    if unknown:
        die(f"not in this script: {', '.join(unknown)}")
    if args.seed is not None and len(ids) > 1:
        die("--seed applies to one panel; rendering several would reuse it")

    key = api_key()
    if not key and not args.dry_run:
        die("no API key found. Either\n"
            "        echo 'sk-your-key' > .bfl-key      (simplest; gitignored)\n"
            "    or  export BFL_API_KEY=sk-your-key\n"
            "    Get one at https://app.bfl.ai")

    ok = 0
    for pid in ids:
        got = render(pid, doc, args, key)
        if got:
            doc = json.loads(sp.read_text())      # re-read: the editor may be running
            doc["panels"][pid].update(got)
            sp.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
            ok += 1
    if ok:
        print(f"\n{ok} panel(s) rendered; seeds recorded in {sp.name}.")
        print("Rebuild:  python3 tools/build.py " + str(sp))


if __name__ == "__main__":
    main()
