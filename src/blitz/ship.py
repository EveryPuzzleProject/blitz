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


def _stale(rec: dict, current: tuple, rule: Rule) -> bool:
    """Whether a Ready / Not ready was given on an earlier version of the puzzle than `current` (the packet's
    fingerprints), and so no longer counts. A Ready goes stale whoever gave it. A Not ready goes stale only
    when an AI gave it: a person's Not ready is a diagnosis, and stands until the owner decides."""
    xd = ((rec.get("proof") or {}).get("review") or {}).get("xd")
    return bool(current and xd and xd not in current
                and (rec.get("answer") == "ready" or kind_of(rec, rule) in ("ai", "check")))


def standing(batch: dict, proofs: list[dict], *, check_ok: bool = False, codes: frozenset | set = frozenset(),
             current: tuple = (), rule: Rule = Rule()) -> dict:
    """Whether one puzzle ships: THE ship rule. Nothing else decides it.

    batch: the ledger's latest batch:<pid> (the owner's Ship / Hold on the batch page), or {}.
    proofs: each reviewer's latest proof:<pid> record (Ready / Not ready).
    check_ok: triage's ship check passes. codes: triage's reason codes for the puzzle.
    current: the fingerprints of the puzzle's current version. A Ready on another version doesn't count,
      and neither does an AI's Not ready on another version; a person's Not ready stands across versions.

    Returns {status: ship | hold, reason, why, rule: owner | people | ai | "", by, said, apply}:
    - the owner's own latest decision wins (reason owner-hold when it is Hold or Not ready);
    - otherwise any Not ready that stands holds it for the owner (not-ready): a person's on any version, the
      AI reviewer's on the current one;
    - otherwise one person's Ready ships it (rule "people");
    - otherwise, with rule.ai_ready on, the AI's Ready ships it (rule "ai"), unless it carries one of PERSON_CODES
      (clue-by-sequence), which only a person's Ready ships;
    - otherwise it waits (no-ready; proof-stale when all that was said, a Ready or an AI's Not ready, was on
      an earlier version);
    - and a puzzle that would ship is held when it carries one of rule.hold_codes (the code is the reason).
    said: every decision counted, oldest first; apply: the Ready records whose edits the import applies."""
    said = []
    for r in sorted(proofs, key=lambda r: r.get("at", "")):
        if r.get("answer") not in ("ready", "notready") or _name(r) in rule.ignore:
            continue
        said.append({"who": r.get("by", ""), "kind": kind_of(r, rule), "answer": r["answer"], "note": r.get("note", ""),
                     "at": r.get("at", ""), "stale": _stale(r, current, rule), "rec": r})
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
            over = [s for s in said if s["answer"] == "notready" and not s["stale"]]  # said so: the owner may not have seen a later one
            res = out("ship", "", f"Ready by {mine['who']}" + (f", over a Not ready by {who(over)}"
                      + (" given after it" if any(s["at"] > mine["at"] for s in over) else "") if over else ""), mine["who"], "owner")
    elif batch.get("answer") == "hold":
        res = out("hold", "owner-hold", f"held on the batch page by {batch.get('by', '')}" + (f": {batch['note']}" if batch.get("note") else ""))
    elif batch.get("answer") == "ship":
        res = out("ship", "", f"Ship on the batch page by {batch.get('by', '')}", batch.get("by", ""), "owner")
    if res is None:
        no = [s for s in said if s["answer"] == "notready" and not s["stale"]]
        people = [s for s in ready if s["kind"] == "helper"]
        ai = any(s["kind"] == "ai" for s in ready)
        person = sorted(set(codes) & set(PERSON_CODES))  # needs a person's Ready, whatever ai_ready says
        ai_ok = {"off": False, "both": ai and check_ok, "either": ai or check_ok}[rule.ai_ready] and not person
        if no:
            res = out("hold", "not-ready", "said Not ready by " + "; ".join(s["who"] + (f": {s['note']}" if s["note"] else "") for s in no))
        elif people:
            res = out("ship", "", f"Ready by {who(people)}, no Not ready", who(people), "people")
        elif ai_ok:
            by = " and ".join(x for x in ("the AI proof reviewer's Ready" if ai else "", "the ship check passes" if check_ok else "") if x)
            res = out("ship", "", f"{by} (ai_ready: {rule.ai_ready}), no Not ready", by, "ai")
        elif any(s["stale"] for s in said):
            res = out("hold", "proof-stale", "; ".join(f"{s['who']}'s {'Ready' if s['answer'] == 'ready' else 'Not ready'}" for s in said if s["stale"])
                      + " was on an earlier version of the puzzle")
        else:
            has = [x for x in ("the AI proof reviewer said Ready" if ai else "", "the ship check passes" if check_ok else "") if x]
            res = out("hold", "no-ready", "no person has said Ready" + (f" ({'; '.join(has)})" if has else "")
                      + (f"; {', '.join(person)} needs a person's Ready, whatever ai_ready says" if person else ""))
    held = sorted(set(codes) & set(rule.hold_codes))
    if res["status"] == "ship" and held:
        res = {**out("hold", held[0], f"carries {', '.join(held)}: held whoever said Ready"), "rule": res["rule"]}
    return res


# ---- the queues: what the batch asks of people ---------------------------------------------

QUEUES = ("question", "unchecked", "broken", "shippable", "shipped", "set-aside", "not-a-crossword")
# a held puzzle's queue, by its reason; every reason not named here is the pipeline's (broken)
QUEUE_OF = {"not-ready": "question", "owner-hold": "question", "edits-differ": "question", "candidate-undecided": "question",
            "proposal-waits": "question",
            "no-ready": "unchecked", "proof-stale": "unchecked"}
# the stage a broken puzzle's reason points to, where triage recorded none (triage's blocking names its own)
STAGE_OF = {"mark-invalid": "proof review", "misprint-edit": "proof review", "packet-stale": "proof packet", "no-packet": "proof packet", "edits-unapplied": "import", "xd-exists": "import",
            "clue-typed": "text step", "awaits-replace": "assembly"}
# A Not ready that waits on the pipeline, not on a person's answer (its own reason, in the broken queue, with what
# was said kept on the row as `asked`):
#   awaits-replace: the owner's Not ready on a linked-ends puzzle carries fixes to the grid (its shape, its squares'
#     numbers, key letters) that the packet wasn't made from: the pipeline reads them in and places the clues again
#     (xword-ocr linkedends.hint, `remedy replace`). The owner's only (the owner's rule, 2026-11-12, "Owner only for
#     now"): a helper's or a guest's fixes restart nothing, so their Not ready stays a question for the owner.
# (An AI's question on an incomplete puzzle stays a question: it may be that a clue is not printed in the paper, which
# only a person can decide. The cold review of 2026-11-12 found 9 such among the Collegian's 18.)
WAITS = ("awaits-replace",)
# triage codes that need a person's Ready, whatever ai_ready says: an AI's Ready and the ship check never ship them.
# clue-by-sequence: a clue placed by the list's sequence on a linked-ends puzzle (xword-ocr linkedends). Not a hold on
# a person's Ready: the doubt shows on the clue's proof row.
PERSON_CODES = ("clue-by-sequence",)
GRID_FIX = re.compile(r"(grid|num|cell):r\d+c\d+")  # the edits the re-place stage reads
# the ship check's findings that make a puzzle incomplete, and the stage each points to
INCOMPLETE_STAGE = {"grid-unsolved": "key reading", "clue-empty": "parts", "clue-missing": "assembly", "clue-extra": "assembly",
                    "second-set-missing": "assembly"}
# a question about a header belongs to a group shared across puzzles (by the header it is about); one
# about a clue, a square or a printed line is that puzzle's own
GROUPS = {"title": "the title", "byline": "the byline", "notes": "the notes", "candidate": "a candidate clue list"}
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
    field = m[1] if m else "notes" if row == "notes" else "candidate" if (row or "").startswith("candidate:") else ""
    return {"author": "byline", "note": "notes"}.get(field, field)


def _ask(text: str) -> dict:
    """A reviewer's comment as a question: its text without the reviewer's own preamble, and what it suggests."""
    text = re.sub(r"^Flag for the maintainer:\s*", "", (text or "").strip())
    q, _, suggest = text.partition(" Suggest: ")
    return {"text": q.strip(), **({"suggest": suggest.strip()} if suggest.strip() else {})}


def asks_of(reason: str, why: str, batch: dict, proofs: list[dict], rule: Rule, current: tuple = ()) -> list[dict]:
    """The questions a held puzzle waits on, as recorded: each Not ready's comments (the row on the
    proof page each is about: ?k=<row>), its note where it left no comments, the owner's Hold on the
    batch page, or the edits two reviewers made two ways. [{who, kind, at, row, text, suggest, group}]."""
    out = []
    if reason == "edits-differ":
        keys = [k.strip() for k in why.partition(": ")[2].split(",") if k.strip()]
        return [{"who": "the import", "kind": "import", "at": "", "row": keys[0] if keys else "", "group": "",
                 "text": "Two reviewers changed the same thing two ways (" + ", ".join(keys) + "): which one stands?"}]
    for r in sorted(proofs, key=lambda r: r.get("at", "")):
        if r.get("answer") != "notready" or _name(r) in rule.ignore or _stale(r, current, rule):
            continue  # an AI's Not ready on an earlier version doesn't stand: its questions aren't asked
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


def sent_back(proofs: list[dict], rule: Rule, current: tuple = ()) -> dict | None:
    """The latest standing Not ready that sends the puzzle back to the pipeline (its review carries a
    sendback): {who, at, kind, part, note}, or None. The person is saying the question isn't one to
    answer on the proof page, so the puzzle is the pipeline's (broken), not held on a question."""
    for r in sorted(proofs, key=lambda r: r.get("at", ""), reverse=True):
        sb = ((r.get("proof") or {}).get("review") or {}).get("sendback")
        if r.get("answer") == "notready" and sb and _name(r) not in rule.ignore and not _stale(r, current, rule):
            return {"who": r.get("by", ""), "at": r.get("at", ""), "kind": sb.get("kind") or "other", "part": sb.get("part") or "",
                    "note": (sb.get("note") or "").strip()}
    return None


def awaits_replace(proofs: list[dict], rule: Rule, xd: str, ocr: dict) -> dict | None:
    """The owner's latest Not ready on a linked-ends puzzle whose fixes to the grid wait to be read in (the owner's
    only: xword-ocr's stage reads no one else's, by the owner's rule of 2026-11-12, so nobody else's wait): it
    carries grid:, num: or cell: edits (the import applies only a Ready's edits; the stage that places the clues
    reads these from the ledger), and the packet doesn't record that it was made from that decision (ocr.json's
    reviewer_fixes.decisions: who and when, as the stage wrote them). {who, at, note, shape, numbers, letters,
    read_in} (how many of each; read_in: the packet records that decision, so the fixes are in it), or None when
    their latest Not ready carries no such fix: nothing here is worked out from the edits but their count."""
    if not linked(xd):
        return None
    used = {(d.get("by"), d.get("at")) for d in (ocr.get("reviewer_fixes") or {}).get("decisions") or []}
    for r in sorted(proofs, key=lambda r: r.get("at", ""), reverse=True):
        if r.get("answer") != "notready" or _name(r) in rule.ignore or kind_of(r, rule) != "owner":
            continue
        edits = ((r.get("proof") or {}).get("review") or {}).get("edits") or {}
        n = {"grid": 0, "num": 0, "cell": 0}
        for k, v in edits.items():
            m = GRID_FIX.fullmatch(k)
            if m and not (m[1] == "cell" and v in ("_", "#")):  # cell: "_" says what its grid: edit says
                n[m[1]] += 1
        if not any(n.values()):
            return None  # their latest word carries no such fix: it is a question
        return {"who": r.get("by", ""), "at": r.get("at", ""), "note": (r.get("note") or "").strip(),
                "shape": n["grid"], "numbers": n["num"], "letters": n["cell"], "read_in": (r.get("by"), r.get("at")) in used}
    return None


def _incomplete(findings: list, incomplete: list, code: str) -> list[dict]:
    """The ship check's incompleteness as broken items, each with the stage its finding points to."""
    stages = [INCOMPLETE_STAGE[c] for c in findings if c in INCOMPLETE_STAGE]
    return [{"what": str(x), "stage": stages[i] if len(stages) == len(incomplete) else (stages[0] if len(set(stages)) == 1 else ""),
             "code": code, "detail": ""} for i, x in enumerate(incomplete or [])]


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
    elif row["reason"] == "awaits-replace":
        w = row["awaits"]
        fixes = ", ".join(f"{n} {what}" for n, what in ((w["shape"], "square(s) of the grid's shape"), (w["numbers"], "square number(s)"),
                                                          (w["letters"], "key letter(s)")) if n)
        out = [{"what": f"a reviewer's fixes to the grid wait to be read in ({fixes}): the words and the clues' places are made again from them",
                "stage": STAGE_OF["awaits-replace"], "code": "awaits-replace", "detail": ""}]  # the note is in `asked`
        out += _incomplete(row["check"]["findings"], incomplete, "incomplete")
    elif row["reason"] == "incomplete":
        out = _incomplete(row["check"]["findings"], incomplete, "incomplete")
    return out or [{"what": row["why"], "stage": STAGE_OF.get(row["reason"], ""), "code": row["reason"], "detail": ""}]


def filled_by(ship: dict, edits: dict) -> list[str]:
    """The ship check's incompleteness that the edits about to be applied make whole (its lines of
    ship.incomplete): an unsolved grid (grid-unsolved, which names its squares) when every one of those squares
    has its letter among the edits. Nothing else: an empty or missing clue, or a second set, isn't made whole by
    an edit here (a clue typed where the packet has none is not a reading fix)."""
    out = []
    for f in ship.get("findings") or []:
        if (isinstance(f, dict) and f.get("code") == "grid-unsolved" and f.get("cells") and f.get("detail") in (ship.get("incomplete") or [])
                and all(isinstance(edits.get(f"cell:{c}"), str) and len(edits[f"cell:{c}"]) == 1 and edits[f"cell:{c}"].isalpha() for c in f["cells"])):
            out.append(f["detail"])
    return out


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
      puzzles with nothing but shared questions, then fewest questions), then the rest by queue and id; among
      the unchecked, the puzzles a Ready ships before the ones it can't yet (`also`: the ship check's
      incompleteness, kept on an unchecked puzzle too, so the card can say a Ready won't ship it).
    asked (a broken puzzle whose Not ready waits on the pipeline: WAITS, or needs work after a reviewer's fixes
      were read in): what was said on it, as a question's asks are, shown on its card with nothing to answer.
    reviewed: a person (the owner or a helper) has said Ready or Not ready: never an AI alone.
    spot_check: shipped on someone else's word than the owner's, and in the fixed one-in-ten sample.
    Returns the groups, largest first: [{key, label, puzzles, asks}]."""
    for r in rows:
        r["queue"] = (r["status"] if r["status"] in ("shipped", "shippable") else r["reason"] if r["status"] == "out"
                      else QUEUE_OF.get(r["reason"], "broken"))
        r["reviewed"] = any(s["kind"] in ("owner", "helper") for s in r.get("said") or [])
        r["spot_check"] = r["queue"] == "shipped" and r.get("rule") != "owner" and spot(r["pid"])
        if r["queue"] != "question":
            r["asks"] = []
        if r["queue"] not in ("question", "unchecked"):
            r["also"] = []
        if r["queue"] != "broken":
            r.pop("asked", None)
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
        if r["queue"] == "unchecked":  # the ones a Ready ships before the ones it can't yet (the ship check's incompleteness)
            return (q, bool(r.get("also")), 0, 0, r["pid"])
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
                      "note": p.get("note", ""), "xd": p.get("xd", ""), **({"sendback": p["sendback"]} if p.get("sendback") else {}),
                      # what the reviewer marked as printed wrong (the proof page's control): a clue's or a header's
                      # misprint, a misprinted key letter; the shape the AI reviewer's review has them in
                      **({k: p[k] for k in ("typos", "key_corrections") if p.get(k)})}
            out.append({"id": f"proof:{pid}", "answer": p["decision"], "note": (p.get("note") or "").strip(), "fix": "", "by": by,
                        "at": p.get("at", ""), "via": SITE, "proof": {"xdid": pid, "review": review, "at": p.get("at", "")}})
    return out


def fingerprint(text: str) -> str:
    return hashlib.sha1(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()[:12]


def _header(xd: str, key: str) -> str:
    return next((line[len(key) + 2:].strip() for line in xd.split("\n\n\n")[0].split("\n") if line.startswith(key + ": ")), "")


# ---- the reviewers' edits, onto the packet's xd ----------------------------------------------

APPLIED = re.compile(r"clue:[AD]\d+(?:\^[A-Za-z][\w-]*)?|cell:r\d+c\d+|meta:(title|author|byline|puzzle_number|editor|feature)"
                     r"|candidate:[AD]-alt\d+")
# A candidate clue list (assembly's: a list that fits the grid, neither its clues nor a recognised second set; the
# packet's ocr.json candidates) is decided on the proof page by an edit candidate:<id> with one of these values:
# remove (not this puzzle's), answers (the printed answers, not clues), clues (these are the real clues: they
# replace the list in the xd), second:<Key> (a second clue set: its clues become the "A1 ^Key:" lines).
CANDIDATE_VALUE = re.compile(r"remove|answers|clues|second:[A-Za-z][\w-]*")
HEADER ={"title": "Title", "author": "Author", "byline": "Byline", "puzzle_number": "Number", "editor": "Editor", "feature": "Feature"}
META_RE = re.compile(r"^([AD]\d+) \^([A-Za-z][\w-]*): ?(.*)$")


def _meta_key(name: str) -> str:
    return "-".join(w[:1].upper() + w[1:].lower() for w in name.strip().split("-"))


def refused(edits: dict, text: str) -> list[str]:
    """The edits this import can't apply (the puzzle is held for them): kinds it doesn't know (a
    line's label or keep, a fill-in blank, a note), a rebus square, a header of several lines. A
    linked-ends puzzle takes its own kinds (LINKED_APPLIED: a square's kind, a square's printed number,
    a printed line's text and keep); whether each can be applied safely is apply_linked()'s to say."""
    bad = lambda k, v: k.startswith(("clue:", "meta:")) and (not isinstance(v, str) or bool(CONTROL.search(v)))  # one line of the xd
    if linked(text):
        return sorted(k for k, v in edits.items() if not LINKED_APPLIED.fullmatch(k) or bad(k, v)
                      or (k.startswith("line:") and (not isinstance(v, str) or bool(CONTROL_BUT_NL.search(v)))))
    return sorted(k for k, v in edits.items() if not APPLIED.fullmatch(k) or (k.startswith("cell:") and len(v or "") != 1)
                  or bad(k, v)
                  or (k.startswith("candidate:") and not CANDIDATE_VALUE.fullmatch(v or "")))


def words(cells: list[list[str]], outside: str = "#") -> dict[str, list[tuple[int, int]]]:
    """{A1: its squares, D1: ...} for a grid's numbered words, in the order the grid numbers them (words of
    one letter aren't numbered). outside: the characters that aren't squares of the puzzle ('#'; in a
    linked-ends grid '_' too, the template around the diamond)."""
    rows, cols = len(cells), len(cells[0])
    white = lambda r, c: 0 <= r < rows and 0 <= c < len(cells[r]) and cells[r][c] not in outside
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
                    sq, i = [], 0
                    while white(r + dr * i, c + dc * i):
                        sq.append((r + dr * i, c + dc * i))
                        i += 1
                    out[f"{lab}{n}"] = sq
    return out


def answers(cells: list[list[str]], outside: str = "#") -> dict[str, str]:
    """{A1: HELP, D1: HUGE} for a grid's numbered words (words of one letter aren't numbered)."""
    return {lab: "".join(cells[r][c] for r, c in sq) for lab, sq in words(cells, outside).items()}


def _set_header(head: list[str], key: str, v: str) -> list[str]:
    """The header lines with a meta:<field> edit applied: a header that's there keeps its place."""
    name = HEADER[key[5:]]
    at = next((i for i, h in enumerate(head) if h.startswith(f"{name}:")), None)
    head = [h for h in head if not h.startswith(f"{name}:")]
    if v and at is not None:
        head.insert(at, f"{name}: {v}")
    elif v:
        head.insert(next((i for i, h in enumerate(head) if h.split(":")[0] not in HEADER.values()), len(head)), f"{name}: {v}")
    return head


def apply_edits(text: str, edits: dict) -> tuple[str, list[str]]:
    """The xd text with the edits applied (APPLIED kinds; refused() says which can't be). A changed key
    square changes the answers of the words through it. Returns (text, the keys applied). A linked-ends
    xd goes through apply_linked() (an edit it can't apply is left out of the keys)."""
    if linked(text):
        return apply_linked(text, edits)[:2]
    head, grid, *rest = text.replace("\r\n", "\n").rstrip("\n").split("\n\n\n")
    head, cells, done = head.split("\n"), [list(r) for r in grid.split("\n")], []
    for k, v in edits.items():
        m = re.fullmatch(r"cell:r(\d+)c(\d+)", k)
        if m:
            cells[int(m[1]) - 1][int(m[2]) - 1] = v.upper()
            done.append(k)
        elif k.startswith("meta:"):
            head = _set_header(head, k, v)
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


# ---- linked ends: the first crosswords (the New York World's FUN, 1913-14) ---------------------
# Their xd is a different shape (xword-ocr linkedends.py, numbering.py): no Across and Down lists. Each word's
# two end squares carry printed numbers and its clue line is labelled by the pair ("1-2. An insect. ~ BEE"), or by
# the slot's own label where a number wasn't read ("A4. ..."); the across words' lines come first, then the down
# words', each in the grid's order; a word printed in the grid (every square a letter in the Numbering section)
# has no line. The header says "Clues: linked ends", the notes' Numbering: section says which square has which
# number, and '_' is the template outside the puzzle (there are no black squares). The proof page keys a clue
# by its word's standard label (clue:A6), a square's printed number as num:r3c5, a square's kind as grid:r3c5
# ('.' a square of the puzzle, '_' outside it, '#' black; the key's square takes the same value as cell:r3c5).
#
# blitz has no dependency on xword-ocr, so the Numbering section's reader and writer are here as well as in
# xword-ocr numbering.py (parse_numbering_section, numbering_section): the format is that module's.

CONTROL = re.compile(r"[\x00-\x1f\x7f]")  # no clue or header holds one (a line break, a tab)
CONTROL_BUT_NL = re.compile(r"[\x00-\x09\x0b-\x1f\x7f]")  # a printed line may hold a line break, nothing else
LINKED_APPLIED = re.compile(r"clue:[AD]\d+|cell:r\d+c\d+|grid:r\d+c\d+|num:r\d+c\d+|line:B\d+|keep:B\d+"
                            r"|meta:(title|author|byline|puzzle_number|editor|feature)")
PAIR_LINE = re.compile(r"([A-Za-z0-9?]+-[A-Za-z0-9?]+|[AD]\d+)\. (.*) ~ (.*)$")
OUTSIDE = "#_"  # not squares of a linked-ends puzzle
PRINTED_HEAD = "Printed with puzzle:"  # the xd notes block of the printed lines the packet keeps (xword-ocr textstep)
EVIDENCE_HEADER = {"title": "Title", "number": "Number", "byline": "Byline", "author": "Author", "editor": "Editor",
                   "feature": "Feature", "date": "Date"}  # ocr.json's evidence fields and the xd header each gives
_SYM = {str(n): (chr(ord("a") + n - 10) if n < 36 else chr(ord("A") + n - 36)) for n in range(10, 62)}
_NUM = {v: k for k, v in _SYM.items()}


def linked(text: str) -> bool:
    """The xd is in the linked-ends style: its header says so."""
    return "\nClues: linked ends" in "\n" + text.replace("\r\n", "\n").split("\n\n\n")[0]


def _numbers(lines: list[str]) -> dict[tuple[int, int], str]:
    """{(row, col): the number printed in the square, or the letter} from a Numbering: section (its key line
    first): 1-9 as digits, 10 on as a, b, ... up to the last the key line names; any other letter is a letter
    printed in the square; "?" is a number past the section's 61 symbols, which it can't say (kept as "?", so
    writing the section again doesn't lose the mark; it names no pair)."""
    out = {}
    top = max((int(v) for v in re.findall(r"=(\d+)", lines[0])), default=9)
    for r, row in enumerate(lines[1:]):
        for c, ch in enumerate(row):
            if ch.isdigit():
                out[(r, c)] = ch
            elif ch in _NUM and int(_NUM[ch]) <= top:
                out[(r, c)] = _NUM[ch]
            elif ch.isalpha() or ch == "?":
                out[(r, c)] = ch
    return out


def _numbering(cells: list[list[str]], nums: dict[tuple[int, int], str]) -> list[str]:
    """The Numbering: section's lines for the grid and its numbers, as xword-ocr writes it."""
    used = sorted({int(v) for v in nums.values() if v.isdigit() and int(v) >= 10 and v in _SYM})
    key = [f"{_SYM[str(n)]}={n}" for n in (used[:1] + used[-1:] if len(used) > 1 else used)]
    lines = ["Numbering: " + " ".join(key) if key else "Numbering:"]
    for r, row in enumerate(cells):
        out = ""
        for c, ch in enumerate(row):
            v = nums.get((r, c))
            out += ((_SYM.get(v, "?") if int(v) >= 10 else v) if v.isdigit() else v) if v is not None else ch if ch in OUTSIDE else "."
        lines.append(out)
    return lines


def _block(after: list[str], at: int) -> int:
    """The end (exclusive) of the notes block that starts at line `at`: its lines run to the next blank one."""
    end = at + 1
    while end < len(after) and after[end].strip():
        end += 1
    return end


def read_linked(text: str) -> dict:
    """A linked-ends xd, read by its own record: {head: the header lines, cells, after: every line after the grid
    (the clue lines, then the notes), words: {A2: its squares} ('_' outside the puzzle), nums: the Numbering
    section, numbering: (start, end) of that section in `after`, given: the words printed in the grid, line:
    {A2: its clue line's place in `after`} (the across words' lines, then the down words', each in the grid's
    order), label: {A2: "1-2"}, clues: {A2: text}, error}.

    error: why the clue lines can't be put on the grid's words, "" when they can: there aren't as many lines as
    words that want one, or a line's own label (A4), or a pair the Numbering section gives one word, names another
    word than its place in the list does. With an error, line is empty and clues are keyed by the printed labels."""
    head, grid, *rest = text.replace("\r\n", "\n").rstrip("\n").split("\n\n\n")
    after = "\n\n\n".join(rest).split("\n") if rest else []
    cells = [list(r) for r in grid.split("\n")]
    at = []
    for i, ln in enumerate(after):
        if PAIR_LINE.match(ln):
            at.append(i)
        elif ln.strip():
            break
    nb = next((i for i, ln in enumerate(after) if ln.startswith("Numbering:")), None)
    numbering = (nb, _block(after, nb)) if nb is not None else None
    nums = _numbers(after[numbering[0]:numbering[1]]) if numbering else {}
    w = words(cells, OUTSIDE)
    given = {lab for lab, sq in w.items() if all(nums.get(q, "").isalpha() for q in sq)}
    want = [lab for d in "AD" for lab in w if lab[0] == d and lab not in given]
    printed = [PAIR_LINE.match(after[i]) for i in at]
    error = ""
    if len(at) != len(want):
        error = f"the xd lists {len(at)} clue line(s) for the {len(want)} word(s) of its grid that want one"
    else:
        by_pair = {}
        for lab in want:
            a, b = w[lab][0], w[lab][-1]
            if "?" not in (nums.get(a, "?"), nums.get(b, "?")):
                by_pair.setdefault(f"{nums[a]}-{nums[b]}", []).append(lab)
        for lab, m in zip(want, printed):
            named = [m[1]] if re.fullmatch(r"[AD]\d+", m[1]) else by_pair.get(m[1]) or []
            if named and lab not in named:
                error = (f"the clue line labelled {m[1]} is listed where {lab}'s belongs, and its label names "
                         f"{' or '.join(named)}: the clue list and the Numbering section disagree")
                break
    out = {"head": head.split("\n"), "cells": cells, "after": after, "words": w, "nums": nums, "numbering": numbering,
           "given": given, "error": error, "line": {}, "label": {}, "clues": {}}
    if error:
        for i, m in enumerate(printed):
            out["clues"][m[1] if m[1] not in out["clues"] else f"{m[1]} (line {i + 1})"] = m[2]
    else:
        for lab, i, m in zip(want, at, printed):
            out["line"][lab], out["label"][lab], out["clues"][lab] = i, m[1], m[2]
    return out


def _square_edits(edits: dict, cells: list[list[str]]) -> tuple[dict, list[str]]:
    """What the grid: and cell: edits make of each square of a linked-ends grid: ({(row, col): {keys, to}}, what
    can't be applied). The proof page changes a square's kind as grid:r3c5 ('.', '_' or '#') and gives the key's
    square the same value (cell:r3c5), then a letter typed in a new square replaces that; a cell: edit alone is a
    letter read again. to: the character the xd's grid gets."""
    sq, out, cant = {}, {}, []
    for k, v in edits.items():
        m = re.fullmatch(r"(grid|cell):r(\d+)c(\d+)", k)
        if m:
            sq.setdefault((int(m[2]) - 1, int(m[3]) - 1), {})[m[1]] = v
    for (i, j), e in sq.items():
        keys = [f"{x}:r{i + 1}c{j + 1}" for x in ("grid", "cell") if x in e]
        if not (0 <= i < len(cells) and 0 <= j < len(cells[i])):
            cant.append(f"{keys[0]}: the grid has no such square")
            continue
        kind, letter, now = e.get("grid"), e.get("cell"), cells[i][j]
        if letter in ("_", "#", "."):  # the key's square given its kind, as the page writes it beside grid:
            kind, letter = (kind if kind is not None else letter), None
            if kind != e["cell"]:
                cant.append(f"{' and '.join(keys)} say two things about one square ({e['grid']!r}, {e['cell']!r})")
                continue
        if (kind is not None and kind not in ("_", "#", ".")) or (letter is not None and not (isinstance(letter, str) and len(letter) == 1 and letter.isalpha())):
            cant.append(f"{keys[-1]}: {e[keys[-1].split(':')[0]]!r} is neither one letter nor a kind of square ('.', '_', '#')")
        elif kind in ("_", "#") and letter is not None:
            cant.append(f"{' and '.join(keys)} say two things about one square (outside the puzzle, and the letter {letter})")
        elif kind in ("_", "#"):
            out[(i, j)] = {"keys": keys, "to": kind}
        elif letter is not None and kind is None and now in OUTSIDE:
            cant.append(f"{keys[0]}: a letter for a square that is outside the puzzle (grid:r{i + 1}c{j + 1} would say it is one)")
        elif letter is not None:
            out[(i, j)] = {"keys": keys, "to": letter.upper()}
        elif now in OUTSIDE or e.get("cell") == ".":  # a square of the puzzle with no letter: the grid would ship unsolved
            cant.append(f"{keys[0]}: makes r{i + 1}c{j + 1} a square of the puzzle and gives it no letter")
        else:
            out[(i, j)] = {"keys": keys, "to": now}  # already a square of the puzzle: nothing changes
    return out, cant


def printed_lines(ocr: dict, review: dict, edits: dict | None = None) -> list[dict]:
    """The lines printed with the puzzle as the packet has them, with a reviewer's line:B<n> (its text) and
    keep:B<n> (kept or not) edits: [{n, text, keep, label}]. text is the text step's correction where it made
    one; a line a header was read from has no keep of its own and isn't kept."""
    fixed, edits = (review or {}).get("corrections") or {}, edits or {}
    return [{"n": ln.get("n"), "label": ln.get("label") or "",
             "text": edits.get(f"line:B{ln.get('n')}") or fixed.get(f"line:B{ln.get('n')}") or ln.get("text") or "",
             "keep": bool(edits.get(f"keep:B{ln.get('n')}", ln.get("keep", False)))} for ln in (ocr or {}).get("lines") or []]


def block_lines(lines) -> list[str]:
    """The lines of the xd's "Printed with puzzle:" block for the packet's printed lines (printed_lines()): the kept
    ones in the packet's order, a line break inside one's text (a paragraph break a reviewer gave it) a line of
    the block."""
    return [t for ln in lines if ln["keep"] for t in ln["text"].split("\n")]


def printed_place(xd: str, ocr: dict, review: dict) -> dict | None:
    """Where the packet's printed lines land in its xd, and what the import does with a reviewer's keep / discard
    or text edit to one: recorded per puzzle in the ship record (`printed`), so the proof page can show what the
    notes would be with a review's edits without working any of this out. None for a packet with no printed lines.

    {head: the block's heading in the xd's notes, lines: the numbers (B<n>) of the packet lines the block is made
    of, in its order, or None when the xd's block is not the packet's kept lines (then nothing says where an edit
    lands, and none is applied), edits: "applied" (a linked-ends puzzle: the block is written again from the kept
    lines, apply_linked) or "held" (any other puzzle: a Ready carrying a keep: or line: edit holds it as
    edits-unapplied), fixed: the lines a header was read from (not kept or dropped), says: that, in words}."""
    if not xd or not (ocr or {}).get("lines"):
        return None
    lines = printed_lines(ocr, review or {})
    after = "\n\n\n".join(xd.replace("\r\n", "\n").rstrip("\n").split("\n\n\n")[2:]).split("\n")
    at = next((i for i, ln in enumerate(after) if ln == PRINTED_HEAD), None)
    block = after[at + 1:_block(after, at)] if at is not None else []
    agrees = block == block_lines(lines)
    applied = linked(xd)
    fixed = sorted({n for n in ((ocr or {}).get("evidence") or {}).values() if isinstance(n, int)})
    says = ("the xd's printed lines are not the packet's kept lines, so nothing says where an edit to one lands: none is applied"
            if not agrees else
            "the import writes this block again from the kept lines, in the packet's order, with each line's text as edited"
            if applied else
            "the import doesn't apply a keep, discard or text edit of a printed line to this kind of puzzle yet: a Ready "
            "carrying one holds the puzzle (edits-unapplied), and the notes stay as the packet has them")
    return {"head": PRINTED_HEAD, "lines": [ln["n"] for ln in lines if ln["keep"]] if agrees else None,
            "edits": "applied" if applied and agrees else "held", "fixed": fixed, "says": says}


def apply_linked(text: str, edits: dict, ocr: dict | None = None, review: dict | None = None) -> tuple[str, list[str], list[str]]:
    """A linked-ends xd with the reviewers' edits applied: (text, the keys applied, what can't be applied safely,
    in words). Any of the last holds the puzzle (edits-unapplied): nothing is applied in part.

    - clue:A6: the text of the clue line of that word (the line keeps its pair).
    - cell:r3c5 = a letter: the key's square; the answers of the words through it follow.
    - grid:r3c5 (with the page's cell:r3c5 beside it): the square's kind. '_' or '#' takes it out of the puzzle, '.'
      with a letter puts it in. Applied only when the grid keeps the same words (each word of the packet's grid
      still there under its label, longer or shorter) and no printed number is left on a square outside the
      puzzle: a fix that makes or removes a word, renumbers the words, or moves a numbered end means the clues
      have to be placed again, which is assembly's, not the import's.
    - num:r3c5: the number (or letter) printed in a square, "" for none. The Numbering section is written again,
      and a clue line whose word's end squares it touches takes the pair they then give (its slot's own label
      when an end has no number). Not applied when it changes which words are printed in the grid.
    - line:B4 / keep:B3 (ocr, review: the packet's): a printed line's text, and whether it is kept. The xd's
      "Printed with puzzle:" block is the packet's kept lines in order, and is written again from them. A line a
      header was read from can't be dropped, and its text must still give the xd's header.
    - meta:title and the other headers, as in any xd."""
    m = read_linked(text)
    head, after, was = list(m["head"]), list(m["after"]), m["words"]
    cells, nums = [row[:] for row in m["cells"]], dict(m["nums"])
    done, cant = [], []
    for k, v in edits.items():
        if not LINKED_APPLIED.fullmatch(k):
            cant.append(f"{k}: not a kind of edit the import applies to a linked-ends puzzle")
        elif k.startswith(("clue:", "meta:")) and (not isinstance(v, str) or CONTROL.search(v)):
            cant.append(f"{k}: its value isn't one line of text (a line break, a tab or another control character)")
        elif k.startswith("line:") and isinstance(v, str) and CONTROL_BUT_NL.search(v):
            cant.append(f"{k}: a printed line's text holds a tab or another control character")
        elif k.startswith("line:") and (not isinstance(v, str) or any(not t.strip() for t in v.split("\n")[1:])):
            cant.append(f"{k}: a printed line's text can hold line breaks, not an empty line (the xd's block ends at one)")
    # the squares: kinds and letters
    squares, bad = _square_edits(edits, cells)
    cant += bad
    for (i, j), s in squares.items():
        cells[i][j] = s["to"]
        done += s["keys"]
    shape = [(i, j) for (i, j), s in squares.items() if (m["cells"][i][j] in OUTSIDE) != (s["to"] in OUTSIDE)]
    # the printed numbers
    for k, v in edits.items():
        n = re.fullmatch(r"num:r(\d+)c(\d+)", k)
        if not n:
            continue
        sq, v = (int(n[1]) - 1, int(n[2]) - 1), (v or "").strip() if isinstance(v, str) else None
        if v is None or not re.fullmatch(r"\d{1,2}|[A-Za-z]|", v) or (v.isdigit() and not 1 <= int(v) <= 61):
            cant.append(f"{k}: {edits[k]!r} is neither a number the Numbering section can hold (1-61), a letter, nor empty")
        elif not (0 <= sq[0] < len(cells) and 0 <= sq[1] < len(cells[sq[0]])) or (v and cells[sq[0]][sq[1]] in OUTSIDE):
            cant.append(f"{k}: a number for a square that isn't one of the puzzle's")
        else:
            if v:
                nums[sq] = v.upper() if v.isalpha() else str(int(v))
            else:
                nums.pop(sq, None)
            done.append(k)
    if nums != m["nums"] and not m["numbering"]:
        cant.append("num: edits, and the xd has no Numbering section to record them in")
    now = words(cells, OUTSIDE)
    if shape:
        said = ", ".join(f"grid:r{i + 1}c{j + 1}" for i, j in shape)
        gone, new = [lab for lab in was if lab not in now or not set(was[lab]) & set(now[lab])], [lab for lab in now if lab not in was]
        if gone or new or list(now) != list(was):
            cant.append(f"{said}: the fix changes which words the grid has or how they are numbered ("
                        + "; ".join(x for x in (f"no longer the same word: {' '.join(gone[:6])}" if gone else "",
                                                 f"new: {' '.join(new[:6])}" if new else "") if x)
                        + "): the clues have to be placed again (assembly), not edited at import")
        lost = sorted(sq for sq in nums if sq[0] < len(cells) and sq[1] < len(cells[sq[0]]) and cells[sq[0]][sq[1]] in OUTSIDE)
        if lost:
            cant.append(f"{said}: leaves a printed number on a square outside the puzzle ("
                        + ", ".join(f"{nums[sq]} at r{sq[0] + 1}c{sq[1] + 1}" for sq in lost[:6])
                        + "): say where it is printed (num:), or place the clues again (assembly)")
    if {lab for lab, sq in now.items() if all(nums.get(q, "").isalpha() for q in sq)} != m["given"]:
        cant.append("num: edits change which words are printed in the grid (and so have no clue): the clues have to be placed again")
    # the clue lines: text, pair and answer
    touched = [k for k in edits if k.startswith(("clue:", "num:", "grid:", "cell:"))]  # each reaches a clue line: its text, pair or answer
    if m["error"] and touched:
        cant.append(f"{', '.join(touched[:4])}: {m['error']}")
    # the packet's own record of each clue row (ocr.json clues: {A12: {printed: "13-14"}}; older packets a list of
    # pairs): what the reviewer was looking at when they edited clue:A12
    rows = (ocr or {}).get("clues")
    rows = dict(rows) if isinstance(rows, list) else rows
    for k, v in edits.items():
        if k.startswith("clue:") and not m["error"]:
            lab = k[5:]
            if lab not in m["line"]:
                cant.append(f"{k}: the grid has no such word with a clue" + (" (it is printed in the grid)" if lab in m["given"] else ""))
            elif ocr is not None and (not isinstance(rows, dict) or lab not in rows):
                cant.append(f"{k}: the packet records no such clue row, so nothing says the edit is for the line it would land on")
            elif ocr is not None and ((rows[lab] or {}).get("printed") or lab) != m["label"][lab]:
                cant.append(f"{k}: the proof page's row {lab} is the clue printed {(rows[lab] or {}).get('printed') or 'with no pair'}, and the xd's "
                            f"line for that word is {m['label'][lab]}: the page and the xd disagree (rebuild the packet)")
            else:
                done.append(k)
    if not cant and not m["error"]:
        for lab, i in m["line"].items():
            _, clue, answer = PAIR_LINE.match(after[i]).groups()
            a, b, a0, b0 = now[lab][0], now[lab][-1], was[lab][0], was[lab][-1]
            label = m["label"][lab]
            if (a, b, nums.get(a), nums.get(b)) != (a0, b0, m["nums"].get(a0), m["nums"].get(b0)):  # an end moved, or its number changed
                label = f"{nums[a]}-{nums[b]}" if "?" not in (nums.get(a, "?"), nums.get(b, "?")) else lab
            if "".join(cells[r][c] for r, c in now[lab]) != "".join(m["cells"][r][c] for r, c in was[lab]):
                answer = "".join(cells[r][c] for r, c in now[lab])
            after[i] = f"{label}. {edits.get(f'clue:{lab}', clue)} ~ {answer}"
    # the Numbering section, when a number or the shape changed
    if not cant and m["numbering"] and (nums != m["nums"] or shape):
        after[m["numbering"][0]:m["numbering"][1]] = _numbering(cells, nums)
    for k, v in edits.items():
        if k.startswith("meta:") and LINKED_APPLIED.fullmatch(k) and isinstance(v, str) and "\n" not in v:
            head = _set_header(head, k, v)
            done.append(k)
    # the printed lines: their text, and which are kept
    lines = [k for k in edits if k.startswith(("line:", "keep:"))]
    if lines:
        have = {ln["n"]: ln for ln in printed_lines(ocr or {}, review or {})}
        evidence = {}
        for f, n in ((ocr or {}).get("evidence") or {}).items():
            if n is not None:
                evidence.setdefault(n, []).append(f)
        at = next((i for i, ln in enumerate(after) if ln == PRINTED_HEAD), None)
        block = after[at + 1:_block(after, at)] if at is not None else []
        if block != block_lines(have.values()):
            cant.append(f"{', '.join(lines[:4])}: the xd's printed lines aren't the packet's kept lines, so the edit has no place in it")
        heads = {h.partition(": ")[0]: h.partition(": ")[2].strip() for h in [*head]}
        for k in lines:
            n, v = int(k.partition(":B")[2]), edits[k]
            if n not in have:
                cant.append(f"{k}: the packet has no such printed line")
            elif k.startswith("keep:") and (not isinstance(v, bool) or n in evidence):
                cant.append(f"{k}: " + ("its value isn't kept or not kept" if not isinstance(v, bool) else
                                        f"the line is where the {' and '.join(evidence[n])} was read from: it isn't a line kept or dropped"))
            elif k.startswith("line:") and not v.strip():
                cant.append(f"{k}: an empty line (keep:B{n} drops a line)")
            elif k.startswith("line:") and any(not heads.get(EVIDENCE_HEADER.get(f, "")) or not _count(v.lower(), heads[EVIDENCE_HEADER[f]].lower())
                                               for f in evidence.get(n, [])):
                cant.append(f"{k}: the line is where the {' and '.join(evidence[n])} was read from, and as edited it doesn't show the "
                            "xd's header: the header has to be given its value with it (meta:), or the line left as it was")
            else:
                done.append(k)
        if not cant:
            new = block_lines(printed_lines(ocr or {}, review or {}, edits))
            if at is not None and new:
                after[at + 1:_block(after, at)] = new
            elif at is not None:  # nothing kept any more: the block goes, with the blank line that set it off
                end = _block(after, at)
                del after[at:end + 1 if end < len(after) else end]
                while after and not after[-1].strip():
                    after.pop()
            elif new:  # the first kept line: the block comes first in the notes
                first = next((i for i, ln in enumerate(after) if ln.strip() and not PAIR_LINE.match(ln)), None)
                if first is None:
                    after += ["", "", PRINTED_HEAD, *new]
                else:
                    after[first:first] = [PRINTED_HEAD, *new, ""]
    if cant:
        return text, [], cant
    out = "\n".join(head) + "\n\n\n" + "\n".join("".join(r) for r in cells) + ("\n\n\n" + "\n".join(after) if after else "") + "\n"
    return out, done, []


def candidate_decisions(records: list[dict], rule: "Rule" = None, current: tuple = ()) -> dict[str, dict]:
    """THE test of whether a candidate clue list is decided, for the record, the batch card, the proof page's
    wording and the import alike. records: each reviewer's latest proof:<pid> record; current: the fingerprints
    of the puzzle's current version.

    A choice is a candidate:<id> edit with a CANDIDATE_VALUE, made by a person (the owner or a helper, not one of
    rule.ignore): an AI reviewer or the ship check asks, it never decides, whatever ai_ready says. A choice
    *counts* when its review said Ready on the current version, which is exactly when the import takes that
    review's edits (standing()'s apply). Returns {id: {decision, kind, at}} for a choice that counts (the latest),
    else {decision: "", pending: {decision, kind, at, why}} for the latest choice that doesn't, with why
    ("in a review that said Not ready", "in a Ready on an earlier version of the puzzle").
    xword-ocr's triage.candidate_decisions mirrors this, less rule.ignore, which it doesn't know."""
    rule = rule or Rule()
    out: dict[str, dict] = {}
    for r in sorted(records, key=lambda r: r.get("at", "")):
        kind = kind_of(r, rule)
        if kind not in ("owner", "helper") or r.get("answer") not in ("ready", "notready") or _name(r) in rule.ignore:
            continue
        review = (r.get("proof") or {}).get("review") or {}
        stale = bool(current and review.get("xd") and review["xd"] not in current)
        why = "in a review that said Not ready" if r["answer"] != "ready" else "in a Ready on an earlier version of the puzzle" if stale else ""
        for k, v in (review.get("edits") or {}).items():
            if not (k.startswith("candidate:") and CANDIDATE_VALUE.fullmatch(v or "")):
                continue
            said = {"decision": v, "kind": kind, "at": r.get("at", "")[:10]}
            if not why:
                out[k[10:]] = said
            elif not (out.get(k[10:]) or {}).get("decision"):
                out[k[10:]] = {"decision": "", "pending": {**said, "why": why}}
    return out


def apply_candidates(text: str, candidates: list[dict], edits: dict) -> tuple[str, list[str], list[str]]:
    """The xd text with the decisions on its candidate clue lists applied (the candidate:<id> edits; candidates:
    the packet's ocr.json candidates). remove and answers leave the xd as it is: an undecided candidate was never
    in it. second:<Key> writes each of the candidate's clues as the "D1 ^Key:" line under its clue; clues puts
    the candidate's text in place of each clue of its direction. Each of those two is said in the xd's notes (a
    decision is a note). Returns (text, the keys applied, what is left partial: a chosen list that doesn't
    cover its direction's slots, or a second set that doesn't cover every clue, which holds the puzzle)."""
    by = {c["id"]: c for c in candidates}
    done, partial, notes = [], [], []
    body = text.replace("\r\n", "\n").rstrip("\n").split("\n\n\n")
    was = body[2].split("\n") if len(body) > 2 else []
    lines = list(was)
    for k, v in edits.items():
        c = by.get(k[len("candidate:"):]) if k.startswith("candidate:") else None
        if c is None or not CANDIDATE_VALUE.fullmatch(v or ""):
            continue
        done.append(k)
        name, d = ("Across" if c["dir"] == "A" else "Down"), c["dir"]
        texts = {label: (x.get("text") or "").strip() for label, x in (c.get("clues") or {}).items()}
        if v == "clues":
            gone = []
            for i, ln in enumerate(lines):
                m = re.match(r"([AD]\d+)\. (.*) ~ (.*)$", ln)
                if m and m[1][0] == d:
                    lines[i] = f"{m[1]}. {texts.get(m[1]) or '[missing]'} ~ {m[3]}"
                    if not texts.get(m[1]):
                        gone.append(m[1])
            if gone:
                partial.append(f"the list chosen as the {name} clues has no clue for {' '.join(gone[:8])}"
                               + (f" (+{len(gone) - 8})" if len(gone) > 8 else ""))
            notes.append(f"Clues: the {name} clues are the list assembly recorded as a candidate ({c.get('why', '')}); a reviewer "
                         "decided on the proof page that these are the real clues. They are as the OCR read them.")
        elif v.startswith("second:"):
            key, out, i = _meta_key(v.split(":", 1)[1]), [], 0
            while i < len(lines):
                out.append(lines[i])
                m = re.match(r"([AD]\d+)\. ", lines[i])
                i += 1
                if m and m[1][0] == d and texts.get(m[1]):
                    while i < len(lines) and META_RE.match(lines[i]) and lines[i].startswith(m[1] + " "):
                        out.append(lines[i])  # after the clue's own metadata lines
                        i += 1
                    out.append(f"{m[1]} ^{key}: {texts[m[1]]}")
            lines = out
            notes.append(f"Clue sets: the ^{key} line under each {name} clue is a second list that fits the grid, recorded by "
                         f"assembly as a candidate ({c.get('why', '')}); a reviewer decided on the proof page that it is a second "
                         "clue set. Its clues are as the OCR read them.")
    if lines == was and not notes:
        return text, done, partial
    clues = {m[1] for ln in lines if (m := re.match(r"([AD]\d+)\. ", ln))}
    for key in sorted({_meta_key(v.split(":", 1)[1]) for k, v in edits.items() if k in done and v.startswith("second:")}):
        have = {m[1] for ln in lines if (m := META_RE.match(ln)) and _meta_key(m[2]) == key}
        if have != clues:
            partial.append(f"the ^{key} set has {len(have)} of {len(clues)} clues")
    body[2] = "\n".join(lines)
    rest = [b.strip("\n") for b in "\n\n\n".join(body[3:]).split("\n\n") if b.strip()]
    out = "\n\n\n".join(body[:3]) + "\n"
    if rest or notes:
        out += "\n\n" + "\n\n".join([*rest, *notes]) + "\n"
    return out, done, partial


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
        # The packet's candidate clue lists (assembly's record), each with what people have chosen for it on the
        # proof page (candidate_decisions: THE test of "is it decided", the same one the import applies below).
        cands = pk["ocr"].get("candidates") or []
        if cands:
            said_c = candidate_decisions(list((proofs.get(pid) or {}).values()), rule, current)
            row["candidates"] = [{"id": c["id"], "dir": c["dir"], "clues": len(c.get("clues") or {}), "slots": c.get("slots", 0),
                                  "reads_as": c.get("reads_as", ""), **(said_c.get(c["id"]) or {"decision": ""})} for c in cands]
        open_c = [c for c in row.get("candidates") or [] if not c["decision"]]

        def candidate_asks(row=row, open_c=open_c):
            """The pipeline's own question for each candidate list no counting decision settles. A reviewer's
            question stays on the row the reviewer gave it: nothing here guesses that a question about the notes
            was about a candidate."""
            for c in open_c:
                name, p = ("Across" if c["dir"] == "A" else "Down"), c.get("pending")
                row["asks"].append({"who": "assembly", "kind": "pipeline", "at": "", "row": f"candidate:{c['id']}", "group": "candidate",
                                    "text": f"Another {name} list fits this grid ({c['clues']} of {c['slots']} slots) and isn't its clues or a "
                                            "recognised second set. What is it: not this puzzle's, a second clue set, the real clues, or the "
                                            "printed answers?" + (f" ({'The owner' if p['kind'] == 'owner' else 'A helper'} chose "
                                            f"\"{p['decision']}\" {p['why']}, so it doesn't count yet: it counts in a Ready on this version.)" if p else "")})
        if st["status"] != "ship":
            # nobody's Ready counts for it (none given, or all that was said was on an earlier version) and triage says
            # it needs work: the pipeline's, not a proofread to ask of a person, whoever looked at an earlier version
            if st["reason"] in ("no-ready", "proof-stale") and t.get("decision") != "ready":
                row.update(reason="needs-work", why="needs work: " + ("; ".join(
                    sorted({b.get("code") or b.get("part") or "" for b in t.get("blocking") or [] if isinstance(b, dict)} - {""})) or "triage's defects") + "; " + st["why"])
            sb = sent_back(list((proofs.get(pid) or {}).values()), rule, current) if row["reason"] == "not-ready" else None
            if sb:  # a reviewer said it is the pipeline's to mend, not a question for the proof page
                row.update(reason="sent-back", sent_back=sb, why=f"sent back from the proof page by {sb['who']}: "
                           + SENT_BACK.get(sb["kind"], (sb["kind"], ""))[0] + (f": {sb['note']}" if sb["note"] else ""))
            if row["reason"] in ("not-ready", "owner-hold"):
                # A Not ready that waits on the pipeline, not on an answer: the pipeline's (broken), with what was said
                # kept on the row. Decided here, from the ledger's record and the packet's, never on the page.
                mine = list((proofs.get(pid) or {}).values())
                said_so = asks_of(row["reason"], row["why"], latest.get(f"batch:{pid}") or {}, mine, rule, current)
                wr = awaits_replace(mine, rule, pk["xd"], pk["ocr"])
                if wr and wr["read_in"]:
                    # the packet was made from their fixes. Triage says it still needs work: the pipeline's, with what they
                    # said kept. Triage says it is ready for review: theirs to look at again, a question as before.
                    if t.get("decision") != "ready":
                        row.update(reason="needs-work", asked=said_so, why="needs work after the reviewer's fixes to the grid were read in: "
                                   + ("; ".join(sorted({b.get("code") or b.get("part") or "" for b in t.get("blocking") or []
                                                        if isinstance(b, dict)} - {""})) or "triage's defects") + "; " + st["why"])
                elif wr:
                    fixes = ", ".join(f"{n} {what}" for n, what in ((wr["shape"], "of the grid's shape"), (wr["numbers"], "square numbers"),
                                                                      (wr["letters"], "key letters")) if n)
                    row.update(reason="awaits-replace", awaits=wr, asked=said_so,
                               why=f"waiting on the pipeline: {wr['who']} said Not ready with fixes to the grid ({fixes}) that the "
                                   "packet wasn't made from; the clues are placed again from them" + (f": {wr['note']}" if wr["note"] else ""))
            if QUEUE_OF.get(row["reason"]) == "question":
                row["asks"] = asks_of(row["reason"], row["why"], latest.get(f"batch:{pid}") or {}, list((proofs.get(pid) or {}).values()), rule, current)
                # what an answer won't mend: said beside the question, so nobody is surprised when it still doesn't ship
                row["also"] = [str(x) for x in ship.get("incomplete") or []]
                candidate_asks()
            elif row["reason"] not in QUEUE_OF:
                row["broken"] = broken_of(row, t.get("blocking"), ship.get("incomplete"))
            if QUEUE_OF.get(row["reason"]) == "unchecked":  # a Ready wouldn't ship it yet: said on its card, and it is walked last
                row["also"] = [str(x) for x in ship.get("incomplete") or []]
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
        # a linked-ends packet must say its page shows its xd: its clue rows are keyed by word, its xd lines by pair,
        # and nothing else says the two agree (a packet that doesn't record it is not taken as agreeing)
        if not review.get("matches_xd", not linked(pk["xd"])):
            hold("packet-stale", "its proof packet doesn't show its xd: rebuild the packet")
            continue
        edits, differ, sources = {}, set(), []
        for r in st["apply"]:
            mine = ((r.get("proof") or {}).get("review") or {}).get("edits") or {}
            if kind_of(r, rule) not in ("owner", "helper"):  # an AI asks, a person decides: its candidate edits are never the decision
                mine = {k: v for k, v in mine.items() if not k.startswith("candidate:")}
            differ |= {k for k, v in mine.items() if k in edits and edits[k] != v}
            edits.update({k: v for k, v in mine.items() if k not in edits})
            if mine:
                sources.append(r.get("by", ""))
        # incomplete: what the ship check found that no Ready makes whole. The one thing a Ready reviewer's edits do
        # make whole is a key square the packet left unread, when each such square has its letter among them
        # ...and only when a person's decision ships it (the owner's, or a helper's Ready): an AI reviewer's Ready never
        # lifts it with its own letter, whatever ai_ready says
        filled = filled_by(ship, edits) if st["rule"] in ("owner", "people") else []
        if [x for x in ship.get("incomplete") or [] if x not in filled]:
            hold("incomplete", "Ready, but incomplete: " + "; ".join(map(str, ship["incomplete"])))
            continue
        if filled:
            st = {**st, "why": st["why"] + f"; the ship check's \"{'; '.join(filled)}\" is filled by the edits applied"}
        if differ:
            hold("edits-differ", "reviewers' edits differ: " + ", ".join(sorted(differ)[:6]))
            continue
        bad = refused(edits, pk["xd"])
        if bad:
            hold("edits-unapplied", "proof-page edits the import can't apply yet: " + ", ".join(bad[:6]))
            continue
        # its candidate clue lists: each decided by a Ready reviewer's edit, or the puzzle waits for that decision
        undecided = [c["id"] for c in cands if f"candidate:{c['id']}" not in edits]
        if undecided:
            row.update(reason="candidate-undecided", why=f"{st['why']}; but {len(undecided)} candidate clue list(s) "
                       f"({', '.join(undecided)}) not decided by a person who said Ready on this version")
            candidate_asks(open_c=[c for c in row["candidates"] if c["id"] in undecided])
            row["also"] = [str(x) for x in ship.get("incomplete") or []]
            continue
        text, cdone, partial = apply_candidates(pk["xd"], cands, edits)
        if partial:
            hold("candidate-partial", "a candidate list was taken into the puzzle, and it isn't whole: " + "; ".join(partial))
            continue
        if linked(text):  # its own kinds of edit, each applied whole or the puzzle held with what can't be
            text, done, cant = apply_linked(text, edits, pk["ocr"], pk["review"])
            if cant:
                hold("edits-unapplied", "proof-page edits the import can't apply to this linked-ends puzzle as it stands: "
                     + "; ".join(cant[:3]) + (f" (+{len(cant) - 3})" if len(cant) > 3 else ""))
                continue
        else:
            text, done = apply_edits(text, edits)
        if filled and "." in text.split("\n\n\n")[1]:  # the letters were given, and a square is still unread in what would ship
            hold("incomplete", "Ready, but incomplete: " + "; ".join(map(str, ship["incomplete"])) + " (the edits don't fill every square)")
            continue
        done = cdone + done
        passing[pid] = {"text": text, "edits": done, "edit_values": edits, "edit_sources": sources, "standing": st, "row": row,
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
# Whose misprint marks take effect (the owner's rule, 2026-11-13, "Owner only for now"): a typos or key_corrections
# entry from the owner (rule.owner on the review site, or their own tools) or from the AI proof reviewer (2026-11-11).
# Anyone else's is a proposal: kept in the ledger, shown on the proof page and in the xd as it will ship as "proposed
# by ..., waiting for the owner", never applied at ship-export nor (a key letter) corrected here.
MARKS_COUNT = ("owner", "ai")
MARK_MAX = 200  # characters in a mark's printed or meant words


def mark_problem(t, key_letter: bool = False) -> str:
    """Why a typos / key_corrections entry can't be taken, "" when it can: its key names a clue, a header or (a key
    letter) a square; printed and meant (corrected) are strings of one line, with no tab or control character, at
    most MARK_MAX characters, and differ; a key letter's are one letter each."""
    if not isinstance(t, dict):
        return "not an entry"
    key, p = t.get("key"), t.get("printed")
    m = t.get("corrected", t.get("meant")) if key_letter else t.get("meant")  # key_corrections say corrected; a typos entry for a square, meant
    if not isinstance(key, str) or not (re.fullmatch(r"cell:r\d+c\d+", key) if key_letter else _TYPO_KEY.fullmatch(key)):
        return f"its key {key!r} names no {'square' if key_letter else 'clue or header'}"
    for name, v in (("printed", p), ("corrected" if key_letter else "meant", m)):
        if not isinstance(v, str) or not v.strip():
            return f"{key}: no {name} text"
        if CONTROL.search(v):
            return f"{key}: its {name} text holds a line break, a tab or another control character"
        if len(v) > MARK_MAX:
            return f"{key}: its {name} text is over {MARK_MAX} characters"
        if key_letter and not re.fullmatch(r"[A-Za-z]", v.strip()):
            return f"{key}: its {name} letter isn't one letter"
    if p.strip() == m.strip():
        return f"{key}: printed and meant are the same"
    return ""
_DIR = {"A": "Across", "D": "Down"}
# a misprint's key: a clue, a key square, or a header under either name a reviewer uses for it (the proof
# page's evidence row ev:title / ev:byline / ev:number, or the edit's meta:title)
_TYPO_KEY = re.compile(r"clue:[AD]\d+(?:\^[\w-]+)?|cell:r\d+c\d+|(?:meta|ev):(?:title|author|byline|puzzle_number|number|editor|feature)")


def _field(key: str) -> str:
    """The HEADER field a header's key names (ev:number and meta:puzzle_number are both puzzle_number); "" for others."""
    m = re.fullmatch(r"(?:meta|ev):(\w+)", key or "")
    name = {"number": "puzzle_number"}.get(m[1], m[1]) if m else ""
    return name if name in HEADER else ""


def _word(word: str) -> re.Pattern:
    """`word` as a whole word or phrase: not inside a longer word ("Tow" is not in "Towel")."""
    return re.compile(r"(?<!\w)" + re.escape(word) + r"(?!\w)")


def _count(text: str, word: str) -> int:
    return len(_word(word).findall(text or "")) if word else 0


def _swap(text: str, word: str, to: str) -> str:
    return _word(word).sub(lambda m: to, text, count=1)


def _read(text: str) -> tuple[dict, list[list[str]], dict]:
    """An xd's headers {name: value}, its grid's squares, and its clue texts {A1: ..., A1^Easy: ...}."""
    head, grid, *rest = text.replace("\r\n", "\n").rstrip("\n").split("\n\n\n")
    heads = {k: v.strip() for k, sep, v in (h.partition(":") for h in head.split("\n")) if sep}
    if linked(text):  # its clue lines are labelled by pairs: each under its word's standard label, as the page keys it
        return heads, [list(r) for r in grid.split("\n")], read_linked(text)["clues"]
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


def _key_note(cells: list[list[str]], at: tuple[int, int], printed: str, outside: str = "#", names: dict | None = None) -> str:
    """The editorial note for a corrected key letter: the square, what the key printed, what it was corrected
    to, and the answers through it, in the form of Judge's notes. cells is the corrected grid. names: how the
    puzzle itself names each word, where that isn't "17 Across" (a linked-ends puzzle: its printed pair)."""
    was = [row[:] for row in cells]
    was[at[0]][at[1]] = printed.upper()
    a_now, a_was = answers(cells, outside), answers(was, outside)
    through = [lab for lab in a_now if a_now[lab] != a_was.get(lab)]
    name = lambda lab: (names or {}).get(lab) or f"{lab[1:]} {_DIR[lab[0]]}"
    where = f"row {at[0] + 1}, column {at[1] + 1}"
    if not through:
        return f"The printed answer key gave the square at {where} as {printed.upper()}, presumably in error. It has been corrected to {cells[at[0]][at[1]]}."
    gave = f"{name(through[0])} as {a_was[through[0]]}" + (
        " (and so " + " and ".join(f"{name(o)} as {a_was[o]}" for o in through[1:]) + ")" if through[1:] else "")
    return (f"The printed answer key gave {gave}, presumably in error ({printed.upper()} at {where}). It has been corrected to "
            + " and ".join(a_now[lab] for lab in through) + f" ({cells[at[0]][at[1]]}).")


def _label(key: str, names: dict | None = None) -> str:
    """How a note names a clue or a header: A71, A71^Easy, the title; a linked-ends clue by its printed pair
    (names: {A6: "5-6"}), which is how its xd labels it."""
    if key.startswith("clue:"):
        return f"The clue for {names[key[5:]]}" if (names or {}).get(key[5:]) else key[5:]
    return "The " + HEADER.get(_field(key), key.split(":")[-1]).lower()


def _pairs(text: str) -> dict:
    """{A6: "5-6"} for a linked-ends xd whose clue lines carry pairs (a line under its slot's own label is left
    out: the label is its name already); {} for any other xd."""
    return {lab: p for lab, p in read_linked(text)["label"].items() if p != lab} if linked(text) else {}


def edit_records(packet_xd: str, applied: str, apply: list[dict], rule: Rule = Rule(), pid: str = "", ocr: dict | None = None,
                 packet_review: dict | None = None) -> dict:
    """The xd that ships, the record of every edit between the packet's xd and it, and the corrections of the
    print that travel beside it.

    applied: the packet's xd with the Ready reviewers' edits applied (apply_edits). apply: those Ready records
    (standing()'s), first reviewer first. A reviewer names a misprint in their review's typos {key, printed,
    meant} (key a clue's or a header's: ev:title, ev:byline, ev:number as the reviewer writes them, or meta:title) and a misprinted key letter in key_corrections {key:
    cell:r3c4, printed, corrected, edited, crop, text} (a typos entry with a cell: key is taken the same way).
    Returns {text, records,
    corrections, notes, missing}:
    - text: the xd that ships. A clue's or a header's misprint is as printed in it. A reviewer's edit to that
      clue stands when it has the printed word (a reading fix: the reviewer put the text back as printed, or
      fixed something else in the clue); an old-style edit toward the word meant is kept except for the
      misprint (the word meant goes back to the word printed). A misprinted key letter is corrected in it (by the reviewer's own cell edit, or from their
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
      square the packet's xd doesn't have (nothing to say what it replaced; a line a candidate decision wrote
      is not that: its before is the candidate's text), a value that changed with no edit behind it, an edit
      beside a misprint entry that doesn't say what was printed, or a key correction that doesn't say what
      the key printed, or doesn't match the square. Words are matched whole ("Tow" is not in "Towel").

    A linked-ends xd (packet_review: the packet's review.json, for its printed lines) has four more kinds of record,
    under the same classes: a square's kind (grid:r3c10, what "grid square": '_' outside the puzzle, or the
    letter of a square put into it; the page's cell: edit beside it is the same change, named in `with`), a
    square's printed number (num:r3c5, what "square number", with `pairs`: the clue lines whose label follows),
    a printed line's text (line:B4, what "printed line") and whether it is kept (keep:B3, what "printed line
    kept": a decision, with the line's text). Its clues are keyed by their words' standard labels, as the proof
    page keys them, with the printed pair in `pair`."""
    ocr = ocr or {}
    is_linked = linked(packet_xd)
    outside, pairs = (OUTSIDE if is_linked else "#"), _pairs(packet_xd)
    was_h, was_c, was_q = _read(packet_xd)
    owner, value, typos, seen, of_key, key_said = {}, {}, [], set(), set(), {}
    invalid, proposals, row_marks = [], [], []  # marks that can't be taken (they hold the puzzle); marks that wait for the owner
    who = lambda r: {"by": r.get("by", ""), "kind": kind_of(r, rule), "via": r.get("via", ""), "at": r.get("at", "")}
    for r in apply:
        review = (r.get("proof") or {}).get("review") or {}
        for k, v in (review.get("edits") or {}).items():
            if k not in owner:
                owner[k], value[k] = r, v
        counts = kind_of(r, rule) in MARKS_COUNT and _name(r) not in rule.ignore  # the owner's rule of 2026-11-13
        for kind, ts in (("typos", review.get("typos") or []), ("key_corrections", review.get("key_corrections") or [])):
            for t in ts if isinstance(ts, list) else [ts]:
                why = mark_problem(t, kind == "key_corrections" or str((t or {}).get("key", "") if isinstance(t, dict) else "").startswith("cell:"))
                if why and counts:
                    invalid.append(f"{kind} from {r.get('by', '')}: {why}")
                elif why and _name(r) not in rule.ignore:  # a helper's or a guest's: dropped, said, holding nothing
                    k0, p0 = (t.get("key"), t.get("printed")) if isinstance(t, dict) else (None, None)
                    if isinstance(k0, str) and _TYPO_KEY.fullmatch(k0) and not k0.startswith("cell:") and isinstance(p0, str) and p0.strip():
                        row_marks.append((k0, p0.strip(), None, r))  # it still names its row and its printed words: its own edit is checked
                    proposals.append({"key": str(t.get("key", "")) if isinstance(t, dict) else "", "printed": "", "meant": "", **who(r),
                                      "what": "malformed", "status": "not taken", "says": f"A mark that can't be taken, dropped: {why}."})
                elif not counts and _name(r) not in rule.ignore:
                    letter = kind == "key_corrections" or t["key"].startswith("cell:")
                    meant = (t.get("corrected") if kind == "key_corrections" else t.get("meant")).strip()
                    if not letter:  # whoever marked it, the row ships as printed (its edit is checked below)
                        row_marks.append((t["key"], t["printed"].strip(), meant, r))
                    proposals.append({"key": t["key"], "printed": t["printed"].strip(), "meant": meant, **who(r),
                                      "what": "key letter" if letter else "misprint", "status": "waiting for the owner",
                                      "says": (f"The key prints {t['printed'].strip().upper()} at {t['key'][5:]}; proposed: {meant.upper()}." if letter
                                               else f"{_label(t['key'], pairs)} is printed '{t['printed'].strip()}'; proposed: '{meant}'.")})
        if not counts:
            continue  # a helper's or a guest's marks are proposals; their edits are classed on their own evidence
        for t in review.get("typos") or []:
            t3 = (str(t.get("key") or ""), str(t.get("printed") or "").strip(), str(t.get("meant") or "").strip()) if isinstance(t, dict) else None
            if t3 and t3 not in seen and not mark_problem(t, t3[0].startswith("cell:")):
                seen.add(t3)
                typos.append((*t3, r))
        # xword-ocr's reviewer names a misprinted key letter in key_corrections {key: cell:r3c6, printed, corrected,
        # edited, crop, text}: edited false = the packet's grid already had the corrected letter. Its text is the note.
        for t in review.get("key_corrections") or []:
            if mark_problem(t, True):
                continue
            t3 = (str(t.get("key") or ""), str(t.get("printed") or "").strip(), str(t.get("corrected") or "").strip())
            of_key.add(t3)
            if t3 not in seen:
                seen.add(t3)
                typos.append((*t3, r))
                key_said.setdefault(t3[0], {"text": str(t.get("text") or "").strip(), "crop": t.get("crop") or ""})
    whole = lambda key, printed, meant: bool(printed and meant and printed != meant and _TYPO_KEY.fullmatch(key))
    records, missing, have, more_edits, back, key_fix, said, misedit = [], [], {}, {}, set(), {}, {}, []
    edit_key = lambda key: f"meta:{_field(key)}" if _field(key) else key  # the edit a misprint's key sits beside
    # the candidate lists a reviewer took in (as the clues, or as a second set): their decision wrote those lines
    lists = [k for k in owner if k.startswith("candidate:") and (value[k] == "clues" or str(value[k]).startswith("second:"))]
    cands = {f"candidate:{c.get('id')}": c for c in ocr.get("candidates") or [] if isinstance(c, dict)}

    def marked_row(key, printed, meant):
        """A clue's or a header's mark beside an edit to that row: the edit stands when it keeps the printed words once;
        with the words meant once instead, those go back as printed; anything else would ship the row other than as
        printed (the words meant typed twice or in another case, the printed words gone), and holds the puzzle."""
        ek = edit_key(key)
        v = more_edits.get(ek, value[ek]) or ""
        if not whole(key, printed, meant):
            missing.append(f"{key}: an edit beside a misprint entry that doesn't say what was printed and what was meant")
        elif _count(v, printed) == 1:
            pass  # the edit keeps the printed words: it stands as it is, and whatever else it changes is classed on its own
        elif not _count(v, printed) and _count(v, meant) == 1:  # an edit toward the words meant: they go back as printed
            more_edits[ek] = _swap(v, meant, printed)
            back.add(ek)
        else:
            misedit.append(f"{ek}: the edit (“{v[:80]}”) doesn't keep the printed “{printed}” once, beside the mark that it "
                           f"is printed so and meant “{meant}”: the row would ship other than as printed")

    for key, printed, meant, r in typos:
        if key.startswith("cell:") or (key, printed, meant) in of_key:  # case 3: the key's letter is corrected here, and only with its whole record
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
        elif edit_key(key) in owner:  # case 2 on a clue or header the reviewer also edited
            marked_row(key, printed, meant)
    # a helper's or a guest's mark (design/ship.md, the table under "A marked row ships as printed"): it checks only the
    # marker's own edit on the row, never another person's, so blitz doesn't ship the print corrected on their word; the
    # correction itself waits for the owner. A dropped (malformed) mark that still names its row and printed words: the
    # marker's own edit stands only if it keeps them once.
    for key, printed, meant, r in row_marks:
        ek = edit_key(key)
        if ek not in owner or owner[ek].get("by") != r.get("by"):
            continue  # no edit on the row, or another person's: it ships as it is
        if meant is not None:
            marked_row(key, printed, meant)
        elif _count(more_edits.get(ek, value[ek]) or "", printed) != 1:
            misedit.append(f"{ek}: the edit (“{str(value[ek])[:80]}”) doesn't keep the printed “{printed}” once, beside the same "
                           f"reviewer's mark (dropped: malformed) that it is printed so: the row would ship other than as printed")
    # the follow-on edits (a key letter corrected from its entry alone, a misprint taken back out of an edit) are
    # applied here, and one that isn't applied is never recorded or noted as if it were: the puzzle is held for it
    if invalid or misedit:  # held before anything is made of them
        return {"text": applied, "records": [], "corrections": [], "notes": [], "missing": [], "invalid": invalid, "misedit": misedit,
                "proposals": proposals, "waits": []}
    if more_edits:
        text, did, cant = apply_linked(applied, more_edits) if is_linked else (*apply_edits(applied, more_edits), [])
        cant = cant or [f"{k}: the xd has no such clue, square or header to change" for k in more_edits if k not in did]
        if cant:
            return {"text": applied, "records": [], "corrections": [], "notes": [], "missing": [],
                    "cant": [f"a correction named in the review ({', '.join(more_edits)}) can't be made: " + "; ".join(cant[:3])]}
    else:
        text = applied
    value.update(more_edits)
    now_h, now_c, now_q = _read(text)

    def evidence(k):
        crop = (ocr.get("clues") or {}).get(k[5:]) if k.startswith("clue:") else None
        page = ((key_said.get(k) or {}).get("crop") or (ocr.get("answer_page") or {}).get("image")) if k.startswith("cell:") else None
        return {"proof": f"{PROOF_PAGE}{pid}&k={k}", **({"image": crop.get("image") or ocr.get("clue_image", ""), "box": crop["box"]} if crop and crop.get("box") else {}),
                **({"image": page} if page else {})}

    def add(k, what, before, after, r, **more):
        if before == after:
            return  # an edit that changes nothing is no edit
        why = _why(r, more.get("decided_by") or k) or (_why(r, "line:" + k[5:]) if k.startswith("keep:") else "")
        # a mark on the row says which words are the print's mistake, nothing about the rest of the edit: that is
        # classed on its own evidence (a comment on the row: a reading fix; none: unclassed, listed for the owner)
        cls = (DECISION if what in ("decision", "printed line kept") or more.get("decided_by") else KEY_FIX if k in key_fix
               else UNCLASSED if k in back or not why else READING)
        have[k] = {"key": k, "what": what, "class": cls, "before": before, "after": after, **who(r), "stage": EDIT_STAGE,
                   **({"why": why} if why else {}), "evidence": evidence(k), **more,
                   **({"beside": "a correction of the print, not applied: see corrections"} if k in back else {})}
        records.append(have[k])

    lk0, lk1 = (read_linked(packet_xd), read_linked(text)) if is_linked else ({}, {})
    if is_linked:  # the squares: a kind and the key's letter for one square are one change, under the grid: key
        a0 = answers(was_c, outside)
        for (i, j), s in _square_edits({k: v for k, v in value.items() if k.startswith(("grid:", "cell:"))}, was_c)[0].items():
            k = s["keys"][0]
            one = [row[:] for row in was_c]
            one[i][j] = s["to"]
            a1 = answers(one, outside)
            add(k, "grid square" if k.startswith("grid:") else "key square", was_c[i][j], s["to"], owner[k],
                words={lab: [a0.get(lab, ""), a1.get(lab, "")] for lab in {**a0, **a1} if a0.get(lab) != a1.get(lab)},
                **({"with": s["keys"][1:]} if s["keys"][1:] else {}))
        lines0 = {ln["n"]: ln for ln in printed_lines(ocr, packet_review or {})}
    for k, r in owner.items():
        v = value[k]
        if is_linked and k.startswith(("grid:", "cell:")):
            if not any(k in (h["key"], *h.get("with", [])) for h in records) and not _square(was_c, "cell:" + k.partition(":")[2]):
                missing.append(f"{k}: the packet's grid has no such square")
        elif is_linked and k.startswith("num:"):
            n = re.fullmatch(r"num:r(\d+)c(\d+)", k)
            sq = (int(n[1]) - 1, int(n[2]) - 1)
            add(k, "square number", lk0["nums"].get(sq, ""), lk1["nums"].get(sq, ""), r,
                pairs={lab: [lk0["label"][lab], lk1["label"].get(lab, "")] for lab in lk0["label"]
                       if lk0["label"][lab] != lk1["label"].get(lab) and sq in (lk0["words"][lab][0], lk0["words"][lab][-1])})
        elif is_linked and k.startswith(("line:", "keep:")):
            ln = lines0.get(int(k.partition(":B")[2]))
            if ln is None:
                missing.append(f"{k}: the packet has no such printed line")
            elif k.startswith("line:"):
                add(k, "printed line", ln["text"], v, r, kept=bool(value.get("keep:" + k[5:], ln["keep"])))
            else:
                add(k, "printed line kept", "kept" if ln["keep"] else "not kept", "kept" if v else "not kept", r,
                    line=value.get("line:" + k[5:]) or ln["text"])
        elif k.startswith("clue:"):
            wrote = next((c for c in lists if "^" in k and c[len("candidate:"):][:1] == k[5:6]
                          and _meta_key(str(value[c]).partition(":")[2]) == k.partition("^")[2]), None) if k[5:] not in was_q else None
            if wrote:  # a line a second-set decision wrote, then fixed by a reviewer: before is the candidate's own text
                was = (((cands.get(wrote) or {}).get("clues") or {}).get(k[5:].partition("^")[0]) or {}).get("text")
                add(k, "second clue set", (was or "").strip(), v, r, written_by=wrote, **({} if was is not None else {"read": False}))
            elif k[5:] not in was_q:
                missing.append(f"{k}: the packet's xd has no such clue, so nothing says what the edit replaced")
            else:
                add(k, "second clue set" if "^" in k else "clue", was_q[k[5:]], v, r, **({"pair": pairs[k[5:]]} if pairs.get(k[5:]) else {}))
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
    names = {v: k for k, v in HEADER.items()}
    diffs = [(f"clue:{k}", "second clue set" if "^" in k else "clue", was_q.get(k), now_q.get(k)) for k in {**was_q, **now_q}]
    diffs += [(f"meta:{names[n]}" if n in names else f"header:{n}", "header", was_h.get(n, ""), now_h.get(n, "")) for n in {**was_h, **now_h}]
    if [len(r) for r in was_c] != [len(r) for r in now_c]:
        missing.append("the grid's size changed from the packet's xd with no edit recorded")
    else:
        diffs += [(f"cell:r{i + 1}c{j + 1}", "key square", c, now_c[i][j]) for i, row in enumerate(was_c) for j, c in enumerate(row)]
    if is_linked:  # the same net under what only a linked-ends xd has: its squares' numbers, its lines' pairs, its printed lines
        diffs += [(f"num:r{i + 1}c{j + 1}", "square number", lk0["nums"].get((i, j), ""), lk1["nums"].get((i, j), ""))
                  for i, j in sorted({**lk0["nums"], **lk1["nums"]})]
        moved = [lab for lab in {**lk0["label"], **lk1["label"]} if lk0["label"].get(lab) != lk1["label"].get(lab)]
        if moved and not any(h["what"] in ("square number", "grid square") for h in records):
            missing.append(f"the clue lines of {' '.join(moved[:6])} changed their labels with no edit to a square's number or kind recorded")
        block = lambda t: next((b.strip("\n").split("\n")[1:] for b in t.replace("\r\n", "\n").split("\n\n") if b.strip("\n").startswith(PRINTED_HEAD)), [])
        if block(packet_xd) != block(text) and block(text) != block_lines(printed_lines(
                ocr, packet_review or {}, {k: v for k, v in value.items() if k.startswith(("line:", "keep:"))})):
            missing.append("the printed lines ship as something other than the packet's kept lines with the edits recorded for them")
    for k, what, before, after in diffs:
        if k.startswith("cell:") and k not in have and "grid:" + k[5:] in have:
            k = "grid:" + k[5:]  # a linked-ends square whose kind changed: recorded under the grid: key
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
        note = (key_said.get(key) or {}).get("text") or _key_note(now_c, _square(now_c, key), printed, outside, pairs)  # the reviewer's own words first
        notes.append(note)
        if key in have:
            have[key].update(misprint={"printed": printed, "meant": meant}, note=note)
        else:  # the packet's key already had the letter meant: no edit of ours, the correction is said all the same
            records.append({"key": key, "what": "key square", "class": KEY_FIX, "before": meant, "after": meant, **who(said[key]),
                            "stage": "before review", "misprint": {"printed": printed, "meant": meant}, "note": note, "evidence": evidence(key)})
    for key, printed, meant, r in typos:
        if key.startswith("cell:") or (key, printed, meant) in of_key:
            continue
        fits, says = "unplaced", f"{key or 'a misprint'}: printed '{printed}', meant '{meant}'."
        if whole(key, printed, meant):
            cur = now_q.get(key[5:]) if key.startswith("clue:") else now_h.get(HEADER[_field(key)], "")
            fits = ("unplaced" if cur is None else "printed" if _count(cur, printed) == 1
                    else "already" if not _count(cur, printed) and _count(cur, meant) else "unplaced")
            if cur is not None and not _count(cur, printed) and not _count(cur, meant):  # names words the row doesn't have
                invalid.append(f"typos from {r.get('by', '')}: {key}: “{printed}” isn't in the row's text (nor the words meant)")
            says = f"{_label(key, pairs)} is printed '{printed}'; meant '{meant}'."
        mine = ((r.get("proof") or {}).get("review") or {}).get("edits", {}).get(edit_key(key))
        corrections.append({"key": key, "printed": printed, "meant": meant, **who(r), "fits": fits, "says": says, "evidence": evidence(key),
                            **({"edit": mine} if mine is not None else {})})
    # a helper's or a guest's key correction whose square they also changed to it: the letter would be corrected here
    # on their word, which the owner's rule keeps for the owner: held, a question for the owner
    waits = [p for p in proposals if p["what"] == "key letter" and p["key"] in owner and owner[p["key"]].get("by") == p["by"]
             and str(value.get(p["key"]) or "").upper() == p["meant"].upper()]
    if invalid:
        return {"text": applied, "records": [], "corrections": [], "notes": [], "missing": [], "invalid": invalid, "misedit": [],
                "proposals": proposals, "waits": []}
    return {"text": with_notes(text, notes), "records": records, "corrections": corrections, "notes": notes, "missing": missing,
            "invalid": invalid, "misedit": misedit, "proposals": proposals, "waits": waits}


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
        if not mark_problem(c) and _TYPO_KEY.fullmatch(key) and not key.startswith("cell:"):
            cur = clues.get(key[5:]) if key.startswith("clue:") else heads.get(HEADER[_field(key)])
            if cur is not None and _count(cur, printed) == 1:  # the printed word, whole, once: the word meant takes its place
                ek = key if key.startswith("clue:") else f"meta:{_field(key)}"
                new, did = apply_edits(text, {ek: _swap(cur, printed, meant)})
                if ek in did:  # said to be applied only when it was (a linked-ends xd can refuse an edit)
                    text, done = new, "applied"
            elif cur is not None and not _count(cur, printed) and _count(cur, meant):
                done = "noted"
            note = f"{_label(key, _pairs(text))} is printed '{printed}'; corrected to '{meant}'." if done != "not applied" else ""
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


READ_IN_STAGE = "re-place"  # xword-ocr read the owner's fixes into the packet before review (linkedends.hint)


def read_in_records(ocr: dict, pid: str = "") -> list[dict]:
    """The edit records for what the packet's base values owe to the owner, not to the OCR: the squares, key letters
    and printed numbers the pipeline read in from the owner's fixes on the proof page when it made the packet
    (ocr.json's reviewer_fixes.squares, xword-ocr's record: {key, value, was, by, at}). They are in the packet's xd
    already, so no Ready's edit carries them, and without these they would ship with no record. One per square
    whose value is not what the stage had there (`was`), or whose `was` the stage didn't record (a number: before
    "", before_recorded false). Class: a square's kind and a printed number are readings of the printed grid; a
    key letter is unclassed (nothing says whether the key was misread or misprinted: never guessed). Stage
    READ_IN_STAGE; `via` says how it reached the xd."""
    what = {"grid": "grid square", "cell": "key square", "num": "square number"}
    out = []
    for s in (ocr.get("reviewer_fixes") or {}).get("squares") or []:
        kind = str(s.get("key", "")).partition(":")[0]
        if kind not in what or ("was" in s and s["was"] == s.get("value")):
            continue
        out.append({"key": s["key"], "what": what[kind], "class": UNCLASSED if kind == "cell" else READING,
                    "before": s.get("was", ""), **({} if "was" in s else {"before_recorded": False}), "after": s.get("value", ""),
                    "by": s.get("by", ""), "kind": "owner", "via": "read into the packet by the pipeline from the owner's proof-page fixes",
                    "at": s.get("at", ""), "stage": READ_IN_STAGE, "evidence": {"proof": f"{PROOF_PAGE}{pid}&k={s['key']}"}})
    return out


def _record_edits(passing: dict, packs: dict, rule: Rule) -> None:
    """Every passing puzzle's xd as it ships (a clue's or header's misprint as printed, a misprinted key letter
    corrected and noted), its edit records and its corrections; a puzzle with an edit that has no whole record
    leaves `passing`, held as edit-unrecorded (the import's: broken)."""
    for pid, x in list(passing.items()):
        e = edit_records(packs[pid]["xd"], x["text"], x["standing"]["apply"], rule, pid, packs[pid]["ocr"], packs[pid]["review"])
        if e.get("cant"):  # a correction the review names that the import can't make: held, and nothing says it was made
            why = "proof-page edits the import can't apply: " + "; ".join(e["cant"])
            x["row"].update(reason="edits-unapplied", why=why, broken=[{"what": why, "stage": "import", "code": "edits-unapplied", "detail": ""}])
            del passing[pid]
            continue
        for code, items, stage, what in (("mark-invalid", e.get("invalid"), "proof review", "a misprint mark that can't be taken"),
                                         ("misprint-edit", e.get("misedit"), "proof review", "a marked row that would ship other than as printed")):
            if items and pid in passing:
                why = f"{what}: " + "; ".join(items[:3]) + (f" (+{len(items) - 3})" if len(items) > 3 else "")
                x["row"].update(reason=code, why=why, broken=[{"what": why, "stage": stage, "code": code, "detail": ""}])
                del passing[pid]
        if pid not in passing:
            continue
        if e.get("waits"):
            w = e["waits"]
            x["row"].update(reason="proposal-waits", proposals=e["proposals"], why="a key letter corrected on the word of someone the "
                            "owner's rule doesn't take it from (" + ", ".join(sorted({p["by"] for p in w})) + "): it waits for the owner",
                            asks=[{"who": p["by"], "kind": p["kind"], "at": p["at"][:10], "row": p["key"], "group": "",
                                   "text": p["says"] + " A misprinted key letter is corrected only on the owner's word: accept it with your "
                                           "own mark on the proof page, or put the letter back."} for p in w])
            del passing[pid]
            continue
        if e["missing"]:
            why = "an edit with no whole record of what it changed: " + "; ".join(e["missing"][:4]) + (
                f" (+{len(e['missing']) - 4})" if len(e["missing"]) > 4 else "")
            x["row"].update(reason="edit-unrecorded", why=why, broken=[{"what": why, "stage": "import", "code": "edit-unrecorded", "detail": ""}])
            del passing[pid]
            continue
        # first what the packet itself was made from (the owner's fixes read in before review), then the Readys' edits
        x.update(edit_records=read_in_records(packs[pid]["ocr"], pid) + e["records"], corrections=e["corrections"], notes=e["notes"], text=e["text"],
                 proposals=e.get("proposals") or [])
        if x["proposals"]:
            x["row"]["proposals"] = [{k: p[k] for k in ("key", "printed", "meant", "what", "says", "status", "kind")} for p in x["proposals"]]
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


def _printed(ocr: dict, review: dict, edits: dict | None = None) -> list[dict]:
    """The lines printed with the puzzle that the packet keeps, with the text step's label for each
    (the export's Notes rule picks among them by label), as the text step corrected them (line:B<n>), and
    then as the reviewers' applied edits have them (line:B<n> the text, keep:B<n> kept or not: today a
    linked-ends puzzle's only, any other puzzle being held on such an edit)."""
    fixed, edits = review.get("corrections") or {}, edits or {}
    return [{"label": ln.get("label") or "", "text": edits.get(f"line:B{ln.get('n')}") or fixed.get(f"line:B{ln.get('n')}") or ln["text"]}
            for ln in ocr.get("lines") or []
            if edits.get(f"keep:B{ln.get('n')}", ln.get("keep", True)) and ln.get("label") and (ln.get("text") or "").strip()]


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
               **({"proposals": x["proposals"]} if x.get("proposals") else {}),  # waiting for the owner; the export never reads them
               "check": x["row"]["check"], "codes": x["row"]["codes"],
               "sources": {k: _header(x["text"], h) for k, h in (("grid", "Source"), ("clues", "Clue-Source"), ("key", "Solution-Source"))
                           if _header(x["text"], h)},
               "printed": _printed(pk["ocr"], pk["review"], {k: v for k, v in (x.get("edit_values") or {}).items() if k in x["edits"]})}
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
               "ai_reviewed", "person_reviewed", "credit", "record_url")  # record_url: the puzzle's public record page (records.py)


def write_exports(repo: Path, pub: str) -> None:
    from .records import record_url
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
                              "y" if kinds & {"ai", "check"} or "Text-Review: " in xd else "", "y" if kinds & {"owner", "helper"} else "", CREDIT,
                              record_url(pub, r["xdid"])]))
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
             "why": why(r), "asks": asks(r), "also": r.get("also") or [], "broken": [
                 {**b, "detail": why({**r, "why": b.get("detail") or ""})} for b in r.get("broken") or []],
             "said": said(r), "check": r["check"],
             # a Not ready that waits on the pipeline (WAITS): what was said, shown on its card with nothing to answer
             **({"asked": asks({**r, "asks": r["asked"]})} if r.get("asked") else {}),
             # its candidate clue lists and what a person decided for each ("" undecided): the packet's, and the ledger's
             **({"candidates": r["candidates"]} if r.get("candidates") else {})} for r in p["rows"]]
    return {"_about": "blitz ship: which puzzles of the batch are shipped (in the publication repo's xd/), shippable (pass the "
                      "ship rule, not written yet) or held, with the reason, and the queue each is in: what the batch page asks "
                      "of people. Format: blitz design/ship.md.",
            "batch": p["batch"], "run": p["run"], "packets": p["packets"], "rule": p["rule"],
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "counts": counts(p["rows"]),
            "groups": p["groups"], "spot": {"one_in": SPOT_ONE_IN, "of": "puzzles shipped on someone else's word than the owner's",
                                            "by": "sha1 of the puzzle's id"},
            "puzzles": [{**row, **{k: r[k] for k in ("notes", "corrections", "proposals") if r.get(k)}, **_recorded_more(p, r)} for row, r in zip(rows, p["rows"])]}


def _recorded_more(p: dict, r: dict) -> dict:
    """What the record says beyond the rule's answer, for the proof page: where the packet's printed lines land in
    its xd (printed_place), and for a puzzle that passes, the fingerprint of the xd as it will ship (as_shipped:
    the text itself is in its own file beside the record, AS_SHIPPED)."""
    pk = (p.get("packs") or {}).get(r["pid"]) or {}
    place = printed_place(pk.get("xd", ""), pk.get("ocr") or {}, pk.get("review") or {})
    x = (p.get("passing") or {}).get(r["pid"])
    return {**({"printed": place} if place else {}), **({"as_shipped": fingerprint(x["text"])} if x else {})}


# ---- the xd as it will ship: one file per passing puzzle, beside the ship record ----------------
# The exact text `--write` writes (or wrote) for each puzzle the rule passes, with the record of every edit behind it,
# made by the same code in the same run as the record. The batch page's "Ready to ship" card and the proof page draw
# it; nothing on them works it out. Where: the record's folder, AS_SHIPPED/<pid>.json (the site: batch/<batch>/
# as-shipped/<pid>.json beside ship.json; the publication repo: pipeline/ship/<batch>/as-shipped/<pid>.json).
AS_SHIPPED = "as-shipped"


def _public_who(e: dict) -> dict:
    """An edit record's or a correction's `by` as the site's copy names people: a helper is "a helper", the owner's
    review-site account "the owner" (as record() names them)."""
    if e.get("kind") == "helper":
        return {**e, "by": "a helper"}
    if e.get("kind") == "owner" and str(e.get("by", "")).endswith(f"({SITE})"):
        return {**e, "by": "the owner"}
    return e


def as_shipped(p: dict, rec: dict, public: bool = True) -> dict[str, dict]:
    """{pid: the record of the xd as it will ship} for every puzzle the plan passes (shippable, or shipped and
    unchanged): {_about, pid, xdid, batch, run, at, status, xd (the text), xd_fp, packet, packet_xd, decision {rule,
    ai_ready, by, why, said}, edits {records, packet}, corrections, notes, printed}: the shape of its provenance row,
    with the text. rec: the ship record made with it (record(p, public)), whose `at` and rows it carries."""
    out = {}
    rows = {r["pid"]: r for r in rec["puzzles"]}
    for pid, x in sorted((p.get("passing") or {}).items()):
        pk, st, row = p["packs"][pid], x["standing"], rows[pid]
        pub = _public_who if public else (lambda e: e)
        out[pid] = {
            "_about": "blitz ship: the xd exactly as `blitz ship --write` writes it for this puzzle, with the record of every "
                      "edit behind it (design/ship.md, \"The xd as it will ship\"). Made with the batch's ship record; stale "
                      "when the record is made again.",
            "pid": pid, "xdid": x["xdid"], "batch": p["batch"], "run": p["run"], "at": rec["at"], "status": row["status"],
            "xd": x["text"], "xd_fp": fingerprint(x["text"]), "packet": x["packet"], "packet_xd": x["xd_fp"],
            "decision": {"rule": st["rule"], "ai_ready": p["rule"]["ai_ready"], "why": row["why"], "said": row["said"]},
            "edits": {"records": [pub(e) for e in x.get("edit_records", [])], "packet": packet_edits(pk["ocr"], pk["review"])},
            "corrections": [pub(c) for c in x.get("corrections", [])], "notes": x.get("notes", []),
            # marks by someone whose marks don't take effect (MARKS_COUNT): shown, waiting for the owner, never applied
            "proposals": [pub(q) for q in x.get("proposals", [])],
            "printed": _printed(pk["ocr"], pk["review"], {k: v for k, v in (x.get("edit_values") or {}).items() if k in x["edits"]})}
    return out


def stale_as_shipped(keys, batch: str, docs: dict) -> list[str]:
    """The site's as-shipped files (keys under batch/<batch>/AS_SHIPPED/) of puzzles that no longer pass: removed when
    the record is published again, so a file stays public only while the record points to it."""
    prefix = f"batch/{batch}/{AS_SHIPPED}/"
    return sorted(k for k in keys if k.startswith(prefix) and k.endswith(".json") and k[len(prefix):-5] not in docs)


def write_as_shipped(folder: Path, p: dict, rec: dict, public: bool = True) -> list[Path]:
    """as_shipped() into folder/AS_SHIPPED/<pid>.json; files of puzzles that no longer pass are removed."""
    d = Path(folder) / AS_SHIPPED
    docs = as_shipped(p, rec, public)
    d.mkdir(parents=True, exist_ok=True)
    for old in d.glob("*.json"):
        if old.stem not in docs:
            old.unlink()
    out = []
    for pid, doc in docs.items():
        f = d / f"{pid}.json"
        f.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        out.append(f)
    return out


def write_record(repo: Path, p: dict) -> Path:
    f = Path(repo) / "pipeline" / "ship" / f"{p['batch']}.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    rec = record(p)
    f.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    write_as_shipped(f.parent / p["batch"], p, rec)
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
        "\t".join(CONTROL.sub(" ", str(c[k])) for k in ("xdid", "key", "printed", "meant", "by", "done", "note")) + "\n" for c in corrections),
        encoding="utf-8", newline="\n")
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
