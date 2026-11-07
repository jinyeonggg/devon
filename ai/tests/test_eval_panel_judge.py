from eval_cases import Case
from grader_check import EXPECTED
from panel_judge import compare, panel

KINDS = sorted(EXPECTED)
ANSWERS = {f"out-{kind}": EXPECTED[kind] for kind in KINDS}


def _case():
    review = {"status": "approved", "author": "a", "reviewer": "b", "reviewed_at": "2026-11-01"}
    exp = {
        "allowed": [{"id": "a1"}],
        "forbidden": [{"id": "f1"}],
        "grader_controls": [{"kind": k, "output": f"out-{k}"} for k in KINDS],
        "review": {**review, "pending_notes": []},
    }
    return Case("q-1", 1, "question", "dev", "sg-1", {}, exp)


def _const(v):
    return lambda rubric, output: v


def test_majority_wins():
    assert panel([_const("accept"), _const("accept"), _const("reject")])({}, "x") == "accept"


def test_split_or_tie_is_ambiguous():
    assert panel([_const("accept"), _const("reject")])({}, "x") == "ambiguous"
    assert panel([_const("accept"), _const("reject"), _const("ambiguous")])({}, "x") == "ambiguous"


def test_panel_outvotes_one_wrong_member():
    right = lambda rubric, output: ANSWERS[output]  # noqa: E731
    members = {"a": right, "b": right, "c": _const("accept")}
    reports = compare([_case()], members)
    assert reports["c"]["by_kind"]["forbidden"]["false_accept"] == 1
    assert reports["panel"]["by_kind"]["forbidden"]["correct"] == 1
