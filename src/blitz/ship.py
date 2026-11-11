"""blitz ship: a batch's reviewed puzzles into the publication repo's xd/, and from there a gxd export.

The last milestone of a batch (docs: design/ship.md). It reads what the earlier ones recorded and
works nothing out about a puzzle itself:

    the run's proof packets   <harvest>/proof/<run>/<pid>/puzzle.xd, review.json, ocr.json
    triage's record           <harvest>/triage/<run>/triage.json (reason codes, the ship check)
    the ledger                <publication repo>/fixes/decisions.jsonl (proof:<pid>, batch:<pid>, drops)
    the review site           helpers' Ready / Not ready (blitz site-import), taken into the ledger first

and writes, in the publication's repo:

    xd/<xdid>.xd              the puzzle as its proof packet shows it, with the reviewers' reading fixes: as
                              printed, but for a misprinted key letter, corrected and said in its notes
    fixes/xdids.tsv           the ids it pinned
    provenance.jsonl          per xdid: the packet, who said what, which rule shipped it, the record of every
                              edit (class, before, after, who, where to see it), and the corrections of the
                              print proposed for the gxd export
    gxd-exports.tsv           per xdid: its gxd id and the links crossref credits (as judge's)
    pipeline/ship/<batch>.json  every puzzle of the batch: shipped, shippable or held, with the reason
                              (the batch page draws this file; it computes nothing)

The ship rule is one function, standing(), with its options in Rule. Everything else here applies it.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import shutil
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from pathlib import Path

from .work import Stop

SITE, AGENT = "review site", "agent review"  # a ledger record's via: a helper's (the hosted proof page), an AI's
CHECK_BY = "the ship check"  # the by of the no-model ship check's own Ready (xword-ocr shipcheck)
AI_READY = ("off", "both", "either")
PUBLIC = "https://pub-52ac4a15c4ba43fe8e4af5a496733fb5.r2.dev"  # the review site's packages
PROOF_PAGE = "https://blitz.xwordapp.com/review/?p="
CREDIT = "Every Puzzle Project"


# ---- the ship rule -------------------------------------------------------------------------

@dataclass(frozen=True)
class Rule:
    """The ship rule's options. The defaults are the owner's standing rule (2026-10-19): a puzzle
    ships with at least one person's Ready and no Not ready, and the owner's own decision overrides.

    ai_ready: whether an AI counts as the one Ready when no person has said it. "off" (the default:
      not decided), "both" (the AI proof reviewer's Ready and a passing ship check together) or
      "either" (one of them is enough: xword-ocr docs/ship-gate.md's design).
    hold_codes: triage reason codes that hold a puzzle whoever said Ready (clue-typed: a clue the
      text step supplied with no OCR reading behind it).
    ignore: reviewers whose decisions don't count (a scripted usability test's account).
    owner: the owner's own accounts on the review site. A decision made there under one of these
      names is the owner's, and overrides as the owner's do in their own tools."""
    ai_ready: str = "off"
    hold_codes: tuple = ("clue-typed",)
    ignore: tuple = ()
    owner: tuple = ()


def rule_of(repo: Path, **over) -> Rule:
    """The publication's rule: fixes/ship-rule.json where it has one, then the caller's overrides."""
    f = Path(repo) / "fixes" / "ship-rule.json"
    d = {k: v for k, v in (json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}).items() if not k.startswith("_")}
    d.update({k: v for k, v in over.items() if v is not None})
    if d.get("ai_ready", "off") not in AI_READY:
        raise Stop(f"ai_ready is one of {', '.join(AI_READY)}, not {d['ai_ready']!r}")
    return Rule(**{k: tuple(v) if isinstance(v, list) else v for k, v in d.items()})


def kind_of(rec: dict, rule: Rule = Rule()) -> str:
    """Whose decision a proof record is: owner (made in the maintainer's own tools, or on the review
    site under one of rule.owner's names), helper (anyone else on the review site), ai (the AI proof
    reviewer) or check (the ship check)."""
    if rec.get("via") == AGENT:
        return "check" if rec.get("by", "").startswith(CHECK_BY) else "ai"
    return "helper" if rec.get("via") == SITE and _name(rec) not in rule.owner else "owner"


def _name(rec: dict) -> str:
    return re.sub(rf" \({SITE}\)$", "", rec.get("by", ""))


def standing(batch: dict, proofs: list[dict], *, check_ok: bool = False, codes: frozenset | set = frozenset(),
             current: tuple = (), rule: Rule = Rule()) -> dict:
    """Whether one puzzle ships: THE ship rule. Nothing else decides it.

    batch: the ledger's latest batch:<pid> (the owner's Ship / Hold on the batch page), or {}.
    proofs: each reviewer's latest proof:<pid> record (Ready / Not ready).
    check_ok: triage's ship check passes. codes: triage's reason codes for the puzzle.
    current: the fingerprints of the puzzle's current version (a Ready on another version doesn't count).

    Returns {status: ship | hold, reason, why, rule: owner | people | ai | "", by, said, apply}:
    - the owner's own latest decision wins (reason owner-hold when it is Hold or Not ready);
    - otherwise any Not ready, a person's or the AI reviewer's, holds it for the owner (not-ready);
    - otherwise one person's Ready ships it (rule "people");
    - otherwise, with rule.ai_ready on, the AI's Ready ships it (rule "ai");
    - otherwise it waits (no-ready; proof-stale when the only Ready was on an earlier version);
    - and a puzzle that would ship is held when it carries one of rule.hold_codes (the code is the reason).
    said: every decision counted, oldest first; apply: the Ready records whose edits the import applies."""
    said = []
    for r in sorted(proofs, key=lambda r: r.get("at", "")):
        if r.get("answer") not in ("ready", "notready") or _name(r) in rule.ignore:
            continue
        xd = ((r.get("proof") or {}).get("review") or {}).get("xd")
        said.append({"who": r.get("by", ""), "kind": kind_of(r, rule), "answer": r["answer"], "note": r.get("note", ""),
                     "at": r.get("at", ""), "stale": bool(r["answer"] == "ready" and current and xd and xd not in current), "rec": r})
    ready = [s for s in said if s["answer"] == "ready" and not s["stale"]]
    who = lambda ss: ", ".join(s["who"] for s in ss)

    def out(status, reason, why, by="", how=""):
        return {"status": status, "reason": reason, "why": why, "rule": how, "by": by,
                "said": [{k: v for k, v in s.items() if k != "rec"} for s in said],
                "apply": [s["rec"] for s in ready] if status == "ship" else []}

    mine = max((s for s in said if s["kind"] == "owner"), key=lambda s: s["at"], default=None)
    res = None
    if mine and mine["at"] > batch.get("at", ""):
        if mine["answer"] == "notready":
            res = out("hold", "owner-hold", f"{mine['who']} said Not ready on the proof page" + (f": {mine['note']}" if mine["note"] else ""))
        elif mine["stale"]:
            res = out("hold", "proof-stale", f"{mine['who']}'s Ready was on an earlier version of the puzzle: look again")
        else:
            over = [s for s in said if s["answer"] == "notready"]  # said so: the owner may not have seen a later one
            res = out("ship", "", f"Ready by {mine['who']}" + (f", over a Not ready by {who(over)}"
                      + (" given after it" if any(s["at"] > mine["at"] for s in over) else "") if over else ""), mine["who"], "owner")
    elif batch.get("answer") == "hold":
        res = out("hold", "owner-hold", f"held on the batch page by {batch.get('by', '')}" + (f": {batch['note']}" if batch.get("note") else ""))
    elif batch.get("answer") == "ship":
        res = out("ship", "", f"Ship on the batch page by {batch.get('by', '')}", batch.get("by", ""), "owner")
    if res is None:
        no = [s for s in said if s["answer"] == "notready"]
        people = [s for s in ready if s["kind"] == "helper"]
        ai = any(s["kind"] == "ai" for s in ready)
        ai_ok = {"off": False, "both": ai and check_ok, "either": ai or check_ok}[rule.ai_ready]
        if no:
            res = out("hold", "not-ready", "said Not ready by " + "; ".join(s["who"] + (f": {s['note']}" if s["note"] else "") for s in no))
        elif people:
            res = out("ship", "", f"Ready by {who(people)}, no Not ready", who(people), "people")
        elif ai_ok:
            by = " and ".join(x for x in ("the AI proof reviewer's Ready" if ai else "", "the ship check passes" if check_ok else "") if x)
            res = out("ship", "", f"{by} (ai_ready: {rule.ai_ready}), no Not ready", by, "ai")
        elif any(s["stale"] for s in said):
            res = out("hold", "proof-stale", f"{who([s for s in said if s['stale']])}'s Ready was on an earlier version of the puzzle")
        else:
            has = [x for x in ("the AI proof reviewer said Ready" if ai else "", "the ship check passes" if check_ok else "") if x]
            res = out("hold", "no-ready", "no person has said Ready" + (f" ({'; '.join(has)})" if has else ""))
    held = sorted(set(codes) & set(rule.hold_codes))
    if res["status"] == "ship" and held:
        res = {**out("hold", held[0], f"carries {', '.join(held)}: held whoever said Ready"), "rule": res["rule"]}
    return res


# ---- the queues: what the batch asks of people ---------------------------------------------

QUEUES = ("question", "unchecked", "broken", "shippable", "shipped", "set-aside", "not-a-crossword")
# a held puzzle's queue, by its reason; every reason not named here is the pipeline's (broken)
QUEUE_OF = {"not-ready": "question", "owner-hold": "question", "edits-differ": "question",
            "no-ready": "unchecked", "proof-stale": "unchecked"}
# the stage a broken puzzle's reason points to, where triage recorded none (triage's blocking names its own)
STAGE_OF = {"packet-stale": "proof packet", "no-packet": "proof packet", "edits-unapplied": "import", "xd-exists": "import",
            "clue-typed": "text step"}
# the ship check's findings that make a puzzle incomplete, and the stage each points to
INCOMPLETE_STAGE = {"grid-unsolved": "key reading", "clue-empty": "parts", "clue-missing": "assembly", "clue-extra": "assembly",
                    "second-set-missing": "assembly"}
# a question about a header belongs to a group shared across puzzles (by the header it is about); one
# about a clue, a square or a printed line is that puzzle's own
GROUPS = {"title": "the title", "byline": "the byline", "notes": "the notes"}
# A reviewer's send-back from the proof page (a Not ready that says the pipeline has to read something again:
# review.sendback {kind, part, note}): the words and the stage each points to, as xword-ocr problems.py has them
SENT_BACK = {"missing-part": ("a part of the puzzle is missing", "parts"), "ocr-broken": ("the text is badly misread", "parts"),
             "mixed": ("parts of two puzzles are mixed together", "assembly"), "not-a-puzzle": ("this isn't a crossword", ""),
             "other": ("something no edit on the proof page fixes", "")}
SENT_BACK_PART = {"across": ("the Across clues", "parts"), "down": ("the Down clues", "parts"), "grid": ("the grid", "parts"),
                  "key": ("the answer key", "assembly"), "title": ("the title or byline", "assembly")}
SPOT_ONE_IN = 10


def group_of(row: str) -> str:
    """The shared-question group of a proof-page row: the header field it is about (ev:title and
    meta:title: title; author as byline; note as notes), "" for a clue, a square or a printed line."""
    m = re.fullmatch(r"(?:ev|meta):(\w+)", row or "")
    field = m[1] if m else "notes" if row == "notes" else ""
    return {"author": "byline", "note": "notes"}.get(field, field)


def _ask(text: str) -> dict:
    """A reviewer's comment as a question: its text without the reviewer's own preamble, and what it suggests."""
    text = re.sub(r"^Flag for the maintainer:\s*", "", (text or "").strip())
    q, _, suggest = text.partition(" Suggest: ")
    return {"text": q.strip(), **({"suggest": suggest.strip()} if suggest.strip() else {})}


def asks_of(reason: str, why: str, batch: dict, proofs: list[dict], rule: Rule) -> list[dict]:
    """The questions a held puzzle waits on, as recorded: each Not ready's comments (the row on the
    proof page each is about: ?k=<row>), its note where it left no comments, the owner's Hold on the
    batch page, or the edits two reviewers made two ways. [{who, kind, at, row, text, suggest, group}]."""
    out = []
    if reason == "edits-differ":
        keys = [k.strip() for k in why.partition(": ")[2].split(",") if k.strip()]
        return [{"who": "the import", "kind": "import", "at": "", "row": keys[0] if keys else "", "group": "",
                 "text": "Two reviewers changed the same thing two ways (" + ", ".join(keys) + "): which one stands?"}]
    for r in sorted(proofs, key=lambda r: r.get("at", "")):
        if r.get("answer") != "notready" or _name(r) in rule.ignore:
            continue
        kind = kind_of(r, rule)
        if reason == "owner-hold" and kind != "owner":
            continue  # the owner's hold is the one that stands
        base = {"who": r.get("by", ""), "kind": kind, "at": r.get("at", "")[:10]}
        comments = [c for c in ((r.get("proof") or {}).get("review") or {}).get("comments") or [] if (c.get("text") or "").strip()]
        for c in comments:
            row = re.sub(r"^grid:(r\d+c\d+)$", r"cell:\1", c.get("key") or "")
            out.append({**base, "row": row, "group": group_of(row), **_ask(c["text"])})
        if not comments:
            out.append({**base, "row": "", "group": "", "text": (r.get("note") or "").strip() or "said Not ready, with no note"})
    if reason == "owner-hold" and not out:
        out.append({"who": batch.get("by", ""), "kind": "owner", "at": batch.get("at", "")[:10], "row": "", "group": "",
                    "text": (batch.get("note") or "").strip() or "held on the batch page, with no note"})
    return out


def sent_back(proofs: list[dict], rule: Rule) -> dict | None:
    """The latest standing Not ready that sends the puzzle back to the pipeline (its review carries a
    sendback): {who, at, kind, part, note}, or None. The person is saying the question isn't one to
    answer on the proof page, so the puzzle is the pipeline's (broken), not held on a question."""
    for r in sorted(proofs, key=lambda r: r.get("at", ""), reverse=True):
        sb = ((r.get("proof") or {}).get("review") or {}).get("sendback")
        if r.get("answer") == "notready" and sb and _name(r) not in rule.ignore:
            return {"who": r.get("by", ""), "at": r.get("at", ""), "kind": sb.get("kind") or "other", "part": sb.get("part") or "",
                    "note": (sb.get("note") or "").strip()}
    return None


def broken_of(row: dict, blocking: list, incomplete: list) -> list[dict]:
    """What is broken in a puzzle the pipeline holds, each with the stage it points to: triage's blocking
    parts (their restart stage), the ship check's incompleteness, or the import's own reason.
    [{what, stage, code, detail}]; stage "" is not recorded."""
    out, seen = [], set()
    if row["reason"] == "needs-work":
        for b in blocking or []:
            if isinstance(b, dict) and (b.get("restart"), b.get("part")) not in seen:
                seen.add((b.get("restart"), b.get("part")))
                detail = "" if b.get("detail") == "from the verdict" else (b.get("detail") or "")[:200]
                out.append({"what": b.get("part") or b.get("code") or "", "stage": b.get("restart") or "", "code": b.get("code") or "", "detail": detail})
    elif row["reason"] == "sent-back":
        sb = row["sent_back"]
        says, stage = SENT_BACK.get(sb["kind"], (sb["kind"], ""))
        part = SENT_BACK_PART.get(sb["part"])
        out = [{"what": "sent back from the proof page: " + says + (f" ({part[0]})" if part else ""), "stage": part[1] if part else stage,
                "code": "sent-back", "detail": sb["note"][:600]}]
    elif row["reason"] == "incomplete":
        stages = [INCOMPLETE_STAGE[c] for c in row["check"]["findings"] if c in INCOMPLETE_STAGE]
        out = [{"what": str(x), "stage": stages[i] if len(stages) == len(incomplete) else (stages[0] if len(set(stages)) == 1 else ""),
                "code": "incomplete", "detail": ""} for i, x in enumerate(incomplete or [])]
    return out or [{"what": row["why"], "stage": STAGE_OF.get(row["reason"], ""), "code": row["reason"], "detail": ""}]


def spot(pid: str) -> bool:
    """Whether a shipped puzzle is in the maintainer's spot-check sample: about one in SPOT_ONE_IN, fixed by
    the puzzle's id alone, so a puzzle is in the sample or out of it for good."""
    return int(hashlib.sha1(pid.encode("utf-8")).hexdigest()[:8], 16) % SPOT_ONE_IN == 0


def queues(rows: list[dict]) -> list[dict]:
    """Every row's queue and its place in it, set on the rows: what the batch page asks of people.

    queue: shipped, shippable, question (held on a question a person can answer on the proof page),
      unchecked (nobody's Ready counts yet: a whole proofread), broken (the pipeline's: for agents and the
      maintainer, with the stage it points to), set-aside, not-a-crossword. One queue each.
    group: the largest shared-question group among a question puzzle's asks ("" when all are its own).
    order: its place in the batch's walk: questions first (shared groups, largest first; in a group the
      puzzles with nothing but shared questions, then fewest questions), then the rest by queue and id.
    reviewed: a person (the owner or a helper) has said Ready or Not ready: never an AI alone.
    spot_check: shipped on someone else's word than the owner's, and in the fixed one-in-ten sample.
    Returns the groups, largest first: [{key, label, puzzles, asks}]."""
    for r in rows:
        r["queue"] = (r["status"] if r["status"] in ("shipped", "shippable") else r["reason"] if r["status"] == "out"
                      else QUEUE_OF.get(r["reason"], "broken"))
        r["reviewed"] = any(s["kind"] in ("owner", "helper") for s in r.get("said") or [])
        r["spot_check"] = r["queue"] == "shipped" and r.get("rule") != "owner" and spot(r["pid"])
        if r["queue"] != "question":
            r["asks"], r["also"] = [], []
        if r["queue"] != "broken":
            r["broken"] = []
        elif not r.get("broken"):
            r["broken"] = [{"what": r["why"], "stage": STAGE_OF.get(r["reason"], ""), "code": r["reason"], "detail": ""}]
    size = {}
    for r in rows:
        for g in {a["group"] for a in r["asks"] if a["group"]}:
            size[g] = size.get(g, 0) + 1
    rank = sorted(size, key=lambda g: (-size[g], g))
    for r in rows:
        mine = [g for g in rank if any(a["group"] == g for a in r["asks"])]
        r["group"] = mine[0] if mine else ""

    def key(r):
        q = QUEUES.index(r["queue"])
        if r["queue"] != "question":
            return (q, 0, 0, 0, r["pid"])
        own = sum(not a["group"] for a in r["asks"])
        return (q, rank.index(r["group"]) if r["group"] else len(rank), bool(own), len(r["asks"]), r["pid"])
    for i, r in enumerate(sorted(rows, key=key)):
        r["order"] = i
    return [{"key": g, "label": GROUPS.get(g, g), "puzzles": sum(r["group"] == g for r in rows),
             "asks": size[g]} for g in rank]


# ---- reading the milestones ----------------------------------------------------------------

def _load(path: Path, default=None):
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else default


def ledger(repo: Path) -> list[dict]:
    f = Path(repo) / "fixes" / "decisions.jsonl"
    return [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()] if f.exists() else []


def from_site(decisions: dict, have: list[dict], pids: set) -> list[dict]:
    """Helpers' Ready / Not ready from the review site (blitz site-import's file) as ledger records,
    in the shape xword-ocr's batchpage.take_decisions writes: proof:<pid> by "<helper> (review site)".
    One already in the ledger as it stands (same answer, same time) isn't made again."""
    old = {(r["id"], r.get("by")): r for r in have if r["id"].startswith("proof:")}
    out = []
    for pid, d in sorted((decisions.get("puzzles") or decisions).items()):
        for name, p in sorted((d.get("proofs") or {}).items(), key=lambda kv: kv[1].get("at", "")):
            if pid not in pids or p.get("decision") not in ("ready", "notready"):
                continue
            by = f"{name} ({SITE})"
            o = old.get((f"proof:{pid}", by)) or {}
            if o.get("answer") == p["decision"] and o.get("at") == p.get("at", ""):
                continue
            review = {"edits": p.get("edits") or {}, "comments": p.get("comments") or [], "status": p.get("parts") or {},
                      "note": p.get("note", ""), "xd": p.get("xd", ""), **({"sendback": p["sendback"]} if p.get("sendback") else {})}
            out.append({"id": f"proof:{pid}", "answer": p["decision"], "note": (p.get("note") or "").strip(), "fix": "", "by": by,
                        "at": p.get("at", ""), "via": SITE, "proof": {"xdid": pid, "review": review, "at": p.get("at", "")}})
    return out


def fingerprint(text: str) -> str:
    return hashlib.sha1(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()[:12]


def _header(xd: str, key: str) -> str:
    return next((line[len(key) + 2:].strip() for line in xd.split("\n\n\n")[0].split("\n") if line.startswith(key + ": ")), "")


# ---- the reviewers' edits, onto the packet's xd ----------------------------------------------

APPLIED = re.compile(r"clue:[AD]\d+(?:\^[A-Za-z][\w-]*)?|cell:r\d+c\d+|meta:(title|author|byline|puzzle_number|editor|feature)")
HEADER = {"title": "Title", "author": "Author", "byline": "Byline", "puzzle_number": "Number", "editor": "Editor", "feature": "Feature"}
META_RE = re.compile(r"^([AD]\d+) \^([A-Za-z][\w-]*): ?(.*)$")


def _meta_key(name: str) -> str:
    return "-".join(w[:1].upper() + w[1:].lower() for w in name.strip().split("-"))


def refused(edits: dict, text: str) -> list[str]:
    """The edits this import can't apply (the puzzle is held for them): kinds it doesn't know (a
    line's label or keep, a fill-in blank, a note), a rebus square, a header of several lines, and
    any clue or square of a linked-ends puzzle (xword-ocr's import-batch knows that numbering)."""
    linked = "\nClues: linked ends" in "\n" + text.split("\n\n\n")[0]
    return sorted(k for k, v in edits.items() if not APPLIED.fullmatch(k) or (k.startswith("cell:") and len(v or "") != 1)
                  or (k.startswith("meta:") and "\n" in (v or "")) or (linked and not k.startswith("meta:")))


def answers(cells: list[list[str]]) -> dict[str, str]:
    """{A1: HELP, D1: HUGE} for a grid's numbered words (words of one letter aren't numbered)."""
    rows, cols = len(cells), len(cells[0])
    white = lambda r, c: 0 <= r < rows and 0 <= c < cols and cells[r][c] != "#"
    out, n = {}, 0
    for r in range(rows):
        for c in range(cols):
            if not white(r, c):
                continue
            a = not white(r, c - 1) and white(r, c + 1)
            d = not white(r - 1, c) and white(r + 1, c)
            if not (a or d):
                continue
            n += 1
            for on, dr, dc, lab in ((a, 0, 1, "A"), (d, 1, 0, "D")):
                if on:
                    word, i = "", 0
                    while white(r + dr * i, c + dc * i):
                        word += cells[r + dr * i][c + dc * i]
                        i += 1
                    out[f"{lab}{n}"] = word
    return out


def apply_edits(text: str, edits: dict) -> tuple[str, list[str]]:
    """The xd text with the edits applied (APPLIED kinds; refused() says which can't be). A changed key
    square changes the answers of the words through it. Returns (text, the keys applied)."""
    head, grid, *rest = text.replace("\r\n", "\n").rstrip("\n").split("\n\n\n")
    head, cells, done = head.split("\n"), [list(r) for r in grid.split("\n")], []
    for k, v in edits.items():
        m = re.fullmatch(r"cell:r(\d+)c(\d+)", k)
        if m:
            cells[int(m[1]) - 1][int(m[2]) - 1] = v.upper()
            done.append(k)
        elif k.startswith("meta:"):
            name = HEADER[k[5:]]
            at = next((i for i, h in enumerate(head) if h.startswith(f"{name}:")), None)
            head = [h for h in head if not h.startswith(f"{name}:")]
            if v and at is not None:  # a header that's there keeps its place
                head.insert(at, f"{name}: {v}")
            elif v:
                head.insert(next((i for i, h in enumerate(head) if h.split(":")[0] not in HEADER.values()), len(head)), f"{name}: {v}")
            done.append(k)
    cell_edits = any(k.startswith("cell:") for k in done)
    answer = answers(cells) if cell_edits else {}
    lines = []
    for line in (rest[0].split("\n") if rest else []):
        m = re.match(r"([AD]\d+)\. (.*) ~ (.*)$", line)
        if m:
            clue = edits.get(f"clue:{m[1]}", m[2])
            if f"clue:{m[1]}" in edits:
                done.append(f"clue:{m[1]}")
            line = f"{m[1]}. {clue} ~ {answer.get(m[1], m[3])}"
        elif m := META_RE.match(line):
            k = f"clue:{m[1]}^{_meta_key(m[2])}"
            if k in edits:
                line = f"{m[1]} ^{_meta_key(m[2])}: {edits[k]}"
                done.append(k)
        lines.append(line)
    out = "\n".join(head) + "\n\n\n" + "\n".join("".join(r) for r in cells) + "\n\n\n" + "\n".join(lines) + "\n"
    if rest[1:]:
        out += "\n\n" + "\n\n\n".join(rest[1:]) + "\n"
    return out, done


# ---- ids -----------------------------------------------------------------------------------

def _pins(repo: Path) -> tuple[dict, dict]:
    """({provisional pid as pipeline/ids.tsv spells it: xdid}, {(scan, leaf, size, nth): xdid} from fixes/xdids.tsv)."""
    alias = {}
    for r in _tsv(repo / "pipeline" / "ids.tsv"):
        names = (r.get("aliases") or "").split()
        xd = [a for a in names if not re.search(r"-L\d", a)]
        alias.update({a: xd[0] for a in names if re.search(r"-L\d", a) and xd})
    return alias, {(r["identifier"], r["leaf"], r["size"], r["nth"]): r["xdid"] for r in _tsv(repo / "fixes" / "xdids.tsv")}


def _tsv(path: Path) -> list[dict]:
    if not Path(path).exists():
        return []
    return list(csv.DictReader(io.StringIO(Path(path).read_text(encoding="utf-8")), delimiter="\t", quoting=csv.QUOTE_NONE))


def assign_ids(want: list[str], places: dict[str, tuple], repo: Path) -> tuple[dict[str, str], list[dict]]:
    """{pid: xdid} for the puzzles to import and the new pins (rows for fixes/xdids.tsv). A puzzle the
    publication already pinned keeps its id (pipeline/ids.tsv's aliases, or fixes/xdids.tsv by its place:
    scan, leaf, grid size, n-th of that size on the page among every puzzle of the run); a new one gets
    its date's next free letter, in page order. places: {pid: (scan, leaf, size)} for the whole run."""
    alias, by_page = _pins(repo)
    used = set(by_page.values()) | set(alias.values()) | {f.stem for f in (repo / "xd").glob("*.xd")}
    seen, nth = {}, {}
    for pid in sorted(places):
        nth[pid] = seen.get(places[pid], 0)
        seen[places[pid]] = nth[pid] + 1
    out, new = {}, []
    for pid in sorted(want):
        scan, leaf, size = places[pid]
        spelled = re.sub(r"-L(\d+)([b-h])$", lambda m: f"-L{m[1]}-{ord(m[2]) - ord('a') + 1}", pid)
        x = alias.get(pid) or alias.get(spelled) or by_page.get((scan, str(leaf), size, str(nth[pid])))
        if not x:
            base = re.match(r"([a-z]+\d{4}-\d\d-\d\d)", pid)[1]
            x = next(base + s for s in ["", *"bcdefghijklmnopqrstuvwxyz"] if base + s not in used)
            new.append({"xdid": x, "identifier": scan, "leaf": str(leaf), "size": size, "nth": str(nth[pid])})
        used.add(x)
        out[pid] = x
    return out, new


# ---- the plan ------------------------------------------------------------------------------

def _where(proof_root: Path) -> tuple[Path, str, str]:
    proof_root = Path(proof_root).resolve()
    return proof_root.parent.parent, proof_root.name, "/".join([*proof_root.parts[-3:]])  # harvest, run, games-7779/proof/run15


def plan(repo: Path, proof_root: Path, rule: Rule, batch: str = "", site: dict | None = None, pub: str = "") -> dict:
    """What shipping the batch would do, written nowhere: every puzzle of the run with its status
    (shipped: in xd/ as it stands; shippable: passes, not written yet; held, with the reason; out: set
    aside or not a crossword), and the xd text and provenance of each one that passes.

    A puzzle the rule passes can still be held by the import, each a reason of its own: no-packet,
    packet-stale (the packet doesn't show its xd), incomplete (the ship check's: no Ready makes a
    puzzle whole), edits-differ (two reviewers changed one thing two ways), edits-unapplied (a kind of
    edit the import doesn't apply), xd-exists (xd/ has another file under its id)."""
    repo = Path(repo)
    harvest, run, rel = _where(proof_root)
    tri = _load(harvest / "triage" / run / "triage.json")
    if not tri:
        raise Stop(f"No triage record for {run} at {harvest / 'triage' / run}: run xword-ocr triage --proof first.")
    recs = ledger(repo)
    pids = [p["pid"] for p in tri["puzzles"]]
    new_site = from_site(site, recs, set(pids)) if site else []
    recs += new_site
    latest, proofs = {}, {}
    for r in recs:
        latest[r["id"]] = r
        if r["id"].startswith("proof:"):
            proofs.setdefault(r["id"][6:], {})[r.get("by", "")] = r
    packs, places = {}, {}
    for pid in pids:
        folder = Path(proof_root) / pid
        o = _load(folder / "ocr.json") or {}
        xd = (folder / "puzzle.xd").read_text(encoding="utf-8") if (folder / "puzzle.xd").exists() else ""
        packs[pid] = {"folder": folder, "ocr": o, "xd": xd, "review": _load(folder / "review.json") or {}}
        page = ((o.get("stages") or {}).get("pages") or {}).get("page.jpg") or ["", ""]
        grid = xd.split("\n\n\n")[1].split("\n") if xd else o.get("grid") or [""]
        places[pid] = (page[0], str(page[1]), f"{len(grid)}x{len(grid[0])}")
    prov = {r["pid"]: r for r in provenance(repo)}
    rows, passing = [], {}
    for t in tri["puzzles"]:
        pid, pk = t["pid"], packs[t["pid"]]
        codes = {r["code"] for r in t.get("reasons") or []}
        ship = t.get("ship") or {}
        row = {"pid": pid, "title": _header(pk["xd"], "Title"), "date": _header(pk["xd"], "Date"), "disposition": t.get("decision", ""),
               "codes": sorted(codes),
               "check": {"ok": bool(ship.get("ok")), "findings": [f.get("code", "") if isinstance(f, dict) else str(f) for f in ship.get("findings") or []]}}
        rows.append(row)
        drop, aside = latest.get(f"drop:{pid}") or {}, latest.get(f"setaside:{pid}") or {}
        if drop.get("answer") == "not-a-crossword" or aside.get("answer") == "set-aside":
            kind = "not-a-crossword" if drop.get("answer") else "set-aside"
            rec = drop if drop.get("answer") else aside
            row.update(status="out", reason=kind, why=f"{kind.replace('-', ' ')}: {rec.get('note', '')} ({rec.get('by', '')})", said=[], rule="", asks=[], broken=[])
            continue
        review = pk["review"]
        current = tuple(x for x in (review.get("xd_fp"), *(review.get("xd_fp_same") or [])) if x)
        args = dict(check_ok=bool(ship.get("ok")), codes=codes, current=current)
        st = standing(latest.get(f"batch:{pid}") or {}, list((proofs.get(pid) or {}).values()), rule=rule, **args)
        # the smallest ai_ready setting under which the rule passes it: "" when it never does
        row["ships_with"] = next((opt for opt in AI_READY if standing(
            latest.get(f"batch:{pid}") or {}, list((proofs.get(pid) or {}).values()), rule=replace(rule, ai_ready=opt), **args)["status"] == "ship"), "")
        row.update(status="held", reason=st["reason"], why=st["why"], rule=st["rule"], said=st["said"], asks=[], broken=[])
        if st["status"] != "ship":
            if st["reason"] == "no-ready" and t.get("decision") != "ready":
                row.update(reason="needs-work", why="needs work: " + ("; ".join(
                    sorted({b.get("code") or b.get("part") or "" for b in t.get("blocking") or [] if isinstance(b, dict)} - {""})) or "triage's defects") + "; " + st["why"])
            sb = sent_back(list((proofs.get(pid) or {}).values()), rule) if row["reason"] == "not-ready" else None
            if sb:  # a reviewer said it is the pipeline's to mend, not a question for the proof page
                row.update(reason="sent-back", sent_back=sb, why=f"sent back from the proof page by {sb['who']}: "
                           + SENT_BACK.get(sb["kind"], (sb["kind"], ""))[0] + (f": {sb['note']}" if sb["note"] else ""))
            if QUEUE_OF.get(row["reason"]) == "question":
                row["asks"] = asks_of(row["reason"], row["why"], latest.get(f"batch:{pid}") or {}, list((proofs.get(pid) or {}).values()), rule)
                # what an answer won't mend: said beside the question, so nobody is surprised when it still doesn't ship
                row["also"] = [str(x) for x in ship.get("incomplete") or []]
            elif row["reason"] not in QUEUE_OF:
                row["broken"] = broken_of(row, t.get("blocking"), ship.get("incomplete"))
            continue

        def hold(reason, why, row=row, t=t, ship=ship):
            row.update(reason=reason, why=why)
            if reason == "edits-differ":
                row["asks"] = asks_of(reason, why, {}, [], rule)
            else:
                row["broken"] = broken_of(row, t.get("blocking"), ship.get("incomplete"))
        if not pk["xd"]:
            hold("no-packet", "no proof packet for it in this run")
            continue
        if not review.get("matches_xd", True):
            hold("packet-stale", "its proof packet doesn't show its xd: rebuild the packet")
            continue
        if ship.get("incomplete"):
            hold("incomplete", "Ready, but incomplete: " + "; ".join(map(str, ship["incomplete"])))
            continue
        edits, differ, sources = {}, set(), []
        for r in st["apply"]:
            mine = ((r.get("proof") or {}).get("review") or {}).get("edits") or {}
            differ |= {k for k, v in mine.items() if k in edits and edits[k] != v}
            edits.update({k: v for k, v in mine.items() if k not in edits})
            if mine:
                sources.append(r.get("by", ""))
        if differ:
            hold("edits-differ", "reviewers' edits differ: " + ", ".join(sorted(differ)[:6]))
            continue
        bad = refused(edits, pk["xd"])
        if bad:
            hold("edits-unapplied", "proof-page edits the import can't apply yet: " + ", ".join(bad[:6]))
            continue
        text, done = apply_edits(pk["xd"], edits)
        passing[pid] = {"text": text, "edits": done, "edit_sources": sources, "standing": st, "row": row,
                        "packet": f"{rel}/{pid}", "xd_fp": review.get("xd_fp", "")}
    _record_edits(passing, packs, rule)  # each one's record of every edit, its misprint notes; none without (edit-unrecorded)
    ids, pins = assign_ids(list(passing), places, repo)
    for pid, x in sorted(passing.items()):
        row, xdid = x["row"], ids[pid]
        f = repo / "xd" / f"{xdid}.xd"
        row["xdid"] = x["xdid"] = xdid
        ours = (prov.get(pid) or {}).get("xdid") == xdid
        if f.exists() and f.read_text(encoding="utf-8") == x["text"] and ours:
            row.update(status="shipped", reason="", why=f"in xd/ as {xdid}: {(prov[pid].get('shipped') or {}).get('why', '')}")
        elif f.exists() and not ours:
            row.update(reason="xd-exists", why=f"xd/{xdid}.xd is another file (an earlier import's): replace it by hand, or drop it")
            del passing[pid]
        else:
            row.update(status="shippable", reason="", why=x["standing"]["why"])
    for row in rows:  # a puzzle shipped earlier that the rule now holds: still in xd/, and said so
        p = prov.get(row["pid"])
        if row["status"] == "held" and p and (repo / "xd" / f"{p['xdid']}.xd").exists():
            row.update(xdid=p["xdid"], why=row["why"] + f" (already in xd/ as {p['xdid']})")
    groups = queues(rows)
    return {"groups": groups, "pub": pub or re.match(r"[a-z]+", repo.name)[0], "batch": batch or run, "run": run, "packets": rel, "rule": {"ai_ready": rule.ai_ready, "hold_codes": list(rule.hold_codes),
            "ignore": list(rule.ignore), "owner": list(rule.owner)}, "rows": rows, "passing": passing, "pins": [p for p in pins if p["xdid"] in {x["xdid"] for x in passing.values()}],
            "site": new_site, "packs": packs}


def counts(rows: list[dict]) -> dict:
    out = {"puzzles": len(rows), "shipped": 0, "shippable": 0, "held": 0, "out": 0, "held_by": {}, "ships_with": {},
           "queues": {q: 0 for q in QUEUES}, "reviewed": 0, "spot_check": 0}
    for r in rows:
        out[r["status"]] += 1
        out["queues"][r["queue"]] += 1
        out["reviewed"] += bool(r.get("reviewed"))
        out["spot_check"] += bool(r.get("spot_check"))
        if r["status"] == "held":
            out["held_by"][r["reason"]] = out["held_by"].get(r["reason"], 0) + 1
        if r["status"] != "out" and r.get("ships_with"):
            out["ships_with"][r["ships_with"]] = out["ships_with"].get(r["ships_with"], 0) + 1
    return out


# ---- the record of every edit ----------------------------------------------------------------
# The owner's rule (2026-11-11): blitz is faithful to the original, and an edit with no record is not allowed.
# Three cases:
#   1. A reading fix (the scan or the OCR was bad: the reviewer makes our text match what was printed; a clue,
#      a header or a key square). Applied here; recorded in the puzzle's provenance row: what it was, what it
#      became, who changed it, where to see it.
#   2. A misprint in a clue or a header (the scan is good, the original has a mistake: a reviewer's typos entry
#      {key, printed, meant}). NOT applied here: the xd that ships stays as printed, the correction travels
#      beside it as a recorded proposal (the row's corrections), and the gxd export applies it and writes the
#      editorial note.
#   3. A misprinted answer-key letter (a typos entry for a square). Corrected here (the key is evidence for the
#      answers, not part of the puzzle), with an editorial note in the shipped xd's notes naming the square,
#      what the key printed and what it was corrected to, and the provenance record. Without that record it
#      doesn't ship.
# An edit nothing classes is applied and reported as unclassed, never guessed. A change with no whole record
# holds the puzzle (edit-unrecorded).

NOTES_HEAD = "Answer key corrected:"  # the xd notes block ship writes: one line per corrected key letter
EDIT_STAGE = "proof review"
READING, UNCLASSED, DECISION, KEY_FIX = "reading", "unclassed", "decision", "key correction"  # an applied edit's class
_DIR = {"A": "Across", "D": "Down"}
_TYPO_KEY = re.compile(r"clue:[AD]\d+(?:\^[\w-]+)?|cell:r\d+c\d+|meta:(?:title|author|byline|puzzle_number|editor|feature)")


def _read(text: str) -> tuple[dict, list[list[str]], dict]:
    """An xd's headers {name: value}, its grid's squares, and its clue texts {A1: ..., A1^Easy: ...}."""
    head, grid, *rest = text.replace("\r\n", "\n").rstrip("\n").split("\n\n\n")
    heads = {k: v.strip() for k, sep, v in (h.partition(":") for h in head.split("\n")) if sep}
    clues = {}
    for line in (rest[0].split("\n") if rest else []):
        m = re.match(r"([AD]\d+)\. (.*) ~ (.*)$", line)
        if m:
            clues[m[1]] = m[2]
        elif m := META_RE.match(line):
            clues[f"{m[1]}^{_meta_key(m[2])}"] = m[3]
    return heads, [list(r) for r in grid.split("\n")], clues


def _why(rec: dict, key: str) -> str:
    """What the reviewer said about their edit: their comment on its row (the one marked as the reason first)."""
    keys = {key, re.sub(r"^cell:", "grid:", key)}
    cs = [c for c in ((rec.get("proof") or {}).get("review") or {}).get("comments") or []
          if c.get("key") in keys and (c.get("text") or "").strip()]
    return sorted(cs, key=lambda c: not c.get("why"))[0]["text"].strip() if cs else ""


def _square(cells: list[list[str]], key: str) -> tuple[int, int] | None:
    m = re.fullmatch(r"cell:r(\d+)c(\d+)", key)
    i, j = (int(m[1]) - 1, int(m[2]) - 1) if m else (-1, -1)
    return (i, j) if 0 <= i < len(cells) and 0 <= j < len(cells[i]) else None


def _key_note(cells: list[list[str]], at: tuple[int, int], printed: str) -> str:
    """The editorial note for a corrected key letter: the square, what the key printed, what it was corrected
    to, and the answers through it, in the form of Judge's notes. cells is the corrected grid."""
    was = [row[:] for row in cells]
    was[at[0]][at[1]] = printed.upper()
    a_now, a_was = answers(cells), answers(was)
    through = [lab for lab in a_now if a_now[lab] != a_was.get(lab)]
    name = lambda lab: f"{lab[1:]} {_DIR[lab[0]]}"
    where = f"row {at[0] + 1}, column {at[1] + 1}"
    if not through:
        return f"The printed answer key gave the square at {where} as {printed.upper()}, presumably in error. It has been corrected to {cells[at[0]][at[1]]}."
    gave = f"{name(through[0])} as {a_was[through[0]]}" + (
        " (and so " + " and ".join(f"{name(o)} as {a_was[o]}" for o in through[1:]) + ")" if through[1:] else "")
    return (f"The printed answer key gave {gave}, presumably in error ({printed.upper()} at {where}). It has been corrected to "
            + " and ".join(a_now[lab] for lab in through) + f" ({cells[at[0]][at[1]]}).")


def _label(key: str) -> str:
    """How a note names a clue or a header: A71, A71^Easy, the title."""
    return key[5:] if key.startswith("clue:") else "The " + HEADER.get(key[5:], key[5:]).lower()


def edit_records(packet_xd: str, applied: str, apply: list[dict], rule: Rule = Rule(), pid: str = "", ocr: dict | None = None) -> dict:
    """The xd that ships, the record of every edit between the packet's xd and it, and the corrections of the
    print that travel beside it.

    applied: the packet's xd with the Ready reviewers' edits applied (apply_edits). apply: those Ready records
    (standing()'s), first reviewer first. A reviewer names a misprint in their review's typos {key, printed,
    meant}: key a clue's, a header's (meta:title) or a key square's (cell:r3c4). Returns {text, records,
    corrections, notes, missing}:
    - text: the xd that ships. A clue's or a header's misprint is as printed in it: where the reviewer also
      edited that clue, their edit is kept except for the misprint (the word meant goes back to the word
      printed). A misprinted key letter is corrected in it (by the reviewer's own cell edit, or from their
      typos entry when they made none), and said in its notes (the NOTES_HEAD block).
    - records: one per value that ships changed: {key, what (clue, second clue set, key square, header,
      decision), class, before (the packet's xd), after, by, kind (owner, helper, ai, check), via, at, stage, why
      (the reviewer's comment on the row), evidence {proof: the row on the proof page, image, box: the clue's
      crop, or the key's page, in the packet}, words (a key square: the answers through it, before and after),
      misprint {printed, meant} and note (a key correction)}. class is reading (the reviewer's comment on the
      row is the evidence that the page shows the new text; it is quoted, not parsed), key correction (a typos
      entry for the square), decision (not a value of the xd), or unclassed (nothing says which: applied, and
      reported).
    - corrections: the proposals for the gxd export, one per typos entry for a clue or a header: {key,
      printed, meant, by, kind, via, at, fits, says, evidence, edit (the reviewer's own edit, when they made
      one)}. fits: printed (the xd that ships has the printed word once: the export puts the word meant in its
      place), already (it has the word meant and not the printed one: corrected before any reviewer saw it, so
      the xd is not as printed there; the export writes the note only), unplaced (neither, or more than once,
      or the entry is incomplete: the export leaves it alone and says so).
    - notes: the editorial lines for the xd's notes, one per corrected key letter (also when the packet's key
      already had the letter meant: the correction was made before review, and is said all the same).
    - missing: what has no whole record, each in words. Any of it holds the puzzle: an edit to a clue or a
      square the packet's xd doesn't have (nothing to say what it replaced), a value that changed with no edit
      behind it, an edit that corrects a misprint whose printed text can't be put back, or a key correction
      that doesn't say what the key printed, or doesn't match the square."""
    ocr = ocr or {}
    was_h, was_c, was_q = _read(packet_xd)
    owner, value, typos, seen = {}, {}, [], set()
    for r in apply:
        review = (r.get("proof") or {}).get("review") or {}
        for k, v in (review.get("edits") or {}).items():
            if k not in owner:
                owner[k], value[k] = r, v
        for t in review.get("typos") or []:
            t3 = (str(t.get("key") or ""), str(t.get("printed") or "").strip(), str(t.get("meant") or "").strip()) if isinstance(t, dict) else None
            if t3 and t3 not in seen:
                seen.add(t3)
                typos.append((*t3, r))
    who = lambda r: {"by": r.get("by", ""), "kind": kind_of(r, rule), "via": r.get("via", ""), "at": r.get("at", "")}
    whole = lambda key, printed, meant: bool(printed and meant and printed != meant and _TYPO_KEY.fullmatch(key))
    records, missing, have, more_edits, back, key_fix, said = [], [], {}, {}, set(), {}, {}

    for key, printed, meant, r in typos:
        if key.startswith("cell:"):  # case 3: the key's letter is corrected here, and only with its whole record
            at = _square(was_c, key)
            if not whole(key, printed, meant) or len(printed) != 1 or len(meant) != 1 or not at:
                missing.append(f"{key}: a key correction that doesn't say what the key printed and what was meant, or names no square of the grid")
                continue
            cur = (value[key] or "").upper() if key in owner else _read(applied)[1][at[0]][at[1]]
            if cur == meant.upper():
                key_fix[key], said[key] = (printed.upper(), meant.upper()), r
            elif key not in owner and cur == printed.upper():  # no edit: the typos entry is the correction
                more_edits[key], owner[key], value[key] = meant.upper(), r, meant.upper()
                key_fix[key], said[key] = (printed.upper(), meant.upper()), r
            else:
                missing.append(f"{key}: a key correction to {meant.upper()} that doesn't match the square ({cur})")
        elif key in owner:  # case 2 made as an edit: the printed word goes back, the rest of the edit stands
            v = more_edits.get(key, value[key]) or ""
            if not whole(key, printed, meant):
                missing.append(f"{key}: an edit said to correct a misprint, with no record of what was printed and what was meant")
            elif v.count(meant) == 1:
                more_edits[key] = v.replace(meant, printed)
                back.add(key)
            else:
                missing.append(f"{key}: the edit doesn't have '{meant}' exactly once, so the printed text can't be put back")
    text = apply_edits(applied, more_edits)[0] if more_edits else applied
    value.update(more_edits)
    now_h, now_c, now_q = _read(text)

    def evidence(k):
        crop = (ocr.get("clues") or {}).get(k[5:]) if k.startswith("clue:") else None
        page = (ocr.get("answer_page") or {}).get("image") if k.startswith("cell:") else None
        return {"proof": f"{PROOF_PAGE}{pid}&k={k}", **({"image": ocr.get("clue_image", ""), "box": crop["box"]} if crop and crop.get("box") else {}),
                **({"image": page} if page else {})}

    def add(k, what, before, after, r, **more):
        if before == after:
            return  # an edit that changes nothing is no edit
        why = _why(r, more.get("decided_by") or k)
        cls = (DECISION if what == "decision" or more.get("decided_by") else KEY_FIX if k in key_fix
               else UNCLASSED if k in back or not why else READING)
        have[k] = {"key": k, "what": what, "class": cls, "before": before, "after": after, **who(r), "stage": EDIT_STAGE,
                   **({"why": why} if why else {}), "evidence": evidence(k), **more,
                   **({"beside": "a correction of the print, not applied: see corrections"} if k in back else {})}
        records.append(have[k])

    for k, r in owner.items():
        v = value[k]
        if k.startswith("clue:"):
            if k[5:] not in was_q:
                missing.append(f"{k}: the packet's xd has no such clue, so nothing says what the edit replaced")
            else:
                add(k, "second clue set" if "^" in k else "clue", was_q[k[5:]], v, r)
        elif k.startswith("cell:"):
            at = _square(was_c, k)
            if not at:
                missing.append(f"{k}: the packet's grid has no such square")
                continue
            one = [row[:] for row in was_c]
            one[at[0]][at[1]] = (v or "").upper()
            a0, a1 = answers(was_c), answers(one)
            add(k, "key square", was_c[at[0]][at[1]], (v or "").upper(), r,
                words={lab: [a0.get(lab, ""), w] for lab, w in a1.items() if a0.get(lab) != w})
        elif k.startswith("meta:") and k[5:] in HEADER:
            add(k, "header", was_h.get(HEADER[k[5:]], ""), v or "", r, header=HEADER[k[5:]])
        else:  # a decision that isn't a value of the xd (a candidate clue list's): nothing stood there before it
            add(k, "decision", "", v if isinstance(v, str) else json.dumps(v, ensure_ascii=False), r)

    # the net under it: whatever differs between the two xds has a record that says so, or the puzzle is held
    lists = [k for k in owner if k.startswith("candidate:") and (value[k] == "clues" or str(value[k]).startswith("second:"))]
    names = {v: k for k, v in HEADER.items()}
    diffs = [(f"clue:{k}", "second clue set" if "^" in k else "clue", was_q.get(k), now_q.get(k)) for k in {**was_q, **now_q}]
    diffs += [(f"meta:{names[n]}" if n in names else f"header:{n}", "header", was_h.get(n, ""), now_h.get(n, "")) for n in {**was_h, **now_h}]
    if [len(r) for r in was_c] != [len(r) for r in now_c]:
        missing.append("the grid's size changed from the packet's xd with no edit recorded")
    else:
        diffs += [(f"cell:r{i + 1}c{j + 1}", "key square", c, now_c[i][j]) for i, row in enumerate(was_c) for j, c in enumerate(row)]
    for k, what, before, after in diffs:
        if before == after or (k in have and have[k]["after"] == (after or "")):
            continue
        by_list = next((c for c in lists if what != "header" and k[5:6] == c[len("candidate:"):][:1]), None) if k not in have else None
        if by_list:  # a candidate list a reviewer took in as the clues, or as a second set: their decision wrote it
            add(k, what, before or "", after or "", owner[by_list], decided_by=by_list)
        else:
            missing.append(f"{k}: changed from the packet's xd with no edit recorded" if k not in have
                           else f"{k}: ships as something other than the edit recorded for it")

    notes, corrections = [], []
    for key, (printed, meant) in key_fix.items():  # case 3's record: the note, on the edit's record or on its own
        note = _key_note(now_c, _square(now_c, key), printed)
        notes.append(note)
        if key in have:
            have[key].update(misprint={"printed": printed, "meant": meant}, note=note)
        else:  # the packet's key already had the letter meant: no edit of ours, the correction is said all the same
            records.append({"key": key, "what": "key square", "class": KEY_FIX, "before": meant, "after": meant, **who(said[key]),
                            "stage": "before review", "misprint": {"printed": printed, "meant": meant}, "note": note, "evidence": evidence(key)})
    for key, printed, meant, r in typos:
        if key.startswith("cell:"):
            continue
        fits, says = "unplaced", f"{key or 'a misprint'}: printed '{printed}', meant '{meant}'."
        if whole(key, printed, meant):
            cur = now_q.get(key[5:]) if key.startswith("clue:") else now_h.get(HEADER[key[5:]], "")
            fits = "unplaced" if cur is None else "printed" if cur.count(printed) == 1 else "already" if printed not in cur and meant in cur else "unplaced"
            says = f"{_label(key)} is printed '{printed}'; meant '{meant}'."
        mine = ((r.get("proof") or {}).get("review") or {}).get("edits", {}).get(key)
        corrections.append({"key": key, "printed": printed, "meant": meant, **who(r), "fits": fits, "says": says, "evidence": evidence(key),
                            **({"edit": mine} if mine is not None else {})})
    return {"text": with_notes(text, notes), "records": records, "corrections": corrections, "notes": notes, "missing": missing}


def corrected(text: str, corrections: list[dict]) -> tuple[str, list[str], list[dict]]:
    """A shipped xd with its corrections of the print (a clue's, a header's) applied, for the gxd export: (the
    text, the editorial notes for the xd's notes, what became of each: [{key, printed, meant, by, done, note}]).
    done: applied (the printed word was there once, and the word meant is in its place), noted (the xd already
    had the word meant: the note alone), not applied (neither is there, or it can't be placed: nothing is
    changed, and nothing is said in the notes)."""
    notes, rows = [], []
    for c in corrections or []:
        key, printed, meant = c.get("key") or "", c.get("printed") or "", c.get("meant") or ""
        heads, _, clues = _read(text)
        done, note = "not applied", ""
        if printed and meant and printed != meant and _TYPO_KEY.fullmatch(key) and not key.startswith("cell:"):
            cur = clues.get(key[5:]) if key.startswith("clue:") else heads.get(HEADER[key[5:]])
            if cur is not None and cur.count(printed) == 1:
                text, done = apply_edits(text, {key: cur.replace(printed, meant)})[0], "applied"
            elif cur is not None and printed not in cur and meant in cur:
                done = "noted"
            note = f"{_label(key)} is printed '{printed}'; corrected to '{meant}'." if done != "not applied" else ""
        if note:
            notes.append(note)
        rows.append({"key": key, "printed": printed, "meant": meant, "by": c.get("by", ""), "done": done, "note": note})
    return text, notes, rows


def with_notes(text: str, lines: list[str]) -> str:
    """The xd with the corrected key letters said in its notes: a block of its own, after the notes it has."""
    if not lines:
        return text
    body = text.replace("\r\n", "\n").rstrip("\n")
    return body + ("\n\n" if len(body.split("\n\n\n")) > 3 else "\n\n\n") + NOTES_HEAD + "\n" + "\n".join(lines) + "\n"


def packet_edits(ocr: dict, review: dict) -> list[dict]:
    """The changes the packet itself recorded before any reviewer saw it (review.json's corrections: the text
    review's), as edit records: before is the reading the packet's ocr.json holds for the clue, the printed
    line, the key square (its answers rows) or the header ("" with read: false when it holds none), after the
    corrected value, why the review's own note."""
    notes = {t.get("target"): t.get("note", "") for t in review.get("tool_notes") or [] if isinstance(t, dict)}
    lines = {f"line:B{ln.get('n')}": ln.get("text") for ln in ocr.get("lines") or []}
    by = review.get("reviewer_line") or review.get("reviewer") or "the text review"
    out = []
    for k, after in (review.get("corrections") or {}).items():
        cell = re.fullmatch(r"cell:r(\d+)c(\d+)", k)
        if k.startswith("clue:"):
            what, read = "clue", ((ocr.get("clues") or {}).get(k[5:]) or {}).get("text")
        elif cell:
            rows, i, j = ocr.get("answers") or [], int(cell[1]) - 1, int(cell[2]) - 1
            what, read = "key square", rows[i][j] if i < len(rows) and j < len(rows[i]) else None
        elif k.startswith("meta:"):
            what, read = "header", ocr.get(k[5:])
        else:
            what, read = "printed line" if k.startswith("line:") else "value", lines.get(k)
        if read == after:
            continue
        out.append({"key": k, "what": what,
                    "before": read or "", **({} if read is not None else {"read": False}), "after": after, "by": by,
                    "stage": "text review", **({"why": notes[k]} if notes.get(k) else {})})
    return out


def _record_edits(passing: dict, packs: dict, rule: Rule) -> None:
    """Every passing puzzle's xd as it ships (a clue's or header's misprint as printed, a misprinted key letter
    corrected and noted), its edit records and its corrections; a puzzle with an edit that has no whole record
    leaves `passing`, held as edit-unrecorded (the import's: broken)."""
    for pid, x in list(passing.items()):
        e = edit_records(packs[pid]["xd"], x["text"], x["standing"]["apply"], rule, pid, packs[pid]["ocr"])
        if e["missing"]:
            why = "an edit with no whole record of what it changed: " + "; ".join(e["missing"][:4]) + (
                f" (+{len(e['missing']) - 4})" if len(e["missing"]) > 4 else "")
            x["row"].update(reason="edit-unrecorded", why=why, broken=[{"what": why, "stage": "import", "code": "edit-unrecorded", "detail": ""}])
            del passing[pid]
            continue
        x.update(edit_records=e["records"], corrections=e["corrections"], notes=e["notes"], text=e["text"])
        # what the packet's puzzle.xd doesn't show: the ship record carries it, the proof page draws it
        if e["notes"]:
            x["row"]["notes"] = e["notes"]  # added to the shipped xd's notes
        if e["corrections"]:
            x["row"]["corrections"] = [{k: c[k] for k in ("key", "printed", "meant", "fits", "says")} for c in e["corrections"]]  # proposed, not applied


def _edits_of(x: dict, pk: dict) -> dict:
    """A provenance row's edits: the keys applied and whose, each one's record with its class, the packet's own."""
    return {"applied": x["edits"], "from": x["edit_sources"], "records": x.get("edit_records", []),
            "packet": packet_edits(pk["ocr"], pk["review"])}


def unrecorded(repo: Path, p: dict, today: str = "") -> list[dict]:
    """The provenance rows that would give the edit records to puzzles shipped before ship kept them (their
    standing row has no edits.records): the standing row with its edits made again from the ledger and the
    packet. Only a puzzle whose xd in xd/ is still exactly what the plan makes can be rebuilt this way."""
    prov = {r["pid"]: r for r in provenance(repo)}
    return [{**prov[pid], "edits": _edits_of(x, p["packs"][pid]), "corrections": x.get("corrections", []), "notes": x.get("notes", []),
             "backfilled": today or date.today().isoformat()}
            for pid, x in sorted(p["passing"].items())
            if x["row"]["status"] == "shipped" and "records" not in (prov[pid].get("edits") or {})]


def backfill(repo: Path, p: dict, today: str = "") -> list[dict]:
    """unrecorded()'s rows appended to provenance.jsonl (the last row for an xdid stands). No xd is touched."""
    rows = unrecorded(repo, p, today)
    if rows:
        with (Path(repo) / "provenance.jsonl").open("a", encoding="utf-8", newline="\n") as fh:
            fh.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    return rows


# ---- writing -------------------------------------------------------------------------------

def provenance(repo: Path) -> list[dict]:
    """provenance.jsonl's standing rows: the last one written for each xdid."""
    f = Path(repo) / "provenance.jsonl"
    rows = {}
    for line in (f.read_text(encoding="utf-8").splitlines() if f.exists() else []):
        if line.strip():
            r = json.loads(line)
            rows[r["xdid"]] = r
    return list(rows.values())


def _printed(ocr: dict, review: dict) -> list[dict]:
    """The lines printed with the puzzle that the packet keeps, with the text step's label for each
    (the export's Notes rule picks among them by label), as the text step corrected them (line:B<n>)."""
    fixed = review.get("corrections") or {}
    return [{"label": ln.get("label") or "", "text": fixed.get(f"line:B{ln.get('n')}") or ln["text"]} for ln in ocr.get("lines") or []
            if ln.get("keep", True) and ln.get("label") and (ln.get("text") or "").strip()]


def write(repo: Path, p: dict, today: str = "") -> dict:
    """plan()'s result into the publication's repo: the review site's decisions into the ledger, the
    passing puzzles' xd files and pins, their provenance rows, gxd-exports.tsv, and the batch's ship
    record. Returns {written: [xdid], ledger: n}."""
    repo, today = Path(repo), today or date.today().isoformat()
    if p["site"]:
        with (repo / "fixes" / "decisions.jsonl").open("a", encoding="utf-8", newline="\n") as fh:
            fh.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in p["site"])
    written = []
    for pid, x in sorted(p["passing"].items()):
        if x["row"]["status"] == "shipped":
            continue
        f = repo / "xd" / f"{x['xdid']}.xd"
        f.parent.mkdir(exist_ok=True)
        f.write_text(x["text"], encoding="utf-8", newline="\n")
        st, pk = x["standing"], p["packs"][pid]
        row = {"xdid": x["xdid"], "pid": pid, "batch": p["batch"], "run": p["run"], "packet": x["packet"], "packet_xd": x["xd_fp"],
               "xd": fingerprint(x["text"]),
               "shipped": {"at": today, "rule": st["rule"], "ai_ready": p["rule"]["ai_ready"], "by": st["by"], "why": st["why"]},
               "said": st["said"], "edits": _edits_of(x, pk), "corrections": x.get("corrections", []), "notes": x.get("notes", []),
               "check": x["row"]["check"], "codes": x["row"]["codes"],
               "sources": {k: _header(x["text"], h) for k, h in (("grid", "Source"), ("clues", "Clue-Source"), ("key", "Solution-Source"))
                           if _header(x["text"], h)},
               "printed": _printed(pk["ocr"], pk["review"])}
        with (repo / "provenance.jsonl").open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        x["row"].update(status="shipped", why=f"in xd/ as {x['xdid']}: {st['why']}")
        written.append(x["xdid"])
    pins = [r for r in p["pins"] if r["xdid"] in written]
    if pins:
        path = repo / "fixes" / "xdids.tsv"
        new = not path.exists()
        with path.open("a", encoding="utf-8", newline="\n") as fh:
            if new:
                fh.write("xdid\tidentifier\tleaf\tsize\tnth\n")
            fh.writelines("\t".join(r[k] for k in ("xdid", "identifier", "leaf", "size", "nth")) + "\n" for r in pins)
    p["groups"] = queues(p["rows"])  # what was just written is shipped now
    write_exports(repo, p["pub"])
    write_record(repo, p)
    return {"written": written, "ledger": len(p["site"])}


EXPORT_COLS = ("gxd_id", "xdid", "date", "number", "gxd_mr", "exported", "proof_url", "package_url", "scan_url",
               "ai_reviewed", "person_reviewed", "credit")


def write_exports(repo: Path, pub: str) -> None:
    """gxd-exports.tsv from provenance.jsonl: one row per puzzle shipped this way (judge's columns; gxd_mr and
    exported stay empty until an MR carries the puzzle, and a row's values for them are kept)."""
    repo = Path(repo)
    old = {r["xdid"]: r for r in _tsv(repo / "gxd-exports.tsv")}
    out = ["\t".join(EXPORT_COLS)]
    for r in sorted(provenance(repo), key=lambda r: r["xdid"]):
        f = repo / "xd" / f"{r['xdid']}.xd"
        if not f.exists():
            continue
        xd = f.read_text(encoding="utf-8")
        kinds = {s["kind"] for s in r.get("said") or [] if s["answer"] == "ready" and not s.get("stale")}
        o = old.get(r["xdid"]) or {}
        out.append("\t".join([o.get("gxd_id") or r["xdid"], r["xdid"], _header(xd, "Date"), _header(xd, "Number"), o.get("gxd_mr", ""),
                              o.get("exported", ""), PROOF_PAGE + r["pid"], f"{PUBLIC}/{pub}/{r['pid']}/", _header(xd, "Source"),
                              "y" if kinds & {"ai", "check"} or "Text-Review: " in xd else "", "y" if kinds & {"owner", "helper"} else "", CREDIT]))
    (repo / "gxd-exports.tsv").write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")


def record(p: dict, public: bool = True) -> dict:
    """The batch's ship record (pipeline/ship/<batch>.json; batch/<name>/ship.json on the site): the rule, the
    counts, and every puzzle's status with its reason. Review-site account names are left out of the copy the
    site shows: a helper is "a helper", the owner's account there "the owner"."""
    site = lambda s: s["who"].endswith(f"({SITE})")
    alias = lambda s: "a helper" if s["kind"] == "helper" else "the owner"

    def said(row):
        return [{"kind": s["kind"], "answer": s["answer"], "at": s["at"][:10], **({"stale": True} if s.get("stale") else {}),
                 **({} if public and s["kind"] == "helper" else {"who": alias(s) if public and site(s) else s["who"]})}
                for s in row.get("said") or []]

    def why(row):
        text = row["why"]
        for s in row.get("said") or []:
            if public and site(s):
                text = text.replace(s["who"], alias(s))
        return text

    def asks(row):
        whose = {s["who"]: alias(s) for s in row.get("said") or [] if public and site(s)}
        out = []
        for a in row.get("asks") or []:
            a = {**a, "text": why({**row, "why": a["text"]})}
            if a["who"] in whose:
                a = {**a, "who": whose[a["who"]]}
            out.append(a)
        return out

    rows = [{**{k: r.get(k, "") for k in ("pid", "xdid", "title", "date", "status", "reason", "rule", "ships_with", "queue", "group", "order")},
             "reviewed": bool(r.get("reviewed")), "spot_check": bool(r.get("spot_check")),
             "why": why(r), "asks": asks(r), "also": r.get("also") or [], "broken": r.get("broken") or [],
             "said": said(r), "check": r["check"]} for r in p["rows"]]
    return {"_about": "blitz ship: which puzzles of the batch are shipped (in the publication repo's xd/), shippable (pass the "
                      "ship rule, not written yet) or held, with the reason, and the queue each is in: what the batch page asks "
                      "of people. Format: blitz design/ship.md.",
            "batch": p["batch"], "run": p["run"], "packets": p["packets"], "rule": p["rule"],
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "counts": counts(p["rows"]),
            "groups": p["groups"], "spot": {"one_in": SPOT_ONE_IN, "of": "puzzles shipped on someone else's word than the owner's",
                                            "by": "sha1 of the puzzle's id"},
            "puzzles": [{**row, **{k: r[k] for k in ("notes", "corrections") if r.get(k)}} for row, r in zip(rows, p["rows"])]}


def write_record(repo: Path, p: dict) -> Path:
    f = Path(repo) / "pipeline" / "ship" / f"{p['batch']}.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(record(p), ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    return f


# ---- the gxd export ------------------------------------------------------------------------

KEEP = ("Title", "Author", "Editor", "Date", "Number", "Byline", "Rebus", "Special", "Notes")
FLATTEN = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})  # gxd's lint wants plain quotes
NOTE_LABELS = ("intro", "instructions")  # the printed lines that go in gxd's notes when the publication has no Notes rule
NOT_EXPORTED = {"cryptic-no-key": "a cryptic with no key grid: kept in xd/, not exported"}  # triage codes the export holds back


def normalize_author(name: str) -> str:
    """The constructor's name as printed, tidied (xword-ocr export.normalize_author): no Mr./Miss/Ms.,
    a space after a period, single spaces, no trailing punctuation."""
    s = re.sub(r"\.(?=[A-Za-z])", ". ", name)
    s = re.sub(r"\b(?:Mr|Ms|Miss)\.?\s+(?=[A-Z])", "", s)
    return re.sub(r"\s+", " ", s).strip().rstrip(",;:")


def to_gxd(text: str, notes: list[str] = (), feature_as: str | None = None) -> str:
    """A publication repo's xd reduced to the puzzle, as gxd keeps it: Title, Author (tidied), Editor, Date,
    Number, Byline, Rebus, Special and a one-line Notes header; the grid; the clues (with their ^Easy lines);
    and `notes`, the printed text that explains the puzzle. Everything about how we made it (sources, OCR
    flags, what the text step was unsure of, assembly's notes) stays behind, in provenance.jsonl."""
    head, grid, clues, *_ = text.replace("\r\n", "\n").translate(FLATTEN).split("\n\n\n") + [""]
    heads = []
    for line in head.split("\n"):
        key, sep, value = line.partition(": ")
        if key == "Feature" and feature_as and value.strip():
            heads.append((feature_as, value.strip()))
        elif sep and key in KEEP and value.strip():
            heads.append((key, normalize_author(value) if key == "Author" else value.strip()))
    heads.sort(key=lambda kv: KEEP.index(kv[0]) if kv[0] in KEEP else len(KEEP))
    out = "\n".join(f"{k}: {v}" for k, v in heads) + "\n\n\n" + grid.strip("\n") + "\n\n\n" + clues.strip("\n") + "\n"
    if notes:
        out += "\n\n" + "\n\n".join(n.translate(FLATTEN) for n in notes) + "\n"
    return out


def notes_labels(repo: Path, pub: str) -> tuple[tuple, str]:
    """The line labels whose kept lines go in gxd's notes: the owner's Notes rule in the ledger
    (notes-rule:<pubid>, set on the batch page), else NOTE_LABELS. Returns (labels, where it came from)."""
    rec = next((r for r in reversed(ledger(repo)) if r["id"] == f"notes-rule:{pub}"), None)
    if rec and rec.get("answer") is not None:
        return tuple((rec.get("notes_rule") or {}).get("labels") or []), f"the Notes rule of {rec.get('at', '')[:10]} by {rec.get('by', '')}"
    return NOTE_LABELS, "no Notes rule recorded: the default (intro, instructions)"


COMMANDS = """# {pub}: {n} puzzles to gxd (a dry run: none of this has been run)

This folder is what `blitz ship-export {pub}` wrote. Nothing was sent anywhere. gxd branches go to the
fork (gitlab.com/alexdej1/gxd), never to rabidrat/gxd; check `git remote -v` before the push, and go by
the URL. The push and the merge request are the owner's to approve.

Lint (clean apart from what's listed in the report):

    python C:/Users/adeja/Projects/xd/xdlint.py --profile gxd {dest}/{shelf}

A worktree of gxd on its own branch, with only these folders checked out:

    cd C:/Users/adeja/Projects/xd/gxd
    git fetch upstream
    scripts/new-worktree.sh ../../gxd-{branch} {branch} {years}
    cd ../../gxd-{branch}

The puzzles, the receipts, and the publication's row (publications.tsv is sorted by PublicationAbbr: put
the row in its place; add a pubregex.tsv row only if file names need one):

    mkdir -p {shelf} && cp -r {dest}/{shelf}/. {shelf}/
    cat {dest}/receipts.tsv >> receipts.tsv
    # publications.tsv: insert the line in {dest}/publications.tsv

The source archive: every page in source-pages.tsv, named as its archive_path. Pages the scans repo
doesn't hold (in_scans empty) come from archive.org first (`blitz ship-export {pub} --pages` copies the
ones it has into source/):

    scripts/make-source-archive.py {archive} {dest}/source/ --notes NOTES.md --base-url https://archive.org/download/
    scripts/make-source-archive.py --verify {archive} --receipts {dest}/receipts.tsv
    aws s3 cp {archive} s3://gxd-sources/src/{archive}

The checks CI runs, then the commit:

    scripts/check-mr.sh
    git add {shelf} receipts.tsv publications.tsv
    git commit -m "import: {pub}, {n} puzzles ({branch})"

Only with the owner's go-ahead: push to the fork and open the merge request into rabidrat/gxd's master
(gxd/AGENTS.md has the glab command for a fork):

    git remote -v                      # origin must be gitlab.com/alexdej1/gxd
    git push -u origin {branch}

After the merge: fill gxd_mr and exported in {pub}/gxd-exports.tsv for these rows.
"""


def export(repo: Path, dest: Path, pub: str, scans: Path | None = None, shelf: str = "", archive: str = "", received: str = "",
           feature_as: str | None = None, copy_pages: bool = False, name: str = "") -> dict:
    """The gxd export of every puzzle in provenance.jsonl, as a dry run in dest (nothing is sent anywhere):

        <shelf>/<YYYY>/<gxd id>.xd   the puzzles as they'd sit in gxd
        receipts.tsv                 rows for gxd's receipts.tsv (no header)
        source-pages.tsv             every page the puzzles were read from, with its archive name
        source/                      those pages (copy_pages, when the scans repo has them), for make-source-archive.py
        held-back.tsv                puzzles left out, and why
        corrections.tsv              every correction of the print the puzzles carry, and what the export did with it
        publications.tsv             the publication's row for gxd's publications.tsv, if it has none yet (no header)
        COMMANDS.md                  the exact commands that would turn this folder into a merge request

    A puzzle triage marked with one of NOT_EXPORTED's codes stays in the publication's xd/ (a cryptic with
    no key grid: blitz design/games-series-plan.md). The export reads the kind triage recorded; it doesn't guess one."""
    repo, dest = Path(repo), Path(dest)
    shelf, received = shelf or pub, received or date.today().isoformat()
    archive = archive or f"{pub}-scans-{received}.zip"
    labels, labels_from = notes_labels(repo, pub)
    captured = {}
    for r in _tsv(Path(scans) / "sources.tsv") if scans else []:
        m = re.fullmatch(r"pages/([^/]+)/leaf0*(\d+)\.jpg", r["path"])
        if m:
            captured[(m[1], m[2])] = r
    for old in (dest / shelf, dest / "source"):
        if old.exists():
            shutil.rmtree(old)
    dest.mkdir(parents=True, exist_ok=True)
    receipts, held, pages, done, days, corrections = [], [], {}, [], [], []
    for r in sorted(provenance(repo), key=lambda r: r["xdid"]):
        f = repo / "xd" / f"{r['xdid']}.xd"
        if not f.exists():
            held.append((r["xdid"], "not in xd/"))
            continue
        text = f.read_text(encoding="utf-8")
        out_code = next((c for c in r.get("codes") or [] if c in NOT_EXPORTED), "")
        if out_code:
            held.append((r["xdid"], NOT_EXPORTED[out_code]))
            continue
        gid = next((o["gxd_id"] for o in _tsv(repo / "gxd-exports.tsv") if o["xdid"] == r["xdid"] and o.get("gxd_id")), r["xdid"])
        text, fixed_notes, fixed = corrected(text, r.get("corrections"))  # a clue's or header's misprint: corrected here, with its note
        corrections += [{"xdid": r["xdid"], **c} for c in fixed]
        xd = to_gxd(text, [p["text"] for p in r.get("printed") or [] if p["label"] in labels] + list(r.get("notes") or []) + fixed_notes, feature_as)
        day = _header(xd, "Date") or r["xdid"][len(pub):len(pub) + 10]
        used = []
        for role, urls in (r.get("sources") or {}).items():
            for url in urls.split():
                m = re.search(r"archive\.org/details/([^/]+)/page/n(\d+)", url)
                if m:
                    used.append((role, m[1], m[2], f"https://archive.org/details/{m[1]}/page/n{m[2]}/mode/1up"))
        grid_page = next((u for u in used if u[0] == "grid"), None)
        if not grid_page:
            held.append((r["xdid"], "no scan page recorded for its grid"))
            continue
        out = dest / shelf / day[:4] / f"{gid}.xd"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(xd, encoding="utf-8", newline="\n")
        cap = (captured.get(grid_page[1:3]) or {}).get("captured", "")
        receipts.append([cap, received, f"https://github.com/EveryPuzzleProject/{pub}", archive, f"{grid_page[1]}/page/n{grid_page[2]}.jpg", gid])
        for role, item, leaf, url in used:
            pages.setdefault((item, leaf), {"url": url, "used_by": []})["used_by"].append(f"{role}:{gid}")
        done.append(gid)
        days.append(day)
    (dest / "receipts.tsv").write_text("".join("\t".join(r) + "\n" for r in receipts), encoding="utf-8", newline="\n")
    (dest / "held-back.tsv").write_text("xdid\twhy\n" + "".join(f"{x}\t{w}\n" for x, w in held), encoding="utf-8", newline="\n")
    (dest / "corrections.tsv").write_text("xdid\tkey\tprinted\tmeant\tby\tdone\tnote\n" + "".join(
        "\t".join(str(c[k]) for k in ("xdid", "key", "printed", "meant", "by", "done", "note")) + "\n" for c in corrections), encoding="utf-8", newline="\n")
    lines, missing = ["archive_path\tsource\tin_scans\tsha256\tcaptured\tused_by"], 0
    for (item, leaf), pg in sorted(pages.items(), key=lambda kv: (kv[0][0], int(kv[0][1]))):
        row = captured.get((item, leaf)) or {}
        missing += not row
        lines.append("\t".join([f"{item}/page/n{leaf}.jpg", pg["url"], row.get("path", ""), row.get("sha256", ""), row.get("captured", ""),
                                " ".join(pg["used_by"])]))
        if copy_pages and row and (Path(scans) / row["path"]).exists():
            target = dest / "source" / item / "page" / f"n{leaf}.jpg"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(scans) / row["path"], target)
    (dest / "source-pages.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    days = sorted(d for d in days if d)
    row = [pub, pub, name or pub.upper(), "", days[0] if days else "", days[-1] if days else "", str(len(done)), "",
           f"https://github.com/EveryPuzzleProject/{pub}"]
    (dest / "publications.tsv").write_text(chr(9).join(row) + chr(10), encoding="utf-8", newline=chr(10))
    (dest / "COMMANDS.md").write_text(COMMANDS.format(pub=pub, shelf=shelf, n=len(done), archive=archive, dest=dest.resolve().as_posix(),
                                                      years=" ".join(sorted({f"{shelf}/{d[:4]}" for d in days})),
                                                      branch=f"import-{pub}-{days[0][:4]}-{days[-1][2:4]}" if days else f"import-{pub}"),
                                      encoding="utf-8", newline=chr(10))
    return {"exported": done, "held": held, "pages": len(pages), "pages_not_in_scans": missing, "no_capture_date": sum(not r[0] for r in receipts),
            "corrections": {d: sum(c["done"] == d for c in corrections) for d in ("applied", "noted", "not applied")},
            "notes_from": labels_from, "shelf": shelf, "archive": archive, "dest": str(dest)}
