"""The database itself enforces the invariants, even against raw SQL that bypasses the service."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.db


async def _article(engine: AsyncEngine, slug: str = "a") -> int:
    async with engine.begin() as conn:
        result = await conn.execute(
            text("INSERT INTO articles (slug, draft_title) VALUES (:s, 'T') RETURNING id"),
            {"s": slug},
        )
        return int(result.scalar_one())


async def _version(engine: AsyncEngine, article_id: int, number: int) -> int:
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                "INSERT INTO article_versions (article_id, version_number, title, body) "
                "VALUES (:a, :n, 'T', 'B') RETURNING id"
            ),
            {"a": article_id, "n": number},
        )
        return int(result.scalar_one())


async def _publish(engine: AsyncEngine, article_id: int, version_id: int) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE articles SET status='published', current_published_version_id=:v, "
                "published_at=clock_timestamp() WHERE id=:a"
            ),
            {"v": version_id, "a": article_id},
        )


async def test_update_of_a_snapshot_is_rejected(engine: AsyncEngine) -> None:
    article_id = await _article(engine)
    await _version(engine, article_id, 1)
    with pytest.raises(DBAPIError, match="immutable"):
        async with engine.begin() as conn:
            await conn.execute(text("UPDATE article_versions SET title='changed'"))


async def test_truncate_of_snapshots_alone_is_refused_by_the_foreign_key(
    engine: AsyncEngine,
) -> None:
    # PostgreSQL itself refuses to truncate a table that another table references.
    with pytest.raises(DBAPIError, match="referenced in a foreign key"):
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE article_versions"))


async def test_truncate_of_both_tables_is_rejected_without_the_reset_setting(
    engine: AsyncEngine,
) -> None:
    # Listing both tables gets past the foreign-key rule, so the trigger is what stops it.
    with pytest.raises(DBAPIError, match="cannot be truncated"):
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE articles, article_versions"))


async def test_truncate_is_allowed_only_inside_the_reset_transaction(
    engine: AsyncEngine,
) -> None:
    article_id = await _article(engine)
    await _version(engine, article_id, 1)
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL docs.allow_reset = 'on'"))
        await conn.execute(text("TRUNCATE articles, article_versions RESTART IDENTITY"))
    # The setting was local to that transaction, so the guard is back on afterwards.
    with pytest.raises(DBAPIError, match="cannot be truncated"):
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE articles, article_versions"))


@pytest.mark.parametrize(
    "set_clause",
    [
        "status='published'",  # no pointer and no published_at
        "status='published', published_at=clock_timestamp()",  # no pointer
        "status='unpublished'",
    ],
)
async def test_published_status_needs_a_pointer_and_a_time(
    engine: AsyncEngine, set_clause: str
) -> None:
    article_id = await _article(engine)
    with pytest.raises(IntegrityError, match="articles_publish_consistency"):
        async with engine.begin() as conn:
            await conn.execute(
                text(f"UPDATE articles SET {set_clause} WHERE id=:a"),  # noqa: S608
                {"a": article_id},
            )


async def test_a_published_article_cannot_return_to_draft(engine: AsyncEngine) -> None:
    article_id = await _article(engine)
    version_id = await _version(engine, article_id, 1)
    await _publish(engine, article_id, version_id)
    with pytest.raises(DBAPIError):
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE articles SET status='draft', current_published_version_id=NULL, "
                    "published_at=NULL WHERE id=:a"
                ),
                {"a": article_id},
            )


async def test_the_pointer_and_published_at_cannot_be_cleared(engine: AsyncEngine) -> None:
    article_id = await _article(engine)
    version_id = await _version(engine, article_id, 1)
    await _publish(engine, article_id, version_id)
    with pytest.raises(DBAPIError):
        async with engine.begin() as conn:
            await conn.execute(
                text("UPDATE articles SET current_published_version_id=NULL WHERE id=:a"),
                {"a": article_id},
            )


async def test_published_at_cannot_change_once_set(engine: AsyncEngine) -> None:
    article_id = await _article(engine)
    version_id = await _version(engine, article_id, 1)
    await _publish(engine, article_id, version_id)
    with pytest.raises(DBAPIError, match="published_at cannot change"):
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE articles SET published_at = published_at + interval '1 day' WHERE id=:a"
                ),
                {"a": article_id},
            )


async def test_the_pointer_cannot_move_to_a_lower_version_number(engine: AsyncEngine) -> None:
    article_id = await _article(engine)
    v1 = await _version(engine, article_id, 1)
    v2 = await _version(engine, article_id, 2)
    await _publish(engine, article_id, v2)
    with pytest.raises(DBAPIError, match="only move forward"):
        async with engine.begin() as conn:
            await conn.execute(
                text("UPDATE articles SET current_published_version_id=:v WHERE id=:a"),
                {"v": v1, "a": article_id},
            )


async def test_the_slug_cannot_change(engine: AsyncEngine) -> None:
    article_id = await _article(engine)
    with pytest.raises(DBAPIError, match="slug cannot be changed"):
        async with engine.begin() as conn:
            await conn.execute(
                text("UPDATE articles SET slug='other' WHERE id=:a"), {"a": article_id}
            )


async def test_the_pointer_cannot_target_another_articles_version(engine: AsyncEngine) -> None:
    first = await _article(engine, "first")
    second = await _article(engine, "second")
    foreign_version = await _version(engine, second, 1)
    with pytest.raises(IntegrityError, match="articles_current_version_fk"):
        await _publish(engine, first, foreign_version)


async def test_the_live_version_cannot_be_deleted(engine: AsyncEngine) -> None:
    article_id = await _article(engine)
    version_id = await _version(engine, article_id, 1)
    await _publish(engine, article_id, version_id)
    with pytest.raises(IntegrityError, match="articles_current_version_fk"):
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM article_versions WHERE id=:v"), {"v": version_id})
