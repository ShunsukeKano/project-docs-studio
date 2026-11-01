"""Public routes: readers see only the live snapshot of published articles. No login."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ErrorEnvelope
from app.db.session import get_session
from app.domains.articles import service
from app.domains.articles.schemas import PublicArticle, PublicArticleListItem

router = APIRouter(tags=["public"])

Session = Annotated[AsyncSession, Depends(get_session)]


@router.get(
    "/articles",
    operation_id="listPublicArticles",
    summary="List published articles, newest publication first",
    response_model=list[PublicArticleListItem],
    responses={422: {"model": ErrorEnvelope, "description": "Invalid paging values."}},
)
async def list_public_articles(
    session: Session,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[PublicArticleListItem]:
    return await service.list_public_articles(session, limit=limit, offset=offset)


@router.get(
    "/articles/{slug}",
    operation_id="getPublicArticle",
    summary="Read one published article (its live snapshot)",
    response_model=PublicArticle,
    responses={404: {"model": ErrorEnvelope, "description": "The same body for every miss."}},
)
async def get_public_article(slug: str, session: Session) -> PublicArticle:
    return await service.get_public_article(session, slug)
