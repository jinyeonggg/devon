"""repo_selected 이벤트 연결. task-17"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from tests.event_helpers import broken_events as broken_events
from tests.event_helpers import names

from .factories import make_repo, make_run, make_user
from .test_service import FakeRedis, _create


async def test_repo_selected_recorded_once_per_created_interview(db: AsyncSession) -> None:
    run, repos = await _selectable(db)

    await _create(db, run, [r.id for r in repos])
    try:
        await _create(db, run, [r.id for r in repos])  # 진행 중 면접이 있어 거부된다
    except AppError:
        pass

    assert await names(db) == ["repo_selected"]


async def test_repo_selected_not_recorded_when_enqueue_fails(db: AsyncSession) -> None:
    run, repos = await _selectable(db)

    try:
        await _create(db, run, [r.id for r in repos], FakeRedis(fail=True))
    except AppError:
        pass

    assert await names(db) == []


async def test_repo_selected_failure_does_not_block_create(db: AsyncSession, broken_events) -> None:
    run, repos = await _selectable(db)

    interview_id, session_id = await _create(db, run, [r.id for r in repos])

    assert interview_id and session_id
    assert await names(db) == []


async def _selectable(db: AsyncSession):
    run = await make_run(db, await make_user(db))
    return run, [await make_repo(db, run), await make_repo(db, run)]
