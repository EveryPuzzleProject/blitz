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


def issues():
    rows, dec = scan.read_rows(), decisions()
    out = []
    for date, r in sorted(rows.items()):
        p = dec.get(date)
        if p:
            state = "found" if p["verdict"] == "found" else p["verdict"]
            seq = p.get("seq") or ""
            by = "person"
        else:
            state, seq, by = r["verdict"], r.get("seq", ""), "scan"
        g = (r.get("guess") or "").split("|")
        cand, why = (r.get("seq", ""), "the scan saw part of a crossword here") if r.get("seq") else \
                    ((g[0], f"era guess: {g[1]} nearby puzzles were on this page") if g[0] else ("", ""))
        out.append(dict(date=date, pages=int(r["pages"] or 0), state=state, seq=seq, by=by,
                        scan_verdict=r["verdict"], scan_seq=r.get("seq", ""), evidence=r.get("evidence", ""),
                        cand=cand, why=why))
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
.sheet{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:10px;padding:12px}
.pg{background:#fff;border:3px solid transparent;position:relative;cursor:pointer}
.pg img{width:100%;display:block;background:#222}
.pg:hover{border-color:#1d5c3a}
.pg.cand{border-color:#d58a00}.pg.chosen{border-color:#1d5c3a}
.pg .n{position:absolute;left:0;top:0;background:#000b;color:#fff;padding:2px 8px;font-weight:700}
.pg .tag{position:absolute;right:0;top:0;background:#d58a00;color:#fff;padding:2px 8px}
.pg.chosen .tag{background:#1d5c3a}
.pg a{position:absolute;right:4px;bottom:4px;background:#fffd;padding:1px 6px;font-size:12px}
small{color:#555}
</style>
<header>
 <select id=filter>
  <option value=todo>Needs a look</option><option value=check>Scan unsure</option><option value=nohit>Scan found nothing</option>
  <option value=found>Found (spot check)</option><option value=absent>You said no crossword</option><option value=all>All</option>
 </select>
 <button id=prev>&larr; prev</button><b id=title></b><button id=next>next &rarr;</button>
 <button id=absent class=primary>No crossword this day (n)</button>
 <button id=unsure>Can't tell (u)</button>
 <small id=count></small>
</header>
<div id=cand style="padding:12px 12px 0"></div>
<div id=sheet class=sheet></div>
<script>
let list=[],i=0;
const $=id=>document.getElementById(id);
async function load(keep){
  const all=await (await fetch('/api/issues')).json();
  const f=$('filter').value;
  list=all.filter(r=>f=='all'||(f=='todo'&&['check','no-hit','pending','unsure'].includes(r.state))||(f=='check'&&r.state=='check')||(f=='nohit'&&r.state=='no-hit')||(f=='found'&&r.state=='found')||(f=='absent'&&r.state=='absent'));
  const cnt={};all.forEach(r=>cnt[r.state]=(cnt[r.state]||0)+1);
  $('count').textContent=list.length+' in view · '+Object.entries(cnt).map(([k,v])=>k+' '+v).join(' · ');
  if(!keep)i=0; if(i>=list.length)i=Math.max(0,list.length-1);
  show();
}
function show(){
  const r=list[i]; const s=$('sheet'); s.innerHTML='';
  if(!r){$('title').textContent='nothing here';return}
  const dow=new Date(r.date+'T12:00:00').toLocaleDateString('en-US',{weekday:'short'});
  $('title').textContent=r.date+' '+dow+' · '+r.pages+' pages · '+r.state+(r.by=='person'?' (you)':' (scan'+(r.scan_seq?', p'+r.scan_seq:'')+')');
  const c=$('cand'); c.innerHTML='';
  if(r.cand&&r.by=='scan'){
    c.innerHTML='<div style="background:#fff;padding:8px;border:3px solid #d58a00"><b>Page '+r.cand+'</b> <small>('+r.why+')</small> '+
      '<button class=primary onclick="decide(\'found\','+r.cand+')">Yes, the crossword is on page '+r.cand+' (y)</button>'+
      '<br><img style="max-width:100%;margin-top:6px" src="/thumb/'+r.date+'/'+r.cand+'.jpg?w=1500"></div>';
  }
  for(let n=1;n<=r.pages;n++){
    const d=document.createElement('div'); d.className='pg'+(String(r.cand)==n&&r.by=='scan'?' cand':'')+(String(r.seq)==n&&r.by=='person'&&r.state=='found'?' chosen':'');
    d.innerHTML='<img loading=lazy src="/thumb/'+r.date+'/'+n+'.jpg?w=560"><span class=n>'+n+'</span>'+
      (d.className.includes('cand')?'<span class=tag>guess</span>':'')+(d.className.includes('chosen')?'<span class=tag>your pick</span>':'')+
      '<a target=_blank href="/thumb/'+r.date+'/'+n+'.jpg?w=2400">big</a>';
    d.onclick=e=>{if(e.target.tagName!='A')decide('found',n)};
    s.appendChild(d);
  }
  window.scrollTo(0,0);
}
async function decide(verdict,seq){
  const r=list[i];
  await fetch('/api/decide',{method:'POST',body:JSON.stringify({date:r.date,verdict,seq})});
  const f=$('filter').value; await load(true);
  if(f!='todo'&&f!='check'&&f!='nohit'){i=Math.min(i+1,list.length-1);show()}
}
$('filter').onchange=()=>load(false);
$('prev').onclick=()=>{i=Math.max(0,i-1);show()};$('next').onclick=()=>{i=Math.min(list.length-1,i+1);show()};
$('absent').onclick=()=>decide('absent');$('unsure').onclick=()=>decide('unsure');
document.onkeydown=e=>{if(e.target.tagName=='SELECT')return;if(e.key=='n')decide('absent');if(e.key=='u')decide('unsure');if(e.key=='y'&&list[i]&&list[i].cand)decide('found',+list[i].cand);
 if(e.key=='ArrowRight')$('next').click();if(e.key=='ArrowLeft')$('prev').click();
 if(/^[1-9]$/.test(e.key)&&list[i]&&+e.key<=list[i].pages)decide('found',+e.key)};
load();
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
        if self.path != "/api/decide":
            return self.send("not found", "text/plain", 404)
        r = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        assert r["verdict"] in ("found", "absent", "unsure")
        rec = dict(date=r["date"], verdict=r["verdict"], seq=r.get("seq"), by="person", at=time.strftime("%Y-%m-%dT%H:%M:%S"))
        with open(DECISIONS, "a", encoding="utf8") as f:
            f.write(json.dumps(rec) + "\n")
        self.send(json.dumps(rec))


def main():
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8765
    print(f"http://localhost:{port}/   data: {DATA}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()


if __name__ == "__main__":
    main()
