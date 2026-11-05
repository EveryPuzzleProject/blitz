"""A page for a person to settle the Collegian issues the scan could not.

    python tools/collegian/review.py serve [--port 8765]

Shows one issue at a time as a contact sheet of all its pages (a spread each). Click the
page the crossword is on, or say there is no crossword that day. Each decision is a line in
decisions.jsonl (date, verdict, seq, who, when); the scan's own guess (issues.tsv) is shown
but a person's decision always wins. "absent" (a person looked: no puzzle) is a different
state from "no-hit" (the scan found nothing and nobody has looked yet).

Thumbnails come from the archive's image server and are cached under cache/thumb/.
"""
import importlib.util
import json
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_spec = importlib.util.spec_from_file_location("collegian_scan", Path(__file__).with_name("scan.py"))
scan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scan)
DATA = scan.DATA
DECISIONS = DATA / "decisions.jsonl"


def decisions():
    d = {}
    if DECISIONS.exists():
        for line in DECISIONS.read_text("utf8").splitlines():
            if line.strip():
                r = json.loads(line)
                d[r["date"]] = r
    return d


def exceptions():
    """exceptions.tsv: oddities a person has told us about (an extra reprint, a stub, a missed day)."""
    p, out = DATA / "exceptions.tsv", {}
    if p.exists():
        for line in p.read_text("utf8").splitlines()[1:]:
            f = (line.split("\t") + ["", "", "", ""])[:4]
            out.setdefault(f[0], []).append(dict(seq=f[1], kind=f[2], note=f[3]))
    return out


def issues():
    rows, dec, exc, boxes = scan.read_rows(), decisions(), exceptions(), crop_boxes()
    out = []
    for date, r in sorted(rows.items()):
        p = dec.get(date)
        if p:
            state = "found" if p["verdict"] == "found" else p["verdict"]
            seq = p.get("seq") or ""
            by = "person"
            kind = p.get("kind", "regular")
        else:
            state, seq, by, kind = r["verdict"], r.get("seq", ""), "scan", ""
        g = (r.get("guess") or "").split("|")
        cand, why = (r.get("seq", ""), "the scan saw part of a crossword here") if r.get("seq") else \
                    ((g[0], f"era guess: {g[1]} nearby puzzles were on this page") if g[0] else ("", ""))
        # a day a person called absent that deserves a second look: in term time (summer issues often had no puzzle,
        # and the June 1981 ad days are known), or the OCR saw part of a crossword there
        why2 = []
        if state == "absent":
            if date[5:7] not in ("06", "07", "08") and date < "1981-06-10":
                why2.append("an absent day in term time")
            if r["verdict"] == "check" and r.get("seq"):
                ev = json.loads(r.get("evidence") or "{}")
                why2.append(f"the OCR saw part of a crossword on page {r['seq']} "
                            f"({ev.get('nums', 0)} numbered lines, Across/Down heads {ev.get('across', 0)}/{ev.get('down', 0)}"
                            f"{', an answers line' if ev.get('answers_line') else ''})")
        out.append(dict(date=date, pages=int(r["pages"] or 0), state=state, seq=seq, by=by, kind=kind,
                        second_look=bool(why2), why2="; ".join(why2),
                        scan_verdict=r["verdict"], scan_seq=r.get("seq", ""), evidence=r.get("evidence", ""),
                        cand=cand, why=why, extras=exc.get(date, []),
                        hasbox=bool(seq) and (date, int(seq)) in boxes))
    return out


def thumb(date, seq, width):
    p = DATA / "cache" / "thumb" / date / f"seq-{seq}-{width}.jpg"
    if not p.exists():
        m = scan.manifest(date)
        iid = m["sequences"][0]["canvases"][seq - 1]["images"][0]["resource"]["@id"]
        b = scan.get(f"{scan.BASE}{iid}/full/{width},/0/default.jpg")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b)
    return p.read_bytes()


PAGE = r"""<!doctype html><meta charset=utf-8><title>Collegian crosswords</title>
<style>
body{font:15px system-ui;margin:0;background:#f4f1ea;color:#222}
header{position:sticky;top:0;background:#fff;border-bottom:1px solid #ccc;padding:8px 14px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;z-index:2}
button,select{font:inherit;padding:5px 10px;border:1px solid #888;border-radius:5px;background:#fff;cursor:pointer}
button.primary{background:#1d5c3a;color:#fff;border-color:#1d5c3a}
.sheet{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px;padding:12px}
.pg{background:#fff;border:3px solid transparent;position:relative;cursor:pointer}
.pg img{width:100%;display:block;background:#ddd;aspect-ratio:1.28/1;object-fit:contain}
.pg:hover{border-color:#1d5c3a}
.pg.cand{border:6px solid #e8590c;box-shadow:0 0 0 4px #ffd8a8}.pg.chosen{border-color:#1d5c3a}
.pg .n{position:absolute;left:0;top:0;background:#000b;color:#fff;padding:2px 8px;font-weight:700}
.pg .tag{position:absolute;right:0;top:0;background:#d58a00;color:#fff;padding:2px 8px}
.pg.chosen .tag{background:#1d5c3a}
.pg a{position:absolute;right:4px;bottom:4px;background:#fffd;padding:1px 6px;font-size:12px}
small{color:#555}
</style>
<header>
 <select id=filter>
  <option value=todo>Needs a look</option><option value=check>Scan unsure</option><option value=nohit>Scan found nothing</option>
  <option value=second>Second look (absent days)</option><option value=found>Found (spot check)</option><option value=dless>Diagramless</option><option value=absent>You said no crossword</option><option value=all>All</option>
 </select>
 <button id=prev>&larr; prev</button><b id=title></b><button id=next>next &rarr;</button>
 <button id=absent class=primary>No crossword this day (n)</button>
 <button id=unsure>Can't tell (u)</button>
 <button id=dl title="tags the next page you pick as a diagramless">Diagramless (d): off</button>
 <small id=count></small> <a href="/confirm">confirm sheet</a>
</header>
<div id=flash style="display:none;position:fixed;right:14px;bottom:14px;background:#1d5c3a;color:#fff;padding:10px 16px;border-radius:6px;z-index:5;max-width:420px"></div>
<div id=cand style="padding:0 12px"></div>
<div id=sheet class=sheet></div>
<script>
const flash=m=>{const f=document.getElementById('flash');f.textContent=m;f.style.display='block';clearTimeout(flash.t);flash.t=setTimeout(()=>f.style.display='none',6000)};
// The address is the issue (#1978-01-20), and every move is a history entry, so the mouse's back and
// forward buttons are prev and next. history.state keeps the trail across a reload.
let list=[],dl=false,ALL=[],curDate=null,stack=[],idx=0;
const byDate=d=>ALL.find(r=>r.date==d);
const cur=()=>byDate(curDate);
const nextAfter=d=>list.find(r=>r.date>d);
const prevBefore=d=>{let p=null;for(const r of list){if(r.date<d)p=r;else break}return p};
function nav(date){stack=stack.slice(0,idx+1);stack.push(date);idx=stack.length-1;history.pushState({stack,idx},'','#'+date);curDate=date;show();}
window.onpopstate=e=>{if(e.state){stack=e.state.stack;idx=e.state.idx}curDate=location.hash.slice(1)||curDate;show();};
function goPrev(){if(idx>0)history.back();else{const p=prevBefore(curDate);if(p)nav(p.date)}}
function goNext(){if(idx<stack.length-1)history.forward();else{const n=nextAfter(curDate);if(n)nav(n.date)}}
function setDl(v){dl=v;const b=document.getElementById('dl');b.textContent='Diagramless (d): '+(dl?'ON':'off');b.style.background=dl?'#ffe066':'';}
const $=id=>document.getElementById(id);
async function load(){
  const all=await (await fetch('/api/issues')).json();
  const f=$('filter').value; ALL=all;
  list=all.filter(r=>f=='all'||(f=='todo'&&['check','no-hit','pending','unsure'].includes(r.state))||(f=='check'&&r.state=='check')||(f=='nohit'&&r.state=='no-hit')||(f=='found'&&r.state=='found')||(f=='second'&&r.second_look)||(f=='dless'&&r.kind=='diagramless')||(f=='absent'&&r.state=='absent'));
  const cnt={};all.forEach(r=>cnt[r.state]=(cnt[r.state]||0)+1);
  $('count').textContent=list.length+' in view · '+Object.entries(cnt).map(([k,v])=>k+' '+v).join(' · ');
  if(!curDate){   // first load: the address says where we were, else the first issue in view
    curDate=location.hash.slice(1)||(list[0]&&list[0].date)||null;
    const s=history.state; stack=(s&&s.stack)||[curDate]; idx=(s&&s.idx)||0;
    history.replaceState({stack,idx},'','#'+curDate);
  }
  show();
}
async function refilter(){await load();if(list[0])nav(list[0].date);}
function show(){
  const r=cur(); const s=$('sheet'); s.innerHTML='';
  if(!r){$('title').textContent='nothing here';return}
  const dow=new Date(r.date+'T12:00:00').toLocaleDateString('en-US',{weekday:'short'});
  $('title').textContent=r.date+' '+dow+' · '+r.pages+' pages · '+r.state+(r.kind=='diagramless'?' · DIAGRAMLESS':'')+(r.by=='person'?' (you)':' (scan'+(r.scan_seq?', p'+r.scan_seq:'')+')');
  // prefetch the next issues: every suspect page first, then the rest
  const nx=list.filter(q=>q.date>r.date).slice(0,3), pf=(q,n)=>{new Image().src='/thumb/'+q.date+'/'+n+'.jpg?w=480'};
  nx.forEach(q=>{if(q.cand&&q.by=='scan')pf(q,+q.cand)});
  nx.forEach(q=>{for(let n=1;n<=q.pages;n++)if(!(q.by=='scan'&&String(q.cand)==n))pf(q,n)});
  const second=r.second_look?'<div style="background:#d0ebff;border:2px solid #1c7ed6;padding:6px 10px;margin-top:10px"><b>Second look:</b> '+r.why2.replace(/</g,'&lt;')+'. Click the page if there is a crossword; press n to confirm no crossword.</div>':'';
  $('cand').innerHTML=second+(r.extras||[]).map(x=>'<div style="background:#fff3bf;border:2px solid #e8590c;padding:6px 10px;margin-top:10px"><b>Known exception ('+x.kind+(x.seq&&x.seq!='-'?', page '+x.seq:'')+'):</b> '+x.note.replace(/</g,'&lt;')+'</div>').join('');
  const exSeq=new Set((r.extras||[]).map(x=>x.seq));
  for(let n=1;n<=r.pages;n++){
    const d=document.createElement('div'); d.className='pg'+((String(r.cand)==n&&r.by=='scan')||(r.second_look&&String(r.scan_seq)==n)?' cand':'')+(String(r.seq)==n&&r.by=='person'&&r.state=='found'?' chosen':'');
    d.innerHTML='<img '+(d.className.includes('cand')?'fetchpriority=high ':'')+'src="/thumb/'+r.date+'/'+n+'.jpg?w=480"><span class=n>'+n+'</span>'+
      (d.className.includes('cand')?'<span class=tag>guess</span>':'')+(exSeq.has(String(n))?'<span class=tag style="top:26px;background:#7048e8">exception</span>':'')+(d.className.includes('chosen')?'<span class=tag>your pick</span>':'')+
      '<a target=_blank href="/thumb/'+r.date+'/'+n+'.jpg?w=2400">big</a>';
    d.onclick=e=>{if(e.target.tagName!='A')decide('found',n)};
    s.appendChild(d);
  }
  window.scrollTo(0,0);
}
async function decide(verdict,seq){
  const r=cur(); if(!r)return;
  await fetch('/api/decide',{method:'POST',body:JSON.stringify({date:r.date,verdict,seq,kind:(dl&&verdict=='found')?'diagramless':'regular'})});
  setDl(false); await load();
  // went back to redo one? step forward through the ones you passed; otherwise on to the next issue in view
  const what=verdict=='found'?'page '+seq+' is the crossword':verdict=='absent'?'no crossword':'unsure';
  if(idx<stack.length-1){flash('Saved '+r.date+': '+what);history.forward();}
  else{const n=nextAfter(r.date);
    if(n){flash('Saved '+r.date+': '+what);nav(n.date)}
    else{show();flash('Saved '+r.date+': '+what+'. That was the last issue in this view, so there is nothing to move on to.')}}
}
$('filter').onchange=refilter;
$('prev').onclick=goPrev;$('next').onclick=goNext;
$('dl').onclick=()=>setDl(!dl);$('absent').onclick=()=>decide('absent');$('unsure').onclick=()=>decide('unsure');
document.onkeydown=e=>{if(e.target.tagName=='SELECT')return;if(e.key=='n')decide('absent');if(e.key=='d')setDl(!dl);if(e.key=='u')decide('unsure');if(e.key=='y'&&cur()&&cur().cand)decide('found',+cur().cand);
 if(e.key=='ArrowRight')$('next').click();if(e.key=='ArrowLeft')$('prev').click();
 if(/^[1-9]$/.test(e.key)&&cur()&&+e.key<=cur().pages)decide('found',+e.key)};
load();
</script>"""


def crop_boxes():
    """crops.tsv (scan.py crops): the box around each puzzle, in image pixels."""
    p, out = DATA / "crops.tsv", {}
    if p.exists():
        for line in p.read_text("utf8").splitlines()[1:]:
            f = line.split("\t")
            if len(f) >= 7 and f[2]:
                out[(f[0], int(f[1]))] = [int(v) for v in f[2:6]]
    return out


def crop(date, seq, width):
    box = crop_boxes().get((date, seq))
    if not box:
        return thumb(date, seq, width)          # no box recorded: the whole page
    p = DATA / "cache" / "crop" / date / f"seq-{seq}-{width}.jpg"
    if not p.exists():
        m = scan.manifest(date)
        iid = m["sequences"][0]["canvases"][seq - 1]["images"][0]["resource"]["@id"]
        x, y, w, h = box
        b = scan.get(f"{scan.BASE}{iid}/{x},{y},{w},{h}/{width},/0/default.jpg")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b)
    return p.read_bytes()


CONFIRM = r"""<!doctype html><meta charset=utf-8><title>Confirm the OCR's finds</title>
<style>
body{font:15px system-ui;margin:0;background:#f4f1ea;color:#222}
header{position:sticky;top:0;background:#fff;border-bottom:1px solid #ccc;padding:8px 14px;display:flex;gap:12px;align-items:center;flex-wrap:wrap;z-index:2}
button{font:inherit;padding:6px 14px;border:1px solid #888;border-radius:5px;background:#fff;cursor:pointer}
button.primary{background:#1d5c3a;color:#fff;border-color:#1d5c3a}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:10px;padding:12px}
.t{background:#fff;border:4px solid #fff;cursor:pointer;position:relative}
.t img{width:100%;display:block;aspect-ratio:1.3/1;object-fit:contain;background:#ddd}
.t .l{position:absolute;left:0;top:0;background:#000b;color:#fff;padding:2px 8px;font-size:13px}
.t.bad{border-color:#d9480f;background:#ffe3d0}.t.bad .l{background:#d9480f}
.t.crop{border-color:#f08c00;background:#fff3bf}.t.crop .l{background:#f08c00}
.t .m{position:absolute;right:0;top:0;color:#fff;padding:2px 8px;font-size:13px;display:none}
.t.bad .m{display:block;background:#d9480f}.t.crop .m{display:block;background:#f08c00}
.t a{position:absolute;right:4px;bottom:4px;background:#fffd;padding:1px 6px;font-size:12px}
small{color:#555}
</style>
<header><b>The OCR's finds: click a tile once if the CROP is bad (orange), twice if it is NOT a crossword (red)</b>
 <button id=go class=primary>Confirm the rest &rarr; (Enter)</button><button id=prev>&larr; prev batch</button><button id=next>next &rarr;</button><small id=count></small>
 <a href="/">full review page</a></header>
<div id=grid class=grid></div>
<script>
// Every batch of 20 is a history entry (#b0, #b1, ...), so the mouse's back/forward buttons walk the batches,
// including ones already confirmed, which can be re-marked and confirmed again. history.state holds the trail.
const N=20,$=id=>document.getElementById(id),CROPS=location.search.includes('crops=1');   // crops=1: label crops on every found page, decisions untouched
let trail=[],idx=0,mark=new Map();   // trail[i] = {batch:[rows], done, marks:[[date,'crop'|'no']]}
const src=r=>'/crop/'+r.date+'/'+r.seq+'.jpg?w=720';
const save=()=>history.replaceState({trail,idx},'','#b'+idx);
async function pending(){
  const all=await (await fetch('/api/issues')).json();
  const seen=new Set(trail.flatMap(t=>t.batch.map(r=>r.date)));
  return all.filter(r=>(CROPS?(r.state=='found'&&r.hasbox):(r.by=='scan'&&r.state=='found'))&&r.seq&&!seen.has(r.date));
}
function render(){
  const t=trail[idx]; mark=new Map(t.marks||[]); $('grid').innerHTML='';
  $('count').textContent='batch '+(idx+1)+(t.done?' · already confirmed: re-mark and Enter to redo':'');
  t.batch.forEach(r=>{
    const d=document.createElement('div'); d.className='t';
    const wd=new Date(r.date+'T12:00:00').toLocaleDateString('en-US',{weekday:'short'});
    d.innerHTML='<img src="'+src(r)+'"><span class=l>'+r.date+' '+wd+' · p'+r.seq+'/'+r.pages+'</span><span class=m></span><a target=_blank href="/thumb/'+r.date+'/'+r.seq+'.jpg?w=2400">page</a>';
    const paint=()=>{const v=mark.get(r.date);d.classList.remove('crop','bad');if(v){d.classList.add(v=='crop'?'crop':'bad');d.querySelector('.m').textContent=v=='crop'?'bad crop':'NOT a crossword'}
      const no=[...mark.values()].filter(x=>x=='no').length;$('go').textContent='Confirm the '+(t.batch.length-no)+' puzzles → (Enter)'};
    d.onclick=e=>{if(e.target.tagName=='A')return;const c=mark.get(r.date),n=!c?'crop':c=='crop'?'no':null;if(n)mark.set(r.date,n);else mark.delete(r.date);paint()};
    paint(); $('grid').appendChild(d);
  });
  window.scrollTo(0,0);
  pending().then(p=>p.slice(idx==trail.length-1?N:0,(idx==trail.length-1?N:0)+N).forEach(r=>{new Image().src=src(r)}));   // warm the next batch
}
async function go(){
  const t=trail[idx]; if(!t||!t.batch.length)return;
  const redo=!!t.done, ms=[...mark];
  await fetch('/api/bulk',{method:'POST',body:JSON.stringify({redo,cropsonly:CROPS,
    confirm:t.batch.filter(r=>mark.get(r.date)!='no').map(r=>({date:r.date,seq:+r.seq})),
    flag:t.batch.filter(r=>mark.get(r.date)=='no').map(r=>r.date),
    badcrop:t.batch.filter(r=>mark.get(r.date)=='crop').map(r=>({date:r.date,seq:+r.seq})),
    okcrop:t.batch.filter(r=>mark.get(r.date)!='crop'&&mark.get(r.date)!='no').map(r=>({date:r.date,seq:+r.seq}))})});
  t.done=true; t.marks=ms; save();
  if(idx<trail.length-1){history.forward();return}           // redoing: on to the next batch you passed
  const p=await pending();
  if(!p.length){$('grid').innerHTML='<p style="padding:20px">All confirmed. Anything you marked red is under "Needs a look" on the full review page.</p>';$('count').textContent='done';return}
  trail=trail.slice(0,idx+1).concat([{batch:p.slice(0,N)}]); idx=trail.length-1;
  history.pushState({trail,idx},'','#b'+idx); render();
}
window.onpopstate=e=>{if(e.state){if(e.state.trail.length>=trail.length)trail=e.state.trail;idx=e.state.idx}render()};   // the longest trail wins: an older entry's copy is shorter
$('go').onclick=go; $('prev').onclick=()=>history.back(); $('next').onclick=()=>history.forward();
document.onkeydown=e=>{if(e.key=='Enter')go();if(e.key=='ArrowLeft')history.back();if(e.key=='ArrowRight')history.forward()};
(async()=>{
  if(history.state&&history.state.trail){trail=history.state.trail;idx=history.state.idx;render();return}
  const p=await pending();
  if(!p.length){$('count').textContent='nothing left to confirm';return}
  trail=[{batch:p.slice(0,N)}];idx=0;save();render();
})();
</script>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, body, ctype="application/json", code=200):
        if isinstance(body, str):
            body = body.encode("utf8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/":
            return self.send(PAGE, "text/html; charset=utf-8")
        if u.path == "/confirm":
            return self.send(CONFIRM, "text/html; charset=utf-8")
        if u.path.startswith("/crop/"):
            date, seqf = u.path[6:].split("/")
            w = int(urllib.parse.parse_qs(u.query).get("w", ["720"])[0])
            try:
                return self.send(crop(date, int(seqf.split(".")[0]), w), "image/jpeg")
            except Exception as e:
                return self.send(str(e), "text/plain", 502)
        if u.path == "/api/recent":   # dates of the last decisions, oldest first, so prev can redo them after a reload
            seen = []
            if DECISIONS.exists():
                for line in DECISIONS.read_text("utf8").splitlines():
                    if line.strip():
                        d = json.loads(line)["date"]
                        if d in seen:
                            seen.remove(d)
                        seen.append(d)
            return self.send(json.dumps(seen[-30:]))
        if u.path == "/api/issues":
            return self.send(json.dumps(issues()))
        if u.path.startswith("/thumb/"):
            date, seqf = u.path[7:].split("/")
            w = int(urllib.parse.parse_qs(u.query).get("w", ["700"])[0])
            try:
                return self.send(thumb(date, int(seqf.split(".")[0]), w), "image/jpeg")
            except Exception as e:
                return self.send(str(e), "text/plain", 502)
        self.send("not found", "text/plain", 404)

    def do_POST(self):
        if self.path == "/api/bulk":
            # the confirm sheet: tiles a person left alone are confirmed; tiles they clicked go back to "needs a look"
            r = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            at = time.strftime("%Y-%m-%dT%H:%M:%S")
            with open(DECISIONS, "a", encoding="utf8") as f:
                for c in ([] if r.get("cropsonly") else r.get("confirm", [])):
                    f.write(json.dumps(dict(date=c["date"], verdict="found", seq=c["seq"], kind="regular",
                                            by="person", via="confirm-sheet", at=at)) + "\n")
                for d in r.get("flag", []):
                    f.write(json.dumps(dict(date=d, verdict="unsure", seq=None, kind="regular",
                                            by="person", via="confirm-sheet: not a crossword", at=at)) + "\n")
            boxes = crop_boxes()      # the box we drew, kept with the label: a test set for the box finder
            with open(DATA / "crop_flags.jsonl", "a", encoding="utf8") as f:
                for c in r.get("badcrop", []):
                    f.write(json.dumps(dict(date=c["date"], seq=c["seq"], box=boxes.get((c["date"], c["seq"])),
                                            label="bad-crop", by="person", at=at)) + "\n")
                if r.get("redo") or r.get("cropsonly"):             # a batch gone over again: crops now left unmarked are fine (last label per date wins)
                    for c in r.get("okcrop", []):
                        f.write(json.dumps(dict(date=c["date"], seq=c["seq"], box=boxes.get((c["date"], c["seq"])),
                                                label="crop-ok", by="person", at=at)) + "\n")
            return self.send(json.dumps(dict(confirmed=len(r.get("confirm", [])), flagged=len(r.get("flag", [])),
                                             badcrop=len(r.get("badcrop", [])))))
        if self.path != "/api/decide":
            return self.send("not found", "text/plain", 404)
        r = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        assert r["verdict"] in ("found", "absent", "unsure")
        rec = dict(date=r["date"], verdict=r["verdict"], seq=r.get("seq"), kind=r.get("kind", "regular"), by="person", at=time.strftime("%Y-%m-%dT%H:%M:%S"))
        with open(DECISIONS, "a", encoding="utf8") as f:
            f.write(json.dumps(rec) + "\n")
        self.send(json.dumps(rec))


def main():
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8765
    print(f"http://localhost:{port}/   data: {DATA}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()


if __name__ == "__main__":
    main()
