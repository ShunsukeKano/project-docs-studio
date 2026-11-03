"""Business rules for articles. This layer owns the transaction and is the only one that commits."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    EmptyContentError,
    NotFoundError,
    NotPublishedError,
    SlugConflictError,
    VersionConflictError,
    VersionIsLiveError,
)
from app.db.session import set_lock_timeout
from app.domains.articles import repository
from app.domains.articles.models import Article
from app.domains.articles.schemas import (
    ArticleCreate,
    ArticleDetail,
    ArticleStatus,
    ArticleSummary,
    ArticleUpdate,
    PublicArticle,
    PublicArticleListItem,
    PublishResult,
    VersionDetail,
    VersionSummary,
)

MAX_SLUG_LENGTH = 100
SLUG_ATTEMPTS = 5
UNIQUE_VIOLATION = "23505"
FOREIGN_KEY_VIOLATION = "23503"


def _sqlstate(error: IntegrityError) -> str | None:
    orig = error.orig
    code = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
    cause = getattr(orig, "__cause__", None)
    code = code or getattr(cause, "sqlstate", None)
    return str(code) if code else None


def choose_slug(requested: str, taken: set[str]) -> str:
    """The requested slug if free, otherwise the smallest free `-2`, `-3`, ... suffix.

    The base is shortened so the result fits 100 characters; a hyphen left at the cut is dropped.
    """
    if requested not in taken:
        return requested
    number = 2
    while True:
        suffix = f"-{number}"
        stem = requested[: MAX_SLUG_LENGTH - len(suffix)].rstrip("-")
        candidate = stem + suffix
        if candidate not in taken:
            return candidate
        number += 1


def _to_detail(article: Article, live_version_number: int | None) -> ArticleDetail:
    return ArticleDetail(
        id=article.id,
        slug=article.slug,
        status=article.status,
        draft_title=article.draft_title,
        draft_body=article.draft_body,
        draft_tags=list(article.draft_tags),
        draft_version=article.draft_version,
        published_at=article.published_at,
        live_version_number=live_version_number,
        created_at=article.created_at,
        updated_at=article.updated_at,
    )


def _equals_live_snapshot(target: repository.PublishTarget) -> bool:
    """True when the draft is identical to the live snapshot (older snapshots never count)."""
    if target.live_version_number is None:
        return False
    return (
        target.draft_title == target.live_title
        and target.draft_body == target.live_body
        and list(target.draft_tags) == list(target.live_tags or [])
    )


async def require_article(session: AsyncSession, article_id: int) -> None:
    """Raise `not_found` if the article does not exist. Used to answer 404 before 422."""
    async with session.begin():
        if not await repository.article_exists(session, article_id):
            raise NotFoundError()


async def get_article(session: AsyncSession, article_id: int) -> ArticleDetail:
    async with session.begin():
        return await _load_detail(session, article_id)


async def _load_detail(session: AsyncSession, article_id: int) -> ArticleDetail:
    row = await repository.get_article_with_live_number(session, article_id)
    if row is None:
        raise NotFoundError()
    article, live_version_number = row
    return _to_detail(article, live_version_number)


async def create_article(session: AsyncSession, data: ArticleCreate) -> ArticleDetail:
    for _ in range(SLUG_ATTEMPTS):
        try:
            async with session.begin():
                taken = await repository.taken_slugs(session, data.slug[:90])
                article_id = await repository.insert_article(
                    session,
                    slug=choose_slug(data.slug, taken),
                    title=data.title,
                    body=data.body,
                    tags=data.tags,
                )
                return await _load_detail(session, article_id)
        except IntegrityError as error:
            if _sqlstate(error) != UNIQUE_VIOLATION:
                raise
            # Another create took the same number first; the transaction is rolled back, so retry.
    raise SlugConflictError()


async def update_draft(
    session: AsyncSession, article_id: int, data: ArticleUpdate
) -> ArticleDetail:
    """Edit the draft, but only if the writer saw its latest version (optimistic concurrency).

    Edge case: two people editing the same draft. Every edit carries `expected_draft_version`,
    the version the writer's screen was loaded from. The UPDATE in the repository matches only
    while the draft is still at that version, so a stale edit changes nothing and is reported as
    409, instead of silently overwriting the newer edit. No snapshot and no live pointer is touched.
    """
    changes: dict[str, object] = {}
    if "title" in data.model_fields_set and data.title is not None:
        changes["draft_title"] = data.title
    if "body" in data.model_fields_set and data.body is not None:
        changes["draft_body"] = data.body
    if "tags" in data.model_fields_set and data.tags is not None:
        changes["draft_tags"] = data.tags

    async with session.begin():
        new_version = await repository.update_draft_if_current(
            session, article_id, data.expected_draft_version, changes
        )
        if new_version is None:
            # No row matched: the article does not exist (404), or someone saved first (409).
            # The 409 carries the current version so the screen can offer a resubmit.
            current = await repository.current_draft_version(session, article_id)
            if current is None:
                raise NotFoundError()
            raise VersionConflictError(current)
        return await _load_detail(session, article_id)


async def list_articles(
    session: AsyncSession, *, status: ArticleStatus | None, limit: int, offset: int
) -> list[ArticleSummary]:
    async with session.begin():
        articles = await repository.list_articles(
            session, status=status, limit=limit, offset=offset
        )
        return [
            ArticleSummary(
                id=a.id,
                slug=a.slug,
                status=a.status,
                title=a.draft_title,
                draft_version=a.draft_version,
                updated_at=a.updated_at,
            )
            for a in articles
        ]


async def publish_article(
    session: AsyncSession, article_id: int, expected_draft_version: int
) -> PublishResult:
    """Publish the draft as the next numbered snapshot, all in one transaction.

    Order: lock the row (404), check the version (409), check the content (422), compare with
    the live snapshot (nothing new if equal), then write.

    Edge case: atomic Publish. The three writes at the end (bump the counter, insert the snapshot,
    point the article at it) share one transaction, so a failure or a crash anywhere rolls all of
    them back. The article can never be "published" without a snapshot, or point at an old one.
    The database backs this up with a CHECK on status, pointer and published_at, and a composite
    foreign key that only allows the article's own versions.

    Edge case: two Publish requests at once. Both take the same row lock; the second waits, then
    sees the draft version has moved and gets 409, so exactly one snapshot is created.
    """
    async with session.begin():
        await set_lock_timeout(session)  # never wait on the row lock for ever (503 instead)
        target = await repository.lock_article_for_publish(session, article_id)
        if target is None:
            raise NotFoundError()
        # Every decision below uses the locked row, never a value read before the lock.
        if target.draft_version != expected_draft_version:
            raise VersionConflictError(target.draft_version)
        if not target.draft_title.strip() or not target.draft_body.strip():
            raise EmptyContentError()

        if _equals_live_snapshot(target):
            # Nothing new to record. An unpublished article simply goes back to published.
            if target.status != "published":
                await repository.set_published(session, article_id)
            assert target.live_version_number is not None
            assert target.published_at is not None
            return PublishResult(
                created=False,
                version_number=target.live_version_number,
                status="published",
                published_at=target.published_at,
                draft_version=target.draft_version,
            )

        # The three writes below succeed or fail together (see the docstring).
        version_number = await repository.increment_version_counter(session, article_id)
        version_id = await repository.insert_snapshot(
            session,
            article_id=article_id,
            version_number=version_number,
            title=target.draft_title,
            body=target.draft_body,
            tags=list(target.draft_tags),
        )
        published = await repository.mark_published(session, article_id, version_id)
        return PublishResult(
            created=True,
            version_number=version_number,
            status=published.status,
            published_at=published.published_at,
            draft_version=published.draft_version,
        )


async def list_public_articles(
    session: AsyncSession, *, limit: int, offset: int
) -> list[PublicArticleListItem]:
    async with session.begin():
        rows = await repository.list_public(session, limit=limit, offset=offset)
        return [PublicArticleListItem.model_validate(row, from_attributes=True) for row in rows]


async def get_public_article(session: AsyncSession, slug: str) -> PublicArticle:
    """Any article that is not published (missing, never published, taken down) is `not_found`."""
    async with session.begin():
        row = await repository.get_public(session, slug)
        if row is None:
            raise NotFoundError()
        return PublicArticle.model_validate(row, from_attributes=True)


async def unpublish_article(session: AsyncSession, article_id: int) -> ArticleDetail:
    """Take a published article down. Only the status changes; nothing else is touched."""
    async with session.begin():
        await set_lock_timeout(session)
        target = await repository.lock_article_for_publish(session, article_id)
        if target is None:
            raise NotFoundError()
        if target.status != "published":
            raise NotPublishedError()
        await repository.set_unpublished(session, article_id)
        return await _load_detail(session, article_id)


async def list_versions(session: AsyncSession, article_id: int) -> list[VersionSummary]:
    async with session.begin():
        await _require_in_transaction(session, article_id)
        rows = await repository.list_versions(session, article_id)
        return [VersionSummary.model_validate(row, from_attributes=True) for row in rows]


async def get_version(session: AsyncSession, article_id: int, number: int) -> VersionDetail:
    async with session.begin():
        row = await repository.get_version(session, article_id, number)
        if row is None:
            raise NotFoundError()
        return VersionDetail.model_validate(row, from_attributes=True)


async def _require_in_transaction(session: AsyncSession, article_id: int) -> None:
    if not await repository.article_exists(session, article_id):
        raise NotFoundError()


async def restore_version(
    session: AsyncSession, article_id: int, number: int, expected_draft_version: int
) -> ArticleDetail:
    """Copy a snapshot into the draft. Nothing is published and no snapshot is touched.

    Edge case: Restore must not damage the history. It only rewrites the draft columns of the
    article (one UPDATE in the repository): it never changes, adds or deletes a snapshot, and it
    never changes the status, the live pointer or published_at. The writer has to press Publish
    explicitly for the restored text to go live. Like an edit, it checks the expected draft
    version, so it cannot overwrite a newer edit.
    """
    async with session.begin():
        new_version = await repository.restore_into_draft(
            session, article_id, number, expected_draft_version
        )
        if new_version is None:
            # Nothing matched: a missing article or snapshot is 404, otherwise the version is stale.
            if await repository.get_version(session, article_id, number) is None:
                raise NotFoundError()
            current = await repository.current_draft_version(session, article_id)
            if current is None:
                raise NotFoundError()
            raise VersionConflictError(current)
        return await _load_detail(session, article_id)


async def delete_version(session: AsyncSession, article_id: int, number: int) -> None:
    """Delete a snapshot that is not the protected (live) one.

    Edge case: the live version must never be deleted, and hiding the button is not enough, so
    the API refuses it (409 `version_is_live`). It takes the same row lock as Publish, so a delete
    and a publish never interleave: the live version is read under the lock, not before it.
    """
    try:
        async with session.begin():
            await set_lock_timeout(session)
            target = await repository.lock_article_for_publish(session, article_id)
            if target is None:
                raise NotFoundError()
            # The live version stays even after Unpublish, because the pointer is kept.
            if target.live_version_number == number:
                raise VersionIsLiveError()
            if not await repository.delete_version(session, article_id, number):
                raise NotFoundError()
    except IntegrityError as error:
        # The database refuses to delete a referenced snapshot even if the check above is bypassed.
        if _sqlstate(error) == FOREIGN_KEY_VIOLATION:
            raise VersionIsLiveError() from error
        raise
