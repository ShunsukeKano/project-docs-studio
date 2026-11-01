"""A failure after any step of Publish leaves the article and its snapshots exactly as before."""

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.db.session import create_session_factory
from app.domains.articles import repository, service
from app.domains.articles.schemas import ArticleCreate

# The repository functions Publish calls, in order. A failure is injected right after each one.
STEPS = [
    "lock_article_for_publish",
    "increment_version_counter",
    "insert_snapshot",
    "mark_published",
]


class InjectedFailure(RuntimeError):
    pass


async def state(engine: AsyncEngine, article_id: int) -> dict[str, Any]:
    async with engine.connect() as conn:
        article = (
            await conn.execute(
                text(
                    "SELECT status, current_published_version_id, published_at, draft_version, "
                    "last_version_number FROM articles WHERE id = :a"
                ),
                {"a": article_id},
            )
        ).one()
        versions = (
            await conn.execute(
                text(
                    "SELECT id, version_number FROM article_versions WHERE article_id = :a "
                    "ORDER BY id"
                ),
                {"a": article_id},
            )
        ).all()
    return {"article": tuple(article), "versions": [tuple(v) for v in versions]}


def fail_after(name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    original: Callable[..., Awaitable[Any]] = getattr(repository, name)

    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        await original(*args, **kwargs)
        raise InjectedFailure(name)

    monkeypatch.setattr(repository, name, wrapper)


@pytest.fixture
def sessions(engine: AsyncEngine) -> async_sessionmaker[Any]:
    return create_session_factory(engine)


async def new_article(sessions: async_sessionmaker[Any]) -> int:
    async with sessions() as session:
        created = await service.create_article(
            session, ArticleCreate(title="Title", slug="atomic", body="Body")
        )
    return created.id


@pytest.mark.parametrize("step", STEPS)
async def test_a_first_publish_that_fails_changes_nothing(
    step: str,
    engine: AsyncEngine,
    sessions: async_sessionmaker[Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    article_id = await new_article(sessions)
    before = await state(engine, article_id)

    fail_after(step, monkeypatch)
    async with sessions() as session:
        with pytest.raises(InjectedFailure):
            await service.publish_article(session, article_id, expected_draft_version=1)

    assert await state(engine, article_id) == before


@pytest.mark.parametrize("step", STEPS)
async def test_a_republish_that_fails_changes_nothing(
    step: str,
    engine: AsyncEngine,
    sessions: async_sessionmaker[Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    article_id = await new_article(sessions)
    async with sessions() as session:
        await service.publish_article(session, article_id, expected_draft_version=1)
    async with sessions() as session:
        from app.domains.articles.schemas import ArticleUpdate

        await service.update_draft(
            session, article_id, ArticleUpdate(expected_draft_version=2, body="Changed")
        )
    before = await state(engine, article_id)

    fail_after(step, monkeypatch)
    async with sessions() as session:
        with pytest.raises(InjectedFailure):
            await service.publish_article(session, article_id, expected_draft_version=3)

    assert await state(engine, article_id) == before
