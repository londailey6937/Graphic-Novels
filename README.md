# What the Forest Kept — and the pipeline that builds it

Drop a story in. Get a graphic novel out.

```sh
python3 tools/ingest.py   stories/my-story.md          # story -> script skeleton
#   ... an AI pass places the art anchors and writes the orders ...
python3 tools/coverage.py script/my-story.json         # what still needs art
python3 tools/read.py     script/my-story.json         # the reading edition
python3 tools/build.py    script/my-story.json         # the panel edition
./tools/export-pdf.sh     script/my-story.json         # print-ready PDF
```

Every tool takes the script as its argument and defaults to the current one, so a
second story needs no edits anywhere — only its own `script/<slug>.json`.
```
stories/             drop stories here (.md or .txt)
script/<slug>.json   one script per story: meta, sections -> blocks, panels
script/template.json the one standard: art size, print trim/dpi, device targets
images/              finished art, one file per panel id (e.g. p03.png)
images/ref/          canonical character sheets — the likeness authority
docs/likeness.md     keeping a face the same face across panels (ChatGPT workflow)
tools/ingest.py      story -> script skeleton
tools/coverage.py    audits art coverage; requests what's missing
tools/pages.py       panels -> pages: the grammar, the layouts, the caption slots
tools/edit.py        edit the prose against the pictures, in a browser
tools/render.py      panel prompt -> FLUX.2 -> images/<id>.png, seed recorded
tools/read.py        prose + images -> build/read.html   (reading edition)
tools/build.py       script + images -> build/index.html (panel edition)
tools/board.py       script + images -> build/board.html (contact sheet)
tools/art-orders.py  script -> build/art-orders.md (prompts for missing panels)
tools/flux-prompts.py script -> build/flux-prompts.md (Flux-ready, style inlined)
tools/export-pdf.sh  build -> print-ready PDF, one comic page per PDF page
tools/debar.py       strip painted letterbox bars off a render, file it as a panel
```

`ingest.py` parses. `coverage.py` audits. The judgment in the middle — *where* a picture
belongs and *what* it should show — is the one step that isn't a parse, and it is the
step the whole thing exists to support.

`script/story.json` and `script/act1.json` are the earlier draft of this story, kept for
the panel-edition page layouts. New work goes through `script/<slug>.json`.

## What coverage.py actually checks

Four questions, ordered by how badly a wrong answer hurts:

1. **Is any stretch of prose running without a picture?** Over 150 words between
   anchors and it prints `REQUEST ART` with the paragraph range and its opening line.
2. **Does every section have at least one picture?** A section with none is flagged.
3. **Could a child follow the story from the pictures alone?** This is the one worth
   spelling out. A picture sequence only carries a story if each frame has somebody in
   it doing something. An order naming no actor is an establishing shot — fine alone,
   fatal in a run: two in a row and a reader following only the pictures loses the
   thread. That gets flagged, and the report prints **the story as pictures only**, the
   ordered list of every panel's first sentence, so you can read the picture-story
   straight through and see for yourself whether it holds.
4. **Which orders are still unrendered?** That's the worklist.

It also paginates under the template grammar and flags any page holding a count the
grammar doesn't allow. Exit code is 1 on anything blocking, so it can gate a build.

Placing 24 panels in this story, the audit caught two things a read-through hadn't:
a 3-panel and a 2-panel page that the 1/4/9 grammar forbids, and — chasing the fix —
two beats with no picture at all: the morning Walt checks his wrist to see if the band
has been taken back, and the chord of hundreds of kept lives with his new note in it.
Both are now panels. **The pagination constraint found the missing images.**

## The loop

```sh
python3 tools/read.py             # the reading edition
python3 tools/read.py --embed     # self-contained, for sharing (needs Pillow)
python3 tools/build.py            # the panel edition (links to images/)
python3 tools/board.py            # the contact sheet (thumbnails, needs Pillow)
python3 tools/pages.py            # the pagination, without building anything
python3 tools/art-orders.py       # what art is still missing, as prompts
python3 tools/build.py --embed    # single self-contained file, for sharing
./tools/export-pdf.sh             # build/what-the-forest-kept.pdf
```

`--embed` inlines the art at screen size — the longest edge a panel is ever
displayed at is the page itself (1600 units), so that is the cap. It makes an
8–9MB file you can hand someone. The plates in `images/` stay untouched at
2432×3040; `--full` inlines them at that size instead, which is what
`export-pdf.sh` wants and what makes a ~200MB file. Screen work never needs it.

## Rendering

```sh
export BFL_API_KEY=...
python3 tools/render.py p26              # one panel
python3 tools/render.py --missing        # every panel with no art
python3 tools/render.py p26 --seed 41234 # reproduce an earlier frame
python3 tools/render.py p26 --dry-run    # show the request, send nothing
```

Also a **Render with FLUX** button on every panel in the editor, so a prompt can
be written and answered without leaving the page.

Three things it does that a chat window cannot:

* **The prompt is assembled, not retyped.** Panel prompt plus the style bible,
  the same way `flux-prompts.py` emits it. Consistency across panels comes from
  repeating those blocks verbatim.
* **The reference set is attached every time.** `reference_set` in the script
  (up to 8 images) is what holds a face across frames — text sheets describe
  wardrobe, they cannot describe a likeness.
* **The seed is written back into the script.** A frame you can regenerate is a
  frame you can improve: change one variable and hold everything else.

Two defaults are deliberate. Seeds are always explicit — if you do not pass one,
a random seed is chosen locally and recorded, rather than letting the server pick
one you never learn. And **prompt upsampling is off**: `[pro]` and `[max]` rewrite
your prompt before generating unless told not to, and that rewrite is not
deterministic, so it defeats the seed. `--upsample` turns it back on when you
want the model's help finding a composition.

## Editing the story against the pictures

```sh
python3 tools/edit.py             # opens the editor on the current script
```

Every paragraph in reading order, beside the panel it is anchored to. Change the
prose, move it to a different panel, move the caption to a different corner, mark
the line the page turns on. Save, or save and rebuild without leaving the page.

It exists because of an asymmetry worth stating plainly: **a picture is expensive
to change and a sentence is cheap.** When a frame comes back not quite matching
its caption, the caption is almost always the cheaper thing to move.

And it is the only place one failure is visible. The reading edition prints every
paragraph; the panel edition prints only what a panel carries, so **prose with no
anchor silently never reaches the panel edition** — a story can look finished in
one edition and stop short in the other. The editor counts those paragraphs at the
top of the page and flags each one in place. That count reaching zero is what it
means for the panel edition to tell the whole story.

## Two shapes, one story

The reading edition walks prose. The panel edition walks *pages*, and a page is a
layout plus slots. [tools/pages.py](tools/pages.py) is the only place that crossing
is made, so both editions and the audit agree by construction.

It paginates in **prose order — the order the anchors appear in the text**, not
`board_no`. The two differ wherever an anchor was moved against the prose, and
paginating by board order would put the book in a sequence `coverage.py` never
audited. `board_no` orders the contact sheet; the prose orders the book.

Captions are *placed*, never written: one caption per anchored block, verbatim, in
document order. Splitting a paragraph into shorter caption boxes is an editorial
act, so it belongs in the script — split the block there and both editions follow.

A script that already carries `pages` (the earlier drafts do) passes through
untouched, so one command builds either generation.

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

Within the panel edition, the caption grammar still holds: **1, 4 or 9 panels per
page** — the ratio grammar, now that the phone's 1–3 ceiling is gone — and anything
over ~45 words wants its own panel or a `cc` beat block.

## The template standard: one ratio

`script/template.json` holds it, and both builders read it.

**Every panel is 2432×3040 (4:5).** The reason is arithmetic: a 4:5 page subdivides into
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

`tools/art-orders.py` enforces it — every order reads `2432×3040`, and any slot outside
2% tolerance is flagged **off-standard** with the instruction to re-cut the page rather
than re-render at an odd size. Act I predates the standard, so 16 of its 24 outstanding
panels are flagged; `exceptions` in `template.json` grandfathers the two bands whose art
already exists and earns it.

### Why that size and not a rounder one

`2432×3040` is the largest **exact** 4:5 whose edges are both multiples of 16 — the
family is `64n × 80n`, and `n=38` is the last term that generators still take. It is
chosen from the print end, not the screen end: on the 8×10in trim declared in
`template.json` it lands at **304dpi** on both axes, so a full-bleed splash goes to
press with no upsampling and 38px of bleed slop per edge already in the file. The old
plate, 1920×2400, was 240dpi on the same trim — fine on a screen, short for paper.

Screen builds downsample from the plate; nothing ever upsamples. That is the whole
reason the standard is defined once, in `script/template.json`, and read by both
builders and the order generator rather than typed into prompts.

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
scales each slot to a real generation size satisfying both, with the long edge at the
standard plate's 3040px so print stays possible, and flags any slot that can't be
satisfied.

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

## Reading on tablet and desktop

**Two device targets: tablet and desktop. Phone is out of scope.** `targets` in
`script/template.json` states it, and both builders are tuned to that floor:
**768px** (tablet portrait) is the narrowest viewport the book is designed to hold.

The page is a fixed-ratio canvas, so it scales as one unit: `width: min(1600px, 100%)`
with `aspect-ratio` owning the height. `scroll-snap` gives page-at-a-time swiping.

Type does not scale 1:1 — it can't. `--u` is one design pixel
(`calc(100cqw / 1600)`), and every size is `max(floor, calc(N * var(--u)))`: faithful
when there's room, readable when there isn't. Below 1024px the caption measure widens
from 62% to 78% so prose spends the space horizontally instead of towering.

What the 768px floor gives a `grid4` page — the tightest case in the grammar. Cell
sizes are the grid arithmetic; the caption-box share is the fraction of cell height a
typical 20-word caption occupies at that width. The phone column is the measurement
this file used to carry, kept as the reason the target was dropped:

| | phone (402px, dropped) | tablet portrait (768px) | desktop (1600px) |
|---|---|---|---|
| page width | 402 | ~744 | 1600 |
| `grid4` cell | 181×226 | ~362×453 | 779×979 |
| caption type | 11px (floored from 3.5) | 11px (floored from 7.0) | 15px, faithful |
| caption box | ~54% of the cell | ~13% of the cell | ~6% of the cell |

That last row is the whole reason phone is gone. On a phone a caption box eats half
the panel it sits on and there is no CSS that fixes it — the answer is guided view,
one panel at a time the way comic apps do it, which is a different reader, not a
breakpoint. On tablet the cell is twice the size and the caption sits lightly.

Dropping the phone also resolves a contradiction this file used to carry: the
template standard says the page grammar is **1, 4 or 9 panels**, while the caption
grammar said **1–3 panels per page**. The second rule was never a style position —
it was the phone constraint wearing one. With the phone gone, `grid4` is legal again
and the two rules agree.

The reading edition follows the same floor. Above 1024px it is a two-column spread —
prose in a fixed ~33em measure, art sticky beside it — with the tick rail down the
left. At or below 1024px (tablet portrait, and tablet landscape on smaller slates)
the rail hides and the art becomes a pinned band above the prose, holding up to 40vh
so an image is still an image and not a thumbnail.

## Page geometry, and print

Two numbers that used to be one. `page_w`/`page_h` in `script/act1.json` are
**design units** — 1600×2000 (4:5), the coordinate system every `--u`-derived type
size is written against. They are not inches and they are not the render size.

The physical page is declared separately, in `print` in `script/template.json`:

```json
"print": { "trim_in": [8, 10], "dpi": 304, "bleed_in": 0.125 }
```

`build.py` reads that block for its `@page size`, so the PDF comes out at true 8×10in
regardless of what the design units say. 8×10 is itself 4:5, so **trim, page and
plate are all the same shape** — a splash is full-bleed with zero crop, and the
2432×3040 plate lands at 304dpi across it.

Bleed is *cut off* the plate rather than added to it: at 304dpi, 0.125in is 38px, and
the plate already carries that much slop per edge. Add trim/bleed marks before
sending to a printer.

Both builders also set `print-color-adjust: exact`, because this is a dark book and
the default is to drop the paper to white and print the art on a page it was never
composed against.

## Likeness across panels

Text sheets fix wardrobe. They do not fix a face — which is why a man bent over a
creek bed in one panel comes back as a stranger when the next panel turns him to
camera. The fix is a canonical reference *render* per character, attached to every
prompt that names them, plus the previous panel when a shot has to match.

`reference_sheets` and `fixed_marks` in `script/template.json` name the anchors;
per-panel `refs`, `continuity` and `camera` fields in `script/act1.json` carry
shot-to-shot matching:

```json
{ "id": "4b", "area": "b",
  "prompt": "Close on WALT's cupped hands in cold creek water...",
  "camera": "Camera now low and close at the waterline, facing him",
  "refs": ["images/4a.png"],
  "continuity": "same man as 4a, same hour — wet to the forearms; the face is the sheet" }
```

`art-orders.py` splits the prompt into its durable and per-shot halves: a **Project
instructions — paste once** block holding the style bible, cast, reference convention
and fixed marks, then per panel an **Attach these images** list and a four-line
message block. Retyping the durable half per panel is itself a drift source, so it
gets pasted once and never again. A `<details>` fallback on each order carries the
fully-inlined prompt for a chat with no Project loaded, and any panel with `refs` but
no `camera` is flagged — describing the subject afresh is what re-rolls a face.

The full workflow, written for ChatGPT Plus: **[docs/likeness.md](docs/likeness.md)**.
