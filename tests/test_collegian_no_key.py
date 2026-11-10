"""tools/collegian/scan.py publish: the puzzles a person settled as having no answer key printed
become the publication's fixes/no-key-printed.tsv, which xword-ocr reads as a publication rule."""
import importlib.util
import json
import sys
from pathlib import Path


def _scan(data: Path):
    import os

    os.environ["COLLEGIAN_DIR"] = str(data)
    spec = importlib.util.spec_from_file_location("collegian_scan", Path(__file__).parents[1] / "tools" / "collegian" / "scan.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["collegian_scan"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_no_key_settlements_become_rows_for_each_leaf_of_the_puzzle(tmp_path):
    cols = "file\tissue\tdate\tpage\turl\tcaptured\tnote\tcrop_of\tanswers"
    rows = [
        "pages/1977-04-28/seq-4-page.jpg\tcollegian-1977-04-28\t1977-04-28\t4\tu\t2026-11-05\twhole\t\t",
        "pages/1977-04-28/seq-4-puzzle.jpg\tcollegian-1977-04-28\t1977-04-28\t4\tu\t2026-11-05\tcrop\tpages/1977-04-28/seq-4-page.jpg\t",
        "pages/1977-04-29/seq-4-page.jpg\tcollegian-1977-04-29\t1977-04-29\t4\tu\t2026-11-05\twhole\t\t",
        "pages/1977-04-29/seq-4-puzzle.jpg\tcollegian-1977-04-29\t1977-04-29\t4\tu\t2026-11-05\tcrop\tpages/1977-04-29/seq-4-page.jpg\t",
        "pages/1977-04-29/seq-9-key-1977-04-29.jpg\tcollegian-1977-04-29\t1977-04-29\t9\tu\t2026-11-06\tkey\t\tpages/1977-04-29/seq-4-puzzle.jpg",
    ]
    (tmp_path / "pages.tsv").write_text("\n".join([cols, *rows]) + "\n", "utf8")
    decisions = [
        {"id": "1977-04-28", "date": "1977-04-28", "seq": 4, "verdict": "key", "by": "person", "at": "2026-11-06T11:00:00", "source": "/answers"},
        {"id": "1977-04-28", "date": "1977-04-28", "seq": 4, "verdict": "none", "by": "person", "at": "2026-11-06T11:31:03", "source": "/answers"},
        {"id": "1977-04-29", "date": "1977-04-29", "seq": 4, "verdict": "key", "by": "person", "at": "2026-11-06T11:31:21", "source": "/answers"},
    ]
    (tmp_path / "answer_decisions.jsonl").write_text("\n".join(json.dumps(d) for d in decisions) + "\n", "utf8")
    got = _scan(tmp_path).no_key_rows()
    # the last line per id wins; one row for the whole page and one for the crop; the key's own row isn't one
    assert [r[:4] for r in got] == [["collegian-1977-04-28", "0", "person", "2026-11-06T11:31:03"],
                                    ["collegian-1977-04-28", "1", "person", "2026-11-06T11:31:03"]]
    assert "no answer key printed for the puzzle on page 4" in got[0][4] and "/answers" in got[0][4]
