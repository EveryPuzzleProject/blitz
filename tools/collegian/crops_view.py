"""review.py's /crops sheet: check every saved answer-key crop (answers.py save) and mark the bad ones.

Reads answer_keys.jsonl (each saved key: the puzzle, the page it was printed on, the crop's file and archive pixels,
where its box came from) and key_crop_flags.jsonl; draws the saved crop files themselves. Batches of 60, like the
confirm sheet of the page-finding pass: click a crop that is wrong (cut off, the wrong grid, too much of the page),
then "Done with this batch": the clicked ones are `bad-crop`, the rest `crop-ok`. The last label per puzzle wins.
A bad crop goes to /answers' "Bad crops (redraw)" filter, where its page opens zoomed in on the key for a new box.

key_crop_flags.jsonl: id, date, file, region (the crop that was judged), label, by, at, source.
"""
import json
import time

from answers import DATA, KEYS, jl

CROPFLAGS = DATA / "key_crop_flags.jsonl"


def flags():
    return {r["id"]: r for r in jl(CROPFLAGS)}


def short_how(how):
    h = how or ""
    if h.startswith("picked by") and "box drawn" in h:
        return "your box"
    if h.startswith("picked by"):
        return "your pick" + (", extended from a piece" if "extended from" in h else "")
    return "matched automatically" + (", extended from a piece" if "extended from" in h else "")


def queue():
    fl = flags()
    out = []
    for k in jl(KEYS):
        f = fl.get(k["id"])
        # a flag is about the crop it saw: once the key is saved with another box, the flag no longer applies
        current = f if f and f.get("region") == k["region"] else None
        out.append(dict(id=k["id"], date=k["date"], issue=k["issue"], seq=k["seq"], file=k["file"], region=k["region"],
                        how=short_how(k["how"]), flag=current["label"] if current else "",
                        old_flag=f["label"] if f and not current else ""))
    out.sort(key=lambda r: (r["date"], r["id"]))
    return out


def record(r):
    keys = {k["id"]: k for k in jl(KEYS)}
    at = time.strftime("%Y-%m-%dT%H:%M:%S")
    n = 0
    with open(CROPFLAGS, "a", encoding="utf8") as f:
        for label, ids in (("bad-crop", r.get("bad", [])), ("crop-ok", r.get("ok", []))):
            for i in ids:
                k = keys.get(i)
                if k:
                    f.write(json.dumps(dict(id=i, date=k["date"], file=k["file"], region=k["region"], label=label,
                                            by="person", at=at, source="/crops")) + "\n")
                    n += 1
    return dict(saved=n, bad=len(r.get("bad", [])), ok=len(r.get("ok", [])))


PAGE = r"""<!doctype html><meta charset=utf-8><title>Collegian key crops</title>
<style>
body{font:15px system-ui;margin:0;background:#f4f1ea;color:#222}
header{position:sticky;top:0;background:#fff;border-bottom:1px solid #ccc;padding:8px 14px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;z-index:3}
button,select{font:inherit;padding:5px 10px;border:1px solid #888;border-radius:5px;background:#fff;cursor:pointer}
button.primary{background:#1d5c3a;color:#fff;border-color:#1d5c3a}
#help{padding:6px 14px;color:#444}
#sheet{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px;padding:10px 14px}
.c{background:#fff;padding:4px;border:4px solid transparent;cursor:pointer;position:relative}.c:hover{border-color:#888}
.c.bad{border-color:#c92a2a;background:#ffe3e3}.c.bad::after{content:'bad crop';position:absolute;right:6px;top:6px;background:#c92a2a;color:#fff;padding:1px 6px;font-size:12px}
.c img{width:100%;display:block;background:#ddd;aspect-ratio:1/1;object-fit:contain}
.c .cap{font-size:12px;margin-top:3px;color:#333}.c .cap a{float:right}
#flash{display:none;position:fixed;right:14px;bottom:14px;background:#1d5c3a;color:#fff;padding:10px 16px;border-radius:6px;z-index:8}
</style>
<header>
 <select id=filter><option value=todo>Not checked yet</option><option value=bad>Marked bad</option><option value=all>All saved keys</option></select>
 <button id=prev>&larr; prev batch</button><b id=title></b><button id=next>next batch &rarr;</button>
 <button id=done class=primary>Done with this batch (Enter)</button>
 <small id=count></small> <a href="/answers">answers</a>
</header>
<div id=help>Click every crop that is wrong: cut off, the wrong grid, or so loose the key is hard to find. Leave the good ones alone; <b>Done</b> marks the rest fine. Bad ones go to <a href="/answers">/answers</a> &rarr; "Bad crops (redraw)".</div>
<div id=sheet></div><div id=flash></div>
<script>
const $=id=>document.getElementById(id);
const esc=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;');
const DOW=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
const dow=d=>{const [y,m,dd]=d.split('-').map(Number);return d+' '+DOW[new Date(Date.UTC(y,m-1,dd)).getUTCDay()]};
const flash=m=>{const f=$('flash');f.textContent=m;f.style.display='block';clearTimeout(flash.t);flash.t=setTimeout(()=>f.style.display='none',5000)};
const N=60;let ALL=[],list=[],start=0,bad=new Set();
async function load(){ALL=await (await fetch('/api/crops')).json();const f=$('filter').value;
  list=ALL.filter(r=>f=='all'||(f=='todo'&&!r.flag)||(f=='bad'&&r.flag=='bad-crop'));
  const ck=ALL.filter(r=>r.flag).length;
  $('count').innerHTML='<b>'+ck+' of '+ALL.length+' checked</b> · '+ALL.filter(r=>r.flag=='bad-crop').length+' marked bad · '+list.length+' in this view'}
// the address is the batch's first puzzle (#1978-03-20): every batch is a history entry, so back and forward work
function batchAt(id){const i=list.findIndex(r=>r.id==id);return i<0?0:Math.floor(i/N)*N}
function show(){
  const s=$('sheet');s.innerHTML='';bad=new Set(list.slice(start,start+N).filter(r=>r.flag=='bad-crop').map(r=>r.id));
  const b=list.slice(start,start+N);
  if(!b.length){$('title').textContent='nothing more here';
    s.innerHTML='<div style="grid-column:1/-1;background:#fff;border:2px solid #1d5c3a;padding:24px;text-align:center;max-width:600px;margin:20px auto"><h2 style="margin:0 0 8px">Nothing more to see here</h2><p>That was the last batch in this view.</p></div>';return}
  $('title').textContent='crops '+(start+1)+'–'+(start+b.length)+' of '+list.length;
  b.forEach(r=>{const c=document.createElement('div');c.className='c'+(bad.has(r.id)?' bad':'');
    c.innerHTML='<img loading=lazy src="/file/'+r.file+'"><div class=cap><a href="/answers#'+encodeURIComponent(r.id)+'" target=_blank title="open it on /answers">open</a><b>'+esc(dow(r.date))+'</b>'+(r.id!=r.date?' (stub)':'')+
      '<br>key: '+(r.issue==r.date?'same issue':esc(dow(r.issue)))+', page '+r.seq+' · '+esc(r.how)+(r.old_flag?' · <i>redrawn</i>':'')+'</div>';
    c.onclick=e=>{if(e.target.tagName=='A')return;bad.has(r.id)?bad.delete(r.id):bad.add(r.id);c.classList.toggle('bad')};
    $('sheet').appendChild(c)});
  list.slice(start+N,start+2*N).forEach(r=>{new Image().src='/file/'+r.file});    // warm the next batch
  window.scrollTo(0,0);
}
function nav(i){start=Math.max(0,i);const r=list[start];location.hash=r?encodeURIComponent(r.id):''}
window.onhashchange=()=>{start=batchAt(decodeURIComponent(location.hash.slice(1)));show()};
async function done(){const b=list.slice(start,start+N);if(!b.length)return;
  const res=await (await fetch('/api/cropflags',{method:'POST',body:JSON.stringify({bad:b.filter(r=>bad.has(r.id)).map(r=>r.id),ok:b.filter(r=>!bad.has(r.id)).map(r=>r.id)})})).json();
  const f=$('filter').value, keepPlace=f!='todo';  // in "not checked yet" the batch just done leaves the view
  const next=keepPlace?start+N:start;await load();
  flash('Saved: '+res.bad+' bad, '+res.ok+' fine.');
  if(next<list.length)nav(next);else{start=list.length;history.pushState(null,'','#end');show()}}
$('filter').onchange=async()=>{await load();nav(0)};
$('prev').onclick=()=>nav(start-N);$('next').onclick=()=>nav(start+N);$('done').onclick=done;
document.onkeydown=e=>{if(e.target.tagName=='SELECT')return;if(e.key=='Enter')done();if(e.key=='ArrowRight')nav(start+N);if(e.key=='ArrowLeft')nav(start-N)};
(async()=>{await load();start=batchAt(decodeURIComponent(location.hash.slice(1)));show()})();
</script>"""
