"""분석 run 실패 로그는 예상하지 못한 예외에만 Traceback(exc_info)을 남긴다."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from structlog.testing import capture_logs

from app.core.errors import AppError, Reason
from app.features.analysis.pipeline import run as run_module
from app.features.analysis.pipeline.run_support import RunFailure


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expects_traceback"),
    [
        (KeyError("boom"), True),
        (RunFailure("jd_fetch_failed"), False),
        (AppError(Reason.GITHUB_TOKEN_INVALID), False),
    ],
)
async def test_run_failure_log_keeps_traceback_only_for_unexpected_errors(
    monkeypatch, error, expects_traceback
):
    run = SimpleNamespace(created_at=datetime.now(UTC), user_id=uuid4(), document_id=None)

    async def claim_run(ctx, run_id):
        return run

    async def account_for_run(ctx, user_id):
        raise error

    async def finish_run(ctx, run_id, status, code):
        pass

    monkeypatch.setattr(run_module, "claim_run", claim_run)
    monkeypatch.setattr(run_module, "account_for_run", account_for_run)
    monkeypatch.setattr(run_module, "finish_run", finish_run)
    ctx = {"settings": SimpleNamespace(analysis_run_ttl_seconds=3600)}

    with capture_logs() as logs:
        await run_module.run_analysis(ctx, uuid4())

    [entry] = [log for log in logs if log["event"] == "analysis_run_failed"]
    assert entry["exc_info"] is expects_traceback
