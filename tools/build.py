#!/usr/bin/env python3
"""Compose a graphic novel from script/*.json + images/ into build/index.html.

Panels with an `image` render as art. Panels without one render as an ART ORDER
card showing their generation prompt -- so the same build is both the reading
mockup and the brief for the art still to be made.
"""
import base64, json, mimetypes, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT  = ROOT / "build" / "index.html"
OUT_EMBED = ROOT / "build" / "index-embedded.html"
OUT_ART   = ROOT / "build" / "reader.artifact.html"

# Each layout is a CSS grid: (rows, cols, {area: (r1,c1,r2,c2)}, overlaps)
LAYOUTS = {
    "splash":           ("1fr", "1fr", {"a": (1,1,2,2)}),
    "stack2":           ("1fr 1fr", "1fr", {"a": (1,1,2,2), "b": (2,1,3,2)}),
    "stack2-silent":    ("1.55fr 1fr", "1fr", {"a": (1,1,2,2), "b": (2,1,3,2)}),
    "row3-tall":        ("1fr 1fr 1fr", "1fr", {"a": (1,1,2,2), "b": (2,1,3,2), "c": (3,1,4,2)}),
    "strip3":           ("1fr 1.2fr 1fr", "1fr", {"a": (1,1,2,2), "b": (2,1,3,2), "c": (3,1,4,2)}),
    "wide-plus-2":      ("1.35fr 1fr", "1fr 1fr", {"a": (1,1,2,3), "b": (2,1,3,2), "c": (2,2,3,3)}),
    "grid4":            ("1fr 1fr", "1fr 1fr", {"a": (1,1,2,2), "b": (1,2,2,3), "c": (2,1,3,2), "d": (2,2,3,3)}),
    "grid9":            ("1fr 1fr 1fr", "1fr 1fr 1fr",
                         {k: (r, c, r+1, c+1) for k, (r, c) in
                          zip("abcdefghi", [(r, c) for r in (1,2,3) for c in (1,2,3)])}),
    # hero stays exactly 4:5; the two supporting slots are sized to stay inside
    # gpt-image-2's 3:1 edge-ratio cap (2.82:1 and 2.59:1)
    "hero45-plus-2":    ("2.22fr 1fr", "2.26fr 1fr",
                         {"a": (1,1,2,2), "b": (1,2,2,3), "c": (2,1,3,3)}),
    # a hero above a full-bleed sliver: for art that arrives far wider than any
    # ordinary panel. The strip ratio (~9.97:1) is set by the art, not the reverse.
    "hero-plus-strip":  ("11.416fr 1fr", "1fr", {"a": (1,1,2,2), "c": (2,1,3,2)}),
    "tall-plus-inset":  ("1fr 1fr 1fr 1fr", "1fr 1fr 1fr 1fr",
                         {"a": (1,1,5,5), "b": (3,2,5,5)}),
}
INSET = {"tall-plus-inset": {"b"}}


def grid_of(pg):
    """(rows, cols, areas, inset) for a page -- inline `grid` wins over `layout`."""
    g = pg.get("grid")
    if g:
        areas = {k: tuple(v) for k, v in g["areas"].items()}
        return g["rows"], g["cols"], areas, set(g.get("inset", []))
    rows, cols, areas = LAYOUTS[pg["layout"]]
    return rows, cols, areas, INSET.get(pg["layout"], set())

POS = {
    "tl": "top:0;left:0",            "tc": "top:0;left:50%;translate:-50% 0",
    "tr": "top:0;right:0",           "bl": "bottom:0;left:0",
    "bc": "bottom:0;left:50%;translate:-50% 0", "br": "bottom:0;right:0",
    "cc": "top:50%;left:50%;translate:-50% -50%",
}

def esc(s):
    return (s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;"))

def markup(s):
    """*emphasis* -> <em>, preserving escaping."""
    return re.sub(r"\*(.+?)\*", r"<em>\1</em>", esc(s))

def data_uri(rel):
    p = ROOT / rel
    if not p.exists():
        return None
    mime = mimetypes.guess_type(p.name)[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()

def caption(c):
    cls = "cap" + (" emph" if c.get("emph") else "")
    return f'<div class="{cls}" style="{POS[c.get("pos","tl")]}">{markup(c["text"])}</div>'

def panel(p, areas, insets, embed):
    r1,c1,r2,c2 = areas[p["area"]]
    inset = p["area"] in insets
    style = f"grid-area:{r1}/{c1}/{r2}/{c2}"
    cls = "panel" + (" inset" if inset else "") + (" black" if p.get("black") else "")
    body = ""
    if p.get("black"):
        body = ""
    elif p.get("image"):
        src = data_uri(p["image"]) if embed else "../" + p["image"]
        if src:
            body = (f'<img src="{src}" alt="" loading="lazy" '
                    f'style="object-position:{p.get("focal","50% 50%")}">')
        else:
            body = f'<div class="missing">missing file: {esc(p["image"])}</div>'
    else:
        body = ('<div class="order"><div class="order-id">ART ORDER · panel '
                f'{esc(p["id"])}</div><p>{esc(p["prompt"])}</p></div>')
    caps = "".join(caption(c) for c in p.get("captions", []))
    return f'<figure class="{cls}" style="{style}">{body}{caps}</figure>'

def page(pg, meta, embed):
    rows, cols, areas, insets = grid_of(pg)
    inner = "".join(panel(p, areas, insets, embed) for p in pg["panels"])
    over = ""
    if pg.get("title_card"):
        over = (f'<div class="titlecard"><h1>{esc(meta["title"])}</h1>'
                f'<div class="sub">{esc(meta["subtitle"])}</div>'
                f'<div class="by">{esc(meta["byline"])}</div></div>')
    if pg.get("end_card"):
        over = f'<div class="endcard">{esc(pg["end_card"])}</div>'
    return (f'<section class="page" id="p{pg["n"]}" '
            f'style="grid-template-rows:{rows};grid-template-columns:{cols}">'
            f'{inner}{over}'
            f'<div class="folio"><span>{esc(pg["act"])}</span>{pg["n"]}</div>'
            f'</section>')

CSS = """
:root{--pw:{PW}px;--ph:{PH}px;--gutter:clamp(4px,{GUTVW}vw,{GUT}px);
  --ink:#e6e4de;--paper:#0a0c0d;--nettle:#8fa38f;--brass:#c9a86a;--rule:#262b2c;
  --prose:"Spectral","Iowan Old Style",Palatino,Georgia,serif;
  --file:"IBM Plex Mono",ui-monospace,Menlo,monospace}
*{box-sizing:border-box}
html{scroll-snap-type:y proximity}
body{margin:0;background:#111314;color:var(--ink);
  font:300 16px/1.5 var(--prose);
  display:flex;flex-direction:column;align-items:center;gap:34px;padding:34px 12px 80px}
.page{position:relative;width:min(var(--pw),100%);aspect-ratio:{PW}/{PH};
  background:var(--paper);display:grid;container-type:inline-size;
  gap:var(--gutter);padding:var(--gutter);box-shadow:0 18px 60px #0009;
  scroll-snap-align:center}
/* --u is one design pixel: 1/PW of the page's actual width, whatever that is.
   cqw resolves against .page, so it must be declared on descendants, not on .page. */
.page>*{--u:calc(100cqw / {PW})}
.panel{position:relative;margin:0;overflow:hidden;background:#05070a;
  border:1px solid #000;isolation:isolate}
.panel img{width:100%;height:100%;object-fit:cover;display:block;filter:saturate(.92) contrast(1.04)}
.panel.black{background:#000;border-color:#000}
.panel.inset{outline:3px solid var(--paper);z-index:2;box-shadow:0 0 0 1px #000,0 10px 30px #000b}
/* caption boxes: prose-comic register, not dialogue balloons */
.cap{position:absolute;max-width:62%;margin:max(6px,calc(16*var(--u)));
  padding:max(5px,calc(10*var(--u))) max(7px,calc(13*var(--u)));
  background:rgba(6,8,9,.9);border:1px solid var(--rule);border-left:max(2px,calc(3*var(--u))) solid var(--nettle);
  color:var(--ink);font-size:max(11px,calc(15*var(--u)));line-height:1.45;
  letter-spacing:.005em;
  backdrop-filter:blur(3px);text-wrap:pretty;z-index:3}
.cap.emph{border-left-color:var(--brass);font-style:normal;background:rgba(10,9,7,.93)}
.cap em{font-style:italic;color:#fff}
.cc.cap,.cap[style*="-50% -50%"]{max-width:74%;text-align:center;border:none;
  border-top:1px solid #3a3f41;border-bottom:1px solid #3a3f41;background:transparent}
.order{height:100%;display:flex;flex-direction:column;justify-content:center;
  gap:max(5px,calc(10*var(--u)));padding:max(9px,calc(22*var(--u)));background:
   repeating-linear-gradient(45deg,#0c1013 0 12px,#0a0e10 12px 24px)}
.order-id{font:500 max(8px,calc(10*var(--u)))/1 var(--file);letter-spacing:.14em;
  color:#6d8a7a;text-transform:uppercase}
.order p{margin:0;font:300 max(9px,calc(13*var(--u)))/1.6 var(--file);color:#9aa6a2}
.missing{padding:20px;color:#c66;font:12px var(--file)}
.titlecard{position:absolute;inset:auto 0 12%;text-align:center;z-index:4}
.titlecard h1{margin:0;font-size:max(26px,calc(62*var(--u)));font-weight:200;letter-spacing:.055em;
  text-shadow:0 4px 30px #000,0 0 80px #000}
.titlecard .sub{margin-top:calc(10*var(--u));font:400 max(9px,calc(13*var(--u)))/1 var(--file);
  letter-spacing:.34em;color:#a9b6ad;text-transform:uppercase}
.titlecard .by{margin-top:calc(26*var(--u));font-size:max(11px,calc(15*var(--u)));color:#8e9691;letter-spacing:.1em}
.endcard{position:absolute;left:0;right:0;bottom:9%;text-align:center;z-index:4;
  font:400 max(9px,calc(13*var(--u)))/1 var(--file);letter-spacing:.3em;color:#e6e2d8;
  text-shadow:0 2px 24px #000}
.folio{position:absolute;right:var(--gutter);bottom:-24px;font:400 max(9px,calc(11*var(--u)))/1 var(--file);
  color:#5c6461;letter-spacing:.18em}
.folio span{margin-right:12px;color:#43494a}
@media (max-width:760px){
  .cap{max-width:92%;line-height:1.38;letter-spacing:0}
  .cap.emph,.cap[style*="-50% -50%"]{max-width:96%}
  .order p{font-size:max(10px,calc(13*var(--u)))}
}
.plate{width:var(--pw);max-width:100%;padding:6px 2px 0;color:#8f9997}
.plate h2{margin:0;font:200 30px/1.15 var(--prose);letter-spacing:.04em;color:#dfddd6}
.plate-sub{margin-top:8px;font:400 11px/1 var(--file);letter-spacing:.22em;
  text-transform:uppercase;color:var(--nettle)}
.plate-stat{margin-top:12px;padding-top:12px;border-top:1px solid var(--rule);
  font:300 12px/1.6 var(--file);color:#727b79}
@media print{
  .plate{display:none}
  @page{size:{INW}in {INH}in;margin:0}
  body{background:#fff;padding:0;gap:0;display:block}
  html{scroll-snap-type:none}
  .page{width:100%;height:100vh;aspect-ratio:auto;max-width:none;
    box-shadow:none;break-after:page}
  .folio{bottom:6px;color:#7b8380}
}
"""

def plate(data):
    m = data["meta"]
    total = sum(len(p["panels"]) for p in data["pages"])
    done  = sum(1 for p in data["pages"] for q in p["panels"] if q.get("image"))
    black = sum(1 for p in data["pages"] for q in p["panels"] if q.get("black"))
    return (f'<header class="plate"><h2>{esc(m["title"])}</h2>'
            f'<div class="plate-sub">{esc(m["subtitle"])} · {esc(m["byline"])}</div>'
            f'<div class="plate-stat">{len(data["pages"])} pages · {total} panels · '
            f'{done} rendered · {black} intentionally black · '
            f'{total-done-black} outstanding, shown as art orders</div></header>')


def main():
    embed = "--embed" in sys.argv
    data = json.loads((ROOT / "script" / "act1.json").read_text())
    m = data["meta"]
    css = (CSS.replace("{PW}", str(m["page_w"])).replace("{PH}", str(m["page_h"]))
              .replace("{GUT}", str(m.get("gutter", 14)))
              .replace("{GUTVW}", f'{m.get("gutter",14)/m["page_w"]*100:.3f}')
              .replace("{INW}", f'{m["page_w"]/200:.3f}').replace("{INH}", f'{m["page_h"]/200:.3f}'))
    pages = "\n".join(page(p, m, embed) for p in data["pages"])
    done = sum(1 for p in data["pages"] for q in p["panels"] if q.get("image"))
    total = sum(len(p["panels"]) for p in data["pages"])
    fonts = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
             'family=Spectral:ital,wght@0,200;0,300;0,400;1,300;1,400&'
             'family=IBM+Plex+Mono:wght@300;400;500&display=swap">')
    head = f'<title>{esc(m["title"])}</title>{fonts}<style>{css}</style>'
    if "--artifact" in sys.argv:
        # the host supplies <head>, so this file declares no charset of its own --
        # emit numeric character references so it renders right under any assumption
        html = f'{head}\n{plate(data)}\n{pages}\n'
        html = html.encode("ascii", "xmlcharrefreplace").decode("ascii")
    else:
        vp = '<meta name="viewport" content="width=device-width,initial-scale=1">'
        html = f'<!doctype html><meta charset="utf-8">{vp}{head}\n{pages}\n'

    out = OUT_ART if "--artifact" in sys.argv else (OUT_EMBED if embed else OUT)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(f"built {out.relative_to(ROOT)}  ·  {len(data['pages'])} pages  ·  "
          f"art {done}/{total} panels  ·  {len(html)//1024} KB"
          f"{'  (images embedded)' if embed else ''}")

if __name__ == "__main__":
    main()
