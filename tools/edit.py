#!/usr/bin/env python3
"""Edit the story against the pictures. A local editor for the panel edition.

    python3 tools/edit.py                                  # the current script
    python3 tools/edit.py script/what-the-forest-kept.json --port 8000

Opens a page showing every paragraph in reading order beside the panel it is
anchored to. Change the prose, move it to a different panel, move the caption to
a different corner, save. Rebuild without leaving the page.

Why this exists: a caption and its picture are one unit, but they live in
different places -- the text in `sections[].blocks[]`, the art in `panels{}` --
and judging a caption means seeing the frame it sits on. Editing the JSON by hand
means holding the image in your head. This puts them side by side.

The thing it is really for: **prose with no anchor never reaches the panel
edition.** The reading edition prints every paragraph; the panel edition prints
only what a panel carries. So an unanchored block is invisible there, and a story
can look finished in one edition and stop short in the other. Those blocks are
listed first here, and flagged in place, because they are the actual worklist.

Nothing is written until you press Save, and Save rewrites only text, anchors,
caption position and prompts -- never structure.
"""
import json, io, re, subprocess, sys, threading, time, webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote

ROOT = Path(__file__).resolve().parent.parent
THUMB_W = 900
POSITIONS = ["tl", "tc", "tr", "bl", "bc", "br", "cc"]

# kind -> (builder, built file). The linked builds, not the embedded ones: they
# rebuild in about a second and reference ../images, which resolves once /images
# is mounted. Embedding 25 plates to look at a page would cost ~9MB a click.
EDITIONS = {
    "read":  ("tools/read.py",  "build/read.html",  "Reading edition"),
    "panel": ("tools/build.py", "build/index.html", "Panel edition"),
}

# The one piece of furniture the preview keeps: a way back. Fixed, small, and
# out of the way -- it is navigation, not an editing control.
BACK_BAR = """<style>
/* inline-flex, not inline: an inline anchor's padding paints but gives no
   reliable hit box, so only the glyphs themselves took the click */
#back-to-edit{position:fixed;top:12px;right:12px;z-index:99999;
  display:inline-flex;align-items:center;gap:6px;cursor:pointer;
  font:600 12px/1 -apple-system,"Helvetica Neue",Arial,sans-serif;letter-spacing:.04em;
  background:#c9a86a;color:#191308;text-decoration:none;padding:11px 16px;
  border-radius:6px;box-shadow:0 2px 12px rgba(0,0,0,.5);opacity:.55;
  transition:opacity .15s}
#back-to-edit *{pointer-events:none}
#back-to-edit:hover{opacity:1}
@media print{#back-to-edit{display:none}}
</style><a id="back-to-edit" href="/">&larr; Editing</a>"""

_thumbs = {}


def plate_size(rel):
    """(w, h) of the file on disk, or None. Needs Pillow; without it the ratio
    check just goes quiet rather than guessing."""
    p = ROOT / rel
    if not p.exists():
        return None
    try:
        from PIL import Image
        with Image.open(p) as im:
            return im.size
    except ImportError:
        return None


def thumb(rel):
    """A cell-sized JPEG of a plate, cached. The plates are 2432px wide; loading
    24 of them raw would be ~160MB for a page whose job is to show you a face.

    Keyed on the file's mtime, not just its path: `render.py` run from a terminal
    replaces a plate without this process ever hearing about it, and a cache keyed
    on path alone then serves the old picture for as long as the editor is up --
    which looks exactly like the render having silently failed."""
    p = ROOT / rel
    if not p.exists():
        _thumbs.pop(rel, None)
        return None
    key = (rel, p.stat().st_mtime_ns)
    hit = _thumbs.get(rel)
    if hit and hit[0] == key:
        return hit[1]
    try:
        from PIL import Image
        im = Image.open(p).convert("RGB")
        if im.width > THUMB_W:
            im = im.resize((THUMB_W, round(im.height * THUMB_W / im.width)),
                           Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82, optimize=True)
        data = buf.getvalue()
    except ImportError:
        data = p.read_bytes()
    _thumbs[rel] = (key, data)
    return data


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>%(title)s — editor</title>
<style>
:root{--paper:#0d0f10;--ink:#e6e3da;--dim:#7d857f;--nettle:#8fa38f;--brass:#c9a86a;
  --rule:#242a2b;--warn:#c98a5a;--card:#141719}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
  font:400 15px/1.55 "Iowan Old Style",Palatino,Georgia,serif}
header{position:sticky;top:0;z-index:9;background:#0d0f10ee;backdrop-filter:blur(8px);
  border-bottom:1px solid var(--rule);padding:14px 22px;display:flex;gap:14px;
  align-items:center;flex-wrap:wrap}
h1{font-size:17px;margin:0;font-weight:600;letter-spacing:.01em}
.sub{color:var(--dim);font-size:13px}
button{font:inherit;font-size:13px;padding:7px 15px;border-radius:6px;cursor:pointer;
  border:1px solid var(--rule);background:#1b1f21;color:var(--ink)}
button.primary{background:var(--brass);color:#191308;border-color:var(--brass);font-weight:600}
button:disabled{opacity:.45;cursor:default}
#status{color:var(--dim);font-size:13px;margin-left:auto;font-family:ui-monospace,monospace}
.gap{width:1px;height:22px;background:var(--rule);margin:0 4px}
main{max-width:1180px;margin:0 auto;padding:26px 22px 120px}
.sec{color:var(--nettle);font-size:12px;letter-spacing:.16em;text-transform:uppercase;
  margin:36px 0 14px;padding-bottom:7px;border-bottom:1px solid var(--rule)}
.row{display:grid;grid-template-columns:270px 1fr;gap:20px;padding:18px;margin-bottom:14px;
  background:var(--card);border:1px solid var(--rule);border-radius:9px}
.row.orphan{border-color:var(--warn)}
.art{width:100%%;border-radius:5px;display:block;background:#000}
.drop{position:relative;border-radius:5px;transition:outline-color .12s}
.drop.over{outline:2px dashed var(--brass);outline-offset:3px}
.drop.over::after{content:"drop to replace";position:absolute;inset:0;display:flex;
  align-items:center;justify-content:center;background:#0d0f10cc;color:var(--brass);
  font-size:13px;letter-spacing:.06em;border-radius:5px}
.drop.busy::after{content:"reading…";position:absolute;inset:0;display:flex;
  align-items:center;justify-content:center;background:#0d0f10cc;color:var(--nettle);
  font-size:13px;border-radius:5px}
.dims{font-size:11.5px;font-family:ui-monospace,monospace;color:var(--dim);margin-top:5px}
.dims.bad{color:var(--warn)}
.noart{aspect-ratio:4/5;border:1px dashed var(--warn);border-radius:5px;display:flex;
  align-items:center;justify-content:center;text-align:center;color:var(--warn);
  font-size:12px;padding:16px;line-height:1.5}
.pid{font-family:ui-monospace,monospace;font-size:12px;color:var(--dim);margin-top:7px}
.intent{font-size:12.5px;color:var(--nettle);margin-top:3px;font-style:italic}
textarea{width:100%%;background:#0a0c0d;color:var(--ink);border:1px solid var(--rule);
  border-radius:6px;padding:11px 13px;font:inherit;line-height:1.6;resize:vertical}
textarea:focus{outline:none;border-color:var(--nettle)}
textarea.prompt{font-size:12.5px;color:var(--dim);font-family:ui-monospace,monospace;
  line-height:1.5;margin-top:9px}
.ctrls{display:flex;gap:9px;align-items:center;margin-top:9px;flex-wrap:wrap;font-size:12.5px}
label{color:var(--dim);font-size:12.5px}
select{font:inherit;font-size:12.5px;background:#0a0c0d;color:var(--ink);
  border:1px solid var(--rule);border-radius:5px;padding:5px 8px}
.tag{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--warn);
  border:1px solid var(--warn);border-radius:4px;padding:2px 7px}
.words{color:var(--dim);font-size:11.5px;font-family:ui-monospace,monospace}
button.pick{width:100%%;margin-top:7px;font-size:12px;padding:6px 10px;
  background:#1b1f21;border-color:var(--rule);color:var(--nettle)}
button.pick:hover{border-color:var(--nettle)}
button.render{color:var(--brass)}
button.render:hover{border-color:var(--brass)}
.banner{background:#1b1512;border:1px solid var(--warn);border-radius:8px;padding:15px 18px;
  margin-bottom:8px;font-size:14px}
.banner b{color:var(--warn)}
/* the reference shelf */
.refs{background:var(--card);border:1px solid var(--rule);border-radius:9px;
  padding:15px 18px;margin:12px 0 20px}
.refs h2{margin:0 0 4px;font-size:13px;letter-spacing:.14em;text-transform:uppercase;
  color:var(--nettle);font-weight:600}
.refs .why{color:var(--dim);font-size:12.5px;margin:0 0 12px;max-width:74ch}
.refstrip{display:flex;gap:9px;flex-wrap:wrap;align-items:flex-start}
.chip{position:relative;width:78px}
.chip img{width:78px;height:97px;object-fit:cover;border-radius:5px;display:block;
  border:1px solid var(--rule)}
.chip .x{position:absolute;top:-6px;right:-6px;width:20px;height:20px;border-radius:50%%;
  background:var(--warn);color:#1a1008;border:none;cursor:pointer;font-size:13px;
  line-height:20px;padding:0;font-weight:700}
.chip .n{font-size:10.5px;color:var(--dim);text-align:center;margin-top:3px;
  font-family:ui-monospace,monospace;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap}
.chip.slot{width:78px;height:97px;border:1px dashed var(--rule);border-radius:5px;
  display:flex;align-items:center;justify-content:center;color:var(--dim);
  font-size:26px;cursor:pointer;background:#0f1213}
.chip.slot:hover{border-color:var(--nettle);color:var(--nettle)}
.refs .count{font-size:12px;color:var(--dim);margin-top:10px;
  font-family:ui-monospace,monospace}
.refs .count.full{color:var(--brass)}
/* picker */
#pick{position:fixed;inset:0;background:#06080999;backdrop-filter:blur(4px);
  z-index:999;display:none;align-items:center;justify-content:center;padding:30px}
#pick.on{display:flex}
#pickbox{background:var(--card);border:1px solid var(--rule);border-radius:11px;
  max-width:1000px;width:100%%;max-height:84vh;display:flex;flex-direction:column}
#pickhead{padding:15px 20px;border-bottom:1px solid var(--rule);display:flex;
  gap:12px;align-items:center}
#pickhead h3{margin:0;font-size:14px;font-weight:600}
#pickgrid{padding:18px 20px;overflow:auto;display:grid;
  grid-template-columns:repeat(auto-fill,minmax(112px,1fr));gap:12px}
.cand{cursor:pointer;border:2px solid transparent;border-radius:6px;padding:3px}
.cand:hover{border-color:var(--nettle)}
.cand.in{border-color:var(--brass);opacity:.5}
.cand img{width:100%%;aspect-ratio:4/5;object-fit:cover;border-radius:4px;display:block}
.cand div{font-size:10.5px;color:var(--dim);margin-top:4px;text-align:center;
  font-family:ui-monospace,monospace;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap}
pre{background:#0a0c0d;border:1px solid var(--rule);border-radius:7px;padding:13px;
  overflow:auto;font-size:12px;color:var(--dim);white-space:pre-wrap;font-family:ui-monospace,monospace}
</style></head><body>
<header>
  <h1>%(title)s</h1><span class="sub">%(slug)s</span>
  <button class="primary" id="save">Save</button>
  <button id="rebuild">Save &amp; rebuild</button>
  <span class="gap"></span>
  <button id="v-read">Reading edition ↗</button>
  <button id="v-panel">Panel edition ↗</button>
  <span id="status"></span>
</header>
<main>
  <div class="banner" id="banner"></div>
  <div class="refs">
    <h2>Reference set</h2>
    <p class="why">Attached to every render, in this order. This is what holds a face
      across frames — a text sheet describes wardrobe, it cannot describe a likeness.
      Angle spread beats frame count, and mixing in-world frames with studio ones is
      what keeps the lighting and the grime from drifting. Eight is the API maximum.</p>
    <div class="refstrip" id="refstrip"></div>
    <div class="count" id="refcount"></div>
  </div>
  <div id="rows"></div>
  <pre id="log" style="display:none"></pre>
</main>
<div id="pick"><div id="pickbox">
  <div id="pickhead">
    <h3 id="picktitle">Choose a reference</h3>
    <button id="pickupload">Upload a file…</button>
    <button id="pickclose" style="margin-left:auto">Done</button>
  </div>
  <div id="pickgrid"></div>
</div></div>
<script>
const DOC = %(doc)s;
const SCRIPT_MTIME = %(mtime)s;
const POSITIONS = %(positions)s;
const PANELS = Object.keys(DOC.panels).sort((a,b)=>
  (DOC.panels[a].board_no||0)-(DOC.panels[b].board_no||0));
let dirty = false;

function status(t, c){ const s=document.getElementById('status');
  s.textContent=t; s.style.color=c||'var(--dim)'; }
function mark(){ dirty=true; status('unsaved changes','var(--brass)'); render_banner(); }
function words(t){ return t.trim() ? t.trim().split(/\\s+/).length : 0; }

function render_banner(){
  let orphan=0, ow=0;
  for(const s of DOC.sections) for(const b of s.blocks)
    if(!b.art){ orphan++; ow+=words(b.text); }
  const el=document.getElementById('banner');
  if(orphan===0){
    el.innerHTML='<b>Every paragraph has a picture.</b> The panel edition now '+
      'carries the whole story — rebuild and it will read to the end.';
    el.style.borderColor='var(--nettle)';
  } else {
    el.innerHTML='<b>'+orphan+' paragraph'+(orphan===1?'':'s')+' ('+ow+' words) '+
      'have no picture</b>, so they do not appear in the panel edition at all. '+
      'Anchor each one to a panel below, or accept that the panel edition tells '+
      'a shorter story than the reading edition.';
    el.style.borderColor='var(--warn)';
  }
}

// --- the reference set ------------------------------------------------------
// Two scopes: the script's `reference_set`, used by every render, and a panel's
// own `refs`, which overrides it. The override is for the frames that need
// different light -- a face lit from below inside the ship is not the face on a
// grey studio backdrop, and forcing one set on both drags every render halfway.
const MAX_REFS = 8;
let CANDIDATES = null;
let pickTarget = null;      // null = the global set, otherwise a panel id

function refsOf(pid){
  if(pid) return DOC.panels[pid].refs || [];
  return DOC.reference_set || (DOC.reference_set = []);
}
function setRefs(pid, arr){
  if(pid){
    if(arr.length) DOC.panels[pid].refs = arr; else delete DOC.panels[pid].refs;
  } else DOC.reference_set = arr;
  mark(); renderRefs(); render();
}

function chip(path, label, onRemove){
  const c=document.createElement('div'); c.className='chip';
  const im=document.createElement('img');
  im.src='/thumb?f='+encodeURIComponent(path); im.title=path;
  const x=document.createElement('button');
  x.className='x'; x.textContent='×'; x.title='remove'; x.onclick=onRemove;
  const n=document.createElement('div'); n.className='n'; n.textContent=label;
  c.appendChild(im); c.appendChild(x); c.appendChild(n);
  return c;
}

function renderRefs(){
  const strip=document.getElementById('refstrip');
  const cnt=document.getElementById('refcount');
  strip.innerHTML='';
  const set=refsOf(null);
  set.forEach((p,i)=>{
    strip.appendChild(chip(p, p.split('/').pop().replace(/\\.png$/,''),
      ()=>{ const a=set.slice(); a.splice(i,1); setRefs(null,a); }));
  });
  if(set.length<MAX_REFS){
    const s=document.createElement('div');
    s.className='chip slot'; s.textContent='+'; s.title='add a reference';
    s.onclick=()=>openPick(null);
    strip.appendChild(s);
  }
  cnt.textContent=set.length+' of '+MAX_REFS+' slots used';
  cnt.className='count'+(set.length>=MAX_REFS?' full':'');
}

async function candidates(){
  if(CANDIDATES) return CANDIDATES;
  const r=await fetch('/refs');
  CANDIDATES=await r.json();
  return CANDIDATES;
}

async function openPick(pid){
  pickTarget=pid;
  document.getElementById('picktitle').textContent =
    pid ? ('References for '+pid+' (overrides the set)') : 'Add to the reference set';
  const grid=document.getElementById('pickgrid');
  grid.innerHTML='<div style="color:var(--dim)">loading…</div>';
  document.getElementById('pick').classList.add('on');
  const list=await candidates();
  const cur=refsOf(pid);
  grid.innerHTML='';
  for(const c of list){
    const el=document.createElement('div');
    el.className='cand'+(cur.includes(c.path)?' in':'');
    const im=document.createElement('img');
    im.src='/thumb?f='+encodeURIComponent(c.path); im.loading='lazy';
    const lb=document.createElement('div');
    lb.textContent=c.label; lb.title=c.intent||c.path;
    el.appendChild(im); el.appendChild(lb);
    el.onclick=()=>{
      const a=refsOf(pickTarget).slice();
      const at=a.indexOf(c.path);
      if(at>=0) a.splice(at,1);
      else { if(a.length>=MAX_REFS){ status('8 is the maximum','var(--warn)'); return; }
             a.push(c.path); }
      setRefs(pickTarget, a);
      el.className='cand'+(a.includes(c.path)?' in':'');
    };
    grid.appendChild(el);
  }
}
document.getElementById('pickclose').onclick=()=>
  document.getElementById('pick').classList.remove('on');
document.getElementById('pick').onclick=e=>{
  if(e.target.id==='pick') e.currentTarget.classList.remove('on'); };
document.getElementById('pickupload').onclick=()=>pickFile(async f=>{
  const name=(f.name||'reference').replace(/\\.[^.]+$/,'');
  const r=await fetch('/upload-ref?name='+encodeURIComponent(name),
    {method:'POST',headers:{'Content-Type':f.type},body:await f.arrayBuffer()});
  const t=await r.text();
  if(!r.ok){ status(t,'var(--warn)'); return; }
  const info=JSON.parse(t);
  CANDIDATES=null;
  const a=refsOf(pickTarget).slice();
  if(a.length<MAX_REFS) a.push(info.path);
  setRefs(pickTarget, a);
  openPick(pickTarget);
  status('added '+info.path,'var(--nettle)');
});

// --- dropping art onto a panel ---------------------------------------------
// The plate is 4:5 (2432x3040). Anything else is not rejected -- a frame that
// came back at the wrong ratio is still a frame, and `focal` decides what the
// slot keeps -- but it is called out, because a crop you did not choose is the
// kind of thing you find out about on page 14.
const PLATE_R = 4/5, R_TOL = 0.01, MIN_W = 1024;

function showDims(pid, w, h){
  const p = DOC.panels[pid];
  const r = w/h, off = Math.abs(r-PLATE_R) > R_TOL, small = w < MIN_W;
  const note = off ? '  ✕ not 4:5 — will be cropped to the slot'
                   : (small ? '  ✕ under 1024 wide' : '  ✓ 4:5');
  p._dims = w+'×'+h+note;
  const el = document.querySelector('.dims[data-pid="'+pid+'"]');
  if(el){ el.textContent = p._dims; el.className = 'dims'+((off||small)?' bad':''); }
}

async function probe(pid, rel){
  try{
    const r = await fetch('/thumb?meta=1&f='+encodeURIComponent(rel));
    if(!r.ok) return;
    const d = await r.json();
    showDims(pid, d.w, d.h);
  }catch(e){}
}

function pickFile(cb){
  const inp=document.createElement('input');
  inp.type='file'; inp.accept='image/*';
  inp.onchange=()=>{ if(inp.files && inp.files[0]) cb(inp.files[0]); };
  inp.click();
}

function nextPanelId(){
  let n=0;
  for(const k of Object.keys(DOC.panels)){
    const m=/^p(\\d+)$/.exec(k);
    if(m) n=Math.max(n, parseInt(m[1],10));
  }
  return 'p'+String(n+1).padStart(2,'0');
}

async function sendImage(pid, file, isNew){
  const buf=await file.arrayBuffer();
  const url='/upload?pid='+encodeURIComponent(pid)+(isNew?'&new=1':'');
  const r=await fetch(url,{method:'POST',headers:{'Content-Type':file.type},body:buf});
  const t=await r.text();
  if(!r.ok){ status(t,'var(--warn)'); return null; }
  return JSON.parse(t);
}

// Give an unanchored paragraph a picture of its own: allocate a panel, file the
// image under it, anchor the block. This is the move the editor exists to make --
// an orphan block is a hole in the panel edition, and this is how it gets filled.
async function newPanelFrom(b, secN, file){
  const pid=nextPanelId();
  const info=await sendImage(pid, file, true);
  if(!info) return;
  let maxBoard=0;
  for(const k in DOC.panels) maxBoard=Math.max(maxBoard, DOC.panels[k].board_no||0);
  DOC.panels[pid]={ sec: secN, role: 'splash', board_no: maxBoard+1,
    intent: (b.text||'').split(/(?<=[.!?])\\s/)[0].slice(0,90),
    prompt: '', image: info.path, _v: Date.now() };
  b.art=pid;
  mark(); render(); showDims(pid, info.w, info.h);
  status('new panel '+pid+' → '+info.path,'var(--nettle)');
}

function wireDrop(zone, onFile){
  const stop = e => { e.preventDefault(); e.stopPropagation(); };
  zone.addEventListener('dragover', e => { stop(e); zone.classList.add('over'); });
  zone.addEventListener('dragleave', e => { stop(e); zone.classList.remove('over'); });
  zone.addEventListener('drop', async e => {
    stop(e); zone.classList.remove('over');
    const f = e.dataTransfer.files && e.dataTransfer.files[0];
    if(!f) return;
    if(!/^image\\//.test(f.type)){ status('not an image: '+f.name,'var(--warn)'); return; }
    zone.classList.add('busy');
    try{ await onFile(f); } finally { zone.classList.remove('busy'); }
  });
}

async function replaceArt(pid, file){
  const info = await sendImage(pid, file, false);
  if(!info) return;
  const p = DOC.panels[pid];
  p.image = info.path; p._v = Date.now(); delete p._dims;
  mark(); render(); showDims(pid, info.w, info.h);
  status('filed '+file.name+' → '+info.path,'var(--nettle)');
}

// Prompt in the box above, picture back in the frame at left. Saves first, so
// the renderer reads the prompt you can see rather than the one on disk.
async function renderPanel(pid, btn){
  if(dirty && !await save()) return;
  const old=btn.textContent;
  btn.disabled=true; btn.textContent='rendering…';
  status('rendering '+pid+' — this takes a moment');
  try{
    const r=await fetch('/render?pid='+encodeURIComponent(pid),{method:'POST'});
    const t=await r.text();
    if(!r.ok){ status(t.split('\\n').pop(),'var(--warn)'); return; }
    const info=JSON.parse(t);
    const p=DOC.panels[pid];
    p.image=info.image; p.seed=info.seed; p._v=Date.now(); delete p._dims;
    render();
    status(pid+' rendered · seed '+info.seed,'var(--nettle)');
  } finally { btn.disabled=false; btn.textContent=old; }
}

function pickBtn(text, onFile){
  const b=document.createElement('button');
  b.className='pick'; b.type='button'; b.textContent=text;
  b.onclick=()=>pickFile(onFile);
  return b;
}

function panelSelect(b, secN){
  const sel=document.createElement('select');
  const none=document.createElement('option');
  none.value=''; none.textContent='— no picture —'; sel.appendChild(none);
  const ids=Object.keys(DOC.panels).sort((a,c)=>
    (DOC.panels[a].board_no||0)-(DOC.panels[c].board_no||0));
  for(const pid of ids){
    const o=document.createElement('option');
    o.value=pid;
    o.textContent=pid+' · '+(DOC.panels[pid].intent||'').slice(0,52);
    sel.appendChild(o);
  }
  // what you reach for when the list holds nothing that fits
  const mk=document.createElement('option');
  mk.value='__new'; mk.textContent='＋ new panel from an image…';
  sel.appendChild(mk);
  sel.value=b.art||'';
  sel.onchange=()=>{
    if(sel.value==='__new'){
      sel.value=b.art||'';
      pickFile(f => newPanelFrom(b, secN, f));
      return;
    }
    b.art=sel.value||undefined; if(!sel.value) delete b.art;
    mark(); render();
  };
  return sel;
}

function roleSelect(pid){
  const sel=document.createElement('select');
  for(const r of ['splash','quad']){
    const o=document.createElement('option'); o.value=r; o.textContent=r;
    sel.appendChild(o);
  }
  sel.value=DOC.panels[pid].role||'quad';
  sel.onchange=()=>{ DOC.panels[pid].role=sel.value; mark(); };
  return sel;
}

function render(){
  const host=document.getElementById('rows'); host.innerHTML='';
  for(const sec of DOC.sections){
    const h=document.createElement('div');
    h.className='sec'; h.textContent='Section '+sec.n; host.appendChild(h);
    for(const b of sec.blocks){
      const p = b.art ? DOC.panels[b.art] : null;
      const row=document.createElement('div');
      row.className='row'+(p?'':' orphan');

      const left=document.createElement('div');
      if(p){
        const zone=document.createElement('div');
        zone.className='drop';
        if(p.image){
          const img=document.createElement('img');
          img.className='art'; img.loading='lazy';
          img.src='/thumb?f='+encodeURIComponent(p.image)+'&v='+(p._v||0);
          zone.appendChild(img);
        } else {
          const d=document.createElement('div');
          d.className='noart';
          d.textContent='panel '+b.art+' has no art — drop a 4:5 image here';
          zone.appendChild(d);
        }
        wireDrop(zone, f => replaceArt(b.art, f));
        left.appendChild(zone);
        const dims=document.createElement('div');
        dims.className='dims'; dims.dataset.pid=b.art;
        dims.textContent=p._dims||'';
        left.appendChild(dims);
        left.appendChild(pickBtn(p.image?'Replace image…':'Choose image…',
                                 f => replaceArt(b.art, f)));
        // Write the prompt above, then get a picture without leaving the page.
        const rb=document.createElement('button');
        rb.className='pick render'; rb.type='button';
        rb.textContent=p.image?'Re-render with FLUX':'Render with FLUX';
        rb.onclick=()=>renderPanel(b.art, rb);
        left.appendChild(rb);
        const nref=(p.refs && p.refs.length) ? p.refs.length : 0;
        const rf=document.createElement('button');
        rf.className='pick'; rf.type='button';
        rf.textContent = nref ? ('refs: '+nref+' custom') : 'refs: using the set';
        rf.title='Choose reference images for this panel only';
        if(nref) rf.style.color='var(--brass)';
        rf.onclick=()=>openPick(b.art);
        left.appendChild(rf);
        if(p.seed){
          const sd=document.createElement('div');
          sd.className='dims'; sd.textContent='seed '+p.seed;
          left.appendChild(sd);
        }
        if(p.image && !p._dims) probe(b.art, p.image);
      } else {
        // The orphan row is the one that most needs a picture, so it is a drop
        // target too -- dropping here makes a new panel rather than filling one.
        const zone=document.createElement('div');
        zone.className='drop';
        const d=document.createElement('div');
        d.className='noart';
        d.textContent='no picture — drop a 4:5 image here to give this paragraph '+
          'a panel of its own, or it will not appear in the panel edition';
        zone.appendChild(d);
        wireDrop(zone, f => newPanelFrom(b, sec.n, f));
        left.appendChild(zone);
        left.appendChild(pickBtn('New panel from image…',
                                 f => newPanelFrom(b, sec.n, f)));
      }
      if(p){
        const id=document.createElement('div');
        id.className='pid'; id.textContent=b.art+' · '+(p.role||'quad');
        left.appendChild(id);
        const it=document.createElement('div');
        it.className='intent'; it.textContent=p.intent||''; left.appendChild(it);
      }

      const right=document.createElement('div');
      const ta=document.createElement('textarea');
      ta.value=b.text||''; ta.rows=Math.max(3,Math.ceil((b.text||'').length/78));
      ta.oninput=()=>{ b.text=ta.value; wc.textContent=words(ta.value)+' words'; mark(); };
      right.appendChild(ta);

      const ctrls=document.createElement('div'); ctrls.className='ctrls';
      if(!p){ const t=document.createElement('span');
        t.className='tag'; t.textContent='no picture'; ctrls.appendChild(t); }
      const lab=document.createElement('label'); lab.textContent='picture:';
      ctrls.appendChild(lab); ctrls.appendChild(panelSelect(b, sec.n));

      if(p){
        const rl=document.createElement('label'); rl.textContent='page role:';
        ctrls.appendChild(rl); ctrls.appendChild(roleSelect(b.art));
        const pl=document.createElement('label'); pl.textContent='caption corner:';
        ctrls.appendChild(pl);
        const ps=document.createElement('select');
        for(const q of POSITIONS){ const o=document.createElement('option');
          o.value=q; o.textContent=q; ps.appendChild(o); }
        ps.value=b.pos||'';
        if(!b.pos){ const o=document.createElement('option');
          o.value=''; o.textContent='auto'; ps.insertBefore(o,ps.firstChild); ps.value=''; }
        ps.onchange=()=>{ if(ps.value) b.pos=ps.value; else delete b.pos; mark(); };
        ctrls.appendChild(ps);

        const em=document.createElement('label');
        const cb=document.createElement('input'); cb.type='checkbox'; cb.checked=!!b.emph;
        cb.onchange=()=>{ if(cb.checked) b.emph=true; else delete b.emph; mark(); };
        em.appendChild(cb); em.appendChild(document.createTextNode(' emphasis'));
        ctrls.appendChild(em);
      }
      const wc=document.createElement('span');
      wc.className='words'; wc.textContent=words(b.text||'')+' words';
      ctrls.appendChild(wc);
      right.appendChild(ctrls);

      if(p){
        const pr=document.createElement('textarea');
        pr.className='prompt'; pr.rows=3; pr.value=p.prompt||'';
        pr.oninput=()=>{ p.prompt=pr.value; mark(); };
        right.appendChild(pr);
      }
      row.appendChild(left); row.appendChild(right); host.appendChild(row);
    }
  }
  render_banner();
}

async function save(){
  status('saving…');
  // strip the editor's own bookkeeping (_v, _dims) so the script stays the script
  const clean = JSON.stringify(DOC, (k,v)=> k.startsWith('_') ? undefined : v);
  const r=await fetch('/save',{method:'POST',
    headers:{'Content-Type':'application/json','X-Script-Mtime':SCRIPT_MTIME},
    body:clean});
  const t=await r.text();
  if(r.ok){ dirty=false; status(t,'var(--nettle)'); } else status(t,'var(--warn)');
  return r.ok;
}
// Save, rebuild that edition, then hand the reader the finished page -- no
// editing furniture on it, because the point of looking is to see what a reader
// sees. One small control comes back the other way.
async function preview(kind){
  if(dirty && !await save()) return;
  status('building the '+(kind==='read'?'reading':'panel')+' edition…');
  const r=await fetch('/preview?ed='+kind,{method:'POST'});
  if(!r.ok){ status(await r.text(),'var(--warn)'); return; }
  dirty=false;
  location.href='/view/'+kind;
}
document.getElementById('v-read').onclick=()=>preview('read');
document.getElementById('v-panel').onclick=()=>preview('panel');
document.getElementById('save').onclick=save;
document.getElementById('rebuild').onclick=async()=>{
  if(!await save()) return;
  status('rebuilding…');
  const r=await fetch('/rebuild',{method:'POST'});
  const t=await r.text();
  const log=document.getElementById('log');
  log.style.display='block'; log.textContent=t;
  status(r.ok?'rebuilt':'rebuild failed', r.ok?'var(--nettle)':'var(--warn)');
};
window.onbeforeunload=e=>{ if(dirty){ e.preventDefault(); return ''; } };
renderRefs();
render();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    script_path = None

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="text/plain; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        # Everything here is generated from files that change under the browser --
        # a plate replaced by a render is the whole point of the tool. A cached
        # thumbnail is indistinguishable from a render that silently failed.
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            doc = json.loads(self.script_path.read_text())
            m = doc.get("meta", {})
            html = PAGE % {"title": m.get("title", "script"),
                           "slug": self.script_path.name,
                           "doc": json.dumps(doc),
                           "mtime": json.dumps(str(self.script_path.stat().st_mtime_ns)),
                           "positions": json.dumps(POSITIONS)}
            return self._send(200, html, "text/html; charset=utf-8")
        if u.path == "/refs":
            # everything that could serve as a reference: the ref shelf first,
            # then the panels themselves, since a rendered frame is often the
            # best likeness you have
            doc = json.loads(self.script_path.read_text())
            out = []
            refdir = ROOT / "images" / "ref"
            if refdir.is_dir():
                for f in sorted(refdir.iterdir()):
                    if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                        out.append({"path": f"images/ref/{f.name}",
                                    "label": f.stem, "kind": "ref"})
            for pid, p in sorted(doc.get("panels", {}).items(),
                                 key=lambda kv: kv[1].get("board_no", 0)):
                if p.get("image") and (ROOT / p["image"]).exists():
                    out.append({"path": p["image"], "label": pid,
                                "kind": "panel",
                                "intent": (p.get("intent") or "")[:70]})
            return self._send(200, json.dumps(out), "application/json")
        if u.path.startswith("/view/"):
            kind = u.path[len("/view/"):]
            if kind not in EDITIONS:
                return self._send(404, "no such edition")
            built = ROOT / EDITIONS[kind][1]
            if not built.exists():
                return self._send(404, f"{EDITIONS[kind][1]} has not been built yet")
            html = built.read_text(encoding="utf-8")
            if "</body>" in html:
                html = html.replace("</body>", BACK_BAR + "</body>", 1)
            else:
                html += BACK_BAR
            return self._send(200, html, "text/html; charset=utf-8")
        if u.path.startswith("/images/"):
            rel = unquote(u.path.lstrip("/"))
            if ".." in rel:
                return self._send(403, "no")
            f = ROOT / rel
            if not f.is_file():
                return self._send(404, "missing")
            ctype = {".png": "image/png", ".jpg": "image/jpeg",
                     ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(
                         f.suffix.lower(), "application/octet-stream")
            return self._send(200, f.read_bytes(), ctype)
        if u.path == "/thumb":
            q = dict(pair.split("=", 1) for pair in u.query.split("&") if "=" in pair)
            rel = unquote(q.get("f", ""))
            if not rel or ".." in rel or rel.startswith("/"):
                return self._send(403, "no")
            if q.get("meta"):
                # the *plate's* size, not the thumbnail's -- the ratio check is
                # about the file on disk, and a thumbnail has already lost it
                wh = plate_size(rel)
                if wh is None:
                    return self._send(404, "missing")
                return self._send(200, json.dumps({"w": wh[0], "h": wh[1]}),
                                  "application/json")
            data = thumb(rel)
            if data is None:
                return self._send(404, "missing")
            return self._send(200, data, "image/jpeg")
        self._send(404, "not found")

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/save":
            n = int(self.headers.get("Content-Length", 0))
            try:
                doc = json.loads(self.rfile.read(n))
            except json.JSONDecodeError as e:
                return self._send(400, f"bad json: {e}")
            if "panels" not in doc or "sections" not in doc:
                return self._send(400, "refusing to write: not a story script")
            # The page holds the whole script in memory from the moment it loaded.
            # If anything else touched the file since -- render.py recording a seed,
            # an edit made in a terminal -- a blind save silently reverts it. Compare
            # what the page was given against what is on disk now.
            seen = self.headers.get("X-Script-Mtime")
            now = str(self.script_path.stat().st_mtime_ns)
            if seen and seen != now:
                return self._send(409,
                    "the script changed on disk since this page loaded — reload to "
                    "pick up those edits, then save again. (Nothing was written.)")
            self.script_path.write_text(
                json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
            anchored = sum(1 for s in doc["sections"] for b in s["blocks"] if b.get("art"))
            total = sum(len(s["blocks"]) for s in doc["sections"])
            return self._send(200, f"saved · {anchored}/{total} paragraphs anchored")
        if u.path == "/upload":
            q = dict(pair.split("=", 1) for pair in u.query.split("&") if "=" in pair)
            pid = unquote(q.get("pid", ""))
            if not re.fullmatch(r"[A-Za-z0-9_-]+", pid or ""):
                return self._send(400, "bad panel id")
            doc = json.loads(self.script_path.read_text())
            # `new=1` files art for a panel the browser is about to add and has
            # not saved yet, so it will not be on disk. Refuse to clobber an
            # existing plate that way -- a new panel means a new file.
            if q.get("new"):
                if (ROOT / "images" / f"{pid}.png").exists():
                    return self._send(409, f"images/{pid}.png already exists")
            elif pid not in doc.get("panels", {}):
                return self._send(404, f"no panel {pid} in this script")
            n = int(self.headers.get("Content-Length", 0))
            if n <= 0 or n > 80 * 1024 * 1024:
                return self._send(413, "empty or over 80MB")
            raw = self.rfile.read(n)
            dest = ROOT / "images" / f"{pid}.png"
            dest.parent.mkdir(parents=True, exist_ok=True)
            # A drop replaces a plate, and a plate is the expensive artefact here:
            # minutes of render time, or a frame nobody can generate twice. Keep the
            # one being replaced. Cheap insurance against a file dropped on the
            # wrong row, which is a mistake with no other undo.
            if dest.exists():
                prev = ROOT / "images" / ".replaced"
                prev.mkdir(exist_ok=True)
                stamp = time.strftime("%Y%m%d-%H%M%S")
                dest.replace(prev / f"{pid}-{stamp}.png")
            try:
                from PIL import Image
                im = Image.open(io.BytesIO(raw))
                w, h = im.size
                # normalise to PNG so images/<pid>.png stays the one convention,
                # whatever got dropped
                im.convert("RGB").save(dest, "PNG")
            except ImportError:
                if raw[:8] != b"\x89PNG\r\n\x1a\n":
                    return self._send(400, "needs Pillow to accept anything but PNG")
                dest.write_bytes(raw)
                w = h = 0
            except Exception as e:
                return self._send(400, f"could not read that image: {e}")
            rel = f"images/{pid}.png"
            _thumbs.pop(rel, None)
            return self._send(200, json.dumps({"path": rel, "w": w, "h": h}),
                              "application/json")
        if u.path == "/upload-ref":
            q = dict(pair.split("=", 1) for pair in u.query.split("&") if "=" in pair)
            name = unquote(q.get("name", "")).strip()
            name = re.sub(r"[^A-Za-z0-9_-]+", "-", name).strip("-")[:60]
            if not name:
                return self._send(400, "bad reference name")
            n = int(self.headers.get("Content-Length", 0))
            if n <= 0 or n > 80 * 1024 * 1024:
                return self._send(413, "empty or over 80MB")
            raw = self.rfile.read(n)
            dest = ROOT / "images" / "ref" / f"{name}.png"
            dest.parent.mkdir(parents=True, exist_ok=True)
            i = 2
            while dest.exists():          # never silently replace a reference
                dest = ROOT / "images" / "ref" / f"{name}-{i}.png"
                i += 1
            try:
                from PIL import Image
                Image.open(io.BytesIO(raw)).convert("RGB").save(dest, "PNG")
            except ImportError:
                if raw[:8] != b"\x89PNG\r\n\x1a\n":
                    return self._send(400, "needs Pillow to accept anything but PNG")
                dest.write_bytes(raw)
            except Exception as e:
                return self._send(400, f"could not read that image: {e}")
            rel = f"images/ref/{dest.name}"
            return self._send(200, json.dumps({"path": rel, "label": dest.stem}),
                              "application/json")
        if u.path == "/render":
            q = dict(pair.split("=", 1) for pair in u.query.split("&") if "=" in pair)
            pid = unquote(q.get("pid", ""))
            if not re.fullmatch(r"[A-Za-z0-9_-]+", pid or ""):
                return self._send(400, "bad panel id")
            model = unquote(q.get("model", "max"))
            if model not in ("max", "pro", "flex", "klein"):
                return self._send(400, "bad model")
            cmd = ["python3", "tools/render.py", pid,
                   "--script", str(self.script_path), "--model", model]
            r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                               timeout=420)
            out = (r.stdout + r.stderr).strip()
            if r.returncode != 0:
                return self._send(500, out or "render failed")
            # render.py wrote image+seed into the script; hand them back so the
            # page can update without a reload
            doc = json.loads(self.script_path.read_text())
            p = doc["panels"].get(pid, {})
            _thumbs.pop(p.get("image", ""), None)
            return self._send(200, json.dumps(
                {"image": p.get("image"), "seed": p.get("seed"), "log": out}),
                "application/json")
        if u.path == "/preview":
            q = dict(pair.split("=", 1) for pair in u.query.split("&") if "=" in pair)
            kind = q.get("ed", "")
            if kind not in EDITIONS:
                return self._send(400, "no such edition")
            tool = EDITIONS[kind][0]
            r = subprocess.run(["python3", tool, str(self.script_path)],
                               cwd=ROOT, capture_output=True, text=True)
            if r.returncode != 0:
                return self._send(500, (r.stderr or r.stdout or "build failed").strip())
            return self._send(200, r.stdout.strip() or "built")
        if u.path == "/rebuild":
            out = []
            ok = True
            for cmd in (["python3", "tools/coverage.py", str(self.script_path)],
                        ["python3", "tools/build.py", str(self.script_path)],
                        ["python3", "tools/read.py", str(self.script_path)]):
                r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
                out.append(f"$ {' '.join(cmd[1:])}\n{r.stdout}{r.stderr}".rstrip())
                if r.returncode != 0:
                    ok = False
            return self._send(200 if ok else 500, "\n\n".join(out))
        self._send(404, "not found")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    src = Path(args[0]).resolve() if args else ROOT / "script" / "what-the-forest-kept.json"
    if not src.exists():
        sys.exit(f"no such script: {src}")
    try:
        shown = src.relative_to(ROOT)
    except ValueError:
        shown = src
    port = 8000
    for a in sys.argv[1:]:
        if a.startswith("--port"):
            port = int(a.split("=", 1)[1]) if "=" in a else port
    Handler.script_path = src
    srv = HTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"editing {shown} — {url}\nCtrl-C to stop.")
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
