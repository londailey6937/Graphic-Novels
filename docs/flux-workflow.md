# Switching to Flux

*What to do, in order. The first step is the urgent one.*

## 1. Get the frames out of ChatGPT — before anything else

Walt's likeness exists in exactly one place: images sitting in a chat history you do
not control. Everything below depends on those files. Export them now:

- Every frame from the approved board, at full size — not the contact sheet, the
  individual images. Save them as `images/board/01.png` … `24.png`.
- Every good frame of **Walt's face** you can find, including outtakes and rejects
  that got the face right. Angle variety matters more than frame quality here:
  front, three-quarter both sides, profile, looking down, eyes closed. Save into
  `images/train/walt/`.
- Same for the visitor, if you want it consistent: `images/train/visitor/`.

Aim for **15–20 curated Walt images**, not 40 loose ones. A tight set beats a large
one, because the LoRA learns the average of what you feed it.

Commit them. That is the difference between a likeness you own and a likeness that
lives in someone's session history.

## 2. Train the LoRA

Replicate, roughly $2–5, about half an hour. Upload the curated folder, pick a
trigger token that is not a real word — `w4ltman`, not `walt` — and train against
Flux dev. You get a file back. Download it. That file is now the most valuable
artefact in the project.

Optionally a second, style LoRA trained on the 24 approved board frames, which
holds the palette and light across environments as well as people.

## 3. Render

`build/flux-prompts.md` has all 24 prompts, already inlined with the style and ready
to paste. Replace `<TRIGGER>` with your token.

    python3 tools/flux-prompts.py script/what-the-forest-kept.json

Settings for the screen edition: **1024x1280**, Flux dev, 28–32 steps, guidance
3.0–3.5. Flux schnell at 4 steps for composition proofs.

**Record the seed of every keeper.** This is the single largest gain from leaving a
chat interface: a prompt plus a seed is reproducible, so you can change one variable
and hold everything else. Put the seed in the script beside the panel. A frame you
can regenerate is a frame you can improve.

Save finals as `images/p01.png` … `p24.png` and the board, the reader and the
coverage report all pick them up with no further edits.

## What changes, and what does not

**Gone:** project instructions, attachment conventions, refusal handling. Open
weights do not refuse, so the dead-visitor and portrait refusals stop happening.
Reference sheets stop being something you attach per message — the LoRA carries
identity instead.

**Unchanged:** everything about *direction*. One ratio. The transition rules — one
variable per cut, hold screen direction, climb the scale ladder, time moves forward
visibly, objects persist, never two actorless frames in a row. Anchors ordered
against the prose. A caption is not the image. Marks that are counts and presence,
never sides.

**Still broken in Flux:** laterality. Horizontal flips are standard training
augmentation everywhere, so left and right remain unstable no matter which model you
use. Keep phrasing it as exclusivity — "the only thing on either forearm" — and
never as a side.

## Local or hosted

M2 Pro, 16GB unified, 43GB free.

**Hosted** (Replicate/fal): cents per image, seconds, nothing installed. Required for
training regardless.

**Local** (Draw Things, free, Mac App Store): quantised Flux at ~7GB, renders in
minutes rather than seconds at 1024x1280, free per image, unlimited iteration. Needs
20–30GB of disk — clear space first, 91% full is tight.

Start hosted to get moving. Add Draw Things when iteration volume, not cost, becomes
the thing that hurts.
