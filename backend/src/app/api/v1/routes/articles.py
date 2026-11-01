"""Writer routes for articles (create, edit, list). The router-level login is added in main.py."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import error_responses
from app.db.session import get_session
from app.domains.articles import service
from app.domains.articles.schemas import (
    ArticleCreate,
    ArticleDetail,
    ArticleStatus,
    ArticleSummary,
    ArticleUpdate,
    ExpectedVersion,
    PublishResult,
    VersionDetail,
    VersionSummary,
)

router = APIRouter(tags=["writer"])

Session = Annotated[AsyncSession, Depends(get_session)]
ArticleId = Annotated[int, Path(ge=1, le=2**63 - 1)]
VersionNumber = Annotated[int, Path(ge=1, le=2**31 - 1)]


async def existing_article_id(id: ArticleId, session: Session) -> int:  # noqa: A002
    """Answer 404 for a missing article before the body is checked, so 404 comes before 422."""
    await service.require_article(session, id)
    return id


@router.post(
    "/articles",
    operation_id="createArticle",
    summary="Create an article (a never-published draft)",
    status_code=201,
    response_model=ArticleDetail,
    responses=error_responses(409, 422),
)
async def create_article(
    data: ArticleCreate, response: Response, session: Session
) -> ArticleDetail:
    article = await service.create_article(session, data)
    response.headers["Location"] = f"/api/v1/articles/{article.id}"
    return article


@router.get(
    "/articles",
    operation_id="listArticles",
    summary="List all articles in any state, newest change first",
    response_model=list[ArticleSummary],
    responses=error_responses(422),
)
async def list_articles(
    session: Session,
    status: ArticleStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ArticleSummary]:
    return await service.list_articles(session, status=status, limit=limit, offset=offset)


@router.get(
    "/articles/{id}",
    operation_id="getArticle",
    summary="Get one article, including its draft",
    response_model=ArticleDetail,
    responses=error_responses(404),
)
async def get_article(session: Session, id: ArticleId) -> ArticleDetail:  # noqa: A002
    return await service.get_article(session, id)


@router.patch(
    "/articles/{id}",
    operation_id="updateArticle",
    summary="Partially update the draft",
    response_model=ArticleDetail,
    responses=error_responses(404, 409, 422),
)
async def update_article(
    data: ArticleUpdate,
    session: Session,
    id: Annotated[int, Depends(existing_article_id)],  # noqa: A002
) -> ArticleDetail:
    return await service.update_draft(session, id, data)


@router.post(
    "/articles/{id}/publish",
    operation_id="publishArticle",
    summary="Publish the draft",
    status_code=201,
    response_model=PublishResult,
    responses={
        **error_responses(404, 409, 422),
        200: {"model": PublishResult, "description": "The draft equals the live snapshot."},
    },
)
async def publish_article(
    data: ExpectedVersion,
    response: Response,
    session: Session,
    id: Annotated[int, Depends(existing_article_id)],  # noqa: A002
) -> PublishResult:
    result = await service.publish_article(session, id, data.expected_draft_version)
    # 201 when a snapshot was created, 200 when the draft already equalled the live one.
    response.status_code = 201 if result.created else 200
    return result


@router.post(
    "/articles/{id}/unpublish",
    operation_id="unpublishArticle",
    summary="Take a published article down",
    response_model=ArticleDetail,
    responses=error_responses(404, 409),
)
async def unpublish_article(
    session: Session,
    id: ArticleId,  # noqa: A002
) -> ArticleDetail:
    return await service.unpublish_article(session, id)


@router.get(
    "/articles/{id}/versions",
    operation_id="listVersions",
    summary="Version history, newest first (without the body)",
    response_model=list[VersionSummary],
    responses=error_responses(404),
)
async def list_versions(session: Session, id: ArticleId) -> list[VersionSummary]:  # noqa: A002
    return await service.list_versions(session, id)


@router.get(
    "/articles/{id}/versions/{n}",
    operation_id="getVersion",
    summary="Full content of one snapshot",
    response_model=VersionDetail,
    responses=error_responses(404),
)
async def get_version(
    session: Session,
    id: ArticleId,  # noqa: A002
    n: VersionNumber,
) -> VersionDetail:
    return await service.get_version(session, id, n)


@router.delete(
    "/articles/{id}/versions/{n}",
    operation_id="deleteVersion",
    summary="Delete a snapshot that is not protected",
    status_code=204,
    responses=error_responses(404, 409),
)
async def delete_version(
    session: Session,
    id: ArticleId,  # noqa: A002
    n: VersionNumber,
) -> Response:
    await service.delete_version(session, id, n)
    return Response(status_code=204)


@router.post(
    "/articles/{id}/versions/{n}/restore",
    operation_id="restoreVersion",
    summary="Copy a snapshot into the draft",
    response_model=ArticleDetail,
    responses=error_responses(404, 409, 422),
)
async def restore_version(
    data: ExpectedVersion,
    session: Session,
    id: Annotated[int, Depends(existing_article_id)],  # noqa: A002
    n: VersionNumber,
) -> ArticleDetail:
    return await service.restore_version(session, id, n, data.expected_draft_version)
