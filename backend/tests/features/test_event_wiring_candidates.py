"""repo_recommended 이벤트 연결. task-17"""

from app.features.analysis.candidates import prepare_candidates
from tests.event_helpers import broken_events as broken_events
from tests.event_helpers import names
from tests.features.interview.factories import make_repo, make_run, make_user


async def test_repo_recommended_recorded_once_per_run(db):
    user = await make_user(db)
    run = await make_run(db, user, status="running")
    await make_repo(db, run, in_run=False)

    await prepare_candidates(db, run.id, min_size_kb=0)
    await prepare_candidates(db, run.id, min_size_kb=0)
    await db.commit()

    assert await names(db) == ["repo_recommended"]


async def test_repo_recommended_failure_does_not_block_candidate_save(db, broken_events):
    user = await make_user(db)
    run = await make_run(db, user, status="running")
    await make_repo(db, run, in_run=False)

    rows = await prepare_candidates(db, run.id, min_size_kb=0)

    await db.commit()
    assert len(rows) == 1
    assert await names(db) == []
