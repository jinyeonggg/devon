"""종합·Persona별 서술 후보를 만든다. prompt 로드·provider I/O·저장은 BE 책임이다.

서술 출력에는 점수가 없다. 점수는 llm_tasks.report_score의 단계 판정과 devon_ai.report_scores가
만들며 이 task는 점수 판정 결과를 입력으로 받지 않는다. 보완 반영 여부, 코드 존재와 개인 기여의
분리, unresolved 불일치를 거짓말로 쓰지 않는 것 같은 의미 품질은 검증기가 아니라 평가 사례로 본다.
"""

from dataclasses import asdict

from devon_ai import contracts as c

type NarrativeChecked = c.ContractChecked[c.ReportNarrative]


def _object(properties: dict[str, object]) -> dict[str, object]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _output_schema() -> dict[str, object]:
    text = {"type": "string"}
    texts = {"type": "array", "items": text}
    claim = _object({"text": text, "turn_refs": texts, "evidence_refs": texts})
    claims = {"type": "array", "items": claim}
    summary = _object(
        {"strengths": claims, "gaps": claims, "follow_ups": claims, "practice_actions": claims}
    )
    persona = _object(
        {
            "persona": {"enum": list(c.NARRATIVE_PERSONAS)},
            "tags": texts,
            "strengths": claims,
            "improvements": claims,
            "practice_actions": claims,
            "limitations": texts,
        }
    )
    return _object(
        {
            "headline": text,
            "summary": summary,
            "persona_feedbacks": {"type": "array", "items": persona},
        }
    )


def _payload(report_input: c.ReportInput) -> dict[str, object]:
    return {
        "turns": [
            {
                "turn_id": turn.turn_id,
                "persona": turn.persona,
                "question": turn.question,
                "answer": turn.answer,
                "follows": turn.follows,
                "evidence_refs": list(turn.evidence_refs),
                "analysis": None if turn.analysis is None else asdict(turn.analysis),
            }
            for turn in report_input.turns
        ],
        "evidence": [asdict(item) for item in report_input.evidence],
        "tool_results": [
            {"turn_id": item.turn_id, "result": asdict(item.result)}
            for item in report_input.tool_results
        ],
    }


async def write_narrative(
    report_input: c.ReportInput,
    *,
    prompt: c.PromptSpec,
    limits: c.CallLimits,
    model_call: c.ModelCall[NarrativeChecked],
    max_attempts: int = 2,
) -> c.ModelResult[NarrativeChecked]:
    """서술 후보를 만들고 validate_narrative를 통과한 값만 반환한다.

    재시도는 하지 않으며 시도 횟수·시간은 공통 호출 계층이 제한한다. semantic 실패는 재호출하지
    않는다. 입력이 잘못되면 모델을 부르지 않는다.
    """
    try:
        if type(prompt) is not c.PromptSpec or prompt.task_name != "report":
            raise c.ContractError("schema", "report prompt")
        if type(limits) is not c.CallLimits:
            raise c.ContractError("schema", "report limits")
        c.validate_report_input(report_input)
        request = c.ModelRequest(
            prompt=prompt,
            payload=_payload(report_input),
            schema_name="ReportNarrative",
            schema_version="1",
            output_schema=_output_schema(),
            limits=limits,
            max_attempts=max_attempts,
        )
    except c.ContractError as exc:
        failure = c.CallFailure(exc.stage, "report_input_invalid", "Report input rejected.")
        return c.ModelResult(None, failure, ())

    def validate(raw: object) -> NarrativeChecked:
        # 계약 밖의 최상위 필드(점수 등)를 조용히 버리지 않고 schema 실패로 처리한다.
        if type(raw) is not dict or set(raw) != {"headline", "summary", "persona_feedbacks"}:
            raise c.ContractError("schema", "ReportNarrative")
        return c.validate_narrative(c.decode(c.ReportNarrative, raw), report_input=report_input)

    result = await model_call(request, validate)
    if result.data is None:
        return result
    # 주입된 callable이 validator를 생략했더라도 이 입력 기준으로 다시 확인한다.
    checked = result.data
    if type(checked) is not c.ContractChecked or type(checked.data) is not c.ReportNarrative:
        raise TypeError("ModelCall did not return a checked ReportNarrative")
    try:
        c.validate_narrative(checked.data, report_input=report_input)
    except c.ContractError as exc:
        failure = c.CallFailure(exc.stage, "report_invalid", "Narrative candidate rejected.")
        return c.ModelResult(None, failure, result.attempts)
    return result
