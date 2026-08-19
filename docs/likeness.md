# Likeness across panels

*How to use ChatGPT Plus so the man bent over the creek bed is still the same man
when the next panel turns him to camera.*

## Why it fails by default

The style bible and the character sheets in `script/act1.json` are **text**. Text
fixes attributes — late 50s, curly grey-black hair, short grey beard, olive shirt,
suspenders — and the model reproduces attributes reliably. It does not fix a **face**.
Every generation re-rolls the specific geometry underneath those attributes: eye
spacing, nose bridge, hairline, jaw width, the boundary where the beard stops. Two
renders from the same paragraph give you two men who match the description and do not
match each other.

That is not a prompt-quality problem. No amount of adjectives converges on one face,
because a face is not a list of adjectives. **Identity has to come in as an image.**

Change of camera angle makes it worse, not better: a back-three-quarter of a man
bending over water shares almost no visible identity information with a front-on
close-up. The model has nothing to carry forward, so it invents. Profile views drift
the hardest; extreme close-ups of hands and wrists drift the least.

## The fix, in three layers

### 1. One canonical sheet per character, rendered once

Before any panel of a character, render a **reference sheet**: full front,
three-quarter, and profile in a single frame, even overcast light, no dramatic
shadow hiding the face, consistent scale across the three. Full plate size,
2432×3040, same style bible.

`template.json` names them and `art-orders.py` prints the prompt for any that don't
exist yet:

```json
"reference_sheets": {
  "walt":    "images/ref/walt-sheet.png",
  "visitor": "images/ref/visitor-sheet.png",
  "band":    "images/ref/band-sheet.png"
}
```

Two rules about the sheet, and they are the whole discipline:

- **Generate it once and never regenerate it.** If the sheet drifts, every panel made
  after it drifts with it, and panels made before it are now wrong.
- **Every panel references the sheet, not the last panel alone.** Referencing only
  the previous render compounds drift: panel 12 is a copy of a copy of a copy. The
  sheet is the authority; the previous panel is only for shot-to-shot state.

If you cannot get a clean sheet, promote your best existing render to sheet status —
crop it to the head and shoulders, save it under `images/ref/`, and treat it as
canon from then on. A mediocre fixed face beats an excellent drifting one.

### 2. Attach two images to every order

The prompt goes in the message; the identity goes in the attachments. Paperclip both,
in this order:

1. `images/ref/walt-sheet.png` — the face, the build, the wardrobe.
2. the previous panel in the same beat — the light, the mud, which sleeve is wet, how
   far the band has travelled.

Then say, in the message, **which image is the authority for what**. The model will
otherwise average them:

> Two references attached. Image 1 is the character: reproduce this exact face —
> same hairline, same beard boundary, same nose, same eye spacing. Image 2 is the
> immediately preceding shot: match its light, wardrobe state and dirt exactly.
> This is the same man in the same minute, from a different camera position.

`art-orders.py` prints that attachment list on every order that needs one, from
`reference_sheets` plus the panel's own `refs`.

### 3. Phrase the new panel as a camera move, not a new subject

This is the single largest wording change and it costs nothing.

| drifts | holds |
|---|---|
| "A weathered man in his late 50s faces the camera…" | "**Same man, same moment, camera now in front of him at eye level.** He straightens and looks into the lens." |
| "Close-up of his hands in the water" | "**Push in on the hands from the previous shot.** Nothing else changes." |
| "He looks up, startled" | "**Same frame, same light, 1 second later.** His eyes lift off the water toward something out of frame right." |

You are describing a second setup on the same shoot, not casting a second actor. Add
the negative that actually matters, because the model's instinct is to flatter:

> Do not restyle him, do not idealize him, do not clean him up, do not make him
> younger or more symmetrical. Three weeks unwashed.

## What to paste where

This document is the manual. **`build/art-orders.md` is what you paste from** —
`art-orders.py` assembles both halves for you, so nothing here has to be retyped
per panel.

The prompt splits into a durable half and a per-shot half, and keeping them apart
is most of the discipline:

| | lives in | how often you paste it |
|---|---|---|
| style bible, cast, reference convention, fixed marks, default size | the **Project's custom instructions** | once |
| continuity line, camera move, panel prompt, size | the **chat message**, with the two images attached | per panel |

Retyping the durable half per panel is itself a drift source — a clause dropped in
week three is a look changed in week three. Put it in the Project once and the
per-panel order is four lines. `art-orders.py` prints the project block under
**Project instructions — paste once**, and every panel order below it carries only
its own four lines, with a `<details>` fallback holding the fully-inlined prompt for
a chat with no Project loaded.

## Working in ChatGPT Plus specifically

**Use a Project.** Create one for the book. Put the style bible in the project
instructions and the character sheets in the project files. Every chat inside it
starts with the look and the cast already loaded, so you never retype the bible and
never get a stylistically different Act I page in week three.

**One thread per sequence, not per image.** Within a thread the model can see the
images already in it, so "the man from the image above, now facing camera" works and
gets stronger as the thread grows. Start a fresh thread when the thread gets long
enough that style starts wandering, and seed the new one by re-attaching the sheet.

**Attach, don't cite.** A filename in the prompt is text. Only an attached image is
an image. Re-attach the sheet even in a thread that already contains it once it has
scrolled well back.

**Iterate in place for small deltas.** For "same shot, half a step left" or "same
shot, his head down", reply in the thread asking for the change to *that* image
rather than starting a new prompt. For a genuine new camera setup, write the full
order — nudging an image toward a 90° angle change usually warps the face.

**No seeds, no guarantees.** ChatGPT gives you no seed and no identity-lock, so this
is a discipline for raising the hit rate, not a mechanism. Budget 2–4 attempts on a
hard angle. Accept the one that matches, discard the rest, and never keep a
near-miss for schedule reasons — a drifted panel becomes the reference for the next
one and the error compounds.

## Give yourself things that are checkable

Faces are hard to compare by eye; **asymmetries are easy**. Write two or three
deliberate, verifiable marks into each character sheet and check them on every
delivery. This cast already has some — use them:

- the band is on the **left** wrist, always;
- the visitor has **two** throat ridges, not three;
- Walt's sleeves are rolled, and the rig is on his belt, not a shoulder strap.

Add per-character marks of your own — a scar over one brow, one sleeve rolled higher
than the other — and put them in the sheet text in `script/act1.json`. They cost one
clause and turn "does this look like him?" into a yes/no check.

**The five things to check on every render**, in order of how often they drift:
hairline, beard boundary, nose bridge, eye spacing, ear shape. Then the asymmetries.
Then wardrobe state.

## What the pipeline gives you

Three optional fields per panel in `script/act1.json`:

```json
{ "id": "4b", "area": "b",
  "prompt": "Close on WALT's cupped hands in cold creek water, his own reflection broken. His eyes have just lifted off the water toward something out of frame right.",
  "camera": "Camera now low and close at the waterline, facing him",
  "refs": ["images/4a.png"],
  "continuity": "same man as 4a, same hour — three weeks of forest on him, wet to the forearms; the face is the sheet, not a new face." }
```

- **`refs`** — previous panels this shot must match. `art-orders.py` prints them as
  an attachment list, flagging any that aren't rendered yet, which incidentally gives
  you the **render order**: a panel whose refs are missing is not ready to order.
- **`continuity`** — one sentence on what carries over from the previous shot.
- **`camera`** — the new setup, phrased as a move from the previous one. This is the
  field that does layer 3's work. A panel with `refs` but no `camera` gets a warning
  in the order, because describing the subject afresh is exactly what re-rolls the
  face.

And one list in `script/template.json`, `fixed_marks` — the checkable asymmetries,
which `art-orders.py` folds into the project instructions so they ride on every
prompt without being retyped.

Act I's Walt panels are already chained this way: `4a → 4b → 5a → 6c → 7a → 8c →
9b → 10b/10a → 11a → 11c/11d → 12a → 13a/13b`. Run `python3 tools/art-orders.py`
and each order arrives with its own attachment list.

## The worked example

Panel `4a` is Walt walking a creek bed, small in frame, seen from behind and above.
Panel `4b` is close on his cupped hands with his eyes lifting toward camera. Almost
no shared pixels; maximum drift risk.

**Order for 4b** — attach `images/ref/walt-sheet.png`, then `images/4a.png`:

> Two references attached. Image 1 is the character sheet: reproduce this exact face
> — hairline, beard boundary, nose, eye spacing — and this exact wardrobe. Image 2
> is the immediately preceding shot in the same minute; match its light, water,
> stone and dirt.
>
> [style bible]
>
> Same man, same creek, one minute later. Camera now low and close at the waterline,
> facing him. Close on WALT's cupped hands in cold creek water, his own reflection
> broken. His eyes have just lifted off the water toward something out of frame
> right. Do not restyle him, do not idealize him, do not clean him up. Three weeks
> unwashed. Band is on the left wrist.
>
> Image size 3040x1888.

Check the delivery against the sheet on the five points above before you set
`"image": "images/4b.png"` in the script. If it fails, reroll against the sheet —
never against the failed render.
