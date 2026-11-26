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

from .edition import NOTE_LABELS, corrected, notes_labels  # noqa: F401 (the edition step's; ship-export uses them)
from .work import Stop

SITE, AGENT = "review site", "agent review"  # a ledger record's via: a helper's (the hosted proof page), an AI's
CHECK_BY = "the ship check"  # the by of the no-model ship check's own Ready (xword-ocr shipcheck)
AI_READY = ("off", "both", "ai", "either")  # in order: each passes everything the one before it does
# every puzzle of a batch exits with one grade (grade_of; design/v3-agent-forward.md), in this order
GRADES = ("clean", "reviewed", "doubts", "incomplete", "held", "deferred", "not-a-crossword")
SHIPS = GRADES[:4]  # the grades a batch may ship by (Rule.ship_grades); the rest never ship
WHOSE = ("people", "owner")  # whose input counts (Rule.marks, grid_fixes, typed_clues): any person's, or the owner's only
WHOSE_INPUT = ("marks", "grid_fixes", "typed_clues")
PUBLIC = "https://pub-52ac4a15c4ba43fe8e4af5a496733fb5.r2.dev"  # the review site's packages
PROOF_PAGE = "https://blitz.xwordapp.com/review/?p="
CREDIT = "Every Puzzle Project"


# ---- the ship rule -------------------------------------------------------------------------

@dataclass(frozen=True)
class Rule:
    """The ship rule's options. The defaults are the owner's standing rule (2026-10-19): a puzzle
    ships with at least one person's Ready and no Not ready, and the owner's own decision overrides.

    ai_ready: whether an AI counts as the one Ready when no person has said it. "off" (the default:
      not decided), "both" (the AI proof reviewer's Ready and a passing ship check together), "ai" (the AI's
      Ready alone: the ship check's findings are a reviewer's to weigh, not a hold; since 2026-11-25, for the World's
      Nos. 1-33, read twice blind) or "either" (one of them is enough: xword-ocr docs/ship-gate.md's design).
    hold_codes: triage reason codes that hold a puzzle whoever said Ready (clue-typed: a clue the
      text step supplied with no OCR reading behind it).
    ignore: reviewers whose decisions don't count (a scripted usability test's account).
    owner: the owner's own accounts on the review site. A decision made there under one of these
      names is the owner's, and overrides as the owner's do in their own tools.

    Whose input counts (the owner's rule of 2026-11-13: "the other reviewers can have power to mark shit up and do
    whatever they want, given that we can always go back and fix it"), one value each, "people" (the default: any
    person's, the owner's or a helper's or a guest's, as the owner's) or "owner" (the owner's only; anyone else's
    is a proposal, or waits for the owner). An account on `ignore` never counts; an AI reviewer's input keeps its own
    limits whatever these say (counts_for). Where two people's inputs disagree, the owner's stands; otherwise the
    puzzle is a question for the owner.
    marks: a misprint mark or a key correction (typos, key_corrections): it takes effect (case 2 or 3).
    grid_fixes: a Not ready's fixes to a linked-ends grid (grid:, num:, cell:) that the re-place stage reads in.
    typed_clues: a clue typed on the proof page where the packet has no text for it (the ship check's clue-empty)
      makes the puzzle whole (filled_by).
    owner_ids: the owner's own review-site account ids (Supabase user_id). Publishing the edition is an owner-only
      gate, so the review site's "Publish the edition" counts only from these ids, never by a typed name (edition.py).
    owner_stale: what the owner's Ready on an earlier version of the puzzle does. "hold" (the default: it holds the
      puzzle, "look again", before anyone else's Ready is weighed) or "lapse" (it no longer counts, and the puzzle goes
      on to the rest of the rule: a person's or an AI's Ready on the current version may ship it, and the reason says
      the owner's was on an older version). The owner's word for the World's Nos. 1-33 (2026-11-25): "Let AI Ready
      count". A Not ready, the owner's or any person's, holds on any version either way.
    replace: xdids this batch may write over in xd/ although another source shipped them first (the owner's decision:
      a better reading of the same puzzle, e.g. the World's Nos. 11-12, shipped from the OCR batch nyw-1914-c1 and read
      again by hand in nyw-1914-s1). The provenance row says what it replaced.

    ship_grades: the grades a puzzle ships by with no person's Ready (design/v3-agent-forward.md, "Every puzzle exits
      with a grade"; the owner's decisions of 2026-11-25). () (the default: off, and nothing ships by its grade), or any of
      SHIPS: clean, reviewed, doubts, incomplete. A puzzle whose grade is listed ships as it stands: `doubts` with the
      flags no review has settled listed on the row, `incomplete` with its gaps
      named (which replaces, for a batch that opts in, the 2026-11-23 rule that only a person's "Ready to ship as it
      stands" ships an incomplete puzzle). Any Not ready that stands still holds, a person's or an AI reviewer's, with
      one exception: an AI reviewer's Not ready whose every flag has a kind and none is `structure` (soft_no: a reading
      doubt, a header doubt, a missing part) does not stop a puzzle shipping by its grade (`doubts`, `incomplete` or
      `reviewed`: grade_of); it still stops an AI's Ready shipping it. An AI's Not ready with a flag of no kind holds it
      (AI_NOT_READY), and one with a `structure` flag is graded held (AI_STRUCTURE). Every protection of a person's word stays: the
      owner's decision overrides, an AI never overrides a person, a hold code holds, PERSON_CODES still need a person's
      Ready, and no edit ships without its record.

    ship-rule.json's "batches": {"<batch>": {...}} gives one batch its own values of these (rule_of)."""
    ai_ready: str = "off"
    hold_codes: tuple = ("clue-typed",)
    ignore: tuple = ()
    owner: tuple = ()
    marks: str = "people"
    grid_fixes: str = "people"
    typed_clues: str = "people"
    owner_ids: tuple = ()
    replace: tuple = ()
    owner_stale: str = "hold"
    ship_grades: tuple = ()


def rule_of(repo: Path, batch: str = "", **over) -> Rule:
    """The publication's rule: fixes/ship-rule.json where it has one, then its "batches" entry for this batch (a batch
    shipped on its own terms: the World's Nos. 1-33 on an AI's Ready), then the caller's overrides."""
    f = Path(repo) / "fixes" / "ship-rule.json"
    d = {k: v for k, v in (json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}).items() if not k.startswith("_")}
    d.update({k: v for k, v in ((d.pop("batches", None) or {}).get(batch) or {}).items() if not k.startswith("_")})
    d.update({k: v for k, v in over.items() if v is not None})
    if d.get("owner_stale", "hold") not in ("hold", "lapse"):
        raise Stop(f"owner_stale is hold or lapse, not {d['owner_stale']!r}")
    if d.get("ai_ready", "off") not in AI_READY:
        raise Stop(f"ai_ready is one of {', '.join(AI_READY)}, not {d['ai_ready']!r}")
    for k in WHOSE_INPUT:
        if d.get(k, "people") not in WHOSE:
            raise Stop(f"{k} is one of {', '.join(WHOSE)}, not {d[k]!r}")
    bad = [g for g in d.get("ship_grades") or [] if g not in SHIPS]
    if bad or isinstance(d.get("ship_grades"), str):
        raise Stop(f"ship_grades is a list of {', '.join(SHIPS)}, not {d['ship_grades']!r}")
    return Rule(**{k: tuple(v) if isinstance(v, list) else v for k, v in d.items()})


def kind_of(rec: dict, rule: Rule = Rule()) -> str:
    """Whose decision a proof record is: owner (made in the maintainer's own tools, or on the review
    site under one of rule.owner's names), helper (anyone else on the review site), ai (the AI proof
    reviewer) or check (the ship check)."""
    if rec.get("via") == AGENT:
        return "check" if rec.get("by", "").startswith(CHECK_BY) else "ai"
    return "helper" if rec.get("via") == SITE and _name(rec) not in rule.owner else "owner"


def counts_for(rec: dict, rule: Rule, what: str) -> bool:
    """Whether a person's input of one kind (WHOSE_INPUT: marks, grid_fixes, typed_clues) counts as the owner's would:
    the owner's always, a helper's or a guest's when the rule says "people" for it, an ignored account's never. An AI
    reviewer's or the ship check's is not a person's: False here (an AI's mark has its own rule, MARKS_COUNT)."""
    k = kind_of(rec, rule)
    return _name(rec) not in rule.ignore and (k == "owner" or (k == "helper" and getattr(rule, what) == "people"))


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
             current: tuple = (), rule: Rule = Rule(), grade: str = "") -> dict:
    """Whether one puzzle ships: THE ship rule. Nothing else decides it.

    batch: the ledger's latest batch:<pid> (the owner's Ship / Hold on the batch page), or {}.
    proofs: each reviewer's latest proof:<pid> record (Ready / Not ready).
    check_ok: triage's ship check passes. codes: triage's reason codes for the puzzle.
    current: the fingerprints of the puzzle's current version. A Ready on another version doesn't count,
      and neither does an AI's Not ready on another version; a person's Not ready stands across versions.

    grade: the puzzle's grade as the records give it (grade_of), "" when not worked out. It decides nothing unless
      rule.ship_grades lists it.

    Returns {status: ship | hold, reason, why, rule: owner | people | ai | grade | "", by, said, apply}:
    - the owner's own latest decision wins (reason owner-hold when it is Hold or Not ready);
    - otherwise any Not ready that stands holds it for the owner (not-ready): a person's on any version, the
      AI reviewer's on the current one;
    - otherwise one person's Ready ships it (rule "people");
    - otherwise, with rule.ai_ready on, the AI's Ready ships it (rule "ai"), unless it carries one of PERSON_CODES
      (clue-by-sequence), which only a person's Ready ships;
    - otherwise, with the puzzle's grade in rule.ship_grades, it ships by its grade (rule "grade"), with no Ready at
      all. Never with a Not ready standing, a person's or an AI's, and not a puzzle carrying one of PERSON_CODES;
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
    lapsed = None  # the owner's Ready on an earlier version, when the rule lets it lapse (rule.owner_stale)
    if mine and mine["answer"] == "ready" and mine["stale"] and rule.owner_stale == "lapse" and mine["at"] > batch.get("at", ""):
        lapsed, mine = mine, None
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
        # an AI's Not ready that names only doubts (soft_no): it doesn't stop a puzzle shipping by its grade
        soft = [s for s in no if s["kind"] == "ai" and soft_no(s["rec"])]
        hard = [s for s in no if s not in soft]
        people = [s for s in ready if s["kind"] == "helper"]
        ai = any(s["kind"] == "ai" for s in ready)
        person = sorted(set(codes) & set(PERSON_CODES))  # needs a person's Ready, whatever ai_ready says
        # an AI's Ready never ships over another AI's Not ready, a soft one included: the two disagree (grade_of)
        ai_ok = {"off": False, "both": ai and check_ok, "ai": ai, "either": ai or check_ok}[rule.ai_ready] and not person and not soft
        # by its grade: never over a Not ready that stands (a person's, or an AI's that isn't soft: AI_NOT_READY), never a PERSON_CODE
        by_grade = bool(grade) and grade in rule.ship_grades and not person and not hard
        if hard or (soft and not by_grade):
            res = out("hold", "not-ready", "said Not ready by " + "; ".join(s["who"] + (f": {s['note']}" if s["note"] else "") for s in no))
        elif people:
            res = out("ship", "", f"Ready by {who(people)}, no Not ready", who(people), "people")
        elif ai_ok:
            by = " and ".join(x for x in ("the AI proof reviewer's Ready" if ai else "", "the ship check passes" if check_ok else "") if x)
            res = out("ship", "", f"{by} (ai_ready: {rule.ai_ready}), no Not ready", by, "ai")
        elif by_grade:
            res = out("ship", "", f"graded {grade}: ships by its grade (ship_grades), with no person's Ready, no Not ready", f"its grade ({grade})", "grade")
        elif any(s["stale"] for s in said):
            res = out("hold", "proof-stale", "; ".join(f"{s['who']}'s {'Ready' if s['answer'] == 'ready' else 'Not ready'}" for s in said if s["stale"])
                      + " was on an earlier version of the puzzle")
        else:
            has = [x for x in ("the AI proof reviewer said Ready" if ai else "", "the ship check passes" if check_ok else "") if x]
            res = out("hold", "no-ready", "no person has said Ready" + (f" ({'; '.join(has)})" if has else "")
                      + (f"; {', '.join(person)} needs a person's Ready, whatever ai_ready says" if person else ""))
    if lapsed:  # said, on whatever the rule decided
        res = {**res, "why": res["why"] + f"; {lapsed['who']}'s Ready ({lapsed['at'][:10]}) was on an earlier version of the puzzle, so it "
               "doesn't count here (owner_stale: lapse)", "lapsed": {"who": lapsed["who"], "at": lapsed["at"]}}
    held = sorted(set(codes) & set(rule.hold_codes))
    if res["status"] == "ship" and held:
        res = {**out("hold", held[0], f"carries {', '.join(held)}: held whoever said Ready"), "rule": res["rule"]}
    return res


# ---- the queues: what the batch asks of people ---------------------------------------------

QUEUES = ("question", "unchecked", "broken", "shippable", "shipped", "set-aside", "not-a-crossword")
# a held puzzle's queue, by its reason; every reason not named here is the pipeline's (broken)
QUEUE_OF = {"not-ready": "question", "owner-hold": "question", "edits-differ": "question", "candidate-undecided": "question",
            "proposal-waits": "question", "mark-disputed": "question", "fixes-disputed": "question",
            "no-ready": "unchecked", "proof-stale": "unchecked"}
# the stage a broken puzzle's reason points to, where triage recorded none (triage's blocking names its own)
STAGE_OF = {"mark-invalid": "proof review", "misprint-edit": "proof review", "packet-stale": "proof packet", "no-packet": "proof packet", "edits-unapplied": "import", "xd-exists": "import",
            "clue-typed": "text step", "clue-typed-block": "parts", "awaits-replace": "assembly", "pair-unread": "proof review"}
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
# clue-by-sequence: a clue placed by the list's sequence on a linked-ends puzzle (xword-ocr linkedends). On a person's
# Ready it ships only once every clue line carries its printed pair: a line still labelled by its slot (A4) holds the
# puzzle as pair-unread, whoever said Ready (unread_pairs; the owner's rule, 2026-11-16).
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
    """The latest Not ready on a linked-ends puzzle, by a person whose grid fixes count (Rule.grid_fixes: any person's by
    default since 2026-11-13, or the owner's only; xword-ocr's stage reads the same people's), whose fixes to the grid
    wait to be read in: it
    carries grid:, num: or cell: edits (the import applies only a Ready's edits; the stage that places the clues
    reads these from the ledger), and the packet doesn't record that it was made from that decision (ocr.json's
    reviewer_fixes.decisions: who and when, as the stage wrote them). {who, at, note, shape, numbers, letters,
    read_in} (how many of each; read_in: the packet records that decision, so the fixes are in it), or None when
    their latest Not ready carries no such fix: nothing here is worked out from the edits but their count."""
    if not linked(xd):
        return None
    used = {(d.get("by"), d.get("at")) for d in (ocr.get("reviewer_fixes") or {}).get("decisions") or []}
    for r in sorted(proofs, key=lambda r: r.get("at", ""), reverse=True):
        if r.get("answer") != "notready" or not counts_for(r, rule, "grid_fixes"):
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


def typed_text(v) -> bool:
    """A clue's text as a person typed it on the proof page where the packet had none: one line, not empty, and not
    the text step's own "[missing]" mark."""
    return isinstance(v, str) and bool(v.strip()) and not CONTROL.search(v) and "[missing]" not in v


def filled_by(ship: dict, edits: dict, typed: dict | None = None) -> list[str]:
    """The ship check's incompleteness that the edits about to be applied make whole (its lines of
    ship.incomplete). Called only when a person's decision ships the puzzle (an AI's Ready never makes it whole):

    - an unsolved grid (grid-unsolved, which names its squares) when every one of those squares has its letter
      among `edits`, the edits that ship (a key square the packet left unread, read by a reviewer: a reading fix);
    - clues with no text (clue-empty, which names its clues in `items`) when every one of them has its text in
      `typed`: the own edits of the people whose typed clue counts (Rule.typed_clues), never an AI's (none is
      passed in, whoever's Ready ships the puzzle). Nothing was read for such a
      clue, so it ships typed by a person (class "typed", and the xd's TYPED_HEAD block), never as a reading fix.

    Nothing else: a missing clue (no line for it in the xd), an extra one, a second set isn't made whole by an edit."""
    out = []
    for f in ship.get("findings") or []:
        if not isinstance(f, dict) or f.get("detail") not in (ship.get("incomplete") or []):
            continue
        if (f.get("code") == "grid-unsolved" and f.get("cells")
                and all(isinstance(edits.get(f"cell:{c}"), str) and len(edits[f"cell:{c}"]) == 1 and edits[f"cell:{c}"].isalpha() for c in f["cells"])):
            out.append(f["detail"])
        elif (f.get("code") == "clue-empty" and f.get("items") and typed is not None
              and all(isinstance(c, str) and typed_text(typed.get(f"clue:{c}")) for c in f["items"])):
            out.append(f["detail"])
    return out


def review_of(st: dict, pk: dict) -> str:
    """How a puzzle that passes was reviewed, in words, for its provenance row and its ship record: whose Ready shipped
    it (the owner's, a helper's, or an AI's alone with no person's review), and, for a puzzle read by hand, that it was
    (with the AI's own note, which says what it rests on: "read twice, blind"). So a kind of review can be found again
    if an error turns up in one puzzle it shipped."""
    how = {"owner": "the owner's Ready", "people": "a person's Ready", "ai": "an AI's Ready; no person's review",
           "grade": "shipped by its grade; no person's review"}.get(st.get("rule"), "")
    ai = [r for r in st.get("apply") or [] if r.get("via") == AGENT and not r.get("by", "").startswith(CHECK_BY)]
    notes = sorted({(r.get("note") or "").strip() for r in ai} - {""}) if st.get("rule") == "ai" else []
    read = "read by hand" if (pk.get("review") or {}).get("hand_read") else ""
    lapsed = (f"{st['lapsed']['who']}'s earlier Ready ({st['lapsed']['at'][:10]}) was on an older version of the puzzle, and the "
              + ("AI's" if st.get("rule") == "ai" else "current") + " Ready decided") if st.get("lapsed") else ""
    return "; ".join(x for x in (read, *notes, how, f"by {st['by']}" if st.get("by") else "", lapsed) if x)


def partial_of(apply: list[dict], rule: "Rule", gaps: list[str]) -> dict | None:
    """A person's "Ready to ship as it stands" that waives every gap the ship check left (gaps: its incomplete lines
    nothing else made whole), or None. The owner's rule (2026-11-23): an incomplete puzzle ships only on a human
    review, so only a person's Ready counts (the owner's or a helper's, never an AI's, never an ignored account's),
    and only the gaps it names: its review's partial {missing: the ship check's lines it was shown, note: why we stop
    here}. A gap it doesn't name (another one found since, or the puzzle changed) still holds the puzzle.
    Returns {missing, note, by, kind, at} of the first such Ready."""
    if not gaps:
        return None
    for r in apply:
        p = ((r.get("proof") or {}).get("review") or {}).get("partial")
        if (kind_of(r, rule) in ("owner", "helper") and _name(r) not in rule.ignore and isinstance(p, dict)
                and isinstance(p.get("missing"), list) and set(gaps) <= set(p["missing"])):
            return {"missing": list(gaps), "note": str(p.get("note") or "").strip()[:500], "by": r.get("by", ""),
                    "kind": kind_of(r, rule), "at": r.get("at", "")}
    return None


def typed_clues(ship: dict, filled: list[str]) -> list[str]:
    """The clues (clue:D1) a person's typed text makes whole: the items of each clue-empty finding filled_by() filled."""
    return [f"clue:{c}" for f in ship.get("findings") or [] if isinstance(f, dict) and f.get("code") == "clue-empty"
            and f.get("detail") in filled for c in f.get("items") or []]


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
        q = QUEUES.index(r["queue"]) if r["queue"] in QUEUES else len(QUEUES)  # deferred by the scope rule: last
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


# ---- grades: how far to trust each puzzle that leaves the run ---------------------------------
# design/v3-agent-forward.md, "Every puzzle exits with a grade". Worked out here, by ship, from what the earlier
# milestones recorded and nothing else: triage's reasons, blocking parts and ship check (triage.json), the reviewers'
# records in the ledger, the packet's candidate lists. Never from the scan. formats/ship-record.md has the fields.
#
#   clean            the ship check passed and nothing was flagged
#   reviewed         flags were raised, and a review settled them: an AI proof reviewer's Ready on this version of
#                    the puzzle, or a person's
#   doubts           flags stay open: an AI reviewer's own questions (its Not ready), or what the checks flagged and
#                    no review has looked at; each is listed with its row on the proof page
#   incomplete       a part was never found or never read (triage's blocking parts of kind GAP_KINDS, the ship check's
#                    incompleteness, triage's gap reasons); the gaps are named
#   held             the structure does not hold (a blocking part of another kind: text linked from another puzzle, a
#                    packet that doesn't show its xd), or a protection of the ship rule holds it whatever its grade (a
#                    person's Not ready, the owner's hold, an edit that can't be applied or has no record); a diagnosis
#                    names the stage
#   deferred         set aside (setaside:<pid>), or out of the publication's scope for now
#   not-a-crossword  dropped (drop:<pid>)
#
# A grade says how far to trust a puzzle; whether it ships is the ship rule's (standing: Rule.ship_grades, off by
# default). `held` is exactly the puzzles that would not ship with every grade of SHIPS on (plan works that out by
# applying the rule that way once more), so a grade never promises what the rule would refuse.
GAP_KINDS = ("missing-part", "ocr-broken")  # triage's blocking kinds (xword-ocr problems.py) that are gaps, not structure
GAP_ROW = {"key": "grid", "title": "ev:title"}  # a blocking part's id as the proof page's row; others have none recorded
SAMPLE_OF = ("clean", "reviewed", "doubts")  # the owner reads a sample of what shipped at each of these (2026-11-25)
SAMPLE_N = 10
AI_QUESTION = "ai-question"  # the code of a doubt that is an AI proof reviewer's own question
# An AI proof reviewer's Not ready holds the puzzle whatever its grade: graded held, with the reviewer's words as the
# diagnosis. Its record (the ledger's proof:<pid>: comments keyed by proof-page row, a status per part, a note) can't
# tell a structural problem from a reading doubt: on GAMES 1980-82 the key `grid` carries both "this grid is another
# puzzle's key" and "r5c3 is O in the printed key", and no review carries a send-back or a kind. So none ships until
# a second opinion exists (design/v3-agent-forward.md, slice 5). To let reading doubts ship, the reviewer would have
# to record, per flag, what kind it is (structure: a part linked from another puzzle, a part missing; or reading: a
# letter or a word), or use the review's send-back {kind, part} for what is the pipeline's.
AI_NOT_READY = "ai-not-ready"
# The kind of an AI reviewer's flag (v3 slice 5; xword-ocr proofreview.FLAG_KINDS, kept on the flag's comment as `kind`,
# formats/proof-packet.md): structure holds the puzzle (AI_STRUCTURE), missing is a gap (AI_MISSING: incomplete), every
# other kind is a doubt the puzzle ships with. A puzzle with any AI flag of no kind is read as before: AI_NOT_READY.
FLAG_KINDS = ("structure", "missing", "grid-reading", "clue-reading", "header", "misprint", "convention", "extra")
DOUBT_KINDS = FLAG_KINDS[2:]
AI_STRUCTURE, AI_MISSING = "ai-structure", "ai-missing"
FLAG_PREFIX = "Flag for the maintainer:"
PAGE_ROW = re.compile(r"clue:[AD]\d+(\^[\w-]+)?|line:B\d+|cell:r\d+c\d+|(ev|meta):\w+|candidate:\S+|grid|notes|")  # formats.ROW_KEY


def ai_flags(rec: dict) -> list[dict]:
    """An AI reviewer's flags, from its record's comments (xword-ocr proofreview.record): [{row, text, suggest?, kind}],
    kind "" when none was recorded."""
    out = []
    for c in ((rec.get("proof") or {}).get("review") or {}).get("comments") or []:
        if isinstance(c, dict) and str(c.get("text") or "").startswith(FLAG_PREFIX):
            row = re.sub(r"^grid:(r\d+c\d+)$", r"cell:\1", c.get("key") or "")
            row = row if PAGE_ROW.fullmatch(row) else ""  # a key the page has no row for (clue:key): no row
            out.append({"row": row, **_ask(c["text"]), "kind": c.get("kind") if c.get("kind") in FLAG_KINDS else ""})
    return out


def soft_no(rec: dict) -> bool:
    """An AI reviewer's Not ready that names only doubts and gaps: at least one flag, every flag with a kind, none
    `structure`. It doesn't stop a puzzle shipping by its grade (standing)."""
    fl = ai_flags(rec)
    return bool(fl) and all(f["kind"] for f in fl) and not any(f["kind"] == "structure" for f in fl)


def second_opinion(rec: dict) -> dict | None:
    """A second opinion's account of what it is one of (xword-ocr proofreview.record_second): {of, of_at, of_answer,
    of_flags, settles}, or None for a first review."""
    so = ((rec.get("proof") or {}).get("review") or {}).get("second_opinion")
    return so if isinstance(so, dict) and so.get("of") else None


def ai_rounds(stands: list[dict]) -> list[dict]:
    """The AI reviews that stand, each first review with its second opinion: [{first, second}], each a standing() `said`
    entry (with its `rec`) or None. A second is paired with the first it names (its reviewer, and that record's time
    when it gives one); a second whose first no longer stands is a round of its own."""
    ai = [s for s in stands if s["kind"] == "ai"]
    rounds = [{"first": f, "second": None} for f in ai if not second_opinion(f.get("rec") or {})]
    for s in [s for s in ai if second_opinion(s.get("rec") or {})]:
        so = second_opinion(s["rec"])
        mate = next((r for r in rounds if r["second"] is None and r["first"]["who"] == so["of"]
                     and (not so.get("of_at") or r["first"]["at"] == so["of_at"])), None)
        if mate:
            mate["second"] = s
        else:
            rounds.append({"first": s, "second": None})
    return rounds


def ai_verdict(stands: list[dict]) -> dict:
    """What the AI reviews that stand say, for grade_of (formats/proof-packet.md, "The second opinion"):
    {structure, missing, doubts: [flag], unkinded: bool, settled_by: [said] | None}. Each flag {row, text, suggest?,
    kind, who, second?}; second, on a first review's flag that has a second opinion: "also" (the second flagged the
    same row) or "nothing" (it didn't: it said Ready, or flagged other rows). A first's flag the second's Ready edits
    settle the same way (its `settles`) is not listed. settled_by: the reviews that settle everything (an AI's Ready;
    or a first's Not ready with a second opinion's Ready that settles every one of its flags), None when any flag
    stays."""
    out = {"structure": [], "missing": [], "doubts": [], "unkinded": False, "settled_by": None}
    readies = []
    for r in ai_rounds(stands):
        f, sec = r["first"], r["second"]
        if sec is None:
            if f["answer"] == "ready":
                readies.append([f])
                continue
            flags = [{**x, "who": f["who"]} for x in ai_flags(f["rec"])]
            if not flags:
                flags = [{"row": "", "text": f.get("note") or "said Not ready, with no note", "kind": "", "who": f["who"]}]
        else:
            so = second_opinion(sec["rec"])
            settled = {x.get("key") for x in so.get("settles") or [] if isinstance(x, dict)} if sec["answer"] == "ready" else set()
            rows2 = {x["row"] for x in ai_flags(sec["rec"])} if sec["answer"] == "notready" else set()
            first_flags = ai_flags(f["rec"]) if f["answer"] == "notready" else []
            flags = [{**x, "who": f["who"], "second": "also" if x["row"] in rows2 else "nothing"}
                     for x in first_flags if x["row"] not in settled]
            if sec["answer"] == "notready":
                flags += [{**x, "who": sec["who"]} for x in ai_flags(sec["rec"])]
            if sec["answer"] == "ready" and not flags:
                readies.append([f, sec] if f["answer"] == "notready" else [sec])
                continue
        for x in flags:
            if not x["kind"]:
                out["unkinded"] = True
                out["doubts"].append(x)
            else:
                out["structure" if x["kind"] == "structure" else "missing" if x["kind"] == "missing" else "doubts"].append(x)
    if not (out["structure"] or out["missing"] or out["doubts"]) and readies:
        out["settled_by"] = readies[-1]
    return out
# ---- what an incomplete puzzle lacks, by kind (the row's `lacks`, each gap's `sub`): the first that applies, in this order
LACKS = ("no-key", "page-not-found", "clues-missing", "unsolved-squares", "part-missing")
LACKS_MEANS = {"no-key": "no answer key: none printed (a cryptic's answers as text, a contest), or none found",
               "page-not-found": "a page the puzzle runs onto was asked for and never found",
               "clues-missing": "clues or a clue list missing, empty or unread",
               "unsolved-squares": "squares of the answer grid unread or unsolved",
               "part-missing": "another part the text step found missing"}
LACK_OF = {"key-missing": "no-key", "cryptic-no-key": "no-key", "request-page": "page-not-found",
           "clue-empty": "clues-missing", "clue-missing": "clues-missing", "clue-extra": "clues-missing", "clues-unread": "clues-missing",
           "request-list": "clues-missing", "list-missing-A": "clues-missing", "list-missing-D": "clues-missing",
           "second-set-missing": "clues-missing", "second-clue-set": "clues-missing",
           "grid-unsolved": "unsolved-squares", "key-unread": "unsolved-squares"}
HEADER_TYPED = "header-typed"  # triage: a header's value typed by the text step, with no printed line that gives it


def lack_of(gap: dict) -> str:
    """The kind of a gap, one of LACKS: by its code; a part confirmed not printed by the part the record names (the
    key: no-key); anything else is part-missing."""
    if gap.get("code") == "not-printed":
        return "no-key" if gap.get("part") == "key" else "part-missing"
    return LACK_OF.get(gap.get("code", ""), "part-missing")
# what the codes that aren't triage's mean, for the digest's ranking of failures (triage's own come from its record's groups)
MEANS = {AI_QUESTION: "the AI proof reviewer's own question, left open", "candidate-undecided": "a candidate clue list nobody has decided",
         "grid-unsolved": "squares of the answer grid unread or unsolved (the ship check)", "clue-empty": "clues with no text (the ship check)",
         "clue-missing": "a slot with no clue line (the ship check)", "clue-extra": "a clue line with no slot (the ship check)",
         "second-set-missing": "a second clue set that doesn't cover every clue (the ship check)",
         "notes-other-list": "another list's lines in the notes (the ship check)", "clue-hygiene": "a clue's text looks damaged (the ship check)",
         "no-title": "no Title header (the ship check)", "no-author": "no Author or Byline header (the ship check)",
         "not-ready": "a person said Not ready", AI_NOT_READY: "an AI reviewer said Not ready with a flag of no kind: held, as nothing tells a structural problem from a reading doubt",
         HEADER_TYPED: "a header's value typed by the text step: no printed line gives it",
         AI_STRUCTURE: "an AI reviewer says the puzzle is put together wrong (another puzzle's grid or key, clues for another grid)",
         AI_MISSING: "an AI reviewer says a part is missing or was never read", "owner-hold": "held by the owner", "sent-back": "a reviewer sent it back to the pipeline",
         "no-ready": "needs a person's Ready, whatever its grade", "proof-stale": "the owner's Ready was on an earlier version: look again"}


ITEM_ROW = {"title": "ev:title", "byline": "ev:byline", "key": "grid", "grid": "grid"}  # the text step's own words for an item


def _row_key(k) -> str:
    """A triage item's label as the proof page keys its rows: A12 -> clue:A12, L3 -> line:B3, title -> ev:title; a key
    of the page's own stays; any other word the text step used ("structure", "missing") names no row: ""."""
    k = str(k)
    if re.fullmatch(r"L\d+", k):
        return f"line:B{k[1:]}"
    if re.fullmatch(r"[AD]\d+(\^[\w-]+)?", k):
        return f"clue:{k}"
    return k if re.fullmatch(r"(clue|line|cell|ev|meta|candidate):\S+|grid|notes", k) else ITEM_ROW.get(k, "")


def flags_of(t: dict, candidates: list | tuple = ()) -> list[dict]:
    """What the checks flagged on one puzzle for a reviewer to settle, from triage's record of it (its reasons of class
    defect and severity proof, and the ship check's findings that aren't incompleteness), and the packet's candidate
    clue lists nobody has decided. [{row, rows?, text, code, from}]: row is the proof page's key (?k=<row>), "" when
    the record names none; rows every row a reason names, when more than one. The mapping is xword-ocr
    proofreview.items_for's, which gives the AI reviewer the same items."""
    out = []

    def add(row, text, code, src, rows=()):
        if not any(d["row"] == row and d["code"] == code and d["text"] == text for d in out):
            out.append({"row": row, **({"rows": list(rows)} if len(rows) > 1 else {}), "text": str(text)[:300], "code": code, "from": src})

    ship = t.get("ship") or {}
    reasons = [r for r in t.get("reasons") or [] if isinstance(r, dict)]
    have = {r.get("code") for r in reasons}
    for fd in ship.get("findings") or []:
        if not isinstance(fd, dict):
            continue
        code, detail = fd.get("code", ""), str(fd.get("detail", ""))
        if code in INCOMPLETE_STAGE or code == "triage-doubt" or detail in (ship.get("incomplete") or []):
            continue  # a gap (gaps_of), or the check's echo of triage's own reasons, read below
        if code == "clue-hygiene":
            for piece in detail.split("; "):
                m = re.search(r"\b([AD]\d+(?:\^\w+)?)\b", piece)
                add(f"clue:{m[1]}" if m else "", piece, code, "ship check")
        elif code in ("no-title", "no-author"):
            if ("title-none" if code == "no-title" else "byline-none") not in have:  # triage asks the same of the reviewer
                add("ev:title" if code == "no-title" else "ev:byline", detail, code, "ship check")
        else:
            add("meta:note", detail, code, "ship check")
    for r in reasons:
        if r.get("code") == HEADER_TYPED:  # the value is in the xd, and no printed line gives it: a doubt about that one value
            field = str(r.get("field") or str(r.get("detail", "")).partition(":")[0]).strip()
            add(f"ev:{field}" if re.fullmatch(r"\w+", field) else "", f"typed by the text step, with no printed line that gives it: {r.get('detail', '')}",
                HEADER_TYPED, "triage")
            continue
        if r.get("class") != "defect" or r.get("severity") != "proof":
            continue
        code, detail = r.get("code", ""), re.sub(r"^\d+: ", "", str(r.get("detail", "")))  # without triage's count of the items
        keys = r.get("items") or r.get("labels") or []
        keys = [_row_key(k) for k in (list(keys) if isinstance(keys, (list, dict)) else [])]
        if code.startswith("key-") or code == "gxd-key-near-miss":
            add("grid", detail or code, code, "triage")
        elif code in ("title-none", "byline-none"):
            add("ev:title" if code == "title-none" else "ev:byline", detail or code.replace("-none", ": none found"), code, "triage")
        elif keys:
            named = list(dict.fromkeys(k for k in keys if k))
            add(named[0] if named else "", detail or code, code, "triage", named)
        else:
            m = re.search(r"\b([AD]\d+(?:\^\w+)?)\b", detail)
            add(f"clue:{m[1]}" if m else "", detail or code, code, "triage")
    for c in candidates:
        add(f"candidate:{c['id']}", f"another {'Across' if c.get('dir') == 'A' else 'Down'} list fits this grid ({c.get('clues', 0)} of "
            f"{c.get('slots', 0)} slots) and nobody has decided what it is", "candidate-undecided", "assembly")
    return out


def gaps_of(t: dict, means: dict | None = None, filled: list | tuple = (), blocking: bool = True) -> list[dict]:
    """What one puzzle lacks, as recorded: the ship check's incompleteness that no edit fills (filled: filled_by's
    lines), triage's blocking parts that are gaps (GAP_KINDS; left out with blocking=False, for a puzzle a person's
    Ready ships: their word settles what triage asked of the pipeline), and triage's reasons of class gap (a cryptic
    with no key grid, a second clue set not captured, a part confirmed not printed). [{what, code, stage, detail, row}]."""
    out, means = [], means or {}

    def add(what, code, stage="", detail="", row="", part=""):
        if not any(g["code"] == code and g["detail"] == detail and g["what"] == what for g in out):
            g = {"what": str(what), "code": code, "stage": stage, "detail": str(detail)[:300], "row": row}
            out.append({**g, "sub": lack_of({**g, "part": part})})

    ship = t.get("ship") or {}
    named = set()
    for fd in ship.get("findings") or []:
        if isinstance(fd, dict) and fd.get("detail") in (ship.get("incomplete") or []):
            named.add(fd["detail"])
            if fd["detail"] not in filled:
                items = [c for c in fd.get("items") or [] if isinstance(c, str)]
                add(fd["detail"], fd.get("code", ""), INCOMPLETE_STAGE.get(fd.get("code", ""), ""), "",
                    "grid" if fd.get("code") == "grid-unsolved" else f"clue:{items[0]}" if items else "")
    for x in ship.get("incomplete") or []:
        if x not in named and x not in filled:
            add(x, "incomplete")
    for b in (t.get("blocking") or []) if blocking else []:
        if isinstance(b, dict) and b.get("kind") in GAP_KINDS and b.get("code") != HEADER_TYPED:  # a typed header: a doubt (flags_of)
            detail = "" if b.get("detail") == "from the verdict" else b.get("detail") or ""
            add(b.get("part") or b.get("code") or "", b.get("code") or "", b.get("restart") or "", detail, GAP_ROW.get(b.get("part_id") or "", ""))
    for r in t.get("reasons") or []:
        if isinstance(r, dict) and r.get("class") == "gap":
            detail = "" if r.get("detail") == "from the verdict" else r.get("detail") or ""
            add(means.get(r.get("code", "")) or r.get("code", ""), r.get("code", ""), "", detail, part=str(r.get("part") or ""))
    return out


def grade_of(t: dict, st: dict, proofs: list[dict], rule: Rule, current: tuple = (), means: dict | None = None,
             candidates: list | tuple = (), filled: list | tuple = ()) -> dict:
    """One puzzle's grade from the records (the table above), before the rule's own holds are known (plan sets `held`
    for those). t: triage's record of the puzzle; st: standing()'s answer with no grade given (who said what, and
    whether a person's word ships it); proofs: each reviewer's latest record; candidates: its undecided candidate lists.
    Returns {grade, grade_why, flags (how many the checks raised), settled ({by, kind, at} of the review that settled
    them, or None), doubts (the open ones: [{row, text, code, from}]), gaps, diagnosis ({stage, what, code, detail}, a
    held puzzle's, or None)}."""
    dec = t.get("decision", "")
    base = {"flags": 0, "settled": None, "doubts": [], "gaps": [], "lacks": [], "diagnosis": None}
    if dec in ("not a crossword", "set aside"):
        return {**base, "grade": "not-a-crossword" if dec == "not a crossword" else "deferred", "grade_why": f"triage: {dec}"}
    person_ships = st.get("status") == "ship" and st.get("rule") in ("owner", "people")
    flags = flags_of(t, candidates)
    gaps = gaps_of(t, means, filled, blocking=not person_ships)
    stands = [s for s in st.get("said") or [] if not s.get("stale")]
    recs = {(r.get("by", ""), r.get("at", "")): r for r in proofs}  # standing()'s said leaves the records out
    stands = [s if "rec" in s else {**s, "rec": recs.get((s["who"], s["at"]), {})} for s in stands]
    ai_no = [s for s in stands if s["answer"] == "notready" and s["kind"] == "ai"]
    ai = ai_verdict(stands)
    kinded = bool(ai_no) and not ai["unkinded"]  # every AI flag has a kind: the kinds decide (v3 slice 5)
    # a review that settles what was flagged: a person's Ready that ships it, else the AI reviews' (an AI's Ready with no
    # AI Not ready standing; or a first review's Not ready whose every flag its second opinion's Ready settles). The ship
    # check's own Ready looks at nothing a flag names, so it settles none
    people = [s for s in stands if s["answer"] == "ready" and s["kind"] in ("owner", "helper")] if person_ships else []
    by = people[-1:] or (ai["settled_by"] if not ai_no or kinded else None) or []
    settled = {"by": " and ".join(s["who"] for s in by), "kind": by[-1]["kind"], "at": max(s["at"] for s in by)[:10]} if by else None
    if settled and not people:
        ai_no = []  # every AI flag is settled: by a Ready, or by a second opinion that made the same fix
    # what an AI's Ready can't settle: a candidate list (a person decides it) and a typed header (no crop shows it)
    person_only = ("candidate-undecided", HEADER_TYPED)
    undecided = [d for d in flags if d["code"] in person_only and not (settled and settled["kind"] in ("owner", "helper") and d["code"] == HEADER_TYPED)]
    if settled:
        doubts = undecided
    elif kinded:  # the AI reviewers looked at what was flagged: their doubts are what stays open, each with its kind
        doubts = [d for d in flags if d["code"] in person_only] + [
            {"row": a["row"], "text": a["text"] + (f" Suggest: {a['suggest']}" if a.get("suggest") else ""), "code": AI_QUESTION,
             "from": a["who"], "kind": a["kind"], **({"second": a["second"]} if a.get("second") else {})} for a in ai["doubts"]]
    elif ai_no:  # the AI reviewer looked at what was flagged: its own questions are what stays open
        doubts = [d for d in flags if d["code"] in person_only] + [{"row": a["row"], "text": a["text"] + (f" Suggest: {a['suggest']}" if a.get("suggest") else ""), "code": AI_QUESTION,
                               "from": a["who"]} for a in asks_of("not-ready", "", {}, proofs, rule, current) if a["kind"] == "ai"]
    else:
        doubts = flags
    ok = bool((t.get("ship") or {}).get("ok"))
    structure = [] if person_ships else [b for b in t.get("blocking") or [] if isinstance(b, dict) and b.get("kind") not in GAP_KINDS]
    if not (flags or gaps or ok or settled or doubts or structure):  # the check held it for something read here as neither a flag nor a gap: said, not dropped
        doubts = [{"row": "", "text": str(fd.get("detail", "")) if isinstance(fd, dict) else str(fd), "code": fd.get("code", "") if isinstance(fd, dict) else "",
                   "from": "ship check"} for fd in (t.get("ship") or {}).get("findings") or []] or [
                  {"row": "", "text": "the ship check did not pass, and records no finding", "code": "ship-check", "from": "ship check"}]
    if kinded and not person_ships:  # a part an AI reviewer says is missing: a gap, in the reviewer's words
        for a in ai["missing"]:
            g = {"what": a["text"][:300], "code": AI_MISSING, "stage": "", "detail": a["who"]
                 + (f"; suggest: {a['suggest']}" if a.get("suggest") else "")[:300], "row": a["row"]}
            gaps.append({**g, "sub": lack_of(g)})
    lacks = [k for k in LACKS if any(g["sub"] == k for g in gaps)]  # what it lacks, by kind; the first is the one it is counted under
    out = {**base, "flags": len(flags), "settled": settled, "doubts": doubts, "gaps": gaps, "lacks": lacks}
    if kinded and ai["structure"] and not person_ships:  # an AI reviewer says the puzzle is put together wrong
        a = ai["structure"][0]
        dg = {"stage": "assembly", "what": a["text"][:300], "code": AI_STRUCTURE, "detail": a["who"]}
        return {**out, "grade": "held", "diagnosis": dg, "grade_why": f"an AI reviewer says the structure does not hold: {a['text'][:160]}"}
    if structure:
        b = structure[0]
        dg = {"stage": b.get("restart") or "", "what": b.get("part") or b.get("code") or "", "code": b.get("code") or "",
              "detail": "" if b.get("detail") == "from the verdict" else str(b.get("detail") or "")[:300]}
        return {**out, "grade": "held", "diagnosis": dg, "grade_why": f"the structure does not hold: {dg['what']}"
                + (f" (restart from {dg['stage']})" if dg["stage"] else "")}
    if gaps:
        return {**out, "grade": "incomplete", "grade_why": "not whole: " + "; ".join(g["what"] for g in gaps[:4]) + (f" (+{len(gaps) - 4})" if len(gaps) > 4 else "")}
    if doubts:
        return {**out, "grade": "doubts", "grade_why": f"{len(doubts)} open doubt(s): " + (
            "what only a person settles (a candidate clue list, a header typed with no printed line)" if settled
            else ("the AI reviewers' doubts, after a second opinion" if any(a.get("second") for a in ai["doubts"]) else "the AI reviewer's doubts")
            if kinded else "the AI reviewer's questions" if ai_no else "flagged by the checks, and no review has settled them")}
    if flags:
        return {**out, "grade": "reviewed", "grade_why": f"{len(flags)} flag(s) raised by the checks, settled by {settled['by']} ({settled['at']})"}
    return {**out, "grade": "clean", "grade_why": "the ship check passed and nothing was flagged" if ok else f"nothing was flagged; Ready by {settled['by']}"}


def held_grade(row: dict, would: dict) -> None:
    """A puzzle the rule would hold with every grade of SHIPS on (would: its row from that plan) is graded held, set
    on the row: the diagnosis names the hold and the stage it points to (a person's word: the proof page)."""
    if row.get("grade") in SHIPS and would.get("status") == "held":
        reason = would.get("reason", "")
        no = [s for s in would.get("said") or [] if s.get("answer") == "notready" and not s.get("stale")]
        if reason == "not-ready" and no and all(s.get("kind") == "ai" for s in no):  # an AI's alone: AI_NOT_READY
            reason = AI_NOT_READY
        stage = ((would.get("broken") or [{}])[0].get("stage") or STAGE_OF.get(reason, "")
                 or ("proof review" if reason in QUEUE_OF or reason in ("sent-back", "not-ready", "owner-hold", AI_NOT_READY) else ""))
        row.update(diagnosis={"stage": stage, "what": would.get("why", ""), "code": reason, "detail": ""},
                   grade_why=f"held whatever its grade (otherwise {row['grade']}): {would.get('why', '')}", grade="held")


def digest(rows: list[dict], batch: str, means: dict | None = None) -> dict:
    """The batch digest's own facts, set on the rows and returned for the record (the page draws them and works none
    out): grade_order (each row's place: by grade, then id), to_read (a row in the owner's reading sample),
    {sample: {per_grade, of, from, by, pool: {grade: n}, picked: {grade: [pid]}}, walk: the pids of what ships, in
    order (the ship step-through), failures: the kinds of failure ranked by puzzles [{code, kind: held | gap | doubt,
    stage, means, puzzles, pids}]}.

    The sample: up to SAMPLE_N puzzles that ship (shipped, or ready to ship) from each grade of SAMPLE_OF, the ones
    with the smallest sha1 of "<batch>:<pid>": random with respect to the puzzles, and the same each time the record
    is made, so the owner's reading list doesn't move under them."""
    means = {**MEANS, **{k: v for k, v in (means or {}).items() if v}}
    for i, r in enumerate(sorted(rows, key=lambda r: (GRADES.index(r["grade"]) if r.get("grade") in GRADES else len(GRADES), r["pid"]))):
        r["grade_order"] = i
        r.pop("to_read", None)
    ships = sorted((r for r in rows if r["status"] in ("shipped", "shippable")), key=lambda r: r["grade_order"])
    picked, pool = {}, {}
    for g in SAMPLE_OF:
        of = [r for r in ships if r.get("grade") == g]
        pool[g] = len(of)
        mine = sorted(of, key=lambda r: hashlib.sha1(f"{batch}:{r['pid']}".encode("utf-8")).hexdigest())[:SAMPLE_N]
        for r in mine:
            r["to_read"] = True
        picked[g] = sorted(r["pid"] for r in mine)
    kinds = {}
    for r in rows:
        mine = set()
        if r.get("grade") == "held" and r.get("diagnosis"):
            mine.add(("held", r["diagnosis"]["code"], r["diagnosis"]["stage"]))
        mine |= {("gap", g["code"], g["stage"]) for g in r.get("gaps") or []}
        mine |= {("doubt", d["code"], "") for d in r.get("doubts") or []}
        for k in mine:
            kinds.setdefault(k, []).append(r["pid"])
    order = ("held", "gap", "doubt")
    failures = [{"code": code, "kind": kind, "stage": stage, "means": means.get(code, ""), "puzzles": len(pids), "pids": sorted(pids)}
                for (kind, code, stage), pids in sorted(kinds.items(), key=lambda kv: (-len(kv[1]), order.index(kv[0][0]), kv[0][1], kv[0][2]))]
    return {"sample": {"per_grade": SAMPLE_N, "of": list(SAMPLE_OF), "from": "the puzzles that ship (shipped, or ready to ship)",
                       "by": "the smallest sha1 of \"<batch>:<pid>\" in each grade: random with respect to the puzzles, the same each time",
                       "pool": pool, "picked": picked},
            "walk": [r["pid"] for r in ships], "failures": failures}


# ---- scope: the kinds a publication imports now, and the ones it defers -----------------------
# design/v3-agent-forward.md, "Scope: kinds that are not a priority". The publication states its scope once, in its
# repo: fixes/scope.json, {"crossword": "import", "cryptic": "defer", "variety": "defer"}, with "batches": {"<batch>":
# {...}} for one batch's own values, as ship-rule.json has. A puzzle whose kind the rule defers leaves the batch as a
# stub (id, issue, page, kind; its thumbnail is the batch snapshot's) graded `deferred`, listed on the batch page as
# "known, not transcribed", and never counts as broken.
#
# A puzzle's kind is read from what a milestone recorded, never worked out here (ship is not a classifier). Today
# only triage records one, and only for some cryptics: KIND_CODES. Nothing records `variety`, and nothing records
# `crossword` either (it is what a puzzle with no recorded kind is taken to be), so a rule's `variety` entry defers
# nothing until a milestone records that kind. A puzzle already shipped is never deferred by a rule written later.
KINDS = ("crossword", "cryptic", "variety")
SCOPE_ANSWERS = ("import", "defer")
KIND_CODES = {"cryptic-no-key": "cryptic", "cryptic-unflagged": "cryptic"}  # triage's reason codes that record a kind


def scope_of(repo: Path, batch: str = "", path: Path | None = None) -> dict:
    """The publication's scope rule, {kind: import | defer}: fixes/scope.json (or `path`, to try one), then its
    "batches" entry for this batch. {} when it has none: every kind is imported, as before the rule existed."""
    f = Path(path) if path else Path(repo) / "fixes" / "scope.json"
    d = {k: v for k, v in (json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}).items() if not k.startswith("_")}
    d.update({k: v for k, v in ((d.pop("batches", None) or {}).get(batch) or {}).items() if not k.startswith("_")})
    for k, v in d.items():
        if k not in KINDS or v not in SCOPE_ANSWERS:
            raise Stop(f"{f}: {k!r}: {v!r} is not one of {', '.join(KINDS)}: {' | '.join(SCOPE_ANSWERS)}")
    return d


def recorded_kind(t: dict) -> tuple[str, str]:
    """(a puzzle's kind, what recorded it) from triage's record of it: ("cryptic", "triage: cryptic-no-key"), or
    ("", "") when no milestone recorded a kind for it."""
    for r in t.get("reasons") or []:
        if isinstance(r, dict) and r.get("code") in KIND_CODES:
            return KIND_CODES[r["code"]], f"triage: {r['code']}"
    return "", ""


def stub_of(pid: str, date: str, place: tuple, kind: str, kind_from: str, why: str) -> dict:
    """A deferred puzzle's stub: what is known of a puzzle nobody transcribes for now. {pid, issue, scan, leaf, size,
    kind ("" when no milestone recorded one), kind_from, why}."""
    return {"pid": pid, "issue": date or (re.search(r"\d{4}-\d\d-\d\d", pid) or [""])[0], "scan": place[0], "leaf": place[1], "size": place[2],
            "kind": kind, "kind_from": kind_from, "why": why}


# ---- reading the milestones ----------------------------------------------------------------

def _load(path: Path, default=None):
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else default


def ledger(repo: Path) -> list[dict]:
    f = Path(repo) / "fixes" / "decisions.jsonl"
    return [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()] if f.exists() else []


def from_site(decisions: dict, have: list[dict], pids: set, batches=frozenset()) -> list[dict]:
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
                      **({"partial": p["partial"]} if p.get("partial") else {}),  # ready to ship as it stands
                      # what the reviewer marked as printed wrong (the proof page's control): a clue's or a header's
                      # misprint, a misprinted key letter; the shape the AI reviewer's review has them in
                      **({k: p[k] for k in ("typos", "key_corrections", "declines") if p.get(k)})}
            out.append({"id": f"proof:{pid}", "answer": p["decision"], "note": (p.get("note") or "").strip(), "fix": "", "by": by,
                        "at": p.get("at", ""), "via": SITE, "proof": {"xdid": pid, "review": review, "at": p.get("at", "")}})
    # the batch page's "Publish the edition" (site/schema-8-edition-publish.sql): publish-edition:<batch> by "<name> (review
    # site)", answer publish, or unpublish when taken back. Whether it counts (the owner's only) is edition.publications' to say.
    # Only this publication's batches (`batches`): a row for any other batch name is dropped. Each record keeps the
    # account id (`account`), which is what counts, not the name typed.
    olds = {(r["id"], r.get("account")): r for r in have if str(r.get("id", "")).startswith("publish-edition:")}
    for batch, by_account in sorted((decisions.get("edition_publish") or {}).items()):
        if batch not in batches:
            continue
        for account, d in sorted(by_account.items(), key=lambda kv: kv[1].get("at", "")):
            by, answer = f"{d.get('who') or 'a helper'} ({SITE})", "publish" if d.get("published") else "unpublish"
            o = olds.get((f"publish-edition:{batch}", account)) or {}
            if o.get("answer") == answer and o.get("at") == d.get("at", ""):
                continue
            out.append({"id": f"publish-edition:{batch}", "answer": answer, "note": str(d.get("note") or "").strip()[:500], "by": by,
                        "account": account, "at": d.get("at", ""), "via": SITE})
    return out


def fingerprint(text: str) -> str:
    return hashlib.sha1(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()[:12]


def _header(xd: str, key: str) -> str:
    return next((line[len(key) + 2:].strip() for line in xd.split("\n\n\n")[0].split("\n") if line.startswith(key + ": ")), "")


# ---- the reviewers' edits, onto the packet's xd ----------------------------------------------

APPLIED = re.compile(r"clue:[AD]\d+(?:\^[A-Za-z][\w-]*)?|cell:r\d+c\d+|meta:(title|author|byline|puzzle_number|editor|feature)"
                     r"|candidate:[AD]-alt\d+|label:B\d+")
# A candidate clue list (assembly's: a list that fits the grid, neither its clues nor a recognised second set; the
# packet's ocr.json candidates) is decided on the proof page by an edit candidate:<id> with one of these values:
# remove (not this puzzle's), answers (the printed answers, not clues), clues (these are the real clues: they
# replace the list in the xd), second:<Key> (a second clue set: its clues become the "A1 ^Key:" lines).
CANDIDATE_VALUE = re.compile(r"remove|answers|clues|second:[A-Za-z][\w-]*")
PRINTED_EDIT = re.compile(r"line:B\d+|keep:B\d+")  # a printed line's text and keep: any puzzle (apply_printed)
HEADER ={"title": "Title", "author": "Author", "byline": "Byline", "puzzle_number": "Number", "editor": "Editor", "feature": "Feature"}
META_RE = re.compile(r"^([AD]\d+) \^([A-Za-z][\w-]*): ?(.*)$")


def _meta_key(name: str) -> str:
    return "-".join(w[:1].upper() + w[1:].lower() for w in name.strip().split("-"))


def refused(edits: dict, text: str) -> list[str]:
    """The edits this import can't apply (the puzzle is held for them): kinds it doesn't know (a
    fill-in blank, a note), a rebus square, a header of several lines. Any puzzle takes a printed line's
    text and keep (line:B<n>, keep:B<n>: whether each can be applied safely is _printed_edits()'s to say).
    A linked-ends puzzle takes its own kinds too (LINKED_APPLIED: a square's kind, a square's printed
    number); whether each can be applied safely is apply_linked()'s to say."""
    bad = lambda k, v: k.startswith(("clue:", "meta:", "label:")) and (not isinstance(v, str) or bool(CONTROL.search(v)))  # one line
    bad_line = lambda k, v: k.startswith("line:") and (not isinstance(v, str) or bool(CONTROL_BUT_NL.search(v)))
    if linked(text):
        return sorted(k for k, v in edits.items() if not LINKED_APPLIED.fullmatch(k) or bad(k, v) or bad_line(k, v))
    return sorted(k for k, v in edits.items() if not (APPLIED.fullmatch(k) or PRINTED_EDIT.fullmatch(k))
                  or (k.startswith("cell:") and len(v or "") != 1)
                  or bad(k, v) or bad_line(k, v)
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
    answer = answers(cells, outside_of(cells)) if cell_edits else {}
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


def outside_of(cells) -> str:
    """The characters that aren't squares of a grid: '#', and '_' where the grid uses it (xd's mark for a place
    outside the puzzle's shape, as in the New York World's diamonds read by hand)."""
    return "#_" if any("_" in "".join(r) for r in cells) else "#"


# ---- the ## section form: puzzles read by hand (blitz hand-packets, design/hand-read.md) -------------
# A hand-read xd is in sections ("## Metadata", "## Grid", "## Clues", and "## Design" or "## Labels"), not split by
# blank lines. Ship reads it through unsection(): the Metadata, Grid and Clues sections as the blank-line form that
# the rest of this module reads, with restore() to put the edited text back into the file's own sections, every
# other line as it was. In the World's own form (Nos. 13, 18, 27: clues named by their end squares' pair, a Labels
# section) a clue the proof page shows on a run (ocr.json clues {A6: {printed: "1-3"}}) is read as that run's clue,
# and written back under its pair; a clue no run can name stays as it is (the page shows it as a printed line).

SECTION = re.compile(r"^## (\w+)\s*$")


def sectioned(text: str) -> bool:
    """The xd is in ## sections (the hand-read form), not split by blank lines."""
    return text.replace("\r\n", "\n").lstrip().startswith("## ")


def _sections(text: str) -> list[list]:
    """[[name, lines]] in the file's order: "\n".join over them, each with its "## name" line, is the text again."""
    out = []
    for line in text.replace("\r\n", "\n").split("\n"):
        m = SECTION.match(line)
        if m:
            out.append([m[1], []])
        elif out:
            out[-1][1].append(line)
        else:
            out.append(["", [line]])
    return out


def _join(secs: list[list]) -> str:
    return "\n".join(ln for name, lines in secs for ln in ([f"## {name}"] if name else []) + lines)


def _body(lines: list[str]) -> tuple[int, int]:
    """(start, end) of a section's lines less the blank lines before and after them."""
    i, j = 0, len(lines)
    while i < j and not lines[i].strip():
        i += 1
    while j > i and not lines[j - 1].strip():
        j -= 1
    return i, j


def unsection(text: str, ocr: dict | None = None):
    """(the blank-line form of a sectioned xd, restore): restore(plain) is the file again, in its own sections, with
    whatever was done to the plain text; restore(unsection(text)[0]) == text. Notes ship adds after the clues (a
    corrected key letter's) go in a "## Notes" section at the end. ocr: the packet's, for the World's own form."""
    secs = _sections(text)
    part = lambda name: next((s for s in secs if s[0] == name), None)
    for name in ("Metadata", "Grid", "Clues"):
        if not part(name):
            raise Stop(f"a sectioned xd with no ## {name} section")
    clues = part("Clues")[1][slice(*_body(part("Clues")[1]))]
    # the World's own form: the clue the proof page put on a run is that run's clue here, under its pair in the file
    hr = (ocr or {}).get("hand_read") or {}
    pmap = {}
    if hr.get("pair_form"):
        pmap = {(c or {}).get("printed"): k for k, c in ((ocr or {}).get("clues") or {}).items() if (c or {}).get("printed")}
    names = {}

    def run_label(m):
        names[pmap[m[1]]] = m[1]
        return pmap[m[1]]
    plain_clues = []
    for ln in clues:
        m = re.match(r"^(\S+?)(\. | \^)(.*)$", ln)
        plain_clues.append(run_label(m) + m[2] + m[3] if m and m[1] in pmap else ln)
    get = lambda name: part(name)[1][slice(*_body(part(name)[1]))]
    plain = "\n".join(get("Metadata")) + "\n\n\n" + "\n".join(get("Grid")) + "\n\n\n" + "\n".join(plain_clues) + "\n"

    def restore(new: str) -> str:
        head, grid, *rest = new.replace("\r\n", "\n").rstrip("\n").split("\n\n\n")
        back = []
        for ln in (rest[0].split("\n") if rest else []):
            m = re.match(r"^([AD]\d+)(\. | \^)(.*)$", ln)
            back.append(names[m[1]] + m[2] + m[3] if m and m[1] in names else ln)
        body = {"Metadata": head.split("\n"), "Grid": grid.split("\n"), "Clues": back}
        out = [[name, list(lines)] for name, lines in secs]
        for s in out:
            if s[0] in body:
                i, j = _body(s[1])
                s[1][i:j] = body[s[0]]
        notes = "\n\n\n".join(rest[1:]).strip("\n")
        if notes:
            notes_sec = next((s for s in out if s[0] == "Notes"), None)
            if notes_sec:
                i, j = _body(notes_sec[1])
                notes_sec[1][j:j] = ["", *notes.split("\n")] if j > i else notes.split("\n")
            else:
                last = out[-1][1]
                i, j = _body(last)
                last[j:] = ["", ""]
                out.append(["Notes", [*notes.split("\n"), ""]])
        return _join(out)
    return plain, restore


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
LINKED_APPLIED = re.compile(r"clue:[AD]\d+|cell:r\d+c\d+|grid:r\d+c\d+|num:r\d+c\d+|line:B\d+|keep:B\d+|label:B\d+"
                            r"|meta:(title|author|byline|puzzle_number|editor|feature)")
PAIR_LINE = re.compile(r"([A-Za-z0-9?]+-[A-Za-z0-9?]+|[AD]\d+)\. (.*) ~ (.*)$")
OUTSIDE = "#_"  # not squares of a linked-ends puzzle
PRINTED_HEAD = "Printed with puzzle:"  # the xd notes block of the printed lines the packet keeps (xword-ocr textstep)
# A printed line's label: what the line is (xword-ocr textstep's labels; the proof page's LABELS). It isn't in the xd's
# text (the "Printed with puzzle:" block has the kept lines' text only): it is in the row's `printed`, which the gxd
# export's Notes rule picks from (notes_labels: intro and instructions, unless the owner set the rule), and it is what
# the text step's default keep went by. A reviewer's label:B<n> is applied to `printed` (label_problems() says when it
# can't be), with a record of class decision. "title" is not a line's label: the title is a header (the proof page's
# headers table: meta:title, or its line, ev:title). A label:B<n> = "title" changes no label and makes no Title; it
# is kept on the record as what the reviewer said (`said`), and the line is kept or not by its keep, as any other.
LINE_LABELS = ("instructions", "test-solver", "intro", "credit", "kind", "answers", "section", "furniture", "other-puzzle", "other")
SAID_LABELS = ("title",)  # said of a line, taken as the reviewer's note on it, not as its label
EVIDENCE_HEADER = {"title": "Title", "number": "Number", "byline": "Byline", "author": "Author", "editor": "Editor",
                   "feature": "Feature", "date": "Date"}  # ocr.json's evidence fields and the xd header each gives
_SYM = {str(n): (chr(ord("a") + n - 10) if n < 36 else chr(ord("A") + n - 36)) for n in range(10, 62)}
_NUM = {v: k for k, v in _SYM.items()}


def linked(text: str) -> bool:
    """The xd is in the linked-ends style: its header says so."""
    return "\nClues: linked ends" in "\n" + text.replace("\r\n", "\n").split("\n\n\n")[0]


def unread_pairs(text: str) -> list[str]:
    """The labels of a linked-ends xd's clue lines whose printed pair isn't known: labelled by the slot ("A4.") or
    with a "?" for an end. Such a clue's place wasn't read from the paper, so the puzzle doesn't ship (the owner's
    rule, 2026-11-16): a person gives the end squares' printed numbers on the proof page, or moves the clue to the
    word its pair names, and the re-place labels it by the pair."""
    parts = text.replace("\r\n", "\n").rstrip("\n").split("\n\n\n")
    out = []
    for ln in "\n\n\n".join(parts[2:]).split("\n"):
        m = PAIR_LINE.match(ln)
        if m:
            if re.fullmatch(r"[AD]\d+", m[1]) or "?" in m[1]:
                out.append(m[1])
        elif ln.strip():
            break
    return out


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
    return [{"n": ln.get("n"), "label": label_of(ln, edits),
             "text": edits.get(f"line:B{ln.get('n')}") or fixed.get(f"line:B{ln.get('n')}") or ln.get("text") or "",
             "keep": bool(edits.get(f"keep:B{ln.get('n')}", ln.get("keep", False)))} for ln in (ocr or {}).get("lines") or []]


def label_of(ln: dict, edits: dict | None) -> str:
    """A packet line's label with a reviewer's label:B<n> applied (one of LINE_LABELS; anything else leaves it as it was)."""
    v = (edits or {}).get(f"label:B{ln.get('n')}")
    return v if v in LINE_LABELS else ln.get("label") or ""


def label_problems(edits: dict, ocr: dict) -> list[str]:
    """Why a reviewer's label:B<n> edits can't be applied, in words ([] when they can): a line the packet doesn't
    have, a line a header was read from (it has no label of its own: the header says what it is), a line the packet
    records no keep for (the page would keep or discard it by the new label, the import by nothing recorded), or a
    value that is neither one of LINE_LABELS nor one SAID_LABELS keeps as the reviewer's note."""
    out, lines = [], {ln.get("n"): ln for ln in (ocr or {}).get("lines") or []}
    evidence = {n for n in ((ocr or {}).get("evidence") or {}).values() if isinstance(n, int)}
    for k, v in edits.items():
        if not k.startswith("label:"):
            continue
        n = int(k.partition(":B")[2])
        if v not in LINE_LABELS + SAID_LABELS:
            out.append(f"{k}: {str(v)[:40]!r} is not a label of a printed line ({', '.join(LINE_LABELS)})")
        elif n not in lines:
            out.append(f"{k}: the packet has no such printed line")
        elif n in evidence:
            out.append(f"{k}: the line is where a header was read from, so it has no label of its own")
        elif "keep" not in lines[n] and f"keep:B{n}" not in edits:
            out.append(f"{k}: the packet records no keep for the line, so nothing says whether the new label keeps it")
    return out


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
    lands, and none is applied), edits: "applied" (the block is written again from the kept lines with the edits,
    _printed_edits: any puzzle since 2026-11-25, linked-ends before) or "held" (the block isn't the packet's kept
    lines: a Ready carrying a keep: or line: edit holds it as edits-unapplied), fixed: the lines a header was read
    from (not kept or dropped), says: that, in words}."""
    if not xd or not (ocr or {}).get("lines"):
        return None
    lines = printed_lines(ocr, review or {})
    after = "\n\n\n".join(xd.replace("\r\n", "\n").rstrip("\n").split("\n\n\n")[2:]).split("\n")
    at = next((i for i, ln in enumerate(after) if ln == PRINTED_HEAD), None)
    block = after[at + 1:_block(after, at)] if at is not None else []
    agrees = block == block_lines(lines)
    fixed = sorted({n for n in ((ocr or {}).get("evidence") or {}).values() if isinstance(n, int)})
    says = ("the xd's printed lines are not the packet's kept lines, so nothing says where an edit to one lands: none is "
            "applied, and a Ready carrying one holds the puzzle (edits-unapplied)"
            if not agrees else
            "the import writes this block again from the kept lines, in the packet's order, with each line's text as edited")
    return {"head": PRINTED_HEAD, "lines": [ln["n"] for ln in lines if ln["keep"]] if agrees else None,
            "edits": "applied" if agrees else "held", "fixed": fixed, "says": says}


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
    # (a printed line's text and keep: checked and applied with the printed lines, _printed_edits)
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
    after, did, bad = _printed_edits(head, after, edits, ocr, review)
    done += did
    cant += bad
    if cant:
        return text, [], cant
    out = "\n".join(head) + "\n\n\n" + "\n".join("".join(r) for r in cells) + ("\n\n\n" + "\n".join(after) if after else "") + "\n"
    return out, done, []


def _printed_edits(head: list[str], after: list[str], edits: dict, ocr: dict | None, review: dict | None
                   ) -> tuple[list[str], list[str], list[str]]:
    """A reviewer's line:B<n> and keep:B<n> edits applied to an xd's lines after the grid (any puzzle): (those lines,
    the keys applied, what can't be applied, in words). The "Printed with puzzle:" block is the packet's kept lines in
    order, and is written again from them with the edits. A line a header was read from can't be dropped, and its text
    must still give the xd's header. Nothing is applied when anything can't be."""
    lines = [k for k in edits if k.startswith(("line:", "keep:"))]
    done, cant = [], []
    if not lines:
        return after, done, cant
    after = list(after)
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
        elif k.startswith("line:") and isinstance(v, str) and CONTROL_BUT_NL.search(v):
            cant.append(f"{k}: a printed line's text holds a tab or another control character")
        elif k.startswith("line:") and (not isinstance(v, str) or any(not t.strip() for t in v.split("\n")[1:])):
            cant.append(f"{k}: a printed line's text can hold line breaks, not an empty line (the xd's block ends at one)")
        elif k.startswith("line:") and not v.strip():
            cant.append(f"{k}: an empty line (keep:B{n} drops a line)")
        elif k.startswith("line:") and any(not heads.get(EVIDENCE_HEADER.get(f, "")) or not _count(v.lower(), heads[EVIDENCE_HEADER[f]].lower())
                                           for f in evidence.get(n, [])):
            cant.append(f"{k}: the line is where the {' and '.join(evidence[n])} was read from, and as edited it doesn't show the "
                        "xd's header: the header has to be given its value with it (meta:), or the line left as it was")
        else:
            done.append(k)
    if cant:
        return after, [], cant
    new = block_lines(printed_lines(ocr or {}, review or {}, edits))
    if at is not None and new:
        after[at + 1:_block(after, at)] = new
    elif at is not None:  # nothing kept any more: the block goes, with the blank lines after it (the ones before
        end = _block(after, at)  # it set off what comes next, as they did the block)
        while end < len(after) and not after[end].strip():
            end += 1
        del after[at:end]
        while after and not after[-1].strip():
            after.pop()
    elif new:  # the first kept line: the block comes first in the notes, after the clue lines
        first = next((i for i, ln in enumerate(after) if ln.strip() and not PAIR_LINE.match(ln) and not META_RE.match(ln)), None)
        if first is None:
            after += ["", "", PRINTED_HEAD, *new]
        else:
            after[first:first] = [PRINTED_HEAD, *new, ""]
    return after, done, cant


def apply_printed(text: str, edits: dict, ocr: dict | None, review: dict | None) -> tuple[str, list[str], list[str]]:
    """Any xd with a reviewer's printed-line edits (line:B<n>, keep:B<n>) applied: (text, the keys applied, what can't
    be applied, in words). A linked-ends xd's go through apply_linked() with the rest of its edits; this is the same
    step for an ordinary puzzle, run after apply_edits()."""
    if not any(k.startswith(("line:", "keep:")) for k in edits):
        return text, [], []
    head, grid, *rest = text.replace("\r\n", "\n").rstrip("\n").split("\n\n\n")
    after, done, cant = _printed_edits(head.split("\n"), "\n\n\n".join(rest).split("\n") if rest else [], edits, ocr, review)
    if cant:
        return text, [], cant
    return head + "\n\n\n" + grid + ("\n\n\n" + "\n".join(after) if after else "") + "\n", done, []


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


def assign_ids(want: list[str], places: dict[str, tuple], repo: Path, own: set | frozenset = frozenset()) -> tuple[dict[str, str], list[dict]]:
    """{pid: xdid} for the puzzles to import and the new pins (rows for fixes/xdids.tsv). A puzzle the
    publication already pinned keeps its id (pipeline/ids.tsv's aliases, or fixes/xdids.tsv by its place:
    scan, leaf, grid size, n-th of that size on the page among every puzzle of the run); a new one gets
    its date's next free letter, in page order. places: {pid: (scan, leaf, size)} for the whole run. own: puzzles
    whose packet is named by its xdid already (read by hand: blitz hand-packets), which keep it and pin nothing."""
    alias, by_page = _pins(repo)
    used = set(by_page.values()) | set(alias.values()) | {f.stem for f in (repo / "xd").glob("*.xd")}
    seen, nth = {}, {}
    for pid in sorted(places):
        nth[pid] = seen.get(places[pid], 0)
        seen[places[pid]] = nth[pid] + 1
    out, new = {}, []
    for pid in sorted(want):
        if pid in own:
            out[pid] = pid
            continue
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


def plan(repo: Path, proof_root: Path, rule: Rule, batch: str = "", site: dict | None = None, pub: str = "",
         _grading: bool = False, scope: dict | None = None) -> dict:
    """What shipping the batch would do, written nowhere: every puzzle of the run with its status
    (shipped: in xd/ as it stands; shippable: passes, not written yet; held, with the reason; out: set
    aside or not a crossword), and the xd text and provenance of each one that passes.

    A puzzle the rule passes can still be held by the import, each a reason of its own: no-packet,
    packet-stale (the packet doesn't show its xd), incomplete (the ship check's: no Ready makes a
    puzzle whole), edits-differ (two reviewers changed one thing two ways), edits-unapplied (a kind of
    edit the import doesn't apply), xd-exists (xd/ has another file under its id).

    Every row carries its grade (grade_of; `held` for a puzzle the rule would hold with every grade on, which a second
    pass of this function, _grading, works out), and the plan the digest's facts (digest).

    scope: the publication's scope rule (scope_of; None: read from its repo). A puzzle whose recorded kind it defers
    is out of the batch, with a stub."""
    repo = Path(repo)
    harvest, run, rel = _where(proof_root)
    # a harvest's run has triage's record beside its proof packets; puzzles read by hand have the one blitz hand-packets
    # wrote with them (its ship check of each xd), in the packets' folder
    tri = _load(harvest / "triage" / run / "triage.json") or _load(Path(proof_root) / "triage.json")
    if not tri:
        raise Stop(f"No triage record for {run} at {harvest / 'triage' / run}: run xword-ocr triage --proof first "
                   "(or, for puzzles read by hand, blitz hand-packets, which writes it with the packets).")
    recs = ledger(repo)
    pids = [p["pid"] for p in tri["puzzles"]]
    means = {g.get("code", ""): g.get("means", "") for g in tri.get("groups") or [] if isinstance(g, dict)}  # triage's own words for its codes
    scope = scope_of(repo, batch or run) if scope is None else scope
    new_site = from_site(site, recs, set(pids), {batch or run}) if site else []
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
        if xd and sectioned(xd):  # read by hand: read and edited as the blank-line form, shipped in its own sections
            packs[pid]["sections"] = [name for name, _ in _sections(xd)]
            xd, packs[pid]["restore"] = unsection(xd, o)
            packs[pid]["xd"] = xd
        page = ((o.get("stages") or {}).get("pages") or {}).get("page.jpg") or ["", ""]
        grid = xd.split("\n\n\n")[1].split("\n") if xd else o.get("grid") or [""]
        places[pid] = (page[0], str(page[1]), f"{len(grid)}x{len(grid[0])}")
    prov = {r["pid"]: r for r in provenance(repo)}
    rows, passing = [], {}
    by_xdid = {r["xdid"]: r for r in prov.values()}
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
            row.update(grade="not-a-crossword" if kind == "not-a-crossword" else "deferred", grade_why=row["why"], flags=0, settled=None,
                       doubts=[], gaps=[], lacks=[], diagnosis=None)
            if kind == "set-aside":  # known, not transcribed: a stub, as a puzzle the scope rule defers has
                row["stub"] = stub_of(pid, row["date"], places[pid], *recorded_kind(t), f"set aside by {rec.get('by', '')}: {rec.get('note', '')}")
            continue
        # out of scope for now: its kind as a milestone recorded it, deferred by the publication's rule. Never a puzzle
        # this batch already shipped (a rule written later doesn't take back what is in xd/)
        pkind, pfrom = recorded_kind(t)
        if pkind and scope.get(pkind) == "defer" and pid not in prov:
            why = f"deferred: a {pkind} ({pfrom}), out of scope for now (the publication's fixes/scope.json)"
            row.update(status="out", reason="deferred", why=why, said=[], rule="", asks=[], broken=[], grade="deferred", grade_why=why, flags=0,
                       settled=None, doubts=[], gaps=[], lacks=[], diagnosis=None, stub=stub_of(pid, row["date"], places[pid], pkind, pfrom, why))
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
        # its grade, from the records; and, where the rule ships by grade, the rule's answer with the grade given
        mine_all = list((proofs.get(pid) or {}).values())
        row.update(grade_of(t, st, mine_all, rule, current, means, open_c))
        if rule.ship_grades:
            st = standing(latest.get(f"batch:{pid}") or {}, mine_all, rule=rule, grade=row["grade"], **args)
            row["ships_with"] = next((opt for opt in AI_READY if standing(latest.get(f"batch:{pid}") or {}, mine_all, rule=replace(rule, ai_ready=opt),
                                                                           grade=row["grade"], **args)["status"] == "ship"), "")
            row.update(reason=st["reason"], why=st["why"], rule=st["rule"], said=st["said"])

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
        # people other than the owner gave a square of the grid different values: the re-place used neither (xword-ocr
        # linkedends.hint, reviewer_fixes.undecided), so the packet is as the stage read it there. The owner decides
        undecided = ((pk["ocr"].get("reviewer_fixes") or {}).get("undecided")) or []
        if undecided:
            row.update(reason="fixes-disputed", why="reviewers' fixes to the grid disagree, and none is the owner's: "
                       + ", ".join(u["key"] for u in undecided[:6]) + "; neither was read in, the owner decides",
                       asks=[{"who": v.get("by", ""), "kind": v.get("kind", "helper"), "at": str(v.get("at", ""))[:10], "row": u["key"], "group": "",
                              "text": f"Gave {u['key'].partition(':')[2]} the value “{v.get('value', '')}”. Another reviewer gave it another: "
                                      "which is right? Your own fix on the square settles it."} for u in undecided for v in u.get("values") or []])
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
        # incomplete: what the ship check found that no Ready makes whole. What the edits do make whole, and only when a
        # person's decision ships it (the owner's, or a helper's Ready; never an AI's Ready, whatever ai_ready says):
        # a key square the packet left unread, when each such square has its letter among the edits that ship (since
        # 2026-11-12); a clue the packet has no text for, when each such clue has its text in the own edits of someone
        # whose typed clue counts (Rule.typed_clues: any person's by default), never from an AI's edit (since 2026-11-13)
        people, typists = {}, {}  # the people's own clue edits; the record behind each typed clue
        for r in st["apply"]:
            kd = kind_of(r, rule)
            for k, v in (((r.get("proof") or {}).get("review") or {}).get("edits") or {}).items():
                if kd in ("owner", "helper") and k.startswith("clue:"):
                    people.setdefault(k, v)
                if k.startswith("clue:") and counts_for(r, rule, "typed_clues"):
                    typists.setdefault(k, r)
        typed_by = {k: ((r.get("proof") or {}).get("review") or {}).get("edits", {}).get(k) for k, r in typists.items()}
        filled = filled_by(ship, edits, typed_by) if st["rule"] in ("owner", "people") else []
        # what a person's "Ready to ship as it stands" waives: the gaps it names, and only on a person's word
        part = partial_of(st["apply"], rule, [x for x in ship.get("incomplete") or [] if x not in filled])
        waived = part["missing"] if part else []  # not filled: the gaps stay in what ships, and are said
        if part:
            st = {**st, "why": st["why"] + f"; shipped as it stands, on {part['by']}'s word: {'; '.join(part['missing'])}"
                  + (f" ({part['note']})" if part["note"] else "")}
        if filled:  # what the edits make whole is no gap
            row.update(grade_of(t, st, mine_all, rule, current, means, open_c, filled))
        left = [x for x in ship.get("incomplete") or [] if x not in filled and x not in waived]
        if left and row["grade"] in rule.ship_grades:  # ships as it stands by its grade, the gaps named on its row (the owner, 2026-11-25)
            st = {**st, "why": st["why"] + f"; ships incomplete, by its grade: {'; '.join(map(str, left))}"}
        elif left:
            # a clue a helper typed, which would have made it whole on the owner's word: said, so the card shows why
            waiting = [k for k in typed_clues(ship, filled_by(ship, {}, people))
                       if k not in typists] if st["rule"] in ("owner", "people") else []
            hold("incomplete", "Ready, but incomplete: " + "; ".join(map(str, ship["incomplete"])) + (
                f" ({', '.join(w[5:] for w in waiting)} typed by a helper: a clue typed where none was read makes the puzzle "
                "whole only on the owner's word, the ship rule's typed_clues)" if waiting else ""))
            continue
        typed = {k: typists[k] for k in typed_clues(ship, filled)}
        if filled:
            st = {**st, "why": st["why"] + f"; the ship check's \"{'; '.join(filled)}\" is filled by the edits applied"
                  + (f" ({', '.join(k[5:] for k in typed)} typed by a person: no text was read for it)" if typed else "")}
        if differ:
            hold("edits-differ", "reviewers' edits differ: " + ", ".join(sorted(differ)[:6]))
            continue
        bad = refused(edits, pk["xd"]) or label_problems(edits, pk["ocr"])
        if bad:
            hold("edits-unapplied", "proof-page edits the import can't apply yet: " + ", ".join(bad[:6]))
            continue
        off_runs = ((pk["ocr"].get("hand_read") or {}).get("outside")) or []
        if off_runs and any(k.startswith("cell:") for k in edits):  # their answers would not follow the square
            hold("edits-unapplied", "a key square changed in a puzzle with clues no across or down run can name ("
                 + ", ".join(off_runs[:6]) + "): their answers can't follow it, so the import doesn't apply it yet")
            continue
        # its candidate clue lists: each decided by a Ready reviewer's edit, or the puzzle waits for that decision
        undecided = [c["id"] for c in cands if f"candidate:{c['id']}" not in edits]
        if undecided and row["grade"] in rule.ship_grades:  # an open doubt on its row, not a hold: the list stays out of the xd
            st = {**st, "why": st["why"] + f"; {len(undecided)} candidate clue list(s) left undecided, and out of the xd ({', '.join(undecided)})"}
        elif undecided:
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
            unread = unread_pairs(text)
            if unread:  # whoever said Ready (the owner's rule, 2026-11-16)
                hold("pair-unread", f"Ready, but {len(unread)} clue(s) with no printed pair ({', '.join(unread[:6])}"
                     + (f" +{len(unread) - 6}" if len(unread) > 6 else "") + "): their places weren't read from the paper. "
                     "Give the end squares' printed numbers on the proof page, or move each clue to the word its pair names")
                continue
        elif "Printed" in (pk.get("sections") or []):
            # read by hand, with the paper's other words in ## Printed (blitz design/xd-fields.md): every printed line is
            # there whatever its keep, so a keep or discard is the edition's choice of notes (the provenance row's
            # `printed` carries it) and changes no line of the xd; a line's new text has no place written for it yet
            text, done = apply_edits(text, edits)
            cant = [f"{k}: a printed line's text in ## Printed isn't rewritten by the import yet" for k in edits if k.startswith("line:")]
            if cant:
                hold("edits-unapplied", "proof-page edits to the printed lines the import can't apply as they stand: "
                     + "; ".join(cant[:3]) + (f" (+{len(cant) - 3})" if len(cant) > 3 else ""))
                continue
            done += sorted(k for k in edits if k.startswith("keep:"))
        else:
            text, done = apply_edits(text, edits)
            text, ldone, cant = apply_printed(text, edits, pk["ocr"], pk["review"])
            if cant:
                hold("edits-unapplied", "proof-page edits to the printed lines the import can't apply as they stand: "
                     + "; ".join(cant[:3]) + (f" (+{len(cant) - 3})" if len(cant) > 3 else ""))
                continue
            done += ldone
        squares = any(isinstance(f, dict) and f.get("code") == "grid-unsolved" and f.get("detail") in filled for f in ship.get("findings") or [])
        if squares and any(ch in ".?" for ch in text.split("\n\n\n")[1]):  # the letters were given, and a square is still unread in what would ship
            hold("incomplete", "Ready, but incomplete: " + "; ".join(map(str, ship["incomplete"])) + " (the edits don't fill every square)")
            continue
        if [k for k in typed if _read(text)[2].get(k[5:]) != typed_by[k]]:  # a typed clue that doesn't ship as it was typed
            hold("incomplete", "Ready, but incomplete: " + "; ".join(map(str, ship["incomplete"])) + " (a typed clue doesn't ship as typed)")
            continue
        done = cdone + done + sorted(k for k in edits if k.startswith("label:"))  # a label isn't in the xd's text: it is applied to `printed`
        if part:
            row["partial"] = {"missing": part["missing"], "note": part["note"]}
        row["review"] = review_of(st, pk)
        passing[pid] = {"text": text, "edits": done, "edit_values": edits, "edit_sources": sources, "standing": st, "row": row,
                        **({"partial": part} if part else {}),
                        "packet": f"{rel}/{pid}", "xd_fp": review.get("xd_fp", ""), "typed": typed}
    _record_edits(passing, packs, rule)  # each one's record of every edit, its misprint notes; none without (edit-unrecorded)
    for pid, x in passing.items():
        if packs[pid].get("restore"):  # read by hand: back into the file's own sections
            x["text"] = packs[pid]["restore"](x["text"])
    own = {pid for pid in passing if packs[pid].get("restore") and packs[pid]["review"].get("hand_read")}
    ids, pins = assign_ids(list(passing), places, repo, own)
    for pid, x in sorted(passing.items()):
        row, xdid = x["row"], ids[pid]
        f = repo / "xd" / f"{xdid}.xd"
        row["xdid"] = x["xdid"] = xdid
        ours = (prov.get(pid) or {}).get("xdid") == xdid
        if f.exists() and f.read_text(encoding="utf-8") == x["text"] and ours:
            row.update(status="shipped", reason="", why=f"in xd/ as {xdid}: {(prov[pid].get('shipped') or {}).get('why', '')}")
        elif f.exists() and not ours and xdid not in rule.replace:
            row.update(reason="xd-exists", why=f"xd/{xdid}.xd is another file (an earlier import's): replace it by hand, or drop it")
            del passing[pid]
        else:
            if f.exists() and not ours:  # the owner's decision (rule.replace): this reading takes the place of the earlier one
                was = by_xdid.get(xdid) or {}
                x["replaces"] = {"xdid": xdid, "pid": was.get("pid", ""), "batch": was.get("batch", ""), "xd": fingerprint(f.read_text(encoding="utf-8"))}
            row.update(status="shippable", reason="", why=x["standing"]["why"] + (
                f"; replaces xd/{xdid}.xd, shipped from {x['replaces']['pid'] or 'another source'}" if x.get("replaces") else ""))
    for row in rows:  # a puzzle shipped earlier that the rule now holds: still in xd/, and said so
        p = prov.get(row["pid"])
        if row["status"] == "held" and p and (repo / "xd" / f"{p['xdid']}.xd").exists():
            row.update(xdid=p["xdid"], why=row["why"] + f" (already in xd/ as {p['xdid']})")
    if _grading:  # the pass that asks what the rule holds with every grade on: its rows are all the caller reads
        return {"rows": rows}
    # held: what the rule holds whatever the grade. This plan's own answer when it ships by every grade, else one more pass
    would = rows if set(rule.ship_grades) >= set(SHIPS) else plan(repo, proof_root, replace(rule, ship_grades=SHIPS), batch, site, pub, _grading=True, scope=scope)["rows"]
    for row, w in zip(rows, would):
        held_grade(row, w)
    groups = queues(rows)
    out = {"groups": groups, "pub": pub or re.match(r"[a-z]+", repo.name)[0], "batch": batch or run, "run": run, "packets": rel, "rule": {"ai_ready": rule.ai_ready, "hold_codes": list(rule.hold_codes),
            "ignore": list(rule.ignore), "owner": list(rule.owner), **{k: getattr(rule, k) for k in WHOSE_INPUT}, "ship_grades": list(rule.ship_grades)},
            "means": means, "digest": digest(rows, batch or run, means), "scope": scope, "rows": rows, "passing": passing, "pins": [p for p in pins if p["xdid"] in {x["xdid"] for x in passing.values()}],
            "site": new_site, "packs": packs}
    from . import edition  # the edition of each passing puzzle, and whether the batch's edition is published (design/ship.md, "The edition")
    out["editions"] = edition.preview(repo, out["pub"], out, recs, rule)
    out["edition_published"] = edition.published_of(recs, rule, out["batch"])
    return out


def counts(rows: list[dict]) -> dict:
    out = {"puzzles": len(rows), "shipped": 0, "shippable": 0, "held": 0, "out": 0, "held_by": {}, "ships_with": {},
           "queues": {q: 0 for q in QUEUES}, "reviewed": 0, "spot_check": 0,
           # every puzzle's grade, and how many of each ship (shipped, or ready to ship)
           "grades": {g: 0 for g in GRADES}, "grade_ships": {g: 0 for g in GRADES}, "incomplete": {}}
    for r in rows:
        out[r["status"]] += 1
        out["queues"].setdefault(r["queue"], 0)  # `deferred` (the scope rule's): a queue only where a puzzle is in it
        if r.get("grade") == "incomplete":  # which kind of incomplete: counted once, under the first that applies, and under each it has
            for i, k in enumerate(r.get("lacks") or []):
                c = out["incomplete"].setdefault(k, {"first": 0, "any": 0})
                c["first"] += not i
                c["any"] += 1
        if r.get("grade") in out["grades"]:
            out["grades"][r["grade"]] += 1
            out["grade_ships"][r["grade"]] += r["status"] in ("shipped", "shippable")
        out["queues"][r["queue"]] += 1
        out["reviewed"] += bool(r.get("reviewed"))
        out["spot_check"] += bool(r.get("spot_check"))
        if r["status"] == "held":
            out["held_by"][r["reason"]] = out["held_by"].get(r["reason"], 0) + 1
        if r["status"] != "out" and r.get("ships_with"):
            out["ships_with"][r["ships_with"]] = out["ships_with"].get(r["ships_with"], 0) + 1
        if r.get("typed") and r["status"] in ("shipped", "shippable"):  # clues typed by a person where none was read
            out["typed"] = out.get("typed", 0) + len(r["typed"])
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
TYPED = "typed"  # a clue a person typed where the packet had no text for it (filled_by): nothing was read, so not a reading fix
TYPED_HEAD = "Typed by hand:"  # the xd notes block ship writes: one line per clue a person typed where none was read
# Whose misprint marks take effect: the owner's and the AI proof reviewer's (2026-11-11), and since 2026-11-13 any
# person's (Rule.marks "people", the default; counts_for). With Rule.marks "owner", a helper's or a guest's is a
# proposal: kept in the ledger, shown on the proof page and in the xd as it will ship as "proposed by ..., waiting for
# the owner", never applied at ship-export nor (a key letter) corrected here. A helper's or a guest's mark that can't be
# taken (malformed, or naming words its row doesn't have) is dropped and said, under either setting: it holds nothing,
# and never reaches the export. An owner's or an AI's holds the puzzle (mark-invalid).
MARKS_COUNT = ("owner", "ai")
MARK_MAX = 200  # characters in a mark's printed or meant words


def _dispute(key: str, editor: dict, edit, marker: dict, printed: str, meant: str, rule: Rule) -> dict:
    """A misprint mark against another reviewer's edit on the same row: the owner's question, showing both."""
    why = _why(editor, key)
    return {"key": key, "asks": [
        {"who": editor.get("by", ""), "kind": kind_of(editor, rule), "at": "", "row": key, "group": "",
         "text": f"Edited the row to “{str(edit)[:120]}”" + (f", saying: {why}" if why else ", with no comment")},
        {"who": marker.get("by", ""), "kind": kind_of(marker, rule), "at": "", "row": key, "group": "",
         "text": f"Marks “{printed}” as printed and “{meant}” as meant: a misprint, which would ship as printed. Which is right: "
                 "the reading in the edit, or the misprint?"}]}


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
                 packet_review: dict | None = None, typed: dict | None = None) -> dict:
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
    ocr, typed = ocr or {}, typed or {}
    is_linked = linked(packet_xd)
    was_h, was_c, was_q = _read(packet_xd)
    outside, pairs = (OUTSIDE if is_linked else outside_of(was_c)), _pairs(packet_xd)
    owner, value, typos, seen, of_key, key_said = {}, {}, [], set(), set(), {}
    invalid, proposals, row_marks = [], [], []  # marks that can't be taken (they hold the puzzle); marks that wait for the owner
    who = lambda r: {"by": r.get("by", ""), "kind": kind_of(r, rule), "via": r.get("via", ""), "at": r.get("at", "")}
    for r in apply:
        review = (r.get("proof") or {}).get("review") or {}
        for k, v in (review.get("edits") or {}).items():
            if k not in owner:
                owner[k], value[k] = r, v
        counts = (kind_of(r, rule) in MARKS_COUNT and _name(r) not in rule.ignore) or counts_for(r, rule, "marks")
        holds = counts and kind_of(r, rule) != "helper"  # a mark that can't be taken holds the puzzle: the owner's or the AI's
        for kind, ts in (("typos", review.get("typos") or []), ("key_corrections", review.get("key_corrections") or [])):
            for t in ts if isinstance(ts, list) else [ts]:
                why = mark_problem(t, kind == "key_corrections" or str((t or {}).get("key", "") if isinstance(t, dict) else "").startswith("cell:"))
                if why and holds:
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
    # The owner's "not a misprint" (since 2026-11-13): an explicit decline in the owner's review (declines: [{key,
    # printed, meant, by}], the proof page's button on someone else's mark), or the owner's own edit on the marked row
    # that keeps the printed words once (their edit says what the row is) with no mark of their own on those words.
    # A declined mark is not taken: shown "declined by the owner", never at ship-export, a key letter left as printed.
    # The explicit decline counts on any mark, an AI's included; the owner's edit declines another person's only (an
    # AI's mark beside a person's edit that keeps the printed words is proposed, as before).
    declined = {}  # (key, printed, meant) -> (the owner's record, how)
    edit_key = lambda key: f"meta:{_field(key)}" if _field(key) else key  # the edit a misprint's key sits beside
    for r in apply:
        review = (r.get("proof") or {}).get("review") or {}
        if kind_of(r, rule) != "owner" or _name(r) in rule.ignore:
            for d in review.get("declines") or [] if _name(r) not in rule.ignore else []:  # only the owner declines: said, not taken
                if isinstance(d, dict):
                    proposals.append({"key": str(d.get("key", "")), "printed": str(d.get("printed", "")), "meant": str(d.get("meant", "")), **who(r),
                                      "what": "decline", "status": "not taken",
                                      "says": f"A decline of the mark on {str(d.get('key', '')).partition(':')[2]} (“{d.get('printed', '')}”): "
                                              "not taken, only the owner declines a mark."})
            continue
        mine = {(str(t.get("key", "")), str(t.get("printed", "")).strip()) for t in review.get("typos") or [] if isinstance(t, dict)}
        for d in review.get("declines") or []:
            if isinstance(d, dict) and d.get("key"):
                declined[(str(d["key"]), str(d.get("printed", "")).strip(), str(d.get("meant", "")).strip())] = (r, "declined")
        for key, printed, meant, m in typos:
            ek = edit_key(key)
            if (kind_of(m, rule) == "helper" and (key, printed) not in mine and isinstance((review.get("edits") or {}).get(ek), str)
                    and _count(review["edits"][ek], printed) == 1):
                declined.setdefault((key, printed, meant), (r, "edit"))
    declined_keys = set()

    def decline_says(t3, how):
        what = f"The key letter at {t3[0][5:]}" if t3[0].startswith("cell:") else _label(t3[0], pairs)
        return (f"{what}: marked as printed “{t3[1]}”, meant “{t3[2]}”: declined by the owner"
                + (": their edit on the row keeps the printed words" if how == "edit" else ": not a misprint") + ".")
    for t in list(typos):
        hit = declined.get(t[:3])
        if not hit:
            continue
        typos.remove(t)
        of_key.discard(t[:3])
        proposals.append({"key": t[0], "printed": t[1], "meant": t[2], **who(t[3]), "what": "key letter" if t[0].startswith("cell:") else "misprint",
                          "status": "declined by the owner", "declined_by": hit[0].get("by", ""), "says": decline_says(t[:3], hit[1])})
        if t[0].startswith("cell:"):
            declined_keys.add((t[0], t[1], t[2], id(hit[0])))
    for q in proposals:  # a mark that was waiting for the owner (marks: owner), declined
        hit = declined.get((q["key"], q["printed"], q["meant"])) if q["status"] == "waiting for the owner" else None
        if hit:
            q.update(status="declined by the owner", declined_by=hit[0].get("by", ""), says=decline_says((q["key"], q["printed"], q["meant"]), hit[1]))
            if q["key"].startswith("cell:"):
                declined_keys.add((q["key"], q["printed"], q["meant"], id(hit[0])))
            row_marks[:] = [x for x in row_marks if (x[0], x[1], x[2]) != (q["key"], q["printed"], q["meant"])]
    decliner = {id(r): r for r in apply}
    disputes = []
    by_key = {}
    for t in typos:
        by_key.setdefault(t[0], []).append(t)
    for key, ts in by_key.items():
        if len({(pr, mn) for _, pr, mn, _ in ts}) < 2:
            continue  # one mark on the row, or the same words from everyone who marked it
        kinds = {id(t): kind_of(t[3], rule) for t in ts}
        people = [t for t in ts if kinds[id(t)] in ("owner", "helper")]
        mine = [t for t in ts if kinds[id(t)] == "owner"]
        keep = mine if mine else people if people and len({(pr, mn) for _, pr, mn, _ in people}) == 1 else None
        if keep is None and people:  # two people (not the owner) disagree: neither is taken, the owner decides
            disputes.append({"key": key, "asks": [{"who": t[3].get("by", ""), "kind": kinds[id(t)], "at": "", "row": key, "group": "",
                                                    "text": f"Marks “{t[1]}” as printed and “{t[2]}” as meant. Another reviewer's mark on "
                                                            "the same row says otherwise: which is the misprint?"} for t in people]})
            keep = []
        elif keep is None:
            continue  # only AI reviewers' marks: as before
        for t in ts:
            if t not in keep:
                typos.remove(t)
                if t[0].startswith("cell:"):
                    of_key.discard(t[:3])
                proposals.append({"key": t[0], "printed": t[1], "meant": t[2], **who(t[3]), "what": "key letter" if t[0].startswith("cell:") else "misprint",
                                  "status": "not taken", "says": f"Marks “{t[1]}” as printed, “{t[2]}” meant: not taken, "
                                  + ("the owner's mark on the row says otherwise." if mine else "a person's mark on the row says otherwise." if kinds[id(t)] == "ai"
                                     else "another reviewer's mark on the row says otherwise; the owner decides.")})
    records, missing, have, more_edits, back, key_fix, said, misedit = [], [], {}, {}, set(), {}, {}, []
    kept_printed = set()  # squares a declined key correction leaves as the key printed them
    for key, printed, meant, rid in declined_keys:
        at = _square(was_c, key)
        if not at or len(printed) != 1:
            continue
        cur = (value[key] or "").upper() if key in owner else was_c[at[0]][at[1]]
        if cur == meant.upper() and cur != printed.upper():
            more_edits[key] = printed.upper()
            if key not in owner:
                owner[key] = decliner[rid]
            kept_printed.add(key)
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

    for key, printed, meant, r in list(typos):
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
        elif edit_key(key) in owner and kind_of(r, rule) == "ai" and owner[edit_key(key)] is not r \
                and kind_of(owner[edit_key(key)], rule) in ("owner", "helper"):
            # An AI's mark on a row a person edited (the fourth pass, 2026-11-13): it never changes, drops or overrides a
            # person's edit or its record. Where the two agree (the edit keeps the printed words once) the correction is
            # proposed as usual; where they disagree, the puzzle is a question for the owner, showing both.
            ek = edit_key(key)
            if _count(value[ek] or "", printed) != 1:
                disputes.append(_dispute(ek, owner[ek], value[ek], r, printed, meant, rule))
        elif (edit_key(key) in owner and kind_of(r, rule) == "helper" and edit_key(key) not in (((r.get("proof") or {}).get("review") or {}).get("edits") or {})
              and kind_of(owner[edit_key(key)], rule) in ("owner", "helper") and _count(value[edit_key(key)] or "", printed) != 1):
            # a helper's or a guest's mark on a row another person edited, disagreeing with the edit (since 2026-11-13, when their
            # marks count): one person's edit is never changed by another's mark. The owner's edit stands and the mark is not
            # taken; another helper's: the owner decides
            ek, pr = edit_key(key), owner[edit_key(key)]
            typos.remove((key, printed, meant, r))
            if kind_of(pr, rule) == "owner":
                proposals.append({"key": key, "printed": printed, "meant": meant, **who(r), "what": "misprint", "status": "not taken",
                                  "says": f"Marks “{printed}” as printed, “{meant}” meant: not taken, the owner's edit on the row stands."})
            else:
                disputes.append(_dispute(ek, pr, value[ek], r, printed, meant, rule))
        elif edit_key(key) in owner:  # case 2 on a clue or header the reviewer also edited (the owner's mark governs the row)
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
    if invalid or misedit or disputes:  # held before anything is made of them
        return {"text": applied, "records": [], "corrections": [], "notes": [], "missing": [], "invalid": invalid, "misedit": misedit,
                "proposals": proposals, "waits": [], "disputes": disputes}
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
        cls = (TYPED if k in typed else DECISION if what in ("decision", "printed line kept", "printed line label") or more.get("decided_by")
               or k in kept_printed
               else KEY_FIX if k in key_fix
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
        r = typed.get(k, r)  # a typed clue is recorded as the person's who typed it, whoever's Ready came first with the same text
        if is_linked and k.startswith(("grid:", "cell:")):
            if not any(k in (h["key"], *h.get("with", [])) for h in records) and not _square(was_c, "cell:" + k.partition(":")[2]):
                missing.append(f"{k}: the packet's grid has no such square")
        elif is_linked and k.startswith("num:"):
            n = re.fullmatch(r"num:r(\d+)c(\d+)", k)
            sq = (int(n[1]) - 1, int(n[2]) - 1)
            add(k, "square number", lk0["nums"].get(sq, ""), lk1["nums"].get(sq, ""), r,
                pairs={lab: [lk0["label"][lab], lk1["label"].get(lab, "")] for lab in lk0["label"]
                       if lk0["label"][lab] != lk1["label"].get(lab) and sq in (lk0["words"][lab][0], lk0["words"][lab][-1])})
        elif k.startswith(("line:", "keep:")):  # any puzzle's printed lines
            ln = lines0.get(int(k.partition(":B")[2]))
            if ln is None:
                missing.append(f"{k}: the packet has no such printed line")
            elif k.startswith("line:"):
                add(k, "printed line", ln["text"], v, r, kept=bool(value.get("keep:" + k[5:], ln["keep"])))
            else:
                add(k, "printed line kept", "kept" if ln["keep"] else "not kept", "kept" if v else "not kept", r,
                    line=value.get("line:" + k[5:]) or ln["text"])
        elif k.startswith("label:"):  # what the line is: not in the xd's text; the row's printed carries it (any puzzle)
            ln = lines0.get(int(k.partition(":B")[2]))
            if ln is None:
                missing.append(f"{k}: the packet has no such printed line")
            elif v in SAID_LABELS:  # not a label: said of the line, kept on its record; the line keeps its label
                records.append({"key": k, "what": "printed line label", "class": DECISION, "before": ln["label"], "after": ln["label"], **who(r),
                                "stage": EDIT_STAGE, "said": v, "line": value.get("line:" + k[6:]) or ln["text"],
                                "note": f"called the line the {v}: a {v} is a header (the proof page's headers table), not a line's label, "
                                        "so the line keeps its label and no header is made from it", "evidence": evidence(k)})
            else:
                add(k, "printed line label", ln["label"], v, r, line=value.get("line:" + k[6:]) or ln["text"],
                    kept=bool(value.get("keep:" + k[6:], ln["keep"])))
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
            a0, a1 = answers(was_c, outside), answers(one, outside)
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
    # and under any puzzle's printed lines
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
            if cur is not None and not _count(cur, printed) and not _count(cur, meant) and kind_of(r, rule) == "helper":
                proposals.append({"key": key, "printed": printed, "meant": meant, **who(r), "what": "misprint", "status": "not taken",
                                  "says": f"Marks “{printed}” as printed: not taken, the row's text doesn't have it."})
                continue  # a helper's or a guest's: dropped and said, holding nothing
            if cur is not None and not _count(cur, printed) and not _count(cur, meant):  # names words the row doesn't have
                invalid.append(f"typos from {r.get('by', '')}: {key}: “{printed}” isn't in the row's text (nor the words meant)")
            says = f"{_label(key, pairs)} is printed '{printed}'; meant '{meant}'."
        mine = ((r.get("proof") or {}).get("review") or {}).get("edits", {}).get(edit_key(key))
        corrections.append({"key": key, "printed": printed, "meant": meant, **who(r), "fits": fits, "says": says, "evidence": evidence(key),
                            **({"edit": mine} if mine is not None else {})})
    # a helper's or a guest's key correction whose square they also changed to it: the letter would be corrected here
    # on their word, which the owner's rule keeps for the owner: held, a question for the owner
    waits = [p for p in proposals if p["what"] == "key letter" and p["status"] == "waiting for the owner" and p["key"] in owner
             and owner[p["key"]].get("by") == p["by"]
             and str(value.get(p["key"]) or "").upper() == p["meant"].upper()]
    if invalid:
        return {"text": applied, "records": [], "corrections": [], "notes": [], "missing": [], "invalid": invalid, "misedit": [],
                "proposals": proposals, "waits": []}
    # a clue a person typed where nothing was read: said in the xd's notes, by whom and with their comment, and on its record
    typed_notes = []
    for k in typed:
        if k in have:
            h, alias = have[k], {"owner": "the owner", "helper": "a helper"}.get(have[k]["kind"], have[k]["kind"])
            note = (f"{_label(k, pairs)} was typed by {alias} on the proof page{' (' + h['at'][:10] + ')' if h.get('at') else ''}: "
                    "no text for it was read from the scan" + (f'. Their comment: "{h["why"]}"' if h.get("why") else "."))
            h["note"] = note
            typed_notes.append(note)
        else:
            missing.append(f"{k}: typed by a person, and no record of it made")
    return {"text": with_notes(with_notes(text, notes), typed_notes, TYPED_HEAD), "records": records, "corrections": corrections, "notes": notes,
            "typed": typed_notes, "missing": missing,
            "invalid": invalid, "misedit": misedit, "proposals": proposals, "waits": waits}


def owner_declines(repo: Path, pid: str, rule: Rule) -> set:
    """The marks the owner has declined on a puzzle ("not a misprint", the proof page's button): (key, printed, meant)
    from each of the owner's accounts' latest proof record in the ledger, whatever its answer. The export reads it, so
    a decline given after the puzzle shipped holds at the export too, before the record is made again."""
    latest = {}
    for r in ledger(repo):
        if r.get("id") == f"proof:{pid}" and kind_of(r, rule) == "owner" and _name(r) not in rule.ignore:
            latest[r.get("by", "")] = r
    return {(str(d.get("key", "")), str(d.get("printed", "")).strip(), str(d.get("meant", "")).strip())
            for r in latest.values() for d in ((r.get("proof") or {}).get("review") or {}).get("declines") or [] if isinstance(d, dict)}


# corrected(), the correction of the print, lives in edition.py since 2026-11-16 (the edition step); imported above.


def with_notes(text: str, lines: list[str], head: str = NOTES_HEAD) -> str:
    """The xd with a block of ship's own in its notes, after the notes it has: the corrected key letters (NOTES_HEAD),
    the clues a person typed where none was read (TYPED_HEAD)."""
    if not lines:
        return text
    body = text.replace("\r\n", "\n").rstrip("\n")
    return body + ("\n\n" if len(body.split("\n\n\n")) > 3 else "\n\n\n") + head + "\n" + "\n".join(lines) + "\n"


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
        e = edit_records(packs[pid]["xd"], x["text"], x["standing"]["apply"], rule, pid, packs[pid]["ocr"], packs[pid]["review"], x.get("typed"))
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
        if e.get("disputes") and pid in passing:  # a mark against another's edit, or two people's marks: the owner's question
            d = e["disputes"]
            x["row"].update(reason="mark-disputed", why="a misprint mark disagrees with another reviewer's edit or mark on the same row: "
                            + ", ".join(sorted({q["key"] for q in d})) + "; the owner decides", asks=[a for q in d for a in q["asks"]])
            del passing[pid]
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
        # the clues a person typed where none was read: in the xd's notes (TYPED_HEAD), and counted (the record's counts.typed)
        x["typed"] = [{k: h[k] for k in ("key", "by", "kind", "at", "note") if k in h} for h in x["edit_records"] if h["class"] == TYPED]
        if x["typed"]:
            x["row"]["typed"] = [{"key": h["key"], "kind": h["kind"], "note": h["note"]} for h in x["typed"]]


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
    linked-ends puzzle's only, any other puzzle being held on such an edit; label:B<n> its label, any puzzle's)."""
    fixed, edits = review.get("corrections") or {}, edits or {}
    return [{"label": label_of(ln, edits), "text": edits.get(f"line:B{ln.get('n')}") or fixed.get(f"line:B{ln.get('n')}") or ln["text"]}
            for ln in ocr.get("lines") or []
            if edits.get(f"keep:B{ln.get('n')}", ln.get("keep", True)) and ln.get("label") and (ln.get("text") or "").strip()]


def take_in_site(repo: Path, rows: list[dict]) -> int:
    """The review site's records a run used, appended to the ledger (fixes/decisions.jsonl) unless it already holds
    them (same id, by, account, answer and time), so whatever the run writes from them can be made again from the repo
    alone. Returns how many were appended."""
    if not rows:
        return 0
    key = lambda r: (r.get("id"), r.get("by"), r.get("account", ""), r.get("answer"), r.get("at"))
    have = {key(r) for r in ledger(repo)}
    new = [r for r in rows if key(r) not in have]
    if new:
        f = Path(repo) / "fixes" / "decisions.jsonl"
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a", encoding="utf-8", newline="\n") as fh:
            fh.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in new)
    return len(new)


def grade_record(row: dict) -> dict:
    """A row's grade as its provenance row and its as-shipped file carry it: {grade, why, flags, settled, doubts, gaps}
    (a puzzle that ships is never held, so no diagnosis)."""
    return {"grade": row.get("grade", ""), "why": row.get("grade_why", ""), "flags": row.get("flags", 0),
            "settled": row.get("settled"), "doubts": list(row.get("doubts") or []), "gaps": list(row.get("gaps") or []),
            "lacks": list(row.get("lacks") or [])}


def write(repo: Path, p: dict, today: str = "") -> dict:
    """plan()'s result into the publication's repo: the review site's decisions into the ledger, the
    passing puzzles' xd files and pins, their provenance rows, gxd-exports.tsv, and the batch's ship
    record. Returns {written: [xdid], ledger: n}."""
    repo, today = Path(repo), today or date.today().isoformat()
    take_in_site(repo, p["site"])
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
               **({"proposals": x["proposals"]} if x.get("proposals") else {}),
               **({"typed": x["typed"]} if x.get("typed") else {}),  # clues typed by a person where none was read
               **({"partial": x["partial"]} if x.get("partial") else {}),
               "review": x["row"].get("review", ""),  # how it was reviewed, in words: to find the rest if an error turns up
               "grade": grade_record(x["row"]),  # how far to trust it, with the doubts left open and the gaps named (formats/ship-record.md)
               **({"replaces": x["replaces"]} if x.get("replaces") else {}),  # the earlier ship of this xdid it took the place of  # shipped as it stands: the gaps a person waived, and why  # waiting for the owner; the export never reads them
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
    p["digest"] = digest(p["rows"], p["batch"], p.get("means"))
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
             **({"candidates": r["candidates"]} if r.get("candidates") else {}),
             # shipped as it stands: what is missing, and the reviewer's word on why we stop here
             **({"partial": r["partial"]} if r.get("partial") else {}),
             **({"review": why({**r, "why": r["review"]})} if r.get("review") else {}),
             # its grade (grade_of; formats/ship-record.md): how far to trust it, the doubts left open (each with its row
             # on the proof page), the gaps named, a held puzzle's diagnosis, its place in the digest, and whether it is
             # in the owner's reading sample (to_read)
             "grade": r.get("grade", ""), "grade_why": why({**r, "why": r.get("grade_why", "")}), "flags": r.get("flags", 0),
             "settled": ((_public_who(r["settled"]) if public else r["settled"]) if r.get("settled") else None),
             "doubts": list(r.get("doubts") or []), "gaps": list(r.get("gaps") or []), "lacks": list(r.get("lacks") or []),
             "diagnosis": ({**r["diagnosis"], "what": why({**r, "why": r["diagnosis"]["what"]})} if r.get("diagnosis") else None),
             "grade_order": r.get("grade_order", 0), "to_read": bool(r.get("to_read")),
             # a deferred puzzle's stub: known, not transcribed (the scope rule's, or a person's set-aside)
             **({"stub": {**r["stub"], "why": why({**r, "why": r["stub"]["why"]})}} if r.get("stub") else {})} for r in p["rows"]]
    return {"_about": "blitz ship: which puzzles of the batch are shipped (in the publication repo's xd/), shippable (pass the "
                      "ship rule, not written yet) or held, with the reason, and the queue each is in: what the batch page asks "
                      "of people. Format: blitz design/ship.md.",
            "batch": p["batch"], "run": p["run"], "packets": p["packets"], "rule": p["rule"],
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "counts": counts(p["rows"]),
            # the grades (formats/ship-record.md): their order, which of them this batch ships by, the owner's reading
            # sample, the shipped xd files in the order the digest steps through them, the kinds of failure ranked
            "format": "ship-record/1",
            "grades": {"order": list(GRADES), "ships": list(p["rule"].get("ship_grades") or []),
                       # what an incomplete puzzle lacks, by kind, in the order a puzzle is counted under (counts.incomplete)
                       "lacks": [{"key": k, "means": LACKS_MEANS[k]} for k in LACKS]},
            **{k: (p.get("digest") or {}).get(k) for k in ("sample", "walk", "failures")},
            # the publication's scope rule as this record was made with it (fixes/scope.json), where it has one, and which
            # kinds a milestone records today: a kind nothing records is deferred for no puzzle
            **({"scope": {"rule": p["scope"], "recorded_by": {k: f"triage: {c}" for c, k in KIND_CODES.items()},
                          "stubs": sum(1 for r in p["rows"] if r.get("stub"))}} if p.get("scope") else {}),
            "groups": p["groups"], "spot": {"one_in": SPOT_ONE_IN, "of": "puzzles shipped on someone else's word than the owner's",
                                            "by": "sha1 of the puzzle's id"},
            "puzzles": [{**row, **{k: r[k] for k in ("notes", "corrections", "proposals", "typed") if r.get(k)}, **_recorded_more(p, r)} for row, r in zip(rows, p["rows"])],
            # the owner's "Publish the edition" for the batch (the ledger's publish-edition:<batch>) and how many of its
            # puzzles' editions that publishes: shipped (in xd/), the edition made (design/ship.md, "The edition")
            "edition_published": _published_public(p.get("edition_published") or {"published": False, "at": "", "by": ""}, public),
            "editions_published": editions_published(p)}


def editions_published(p: dict) -> int:
    """How many of the plan's puzzles the manifest lists as published: shipped (in xd/), with its edition made, in a
    batch whose edition the owner has published."""
    if p.get("edition_run"):  # the step ran with this record: the manifest's count, so the two agree
        return p["edition_run"]["published_by_batch"].get(p["batch"], 0)
    if not (p.get("edition_published") or {}).get("published"):
        return 0
    eds = p.get("editions") or {}
    return sum(1 for r in p["rows"] if r["status"] == "shipped" and (eds.get(r["pid"]) or {}).get("status") == "made")


def _published_public(rel: dict, public: bool) -> dict:
    """Whether the edition is published, as the record shows it: the owner's review-site account is "the owner" in
    the public copy."""
    if public and str(rel.get("by", "")).endswith(f"({SITE})"):
        return {**rel, "by": "the owner"}
    return dict(rel)


def _recorded_more(p: dict, r: dict) -> dict:
    """What the record says beyond the rule's answer, for the proof page: where the packet's printed lines land in
    its xd (printed_place), and for a puzzle that passes, the fingerprint of the xd as it will ship (as_shipped:
    the text itself is in its own file beside the record, AS_SHIPPED)."""
    pk = (p.get("packs") or {}).get(r["pid"]) or {}
    place = printed_place(pk.get("xd", ""), pk.get("ocr") or {}, pk.get("review") or {})
    x = (p.get("passing") or {}).get(r["pid"])
    ed = (p.get("editions") or {}).get(r["pid"])
    return {**({"printed": place} if place else {}), **({"as_shipped": fingerprint(x["text"])} if x else {}),
            # its edition (edition/<xdid>.xd): made, with its fingerprint, or held, with the codes that hold it
            **({"edition": {"status": ed["status"], "xd_fp": ed["xd_fp"], "held": [h["code"] for h in ed["held"]],
                            "corrections": sum(c["done"] in ("applied", "noted") for c in ed["corrections"])}} if ed else {})}


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
            # clues a person typed where no text was read: in the xd's notes too (TYPED_HEAD)
            "typed": [pub(t) for t in x.get("typed") or []],
            # its grade, as the record's row has it: how far to trust this text, the doubts left open, the gaps named
            "grade": grade_record(row),
            "printed": _printed(pk["ocr"], pk["review"], {k: v for k, v in (x.get("edit_values") or {}).items() if k in x["edits"]}),
            # the edition made from this xd (design/ship.md, "The edition"): what the publication publishes, the corrections it made
            # and the notes it took; held (no text) when a mark can't be placed
            **({"edition": {**ed, "corrections": [pub(c) for c in ed["corrections"]], "declined": [pub(c) for c in ed["declined"]]}}
               if (ed := (p.get("editions") or {}).get(pid)) else {})}
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
    """The batch's ship record and its as-shipped files into the publication repo, and the editions and the manifest.
    The review site's records the plan used go into the ledger first (take_in_site), so the record, the editions and
    the manifest all rest on what the repo holds, and blitz edition alone makes the same ones again."""
    f = Path(repo) / "pipeline" / "ship" / f"{p['batch']}.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    p["site_taken_in"] = take_in_site(repo, p.get("site") or [])
    if (Path(repo) / "provenance.jsonl").exists():  # the editions and the manifest, from what is shipped (design/ship.md, "The edition")
        from . import edition
        p["edition_run"] = edition.run(repo, p["pub"], plan=p)
    rec = record(p)
    f.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    write_as_shipped(f.parent / p["batch"], p, rec)
    return f


# ---- the gxd export ------------------------------------------------------------------------

KEEP = ("Title", "Author", "Editor", "Date", "Number", "Byline", "Rebus", "Special", "Notes")
FLATTEN = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})  # gxd's lint wants plain quotes
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


# notes_labels() and NOTE_LABELS, the Notes rule, live in edition.py since 2026-11-16 (the edition step); imported above.


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
    rule = rule_of(repo)  # whose decline of a mark counts: the owner's
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
        no = owner_declines(repo, r["pid"], rule)  # declined by the owner after it shipped: not made, not listed
        # a key letter corrected in the shipped xd that the owner has since declined: the xd itself is wrong now, so the
        # puzzle is held back until blitz ship --write ships it again with the letter as printed
        undone = [e for e in (r.get("edits") or {}).get("records") or [] if e.get("class") == "key correction" and e.get("misprint")
                  and (e["key"], e["misprint"].get("printed"), e["misprint"].get("meant")) in no]
        if undone:
            held.append((r["xdid"], "key-declined: the owner has declined the key correction(s) "
                         + ", ".join(f"{e['key'][5:]} {e['misprint']['printed']}->{e['misprint']['meant']}" for e in undone)
                         + " since it shipped: re-ship it first (blitz ship --write), then export"))
            continue
        gid = next((o["gxd_id"] for o in _tsv(repo / "gxd-exports.tsv") if o["xdid"] == r["xdid"] and o.get("gxd_id")), r["xdid"])
        text, fixed_notes, fixed = corrected(text, [c for c in r.get("corrections") or [] if (c.get("key"), c.get("printed"), c.get("meant")) not in no])
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
