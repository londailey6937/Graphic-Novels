# What the Forest Kept — graphic novel build

A text-plus-image pipeline. The script is data; the pages are generated. You never
hand-place a caption box in Photoshop and you never re-flow 14 pages because one
line of prose got longer.

There are two editions, built from two scripts over one set of images.

**Reading edition** — `script/story.json` -> `tools/read.py` -> `build/read.html`.
The prose runs continuously in a single measure; art is anchored to the paragraph it
belongs to and holds in a synced column until the next anchor replaces it. This is the
one to read the story in.

**Panel edition** — `script/act1.json` -> `tools/build.py` -> `build/index.html` and
the PDF. Composed comic pages with caption boxes over the art. This is the one to
print.

```
script/story.json    the prose: sections -> blocks -> {text, art anchor}
script/act1.json     the pages: pages -> panels -> {image, prompt, captions}
images/              finished art, one file per panel id (e.g. 6a.png)
tools/read.py        prose + images -> build/read.html   (reading edition)
tools/build.py       script + images -> build/index.html (panel edition)
tools/art-orders.py  script -> build/art-orders.md (prompts for missing panels)
tools/export-pdf.sh  build -> print-ready PDF, one comic page per PDF page
tools/debar.py       strip painted letterbox bars off a render, file it as a panel
```

## The loop

```sh
python3 tools/read.py             # the reading edition
python3 tools/read.py --embed     # self-contained, for sharing (needs Pillow)
python3 tools/build.py            # the panel edition (links to images/)
python3 tools/art-orders.py       # what art is still missing, as prompts
python3 tools/build.py --embed    # single self-contained file, for sharing
./tools/export-pdf.sh             # build/what-the-forest-kept-act1.pdf
```

Panels without an `image` render as a hatched **ART ORDER** card printing their own
prompt. So an unfinished build is still readable end to end — pacing, caption
length, page turns all testable before a single render exists. Fill art in any
order; the book is always in a viewable state.

## Adding a panel

```json
{ "id": "7c", "area": "c",
  "prompt": "Ground-level macro of the band in wet dirt, first light.",
  "focal": "50% 40%",
  "captions": [{ "pos": "br", "text": "It did not wait for *permission*.", "emph": true }] }
```

- `area` — which slot in the page's `layout` grid (`a`,`b`,`c`,`d`).
- `focal` — CSS `object-position`. Art is cropped to the slot, so this is how you
  keep a face in frame when a 4:5 render lands in a wide panel.
- `captions[].pos` — `tl tc tr bl bc br cc`. `cc` renders as a centered rule-bounded
  block for beat lines.
- `emph: true` — brass left rule, for the line the page turns on.
- `black: true` on a panel — pure black, no art. Silence is a panel.
- `*asterisks*` become italics.

## Layouts

`splash` · `stack2` · `stack2-silent` · `row3-tall` · `strip3` · `wide-plus-2` ·
`grid4` · `tall-plus-inset` · `hero45-plus-2`

Add your own in `LAYOUTS` in [tools/build.py](tools/build.py): a rows spec, a cols
spec, and `{area: (row-start, col-start, row-end, col-end)}`. Listing an area in
`INSET` floats it over the panel beneath with a paper-colored outline.

A page can also carry its own bespoke grid instead of a named layout, which is what
art arriving at an unrepeatable ratio usually needs:

```json
"grid": { "rows": "4.88fr 1fr", "cols": "1fr",
          "areas": { "b": [1,1,2,2], "a": [2,1,3,2] } }
```

Page 10 uses one: the scream came back at 4.72:1 instead of the 4:5 splash it was
ordered as, so the page became a near-square macro (1572×1625) above a 4.72:1 band,
and the beats were reordered to match the prose — the touch, then the sound.

## Why two editions

The panel edition breaks the prose into caption boxes, and that is the right form for
a printed page but the wrong form for reading. A close-third narrator carries this
story; chopping 1,039 words into 30 fragments of 15–40 words, scattered by corner
position across panels, means the reader hunts for text instead of reading sentences.
The rhythm of the prose is the thing that survives least well.

So the reading edition keeps the prose whole and lets the art accompany it instead of
interrupting it. Its rules:

- One measure, ~33em, never moving. The text column is the constant.
- Art is anchored to a paragraph and **holds** until the next anchor. Unrendered
  panels are skipped entirely, so sparse art reads as deliberate illustration rather
  than as holes — and starts participating automatically as it lands.
- Under 900px the column becomes a pinned band above the prose, swapping images
  outright rather than cross-fading in a fixed-height well.
- Each beat carries its **art order inline** — panel id, standard size, state, and a
  link that brings the image up in the column (or jumps to the appendix entry when it
  isn't drawn yet). The reading edition doubles as the production document.
- **Where you are** is shown two ways: a brass rule on the beat you're reading, and a
  rail of ticks down the left, one per panel, filled for rendered and hollow for
  pending, with the current one extended. Ticks are clickable.
- An **art-order appendix** closes the file: every anchored panel with section, size,
  state and full prompt, linked both ways with the inline marks.

Within the panel edition, the caption grammar still holds: **1–3 panels per page**,
never six, and anything over ~45 words wants its own panel or a `cc` beat block.

## The template standard: one ratio

`script/template.json` holds it, and both builders read it.

**Every panel is 1920×2400 (4:5).** The reason is arithmetic: a 4:5 page subdivides into
n×n cells that are *also* 4:5 — 1572×1972, 779×979, 514×648, all within 1% of 0.800.
No other subdivision of a 4:5 page holds the ratio:

| subdivision | cell | ratio |
|---|---|---|
| 1×1 splash | 1572×1972 | 0.797 ✓ |
| 2×2 | 779×979 | 0.796 ✓ |
| 3×3 | 515×648 | 0.794 ✓ |
| 2 stacked | 1572×979 | 1.606 ✗ |
| 2 side by side | 779×1972 | 0.395 ✗ |

So the entire page grammar is **1, 4, or 9 panels** — `splash`, `grid4`, `grid9`. A
sequence that wants 3 beats becomes three splashes, not one three-panel page. That is
the price of one ratio, and it buys: every render drops into any slot with no crop, no
per-panel size bookkeeping, and no `--ar` to get wrong.

`tools/art-orders.py` enforces it — every order reads `1920×2400`, and any slot outside
2% tolerance is flagged **off-standard** with the instruction to re-cut the page rather
than re-render at an odd size. Act I predates the standard, so 16 of its 24 outstanding
panels are flagged; `exceptions` in `template.json` grandfathers the two bands whose art
already exists and earns it.

## Aspect ratios are computed, not guessed

`art-orders.py` derives each panel's true pixel size from the slot it occupies and
emits the matching `--ar`. Generate at that ratio and the art drops in with no crop;
generate at a different one and `focal` decides what survives.

This matters more than it sounds. A 4:5 portrait render dropped into a 1.4:1
landscape slot loses 57% of its height from the middle out. Two ways out: reframe
the prompt to the slot, or change the layout to fit the art. Page 6 took the second
route — `hero45-plus-2` exists because the filament macro deserved a slot at exactly
4:5, and it gets one (1080×1350), with a vertical slice and a letterbox carried around
it for the two supporting beats.

Useful coincidence: a full-page splash and a `grid4` cell are both 4:5, so a
generator left at its portrait default lands correctly in either.

### Sizes are gpt-image-2-legal

`gpt-image-2` takes any resolution in `size`, but only within **edge ratio ≤ 3:1 and
edges that are multiples of 16px**. So `art-orders.py` doesn't just print a ratio — it
scales each slot to a real generation size satisfying both, with the long edge at
2400px so print stays possible, and flags any slot that can't be satisfied.

That check earns its keep: it caught two slots in the first draft of `hero45-plus-2`
at 3.86:1 and 3.26:1, both ungeneratable. The layout's grid was re-solved to
2.22fr/1fr × 2.26fr/1fr, which holds the hero at exactly 4:5 while bringing the
supporting slots to 2.82:1 and 2.59:1. Design constraint discovered by validator,
not by 26 failed renders.

### When the model paints the bars in

Ask gpt-image-2 for a "letterbox" or "widescreen" frame and it will often return the
bars *painted into* a legal canvas rather than a wide one — it has no choice past 3:1.
Panel 6c came back as 1914×822 with 77% of the file pure black; the real picture was a
1912×192 band at 9.96:1.

```sh
python3 tools/debar.py "images/ChatGPT Image ….png" 6c   # needs Pillow
```

Two of the first three deliveries came back this way, so the style bible now ends with
*"Fill the entire frame edge to edge at the stated size: no letterbox bars, no black
borders, no matte"* — and no longer says "4:5 portrait framing", which was stale once
framing went per-panel and was losing to the cinematic look anyway.

`debar.py` finds the live band, crops to it, writes `images/6c.png`, and reports the
true ratio. Then the slot gets shaped to the art: page 6 became `hero-plus-strip`
(11.416fr / 1fr), a 4:5-ish hero above a full-bleed 9.95:1 sliver, and the art drops in
with 0.2% crop.

The alternative was cropping the strip to the 2.586:1 slot it was ordered for, which
would have kept 26% of its width and thrown the alien's head out of frame. **When
delivered art and the slot disagree, reshape the slot** — the art is the expensive
half. That reshaping cut the throat close-up (6b) for want of a slot; it's parked in
`pages[5].reserve` in the script, not deleted, and its beat is already carried by
page 5.

One more rule the sliver taught: a caption box needs ~67px, so it covers 42% of a
158px strip and lands straight on the eyes. Slivers stay silent — the line moves to
the panel above.

## Reading on a phone

The page is a fixed-ratio canvas, so it scales as one unit: `width: min(1600px, 100%)`
with `aspect-ratio` owning the height. Measured at 402x874 (iPhone Pro logical
viewport) the page lands at 402x503, exactly 0.800, no horizontal scroll, panel
slots within 1.3% of their design ratios. `scroll-snap` gives page-at-a-time swiping.

Type does not scale 1:1 — it can't. `--u` is one design pixel
(`calc(100cqw / 1600)`), and every size is `max(floor, calc(N * var(--u)))`: faithful
when there's room, readable when there isn't. A 15px caption would render at 3.5px on
a phone if scaled honestly, so it floors at 11px, and below 760px captions widen from
62% to 92% so prose spends the space horizontally instead of towering.

What that buys, at 402px:

| page kind | verdict |
|---|---|
| splash (1 panel) | reads well — art fills, captions sit lightly |
| 2-panel | fine |
| 3-panel strip | tight but legible |
| `grid4` (4 panels) | **fails** — captions cover ~54% of a 181px-wide cell |

So the 1–3 panels/page rule isn't a style preference, it's the phone constraint.
Page 11 is the one page that breaks it and should split into two 2-panel pages for a
phone edition. The alternative is guided view — one panel at a time, the way comic
apps do it — which is a different reader, not a CSS tweak.

## Page geometry

Digital-first: **1600×2000 (4:5)**, matching the source render's aspect, so art
fills a splash with zero crop and reads on a phone without pinching.

For a print edition, set `page_w`/`page_h` in `script/act1.json` to `1988×3075`
(6.625×10.25in @300dpi, standard US comic trim) and re-render art at 2x. The
`@page` rule in the print CSS derives its size from those numbers, so the PDF
follows automatically. Add trim/bleed marks before sending to a printer.
