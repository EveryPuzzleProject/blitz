"""review.py's /answers sheet: settle the answer keys the matcher could not (answers.py).

Reads only what answers.py recorded: answer_puzzles.jsonl (each puzzle's status and key), answer_candidates.jsonl
(the pages that might carry its key, with the evidence, and the issues to browse and why), answer_grids.jsonl (the
grids detect_grids found on the pages it looked at) and answer_matches.jsonl (what each grid matched, and the
puzzles that share its grid), plus the issue's page list from the archive manifest. It draws those; it never
matches or detects anything.

Each item shows the puzzle and its proposed key side by side, large enough to read clues against answers (click
either to see it at full resolution). A proposed key is the matcher's choice (odd distance, or a spot check of a
match) or the nearest grid it found (unclear). y = yes, it is this puzzle's key; x = no, a different puzzle (it
shares the grid: Shenk reused grids, so the clues and answers are the test). Without a proposed key, or after an
x, pick the key from the issue's pages: first the pages where a grid was detected or the text points, the rest of
the issue folded below; click a page to zoom it, then click the key's outline or drag a box round it. n = no key
printed, u = can't tell.

A person's choice is a line in answer_decisions.jsonl (id, date, seq, verdict key/rejected/none/unsure, the key's
issue and page, the grid clicked or the box drawn, by, at, source); the last line per puzzle wins, and
`answers.py save` takes it.
"""
import json
import time

from answers import CANDS, DECISIONS, GRIDS, MATCHES, PUZZLES, SHORTLIST, jl, key_region, n_pages

ORDER = {"odd-distance": 0, "unclear": 1, "no-key-found": 2, "no-pattern": 3, "matched": 4}


def queue(page_size):
    cands = {(r["date"], r["seq"]): r for r in jl(CANDS)}
    grids = {}
    for r in jl(GRIDS):
        grids[(r["issue"], r["seq"])] = r
    match = {(m["issue"], m["seq"], m["grid"]): m for m in jl(MATCHES)}
    dec = {r["id"]: r for r in jl(DECISIONS)}

    def proposal(issue, seq, gi, how):
        g = grids.get((issue, seq))
        if not g or gi >= len(g["grids"]):
            return None
        x = g["grids"][gi]
        m = match.get((issue, seq, gi)) or {}
        W, H = page_size(issue, seq)
        b = m.get("best") or {}
        return dict(issue=issue, seq=seq, grid=gi, quad=x["quad"], rows=x["rows"], cols=x["cols"], how=how,
                    region=key_region(dict(quad=x["quad"]), W, H), verdict=m.get("verdict", ""),
                    best=b.get("date", ""), issues_after=b.get("issues_after"), distance=b.get("distance"),
                    tie=m.get("tie", ""), shared=[x["date"] for x in m.get("close") or [] if x["distance"] <= 2])
    out = []
    for p in jl(PUZZLES):
        c = cands.get((p["date"], p["seq"]), {})
        ev = {(x["issue"], x["seq"]): x for x in c.get("candidates", [])}
        pages = []
        for issue in c.get("browse", []):
            for q in range(1, n_pages(issue) + 1):
                g = grids.get((issue, q))
                W, H = page_size(issue, q)
                gs = []
                for gi, x in enumerate(g["grids"] if g else []):
                    m = match.get((issue, q, gi))
                    b = m.get("best") if m else None
                    gs.append(dict(gi=gi, quad=x["quad"], rows=x["rows"], cols=x["cols"], has_letters=x["has_letters"],
                                   region=key_region(dict(quad=x["quad"]), W, H),
                                   own=x.get("own_puzzle", False), verdict=m["verdict"] if m else "not scored",
                                   best=(f"{b['date']} p{b['seq']}: {b['distance']} cells differ"
                                         + ("" if b["same_size"] and b["offset"] == [0, 0] else
                                            f", a {x['rows']}x{x['cols']} grid at offset {b['offset']}")) if b else "",
                                   mine=bool(b and b["date"] == p["date"] and b["seq"] == p["seq"]),
                                   source=g["source"]))
                e = ev.get((issue, q))
                score = e["score"] if e else 0
                pages.append(dict(issue=issue, seq=q, W=W, H=H, score=score, why=e["why"] if e else [],
                                  looked=g is not None, grids=gs,
                                  first=score >= SHORTLIST or any(not x["own"] and x["rows"] >= 5 for x in gs)))
        item = dict(id=p["id"], date=p["date"], seq=p["seq"], kind=p["kind"], status=p["status"],
                    why=p.get("why", ""), odd=p.get("odd", ""), decision=dec.get(p["id"]),
                    puzzle_img=f"pages/{p['date']}/seq-{p['seq']}-puzzle.jpg", pages=pages,
                    browse_why=c.get("browse_why", {}))
        k = p.get("key")
        if k:
            item["proposed"] = proposal(k["issue"], k["seq"], k["grid"],
                                        "the matcher's pick" + (" (at an odd distance)" if p["status"] == "odd-distance" else ""))
        elif p.get("near"):
            n = p["near"][0]
            item["proposed"] = proposal(n["issue"], n["seq"], n["grid"], f"the nearest grid the matcher found ({n['verdict']})")
        out.append(item)
    out.sort(key=lambda r: (ORDER.get(r["status"], 9), r["date"], r["seq"]))
    return out


def record(r):
    assert r["verdict"] in ("key", "rejected", "none", "unsure")
    rec = dict(id=r["id"], date=r["date"], seq=int(r["seq"]), verdict=r["verdict"], by="person",
               at=time.strftime("%Y-%m-%dT%H:%M:%S"), source="/answers")
    if r["verdict"] in ("key", "rejected"):
        rec.update(issue=r["issue"], key_seq=int(r["key_seq"]))
        if r.get("grid") is not None:
            rec.update(grid=int(r["grid"]), quad=r["quad"],
                       how=r.get("how") or "clicked a grid detect_grids found (answer_grids.jsonl)")
        else:
            rec.update(box=[int(v) for v in r["box"]], how="drew a box on the page")
    with open(DECISIONS, "a", encoding="utf8") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


PAGE = r"""<!doctype html><meta charset=utf-8><title>Collegian answer keys</title>
<style>
body{font:15px system-ui;margin:0;background:#f4f1ea;color:#222}
header{position:sticky;top:0;background:#fff;border-bottom:1px solid #ccc;padding:8px 14px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;z-index:3}
button,select{font:inherit;padding:5px 10px;border:1px solid #888;border-radius:5px;background:#fff;cursor:pointer}
button.primary{background:#1d5c3a;color:#fff;border-color:#1d5c3a}
#info{padding:8px 14px}
#pair{display:flex;gap:12px;padding:0 14px;align-items:flex-start}
#pair figure{margin:0;flex:1;min-width:0;background:#fff;padding:6px}
#pair figcaption{font-weight:600;margin-bottom:4px}#pair figure img{width:100%;display:block;background:#ddd;cursor:zoom-in}
#pair .acts{margin-top:6px;display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.note{font-size:13px;color:#555;margin-top:4px}
h3{margin:16px 14px 6px;font-size:16px}
.keys{display:grid;grid-template-columns:repeat(auto-fill,minmax(440px,1fr));gap:12px;padding:0 14px}
.kc{background:#fff;padding:6px;border:3px solid transparent;cursor:pointer}.kc:hover{border-color:#1d5c3a}.kc.mine{border-color:#1c7ed6}
.kc img{width:100%;display:block;background:#ddd}.kc .cap{font-size:13px;margin-top:4px}.kc .zoom{float:right}
.sheet{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:10px;padding:0 14px}
details{margin:10px 14px}summary{cursor:pointer;color:#1d5c3a;font-weight:600;margin-bottom:8px}
.pg{background:#fff;padding:4px;position:relative;border:3px solid transparent;cursor:pointer}.pg:hover{border-color:#1d5c3a}
.pg.ev{border-color:#e8590c}.pg .im{position:relative}.pg img{width:100%;display:block;background:#ddd}
.pg .n{position:absolute;left:4px;top:4px;background:#000b;color:#fff;padding:1px 7px;font-weight:700;z-index:1}
.gq{position:absolute;box-sizing:border-box;border:2px solid #e8590c;background:#e8590c22;pointer-events:none}
.gq.mine{border-color:#1c7ed6;background:#1c7ed633}.gq.own{border:2px dashed #888;background:none}
.why{font-size:12px;color:#555;margin:3px 2px;min-height:15px}
small{color:#555}
#zoom{display:none;padding:10px}#zwrap{position:relative;cursor:crosshair;user-select:none;margin:0 auto;max-width:2400px}
#zwrap img{width:100%;display:block;background:#ddd;transition:opacity .15s}#zwrap.loading img{opacity:.25}
#zwrap .gq{pointer-events:auto;cursor:pointer;border-width:3px}#zwrap .gq:hover{background:#e8590c66}#zwrap .gq.own{pointer-events:none}
#dbox{position:absolute;border:3px solid #1c7ed6;background:#1c7ed633;pointer-events:none;display:none}
#lb{display:none;position:fixed;inset:0;background:#000d;z-index:9;overflow:auto;cursor:zoom-out}#lb img{display:block;margin:0 auto;max-width:none}
#flash{display:none;position:fixed;right:14px;bottom:14px;background:#1d5c3a;color:#fff;padding:10px 16px;border-radius:6px;z-index:8;max-width:460px}
</style>
<header>
 <select id=filter><option value=todo>Needs a look</option><option value=shared>Matched on a shared grid (spot check)</option><option value=matched>All matched (spot check)</option><option value=mine>You decided</option><option value=all>All</option></select>
 <button id=prev>&larr; prev</button><b id=title></b><button id=next>next &rarr;</button>
 <button id=back style="display:none">&larr; back (Esc)</button><button id=save class=primary style="display:none">Save my box (Enter)</button>
 <button id=none>No key printed (n)</button><button id=unsure>Can't tell (u)</button>
 <small id=count></small> <a href="/">issues</a>
</header>
<div id=info></div>
<div id=item>
 <div id=pair><figure><figcaption id=puzhd></figcaption><img id=puzimg title="click to see it at full size"></figure>
  <figure id=keyfig><figcaption id=keyhd></figcaption><img id=keyimg title="click to see it at full size"><div class=note id=keynote></div>
   <div class=acts><button class=primary id=yes>Yes, this is its key (y)</button><button id=no>No, a different puzzle (x)</button></div></figure></div>
 <div id=browse></div>
</div>
<div id=zoom><div id=zwrap><img id=zimg><div id=dbox></div></div></div>
<div id=lb><img id=lbimg></div>
<div id=flash></div>
<script>
const $=id=>document.getElementById(id);
const esc=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;');
const flash=m=>{const f=$('flash');f.textContent=m;f.style.display='block';clearTimeout(flash.t);flash.t=setTimeout(()=>f.style.display='none',5000)};
let ALL=[],list=[],cur=null,zp=null,draft=null,drag=null,shown=null;
const thumb=p=>'/thumb/'+p.issue+'/'+p.seq+'.jpg?w='+(p.W>9000?900:600);
const big=p=>'/thumb/'+p.issue+'/'+p.seq+'.jpg?w='+(p.W>9000?3000:1800);
const regionUrl=(pr,w)=>'/region/'+pr.issue+'/'+pr.seq+'.jpg?r='+pr.region.join(',')+'&w='+w;
const rejected=r=>r.decision&&r.decision.verdict=='rejected';
const inView=r=>{const f=$('filter').value;const open=!r.decision||rejected(r);
  return f=='all'||(f=='todo'&&r.status!='matched'&&open)||(f=='mine'&&r.decision)||(f=='matched'&&r.status=='matched'&&!r.decision)||
    (f=='shared'&&r.status=='matched'&&!r.decision&&r.proposed&&r.proposed.shared.length)};
async function load(){
  ALL=await (await fetch('/api/answers')).json(); list=ALL.filter(inView);
  const c={};ALL.forEach(r=>{const k=r.decision?'you: '+r.decision.verdict:r.status;c[k]=(c[k]||0)+1});
  $('count').textContent=list.length+' in view · '+Object.entries(c).map(([k,v])=>k+' '+v).join(' · ');
}
// the address is the puzzle (#1978-03-20) or the puzzle and a zoomed page (#1978-03-20/1978-03-21/14):
// every step is a history entry, so back and forward work and a reload keeps your place
function parse(){const [id,issue,seq]=decodeURIComponent(location.hash.slice(1)).split('/');return {id,issue,seq:+seq}}
async function start(){await load();const h=parse();cur=ALL.find(r=>r.id==h.id)||list[0]||null;
  if(cur&&!h.id)history.replaceState(null,'','#'+cur.id);route()}
window.onhashchange=route;
function route(){const h=parse();const r=ALL.find(x=>x.id==h.id);if(!r){if(cur)show();return}
  if(!cur||cur.id!=r.id||shown!=r.id){cur=r;show()} else if(!h.issue)unzoom();
  if(h.issue){const p=cur.pages.find(p=>p.issue==h.issue&&p.seq==h.seq);if(p)zoom(p)}}
function statusText(r){
  if(r.decision)return 'You said: '+({key:'the key is on '+r.decision.issue+' page '+r.decision.key_seq,rejected:'the proposed key is a different puzzle’s; find its own below',none:'no key printed',unsure:'can’t tell'})[r.decision.verdict];
  return ({matched:'Matched automatically',
    'odd-distance':'Matched at an odd distance for this stretch of the run',
    unclear:'A grid came close, but not clearly enough to accept','no-key-found':'No grid on the pages looked at matched this puzzle',
    'no-pattern':'No grid recorded for this puzzle, so nothing could be matched'})[r.status]||r.status;
}
function outline(box,p,g,clickable){
  const q=document.createElement('div');const xs=g.quad.map(v=>v[0]),ys=g.quad.map(v=>v[1]),x0=Math.min(...xs),y0=Math.min(...ys);
  Object.assign(q.style,{left:100*x0/p.W+'%',top:100*y0/p.H+'%',width:100*(Math.max(...xs)-x0)/p.W+'%',height:100*(Math.max(...ys)-y0)/p.H+'%'});
  q.className='gq'+(g.own?' own':g.mine?' mine':'');
  q.title=g.rows+'x'+g.cols+(g.has_letters?' with letters':'')+(g.own?' · this page’s puzzle':' · '+g.verdict+(g.best?' · nearest: '+g.best:''))+' · '+g.source;
  if(clickable&&!g.own)q.onclick=e=>{e.stopPropagation();decide({verdict:'key',issue:p.issue,key_seq:p.seq,grid:g.gi,quad:g.quad},'the '+g.rows+'x'+g.cols+' grid on '+p.issue+' page '+p.seq)};
  box.appendChild(q);
}
function pageTile(p){
  const d=document.createElement('div');d.className='pg'+(p.score>=4?' ev':'');
  d.innerHTML='<div class=im><img loading=lazy src="'+thumb(p)+'"><span class=n>'+(p.issue==cur.date?'same issue, ':p.issue+', ')+'p'+p.seq+'</span></div>'+
    '<div class=why title="'+esc(p.why.join('\n'))+'">'+esc(p.why[0]||'')+(p.why.length>1?' (+'+(p.why.length-1)+')':'')+(p.looked?'':' · <i>not looked at by the detector</i>')+'</div>';
  p.grids.forEach(g=>outline(d.querySelector('.im'),p,g,false));
  d.onclick=()=>{location.hash=cur.id+'/'+p.issue+'/'+p.seq};
  return d;
}
function show(){
  unzoom(true);
  if(!cur){$('title').textContent='nothing here';$('item').style.display='none';return}
  shown=cur.id;$('item').style.display='';
  $('title').textContent=cur.id+(cur.kind!='regular'?' · '+cur.kind:'');
  const pr=cur.proposed, ask=pr&&!cur.decision;
  $('info').innerHTML='<b>'+esc(statusText(cur))+'.</b> '+(cur.odd?esc(cur.odd)+'. ':'')+
    (ask?'Read a few answers against the clues: <b>y</b> if this is its key, <b>x</b> if it is a different puzzle with the same grid (Shenk reused grids).':
         'Find its key below: click the grid that is its key (click ‘full size’ to read it), or open a page and drag a box.');
  $('puzhd').textContent='The puzzle: '+cur.date+' page '+cur.seq; $('puzimg').src='/file/'+cur.puzzle_img;
  $('puzimg').onclick=()=>lightbox('/file/'+cur.puzzle_img);
  const kf=$('keyfig');
  if(pr){kf.style.display='';
    $('keyhd').textContent=(cur.decision&&cur.decision.verdict=='rejected'?'You rejected: ':'Proposed key: ')+pr.issue+' page '+pr.seq+(pr.issue==cur.date?' (same issue)':'');
    $('keyimg').src=regionUrl(pr,900);$('keyimg').onclick=()=>lightbox(regionUrl(pr,Math.min(2400,pr.region[2])));
    $('keynote').innerHTML=esc(pr.how)+(pr.distance!=null?'; '+pr.distance+' cells differ from this puzzle’s grid':'')+
      (pr.shared.length?'<br>The same grid (within 2 cells) as '+pr.shared.map(esc).join(', '):'')+(pr.tie?'<br>'+esc(pr.tie):'');
    kf.querySelector('.acts').style.display=ask?'':'none';
  } else kf.style.display='none';
  // every grid found on the short-list pages, as a readable crop: click the one that is its key
  const b=$('browse');b.innerHTML='';
  const ks=[];cur.pages.filter(p=>p.first).forEach(p=>p.grids.forEach(g=>{if(!g.own&&g.rows>=5&&g.cols>=5)ks.push([p,g])}));
  ks.sort((a,c)=>(c[1].mine-a[1].mine));
  if(ks.length){
    b.insertAdjacentHTML('beforeend','<h3>Grids found near it ('+ks.length+'): click its key</h3>');
    const kd=document.createElement('div');kd.className='keys';
    ks.forEach(([p,g])=>{const c=document.createElement('div');c.className='kc'+(g.mine?' mine':'');
      const pr={issue:p.issue,seq:p.seq,region:g.region};
      c.innerHTML='<img loading=lazy src="'+regionUrl(pr,700)+'"><div class=cap><a class=zoom href="#">full size</a><b>'+(p.issue==cur.date?'same issue':p.issue)+', page '+p.seq+'</b> · '+g.rows+'x'+g.cols+
        (g.has_letters?' with letters':'')+(g.best?' · nearest puzzle: '+esc(g.best):'')+(g.mine?' · <b style="color:#1c7ed6">nearest this puzzle</b>':'')+'</div>';
      c.onclick=e=>{if(e.target.classList.contains('zoom')){e.preventDefault();e.stopPropagation();lightbox(regionUrl(pr,Math.min(2400,g.region[2])));return}
        decide({verdict:'key',issue:p.issue,key_seq:p.seq,grid:g.gi,quad:g.quad},'the '+g.rows+'x'+g.cols+' grid on '+p.issue+' page '+p.seq)};
      kd.appendChild(c)});
    b.appendChild(kd);
  }
  // the issue's pages: where a grid was detected or the text points first, the rest folded
  if(!cur.pages.length){b.innerHTML='<h3>No issue recorded to browse for this puzzle.</h3>';}
  else{
    const why=Object.entries(cur.browse_why||{}).map(([i,w])=>i+' ('+esc(w)+')').join(' and ');
    const first=cur.pages.filter(p=>p.first), rest=cur.pages.filter(p=>!p.first);
    b.insertAdjacentHTML('beforeend','<h3>'+(ks.length?'None of these? ':'')+'The pages its key may be on: '+why+'. Click a page to zoom it and drag a box round the key.</h3>');
    const s1=document.createElement('div');s1.className='sheet';first.forEach(p=>s1.appendChild(pageTile(p)));b.appendChild(s1);
    if(!first.length)s1.innerHTML='<i style="padding:0 14px">No page with a detected grid or a pointer in the text.</i>';
    if(rest.length){const d=document.createElement('details');d.innerHTML='<summary>The rest of the issue ('+rest.length+' pages: nothing detected, no pointer)</summary>';
      const s2=document.createElement('div');s2.className='sheet';d.appendChild(s2);
      d.ontoggle=()=>{if(d.open&&!s2.children.length)rest.forEach(p=>s2.appendChild(pageTile(p)))};b.appendChild(d);}
  }
  const i=list.findIndex(r=>r.id==cur.id);       // warm the next puzzles' images
  list.slice(i+1,i+3).forEach(r=>{new Image().src='/file/'+r.puzzle_img;if(r.proposed)new Image().src=regionUrl(r.proposed,900)});
  window.scrollTo(0,0);
}
function lightbox(src){$('lbimg').src=src;$('lb').style.display='block';$('lb').scrollTo(0,0)}
$('lb').onclick=()=>{$('lb').style.display='none'};
function zoom(p){
  zp=p;draft=null;$('dbox').style.display='none';$('item').style.display='none';$('zoom').style.display='block';
  $('back').style.display='';$('save').style.display='';
  $('info').innerHTML='<b>'+p.issue+' page '+p.seq+'</b> for the puzzle of '+cur.date+'. Click the answer key’s outline, or drag a box round it if it has none. Esc goes back.';
  const w=$('zwrap');[...w.querySelectorAll('.gq')].forEach(e=>e.remove());w.classList.add('loading');
  $('zimg').onload=()=>{if(zp!==p)return;w.classList.remove('loading');p.grids.forEach(g=>outline(w,p,g,true));
    const g=p.grids.find(g=>!g.own&&g.mine)||p.grids.find(g=>!g.own);   // land near a found grid
    if(g){const y=Math.min(...g.quad.map(v=>v[1]))/p.H*$('zimg').clientHeight;window.scrollTo(0,Math.max(0,y-200))} else window.scrollTo(0,0)};
  $('zimg').src=big(p);
}
function unzoom(quiet){const was=!!zp;zp=null;$('zoom').style.display='none';$('back').style.display='none';$('save').style.display='none';
  if(cur)$('item').style.display='';if(was&&!quiet&&cur)show()}
const pt=e=>{const r=$('zimg').getBoundingClientRect();return [Math.max(0,Math.min(e.clientX-r.left,r.width)),Math.max(0,Math.min(e.clientY-r.top,r.height))]};
$('zwrap').onmousedown=e=>{if(e.button!==0||!zp)return;e.preventDefault();drag=pt(e)};
window.onmousemove=e=>{if(!drag||!zp)return;const p=pt(e),k=zp.W/$('zimg').clientWidth;
  const x0=Math.min(drag[0],p[0]),y0=Math.min(drag[1],p[1]),w=Math.abs(p[0]-drag[0]),h=Math.abs(p[1]-drag[1]);
  draft=[Math.round(x0*k),Math.round(y0*k),Math.round(w*k),Math.round(h*k)];
  Object.assign($('dbox').style,{display:'block',left:x0+'px',top:y0+'px',width:w+'px',height:h+'px'})};
window.onmouseup=e=>{if(e.button===0)drag=null};
function saveBox(){if(!zp||!draft||draft[2]<40||draft[3]<40){flash('Drag a box round the answer grid first');return}
  decide({verdict:'key',issue:zp.issue,key_seq:zp.seq,box:draft},'a box you drew on '+zp.issue+' page '+zp.seq)}
function yes(){const pr=cur&&cur.proposed;if(!pr||cur.decision)return;
  decide({verdict:'key',issue:pr.issue,key_seq:pr.seq,grid:pr.grid,quad:pr.quad,how:'said yes to '+pr.how+' (answer_matches.jsonl)'},'the proposed grid on '+pr.issue+' page '+pr.seq)}
async function no(){const pr=cur&&cur.proposed;if(!pr||cur.decision)return;const r=cur;
  await fetch('/api/answer',{method:'POST',body:JSON.stringify({id:r.id,date:r.date,seq:r.seq,verdict:'rejected',issue:pr.issue,key_seq:pr.seq,grid:pr.grid,quad:pr.quad,how:'said no: '+pr.how+' is a different puzzle’s key'})});
  await load();cur=ALL.find(x=>x.id==r.id);flash('Saved '+r.id+': the proposed key is a different puzzle’s. Find its own key below, or n / u.');show();
  window.scrollTo(0,$('browse').offsetTop-70)}
async function decide(o,what){
  if(!cur)return;const r=cur;
  await fetch('/api/answer',{method:'POST',body:JSON.stringify(Object.assign({id:r.id,date:r.date,seq:r.seq},o))});
  const msg='Saved '+r.id+': '+(o.verdict=='key'?'the key is '+what:o.verdict=='none'?'no key printed':'can’t tell');
  const i=list.findIndex(x=>x.id==r.id), nx=list.slice(i+1).find(x=>x.id!=r.id);
  await load();
  if(nx){flash(msg);location.hash=nx.id}
  else{cur=null;unzoom(true);$('item').style.display='none';$('title').textContent='nothing more here';
    $('info').innerHTML='<div style="background:#fff;border:2px solid #1d5c3a;padding:24px;text-align:center;max-width:600px;margin:20px auto"><h2 style="margin:0 0 8px">Nothing more to see here</h2><p>'+esc(msg)+'. That was the last puzzle in this view.</p><p><button onclick="history.back()">&larr; back to the last one</button></p></div>'}
}
$('filter').onchange=async()=>{await load();if(list[0])location.hash=list[0].id;else{cur=null;show()}};
$('prev').onclick=()=>{const i=list.findIndex(r=>cur&&r.id==cur.id);if(i>0)location.hash=list[i-1].id};
$('next').onclick=()=>{const i=list.findIndex(r=>cur&&r.id==cur.id);if(list[i+1])location.hash=list[i+1].id};
$('back').onclick=()=>{location.hash=cur.id};$('save').onclick=saveBox;$('yes').onclick=yes;$('no').onclick=no;
$('none').onclick=()=>decide({verdict:'none'});$('unsure').onclick=()=>decide({verdict:'unsure'});
document.onkeydown=e=>{if(e.target.tagName=='SELECT')return;
  if($('lb').style.display=='block'){if(e.key=='Escape')$('lb').style.display='none';return}
  if(zp){if(e.key=='Enter')saveBox();if(e.key=='Escape')location.hash=cur.id}
  if(e.key=='n')decide({verdict:'none'});if(e.key=='u')decide({verdict:'unsure'});
  if(!zp&&e.key=='y')yes();if(!zp&&e.key=='x')no();
  if(!zp&&e.key=='ArrowRight')$('next').click();if(!zp&&e.key=='ArrowLeft')$('prev').click()};
start();
</script>"""
