import json
from pathlib import Path

import pytest
from eval_cases import CaseError, load_cases
from review_sheet import fact_record, main, render_sheet

FACTS = """## R1

### F-R1-001 · 선언
| 항목 | 내용 |
| --- | --- |
| 사실 | 의존성이 선언돼 있다 |
| 미확인 | 런타임 사용 여부 |
| 금지 | P4 |

### F-R1-002 · 다른 사실
| 항목 | 내용 |
| --- | --- |
| 사실 | 다른 것 |
"""


def _write_case(root: Path, **exp_extra) -> None:
    for folder in ("inputs", "expectations"):
        (root / folder).mkdir(exist_ok=True)
    inp = {
        "case_id": "e-1",
        "version": 1,
        "control": {
            "kind": "evidence",
            "split": "dev",
            "source_group_id": "sg-1",
            "synthetic": True,
        },
        "payload": {
            "question": "Redis를 쓰나요?",
            "materials": [{"ref": "m1", "path": "build.gradle", "lines": "1-2", "text": "redis"}],
        },
    }
    exp = {
        "case_id": "e-1",
        "version": 1,
        "allowed": [{"id": "a1", "purpose": "선언을 말한다"}],
        "forbidden": [{"id": "f1", "reason": "사용 단정", "type": "P4"}],
        "grader_controls": [{"kind": "ambiguous", "output": "아마 쓸 듯"}],
        "review": {
            "status": "unreviewed",
            "author": "me",
            "reviewer": None,
            "reviewed_at": None,
            "pending_notes": [],
        },
        **exp_extra,
    }
    (root / "inputs" / "e-1.v1.json").write_text(json.dumps(inp), encoding="utf-8")
    (root / "expectations" / "e-1.v1.json").write_text(json.dumps(exp), encoding="utf-8")
    (root / "expectations" / "fact-table.md").write_text(FACTS, encoding="utf-8")


def test_fact_record_reads_only_its_own_table():
    fact = fact_record(FACTS, "F-R1-001")
    assert fact["사실"] == "의존성이 선언돼 있다" and fact["금지"] == "P4"
    assert "다른 것" not in fact.values()


def test_fact_record_missing_id_is_an_error():
    with pytest.raises(CaseError):
        fact_record(FACTS, "F-R9-999")


def test_sheet_shows_every_part_a_reviewer_needs(tmp_path):
    _write_case(tmp_path, source_fact="F-R1-001")
    (case,) = load_cases(tmp_path)
    sheet = render_sheet(case, fact_record(FACTS, "F-R1-001"))
    for text in (
        "Redis를 쓰나요?",
        "build.gradle",
        "의존성이 선언돼 있다",
        "선언을 말한다",
        "사용 단정",
        "아마 쓸 듯",
        "판정 보류",
        "□ 맞음",
        "e-1 통과",
    ):
        assert text in sheet


def test_sheet_without_source_fact_says_so(tmp_path):
    _write_case(tmp_path)
    (case,) = load_cases(tmp_path)
    assert "원본 사실이 연결돼 있지 않습니다" in render_sheet(case, None)


def test_main_writes_one_file_per_case_and_fails_on_unknown_fact(tmp_path):
    _write_case(tmp_path, source_fact="F-R1-001")
    (path,) = main(tmp_path, tmp_path / "out", [])
    assert path.name == "e-1.md" and "검수 시트" in path.read_text(encoding="utf-8")
    _write_case(tmp_path, source_fact="F-R9-999")
    with pytest.raises(CaseError):
        main(tmp_path, tmp_path / "out", [])


@pytest.mark.parametrize("bad", ["", 3, None, ["F-R1-001"]])
def test_loader_rejects_bad_source_fact(tmp_path, bad):
    _write_case(tmp_path, source_fact=bad)
    with pytest.raises(CaseError):
        load_cases(tmp_path)
