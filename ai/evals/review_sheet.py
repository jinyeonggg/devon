"""Render a one-page reviewer sheet per eval case. Not part of the runtime package.

Usage (run in ai/): uv run python evals/review_sheet.py [case_id ...]
Sheets contain the answer key, so they go to the ignored ai/report/ folder, never to a model.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from eval_cases import Case, CaseError, load_cases
from grader_check import EXPECTED

_VERDICT = {"accept": "통과", "reject": "거부", "ambiguous": "판정 보류"}
_FACT_ROWS = ("사실", "확인 범위", "미확인", "확인 수준", "금지", "출처")

_QUESTIONS = (
    "통과 항목이 원본 사실의 '확인 범위'를 넘지 않는가? (원본보다 넓지 않은가)",
    "실패 항목은 모두 원본 사실의 '미확인'에서 나온 넘겨짚기인가? 빠진 넘겨짚기는 없는가?",
    "모델이 받는 자료에서 정답 기준과 다르게 해석할 여지가 없는가?",
    "채점기 시험용 가짜 답의 종류가 맞는가?",
)


def fact_record(fact_table: str, fact_id: str) -> dict[str, str]:
    """Rows of one `### F-… · title` table in fact-table.md, or CaseError if absent."""
    match = re.search(rf"^### {re.escape(fact_id)} .*?(?=^#{{2,3}} |^---)", fact_table, re.M | re.S)
    if not match:
        raise CaseError(f"{fact_id}: not found in fact-table.md")
    rows: dict[str, str] = {}
    for line in match.group(0).splitlines():
        if line.startswith("| ") and " | " in line and not line.startswith("| ---"):
            key, value = line[2:].rstrip(" |").split(" | ", 1)
            rows[key.strip()] = value.strip()
    return rows


def _table(header: tuple[str, ...], rows: list[tuple[str, ...]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    return out + ["| " + " | ".join(c.replace("|", "\\|") for c in r) + " |" for r in rows]


def _payload(payload: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for key, value in payload.items():
        if key != "materials":
            out.append(f"- **{key}**: {value}")
            continue
        for m in value:
            out += [
                "",
                f"**{m['ref']}** — `{m['path']}` ({m['lines']}줄)",
                "",
                "```",
                m["text"],
                "```",
            ]
    return out


def render_sheet(case: Case, fact: dict[str, str] | None) -> str:
    exp, review = case.expectation, case.expectation["review"]
    lines = [
        f"# 검수 시트 — {case.case_id} v{case.version}",
        "",
        f"종류 `{case.kind}` / 구분 `{case.split}` / 원본 그룹 `{case.source_group_id}` / "
        f"작성자 `{review['author']}` / 검수 상태 `{review['status']}`",
        "",
        "## ① 모델이 받는 것",
        "",
        *_payload(case.payload),
        "",
        "## ② 원본 사실",
        "",
    ]
    if fact is None:
        lines.append("이 사례에는 원본 사실이 연결돼 있지 않습니다.")
    else:
        lines += _table(("항목", "내용"), [(k, fact[k]) for k in _FACT_ROWS if k in fact])
    lines += ["", "## ③ 정답 기준 (작성자가 정함)", ""]
    lines += _table(("통과(허용)", "내용"), [(a["id"], a["purpose"]) for a in exp["allowed"]])
    lines += [""]
    lines += _table(
        ("실패(금지)", "내용", "유형"),
        [(f["id"], f["reason"], f["type"]) for f in exp["forbidden"]],
    )
    lines += ["", "## ④ 채점기 시험용 가짜 답", ""]
    lines += _table(
        ("종류", "가짜 답", "채점기가 내야 할 판정"),
        [(g["kind"], g["output"], _VERDICT[EXPECTED[g["kind"]]]) for g in exp["grader_controls"]],
    )
    lines += ["", "## 판단할 것", ""]
    lines += _table(
        ("#", "질문", "판정"),
        [(str(i), q, "□ 맞음 □ 수정 필요 □ 모름") for i, q in enumerate(_QUESTIONS, 1)],
    )
    lines += [
        "",
        "## 결과 전달",
        "",
        f"사례 번호와 판정만 적어 주세요. 예: `{case.case_id} 통과` 또는 "
        f"`{case.case_id} 수정요청 - 2번, 사유 ...`",
        "",
    ]
    return "\n".join(lines)


def main(root: Path, out_dir: Path, only: list[str]) -> list[Path]:
    fact_text = (root / "expectations" / "fact-table.md").read_text(encoding="utf-8")
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for case in load_cases(root):
        if only and case.case_id not in only:
            continue
        fact_id = case.expectation.get("source_fact")
        sheet = render_sheet(case, fact_record(fact_text, fact_id) if fact_id else None)
        path = out_dir / f"{case.case_id}.md"
        path.write_text(sheet, encoding="utf-8", newline="\n")
        written.append(path)
    return written


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    for p in main(here, here.parent / "report" / "review-sheets", sys.argv[1:]):
        sys.stdout.write(f"{p}\n")
