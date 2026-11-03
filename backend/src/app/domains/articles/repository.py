"""Thin data access: SQL only, no business rules, no commits."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any, NamedTuple

from sqlalchemy import Row, insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.articles.models import Article, ArticleVersion


async def insert_article(
    session: AsyncSession, *, slug: str, title: str, body: str, tags: list[str]
) -> int:
    """Insert a new draft. A taken slug raises an IntegrityError (SQLSTATE 23505)."""
    # Only these columns are listed, so the database fills in the rest from its defaults.
    statement = (
        insert(Article)
        .values(slug=slug, draft_title=title, draft_body=body, draft_tags=tags)
        .returning(Article.id)
    )
    return (await session.execute(statement)).scalar_one()


async def get_article_with_live_number(
    session: AsyncSession, article_id: int
) -> tuple[Article, int | None] | None:
    statement = (
        select(Article, ArticleVersion.version_number)
        .outerjoin(ArticleVersion, ArticleVersion.id == Article.current_published_version_id)
        .where(Article.id == article_id)
        .execution_options(populate_existing=True)
    )
    row = (await session.execute(statement)).one_or_none()
    return (row[0], row[1]) if row else None


async def article_exists(session: AsyncSession, article_id: int) -> bool:
    return (
        await session.execute(select(Article.id).where(Article.id == article_id))
    ).scalar_one_or_none() is not None


async def list_articles(
    session: AsyncSession, *, status: str | None, limit: int, offset: int
) -> Sequence[Article]:
    statement = select(Article).order_by(Article.updated_at.desc(), Article.id.desc())
    if status is not None:
        statement = statement.where(Article.status == status)
    return (await session.scalars(statement.limit(limit).offset(offset))).all()


async def taken_slugs(session: AsyncSession, prefix: str) -> set[str]:
    """Every stored slug that starts with the prefix (slugs hold only a-z, 0-9 and hyphens)."""
    statement = select(Article.slug).where(Article.slug.startswith(prefix))
    return set((await session.scalars(statement)).all())


async def update_draft_if_current(
    session: AsyncSession, article_id: int, expected_version: int, changes: dict[str, Any]
) -> int | None:
    """Apply the edit only if the draft is still at the expected version.

    This is the optimistic-concurrency check, in one statement: the WHERE clause matches only
    while `draft_version` equals the version the writer loaded, and the same statement bumps it.
    Two edits cannot both match, so the second one changes nothing instead of overwriting.
    Returns the new draft version, or None when no row matched (missing article or stale version).
    """
    statement = (
        update(Article)
        .where(Article.id == article_id, Article.draft_version == expected_version)
        .values(**changes, draft_version=Article.draft_version + 1)
        .returning(Article.draft_version)
        .execution_options(synchronize_session=False)
    )
    return (await session.execute(statement)).scalar_one_or_none()


async def current_draft_version(session: AsyncSession, article_id: int) -> int | None:
    statement = select(Article.draft_version).where(Article.id == article_id)
    return (await session.execute(statement)).scalar_one_or_none()


class PublishTarget(NamedTuple):
    """The article row under lock, with the live snapshot's content (None if never published)."""

    id: int
    status: str
    draft_title: str
    draft_body: str
    draft_tags: list[str]
    draft_version: int
    published_at: datetime | None
    live_version_number: int | None
    live_title: str | None
    live_body: str | None
    live_tags: list[str] | None


async def lock_article_for_publish(session: AsyncSession, article_id: int) -> PublishTarget | None:
    """Lock the article row until the transaction ends, and read it with its live snapshot.

    FOR UPDATE makes Publish, Unpublish and delete of a version take turns on one article. The
    lock order is always the article row first, then version rows, so they cannot deadlock.
    """
    result = await session.execute(
        text(
            "SELECT a.id, a.status, a.draft_title, a.draft_body, a.draft_tags, a.draft_version, "
            "       a.published_at, v.version_number, v.title, v.body, v.tags "
            "FROM articles a "
            "LEFT JOIN article_versions v ON v.id = a.current_published_version_id "
            "WHERE a.id = :id FOR UPDATE OF a"
        ),
        {"id": article_id},
    )
    row = result.one_or_none()
    return PublishTarget(*row) if row else None


async def increment_version_counter(session: AsyncSession, article_id: int) -> int:
    """Take the next snapshot number. The counter only goes up, so numbers are never reused."""
    result = await session.execute(
        text(
            "UPDATE articles SET last_version_number = last_version_number + 1 "
            "WHERE id = :id RETURNING last_version_number"
        ),
        {"id": article_id},
    )
    return int(result.scalar_one())


async def insert_snapshot(
    session: AsyncSession,
    *,
    article_id: int,
    version_number: int,
    title: str,
    body: str,
    tags: list[str],
) -> int:
    statement = (
        insert(ArticleVersion)
        .values(
            article_id=article_id, version_number=version_number, title=title, body=body, tags=tags
        )
        .returning(ArticleVersion.id)
    )
    return (await session.execute(statement)).scalar_one()


class Published(NamedTuple):
    status: str
    published_at: datetime
    draft_version: int


async def mark_published(session: AsyncSession, article_id: int, version_id: int) -> Published:
    """Point the article at the new snapshot. published_at is set only if it was never set.

    Status, pointer and published_at change in this one statement, which is what keeps them
    consistent. COALESCE keeps the first publication time on a republish. clock_timestamp() is the
    time of the statement itself, so a request that waited for the lock is not given an earlier
    time.
    """
    result = await session.execute(
        text(
            "UPDATE articles SET status = 'published', current_published_version_id = :version, "
            "       published_at = COALESCE(published_at, clock_timestamp()), "
            "       draft_version = draft_version + 1 "
            "WHERE id = :id RETURNING status, published_at, draft_version"
        ),
        {"id": article_id, "version": version_id},
    )
    return Published(*result.one())


async def list_public(session: AsyncSession, *, limit: int, offset: int) -> Sequence[Row[Any]]:
    """Published articles, one statement: title and tags come from the live snapshot only."""
    result = await session.execute(
        text(
            "SELECT a.slug, v.title, v.tags, a.published_at, "
            "       CASE WHEN v.version_number >= 2 THEN v.created_at END AS updated_at "
            "FROM articles a "
            "JOIN article_versions v ON v.id = a.current_published_version_id "
            "WHERE a.status = 'published' "
            "ORDER BY a.published_at DESC, a.id DESC "
            "LIMIT :limit OFFSET :offset"
        ),
        {"limit": limit, "offset": offset},
    )
    return result.all()


async def get_public(session: AsyncSession, slug: str) -> Row[Any] | None:
    """One published article, one statement, so title and body come from the same snapshot."""
    result = await session.execute(
        text(
            "SELECT a.slug, v.title, v.tags, v.body, a.published_at, "
            "       v.created_at AS live_created_at "
            "FROM articles a "
            "JOIN article_versions v ON v.id = a.current_published_version_id "
            "WHERE a.slug = :slug AND a.status = 'published'"
        ),
        {"slug": slug},
    )
    return result.one_or_none()


async def set_unpublished(session: AsyncSession, article_id: int) -> None:
    await session.execute(
        update(Article).where(Article.id == article_id).values(status="unpublished")
    )


async def list_versions(session: AsyncSession, article_id: int) -> Sequence[Row[Any]]:
    result = await session.execute(
        text(
            "SELECT v.id, v.version_number, v.title, v.created_at, "
            "       (v.id = a.current_published_version_id) AS is_live "
            "FROM article_versions v JOIN articles a ON a.id = v.article_id "
            "WHERE v.article_id = :id ORDER BY v.version_number DESC"
        ),
        {"id": article_id},
    )
    return result.all()


async def get_version(session: AsyncSession, article_id: int, number: int) -> Row[Any] | None:
    result = await session.execute(
        text(
            "SELECT v.id, v.version_number, v.title, v.body, v.tags, v.created_at, "
            "       (v.id = a.current_published_version_id) AS is_live "
            "FROM article_versions v JOIN articles a ON a.id = v.article_id "
            "WHERE v.article_id = :id AND v.version_number = :n"
        ),
        {"id": article_id, "n": number},
    )
    return result.one_or_none()


async def restore_into_draft(
    session: AsyncSession, article_id: int, number: int, expected_version: int
) -> int | None:
    """Copy a snapshot's title, body and tags into the draft, in one statement.

    It touches no snapshot and never changes the status, the pointer or published_at.
    Only `articles` is written; `article_versions` is only read (the FROM clause), so the history
    cannot be damaged. The expected-version condition stops it overwriting a newer edit.
    Returns the new draft version, or None when nothing matched.
    """
    result = await session.execute(
        text(
            "UPDATE articles SET draft_title = v.title, draft_body = v.body, "
            "       draft_tags = v.tags, draft_version = articles.draft_version + 1 "
            "FROM article_versions v "
            "WHERE articles.id = :id AND v.article_id = :id AND v.version_number = :n "
            "  AND articles.draft_version = :expected "
            "RETURNING articles.draft_version"
        ),
        {"id": article_id, "n": number, "expected": expected_version},
    )
    return result.scalar_one_or_none()


async def delete_version(session: AsyncSession, article_id: int, number: int) -> bool:
    """Delete one snapshot. The service checks for the live version first; as a second line of
    defence the foreign key (ON DELETE RESTRICT) makes the database refuse to delete a snapshot
    the article still points at, even if that check were skipped by a bug."""
    result = await session.execute(
        text(
            "DELETE FROM article_versions WHERE article_id = :id AND version_number = :n "
            "RETURNING id"
        ),
        {"id": article_id, "n": number},
    )
    return result.scalar_one_or_none() is not None


async def set_published(session: AsyncSession, article_id: int) -> None:
    """Put an unpublished article back to published, keeping its pointer and published_at."""
    await session.execute(
        update(Article).where(Article.id == article_id).values(status="published")
    )
