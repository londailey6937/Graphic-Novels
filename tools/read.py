#!/usr/bin/env python3
"""Build the reading edition: continuous prose, art synced in a second column.

    python3 tools/read.py            -> build/read.html          (links to images/)
    python3 tools/read.py --embed    -> build/read.artifact.html  (self-contained)

Three things beyond plain prose:
  * every beat carries its art order inline -- panel id, standard size, state, and a
    link that brings the image up (or to the appendix entry when it isn't drawn yet)
  * the beat you are reading is marked, and a rail shows where that sits in the run
  * an art-order appendix at the end, one row per panel, linked both ways
"""
import base64, io, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_EDGE, JPEG_Q = 1600, 80


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def markup(s):
    return re.sub(r"\*(.+?)\*", r"<em>\1</em>", esc(s))


def panel_index():
    """panel id -> {image, prompt, page}. Shared with the panel-edition build."""
    d = json.loads((ROOT / "script" / "act1.json").read_text())
    out = {}
    for pg in d["pages"]:
        for p in pg["panels"] + pg.get("reserve", []):
            out[p["id"]] = {"image": p.get("image"), "prompt": p.get("prompt", ""),
                            "page": pg["n"]}
    return out


def embed_img(rel):
    p = ROOT / rel
    try:
        from PIL import Image
        im = Image.open(p).convert("RGB")
        w, h = im.size
        if max(w, h) > MAX_EDGE:
            k = MAX_EDGE / max(w, h)
            im = im.resize((round(w * k), round(h * k)), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=JPEG_Q, optimize=True, progressive=True)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()


CSS = """
:root{
  --paper:#0a0c0d; --ink:#e6e3da; --dim:#79817d; --nettle:#8fa38f; --brass:#c9a86a;
  --rule:#202627; --pend:#8d8464;
  --prose:"Spectral","Iowan Old Style",Palatino,Georgia,serif;
  --file:"IBM Plex Mono",ui-monospace,Menlo,monospace;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--ink);
  font:300 20px/1.78 var(--prose);-webkit-font-smoothing:antialiased}
a{color:inherit}
:focus-visible{outline:2px solid var(--brass);outline-offset:3px}

.masthead{max-width:96rem;margin:0 auto;padding:14vh 5vw 10vh}
.masthead h1{margin:0;font-size:clamp(2.6rem,6vw,4.6rem);font-weight:200;
  letter-spacing:.02em;line-height:1.04;text-wrap:balance}
.masthead .act{margin-top:1.6rem;font:400 .72rem/1 var(--file);letter-spacing:.34em;
  text-transform:uppercase;color:var(--nettle)}
.masthead .by{margin-top:.8rem;font:300 .95rem/1 var(--prose);color:var(--dim);
  letter-spacing:.08em}
.masthead .std{margin-top:2.4rem;font:300 .74rem/1.7 var(--file);color:var(--dim);
  letter-spacing:.04em}
.masthead .rule{margin-top:2.4rem;height:1px;background:var(--rule)}

.spread{max-width:96rem;margin:0 auto;padding:0 5vw 18vh;
  display:grid;grid-template-columns:minmax(0,33em) minmax(0,1fr);
  column-gap:4.5vw;align-items:start}
.prose{min-width:0}
.section{margin:0 0 5.5rem}
.section-mark{display:flex;align-items:center;gap:1.1rem;margin:0 0 2.2rem;
  font:400 .72rem/1 var(--file);letter-spacing:.3em;color:var(--nettle)}
.section-mark::after{content:"";flex:1;height:1px;background:var(--rule)}
p{margin:0 0 1.75rem;text-wrap:pretty;hyphens:auto}
p em{font-style:italic;color:#fff}

/* a beat: its art order, then its prose. The rule marks where you are reading. */
.beat{position:relative;padding-left:1.25rem;margin-left:-1.25rem;
  border-left:2px solid transparent;transition:border-color .4s ease}
.beat.live{border-left-color:var(--brass)}
.beat p{margin-bottom:1.75rem}
.mark{display:flex;flex-wrap:wrap;gap:.2rem .8rem;align-items:baseline;
  margin:0 0 .5rem;font:400 .62rem/1.5 var(--file);letter-spacing:.17em;
  text-transform:uppercase;color:var(--dim)}
.mark a{color:var(--nettle);text-decoration:none;
  border-bottom:1px solid rgba(143,163,143,.35);cursor:pointer}
.mark a:hover{border-bottom-color:var(--nettle)}
.mark .size{font-variant-numeric:tabular-nums}
.mark .state{color:var(--dim)}
.beat.pending .mark a{color:var(--pend);border-bottom-style:dashed;
  border-bottom-color:rgba(141,132,100,.45)}
.beat.live .mark a{color:var(--brass);border-bottom-color:var(--brass)}

.coda{margin:1rem 0 0;font:400 .72rem/1.6 var(--file);letter-spacing:.22em;
  text-transform:uppercase;color:var(--dim)}

/* the rail: one tick per panel, in reading order */
.rail{position:fixed;left:1.4vw;top:50%;transform:translateY(-50%);z-index:8;
  display:flex;flex-direction:column;gap:.42rem;padding:.5rem .35rem}
.rail a{display:block;width:11px;height:2px;background:var(--rule);
  border-radius:1px;transition:background .3s,width .3s}
.rail a.drawn{background:#3d4a42}
.rail a.on{background:var(--brass);width:20px}
.rail .sec{margin:.5rem 0 .2rem;font:400 .5rem/1 var(--file);letter-spacing:.14em;
  color:#4a5250}

/* the art column */
.art{position:sticky;top:12vh;height:76vh;min-width:0}
.frame{display:flex;flex-direction:column;gap:.9rem;margin-bottom:2rem}
.frame img{display:block;width:100%;height:auto;object-fit:contain}
.art:not(.live) .frame img{background:#05070a;border:1px solid var(--rule)}
.plate{display:flex;flex-wrap:wrap;gap:.9rem;align-items:baseline;
  font:400 .66rem/1.5 var(--file);letter-spacing:.16em;text-transform:uppercase;
  color:var(--dim)}
.plate b{color:var(--nettle);font-weight:500}
.plate .count{margin-left:auto;font-variant-numeric:tabular-nums;color:#5d6462}
.art.live{display:block}
.art.live .frame{position:absolute;inset:0;justify-content:center;margin:0;
  opacity:0;visibility:hidden;transition:opacity .55s ease}
.art.live .frame.on{opacity:1;visibility:visible}
.art.live .frame img{flex:1 1 auto;min-height:0}
.art.live .frame .plate{flex:0 0 auto}
@media (prefers-reduced-motion:reduce){
  html{scroll-behavior:auto}
  .art.live .frame,.beat,.rail a{transition:none}
}

/* the appendix */
.orders{max-width:96rem;margin:0 auto;padding:0 5vw 16vh}
.orders h2{margin:0 0 2rem;font:400 .72rem/1 var(--file);letter-spacing:.3em;
  text-transform:uppercase;color:var(--nettle)}
.orders table{width:100%;border-collapse:collapse;font:300 .82rem/1.6 var(--file)}
.orders th{text-align:left;padding:.6rem .9rem .6rem 0;border-bottom:1px solid var(--rule);
  font-weight:500;font-size:.62rem;letter-spacing:.18em;text-transform:uppercase;
  color:var(--dim)}
.orders td{padding:.75rem .9rem .75rem 0;border-bottom:1px solid #14191a;
  vertical-align:top;color:#a8b0ac}
.orders td.id a{color:var(--nettle);text-decoration:none;
  border-bottom:1px solid rgba(143,163,143,.35)}
.orders tr.pending td.id a{color:var(--pend);border-bottom-style:dashed}
.orders td.size{font-variant-numeric:tabular-nums;white-space:nowrap;color:#8e9591}
.orders td.st{white-space:nowrap;font-size:.62rem;letter-spacing:.16em;
  text-transform:uppercase;color:var(--dim)}
.orders tr.drawn td.st{color:var(--nettle)}
.orders td.pr{font:300 .84rem/1.6 var(--prose);color:#9aa19c}
.orders .wrap{overflow-x:auto}
.orders .foot{max-width:44em;margin:-1rem 0 2rem;font:300 .84rem/1.7 var(--prose);
  color:var(--dim)}

/* Two device targets: tablet and desktop. Phone is out of scope — the prose
   measure and the art column cannot both survive 402px, and the fix for that is a
   different reader, not a breakpoint. Tablet portrait is the narrow floor. */
@media (max-width:1024px){ .rail{display:none} }
@media (max-width:1024px){
  .spread{display:flex;flex-direction:column;align-items:stretch;padding:0 7vw 14vh}
  .art{order:-1;position:sticky;top:0;height:auto;padding:.9rem 0 1rem;z-index:5;
    background:var(--paper);border-bottom:1px solid var(--rule);margin-bottom:2rem}
  .art.live .frame{position:static;display:none;opacity:1;visibility:visible;
    transition:none;margin:0;gap:.6rem}
  .art.live .frame.on{display:flex}
  .art.live .frame img{flex:none;width:auto;max-width:100%;max-height:40vh;
    height:auto;margin:0 auto}
  body{font-size:19px;line-height:1.75}
  .masthead{padding:9vh 7vw 7vh}
  .orders{padding:0 7vw 12vh}
}
@media print{
  body{background:#fff;color:#111;
    -webkit-print-color-adjust:exact;print-color-adjust:exact}
  .rail{display:none}
  .spread{display:block;max-width:34em}
  .art{position:static;height:auto}
  .art.live .frame{position:static;opacity:1;visibility:visible;
    break-inside:avoid;margin:1.5rem 0}
  .beat.live{border-left-color:transparent}
}
"""

JS = """
(function(){
  var art = document.querySelector('.art');
  var frames = [].slice.call(art.querySelectorAll('.frame'));
  var beats  = [].slice.call(document.querySelectorAll('.beat'));
  var ticks  = {};
  [].forEach.call(document.querySelectorAll('.rail a'), function(t){
    ticks[t.dataset.panel] = t;
  });
  var byArt = {};
  frames.forEach(function(f){ byArt[f.dataset.art] = f; });
  if (frames.length) art.classList.add('live');

  var shownArt = null, liveBeat = null;
  function showArt(id){
    var f = byArt[id];
    if (!f || f === shownArt) return;
    if (shownArt) shownArt.classList.remove('on');
    f.classList.add('on');
    shownArt = f;
  }
  function setLive(beat){
    if (beat === liveBeat) return;
    if (liveBeat) {
      liveBeat.classList.remove('live');
      var pt = ticks[liveBeat.dataset.panel];
      if (pt) pt.classList.remove('on');
    }
    beat.classList.add('live');
    var t = ticks[beat.dataset.panel];
    if (t) t.classList.add('on');
    liveBeat = beat;
    if (beat.dataset.art) showArt(beat.dataset.art);
  }
  if (frames.length) showArt(frames[0].dataset.art);
  if (beats.length) setLive(beats[0]);

  // the beat occupying the reading band owns the rail and, if it has art, the column
  var io = new IntersectionObserver(function(entries){
    entries.forEach(function(e){ if (e.isIntersecting) setLive(e.target); });
  }, { rootMargin: '-16% 0px -64% 0px', threshold: 0 });
  beats.forEach(function(b){ io.observe(b); });

  // an inline art order or a rail tick brings its image up without leaving the page
  document.addEventListener('click', function(ev){
    var a = ev.target.closest('[data-jump]');
    if (!a) return;
    var id = a.dataset.jump;
    if (byArt[id]) { ev.preventDefault(); showArt(id); }
    var beat = document.querySelector('.beat[data-panel="' + id + '"]');
    if (beat && a.classList.contains('tick')) {
      ev.preventDefault();
      beat.scrollIntoView({ block: 'center' });
    }
  });
})();
"""


def main():
    embed = "--embed" in sys.argv
    story = json.loads((ROOT / "script" / "story.json").read_text())
    tpl = json.loads((ROOT / "script" / "template.json").read_text())
    m = story["meta"]
    idx = panel_index()
    stdw, stdh = tpl["art"]["size"]
    label = tpl["art"]["label"]
    exc = tpl["exceptions"]

    # every anchored panel in reading order, whether drawn yet or not
    seq = []
    for sec in story["sections"]:
        for b in sec["blocks"]:
            pid = b.get("art")
            if pid and not any(s["id"] == pid for s in seq):
                info = idx.get(pid, {"image": None, "prompt": "", "page": None})
                seq.append({"id": pid, "sec": sec["n"], **info})
    drawn = [s for s in seq if s["image"]]

    def order_link(s, cls="", jump=True):
        href = ("../" + s["image"]) if (s["image"] and not embed) else f'#order-{s["id"]}'
        j = f' data-jump="{s["id"]}"' if jump else ""
        return f'<a href="{href}"{j} class="{cls}">{s["id"].upper()}</a>'

    # --- prose column ---------------------------------------------------------
    body = []
    for sec in story["sections"]:
        body.append(f'<section class="section"><h2 class="section-mark">{esc(sec["n"])}</h2>')
        for b in sec["blocks"]:
            pid = b.get("art")
            if not pid:
                body.append(f'<p>{markup(b["text"])}</p>')
                continue
            s = next(x for x in seq if x["id"] == pid)
            is_drawn = bool(s["image"])
            size = f'{stdw}×{stdh}'
            state = "rendered" if is_drawn else "pending"
            note = f' · <span class="state">{esc(exc[pid].split("—")[0].strip())}</span>' \
                   if pid in exc else ""
            cls = "beat" + ("" if is_drawn else " pending")
            artattr = f' data-art="{pid}"' if is_drawn else ""
            body.append(
                f'<div class="{cls}" id="beat-{pid}" data-panel="{pid}"{artattr}>'
                f'<div class="mark">{order_link(s)}'
                f'<span class="size">{label} {size}</span>'
                f'<span class="state">{state}</span>{note}</div>'
                f'<p>{markup(b["text"])}</p></div>')
        body.append("</section>")
    body.append(f'<p class="coda">[ {esc(m["continued"])} ]</p>')

    # --- art column -----------------------------------------------------------
    art = []
    for i, s in enumerate(drawn, 1):
        src = embed_img(s["image"]) if embed else "../" + s["image"]
        art.append(f'<figure class="frame" id="art-{esc(s["id"])}" data-art="{esc(s["id"])}">'
                   f'<img src="{src}" alt="" decoding="async">'
                   f'<figcaption class="plate"><b>{esc(s["sec"])}</b>{esc(s["id"])}'
                   f'<span class="count">{i} / {len(drawn)}</span></figcaption></figure>')

    # --- rail -----------------------------------------------------------------
    rail, last_sec = [], None
    for s in seq:
        if s["sec"] != last_sec:
            rail.append(f'<div class="sec">{esc(s["sec"])}</div>')
            last_sec = s["sec"]
        cls = "tick" + (" drawn" if s["image"] else "")
        rail.append(f'<a href="#beat-{s["id"]}" class="{cls}" data-jump="{s["id"]}" '
                    f'data-panel="{s["id"]}" title="{esc(s["sec"])} {esc(s["id"])}'
                    f'{" (pending)" if not s["image"] else ""}"></a>')

    # --- appendix -------------------------------------------------------------
    rows = []
    for s in seq:
        st = "rendered" if s["image"] else "pending"
        cls = "drawn" if s["image"] else "pending"
        rows.append(f'<tr class="{cls}" id="order-{esc(s["id"])}">'
                    f'<td class="id">{order_link(s)}</td>'
                    f'<td class="st">{esc(s["sec"])}</td>'
                    f'<td class="size">{stdw}×{stdh}</td>'
                    f'<td class="st">{st}</td>'
                    f'<td class="pr">{esc(s["prompt"])}</td></tr>')
    total_panels = len([1 for k, v in idx.items()])
    foot = ""
    if total_panels != len(seq):
        foot = (f'<p class="foot">{len(seq)} of the panel edition\u2019s {total_panels} '
                f'panels are anchored to a paragraph here. The rest are page-composition '
                f'beats with no sentence of their own \u2014 paragraph counts and panel '
                f'counts do not have to match.</p>')
    appendix = (f'<section class="orders"><h2>Art orders · {len(drawn)} of {len(seq)} '
                f'rendered</h2>{foot}<div class="wrap"><table><thead><tr>'
                f'<th>Panel</th><th>Sec</th><th>Size</th><th>State</th><th>Order</th>'
                f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div></section>')

    fonts = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
             'family=Spectral:ital,wght@0,200;0,300;0,400;1,300;1,400&'
             'family=IBM+Plex+Mono:wght@300;400;500&display=swap">')
    act = m["act"].split("—")[0].strip()
    head = f'<title>{esc(m["title"])} — {esc(act)}</title>{fonts}<style>{CSS}</style>'
    pr = tpl.get("print", {})
    std = (f'One ratio throughout: every panel is {label} {stdw}×{stdh} '
           f'({tpl["art"]["ratio"][0]}:{tpl["art"]["ratio"][1]}).')
    if pr:
        tw, th = pr["trim_in"]
        std += (f' That is {pr["dpi"]}dpi on an {tw}×{th}in trim — print resolution, '
                'not screen resolution.')
    tg = tpl.get("targets", {})
    if tg:
        std += (f' Built for {" and ".join(tg["devices"])}; '
                f'{tg["min_width"]}px is the narrow floor.')
    page = (f'<nav class="rail" aria-label="Art anchors">{"".join(rail)}</nav>'
            f'<header class="masthead"><h1>{esc(m["title"])}</h1>'
            f'<div class="act">{esc(m["act"])}</div>'
            f'<div class="by">{esc(m["byline"])}</div>'
            f'<div class="std">{esc(std)}</div><div class="rule"></div></header>'
            f'<main class="spread"><div class="prose">{"".join(body)}</div>'
            f'<aside class="art">{"".join(art)}</aside></main>'
            f'{appendix}<script>{JS}</script>')

    if embed:
        html = (head + "\n" + page).encode("ascii", "xmlcharrefreplace").decode("ascii")
        out = ROOT / "build" / "read.artifact.html"
    else:
        html = ('<!doctype html><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                + head + "\n" + page)
        out = ROOT / "build" / "read.html"
    out.write_text(html)
    words = sum(len(b["text"].split()) for s in story["sections"] for b in s["blocks"])
    print(f"built {out.relative_to(ROOT)} · {words} words · "
          f"{len(drawn)}/{len(seq)} panels rendered · {len(html)//1024} KB")


if __name__ == "__main__":
    main()
