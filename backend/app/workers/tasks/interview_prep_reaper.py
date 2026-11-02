"""준비 job 없이 preparing 으로 남은 면접을 다시 큐에 등록한다. 실행 중인 준비는 건드리지 않는다."""

from datetime import UTC, datetime, timedelta
from typing import Any

from arq.connections import ArqRedis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.db.models import InterviewSession
from app.features.interview.queue import enqueue_interview_prep


async def recover_unqueued_preparations(
    sessions: async_sessionmaker[AsyncSession],
    redis: ArqRedis,
    *,
    min_age_seconds: int,
    now: datetime | None = None,
) -> int:
    """오래된 미착수 preparing 면접을 재등록하고 등록을 확인한 개수를 돌려준다."""
    cutoff = (now or datetime.now(UTC)) - timedelta(seconds=min_age_seconds)
    async with sessions() as db:
        candidates = (
            await db.execute(
                select(InterviewSession.id, InterviewSession.context_state)
                .where(
                    InterviewSession.status == "preparing", InterviewSession.updated_at <= cutoff
                )
                .order_by(InterviewSession.updated_at)
                .limit(100)
            )
        ).all()
    registered = 0
    for interview_id, state in candidates:
        # claim 이 있으면 worker 가 잡았거나 lease 만료 reaper 의 대상이다.
        if isinstance(state, dict) and state.get("prepare_job_id") is not None:
            continue
        # 같은 _job_id 가 이미 큐·실행 중이면 새 job 이 생기지 않는다.
        if await enqueue_interview_prep(redis, interview_id):
            registered += 1
    return registered


async def interview_prep_reaper(ctx: dict[str, Any]) -> None:
    settings = ctx.get("settings") or get_settings()
    await recover_unqueued_preparations(
        ctx["session_factory"],
        ctx["redis"],
        min_age_seconds=settings.interview_prep_reaper_min_age_seconds,
    )
