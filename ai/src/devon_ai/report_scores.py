"""검증된 단계 판정에서 공개 점수를 계산한다(LLM 없음).

환산표와 반올림은 작성자 제안이며 팀 확정 전이다. 값이 바뀌면 이 파일의 상수·함수만 고친다.
"""

from dataclasses import dataclass
from fractions import Fraction
from typing import get_args

from devon_ai import contracts as c

# 단계 → 점수. 0단계는 "질문을 받고도 답하지 못함"에만 쓴다(backend seed_score_criteria와 같은 값).
LEVEL_SCORES: dict[int, int] = {0: 0, 1: 20, 2: 45, 3: 70, 4: 90}


@dataclass(frozen=True)
class ReportScores:
    """key별 점수(공개 순서)와 totalScore. 모두 0~100 정수다."""

    key_scores: tuple[tuple[c.ScoreKeyId, int], ...]
    total_score: int


def _half_up(value: Fraction) -> int:
    """파이썬 round()의 짝수 반올림 대신 .5를 올린다."""
    return (2 * value.numerator + value.denominator) // (2 * value.denominator)


def compute_scores(checked: c.ContractChecked[c.ScoreJudgments]) -> ReportScores:
    """key별로 not_applicable을 뺀 단계 점수의 평균을 내고, totalScore는 key 평균들의 평균이다.

    반올림은 평균을 낸 뒤 한 번만 한다(key별 반올림값으로 total을 다시 평균 내지 않는다).
    """
    if type(checked) is not c.ContractChecked or type(checked.data) is not c.ScoreJudgments:
        raise c.ContractError("schema", "checked score judgments")
    means: list[tuple[c.ScoreKeyId, Fraction]] = []
    for key in get_args(c.ScoreKeyId):
        scores = [
            LEVEL_SCORES[item.level]
            for item in checked.data.judgments
            if item.key == key and item.level != "not_applicable"
        ]
        if not scores:  # 검증기가 막지만 기본 점수를 만들지 않으려고 한 번 더 확인한다.
            raise c.ContractError("semantic", "unscorable key")
        means.append((key, Fraction(sum(scores), len(scores))))
    return ReportScores(
        tuple((key, _half_up(mean)) for key, mean in means),
        _half_up(sum((mean for _, mean in means), Fraction(0)) / len(means)),
    )
