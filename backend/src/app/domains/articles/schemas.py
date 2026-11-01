"""Input and output schemas for articles. The limits quote the API contract."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
)

ArticleStatus = Literal["draft", "published", "unpublished"]


def _normalize_tags(tags: list[str]) -> list[str]:
    """Trim and lowercase each tag, then drop duplicates while keeping the first occurrence."""
    seen: dict[str, None] = {}
    for tag in tags:
        seen.setdefault(tag, None)
    return list(seen)


# Title: 1 to 200 characters after trimming.
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
# Slug: ^[a-z0-9]+(-[a-z0-9]+)*$, 1 to 100 characters.
Slug = Annotated[
    str, StringConstraints(min_length=1, max_length=100, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
]
# Body: at most 100,000 characters; may be empty in a draft.
Body = Annotated[str, Field(max_length=100_000)]
# Tags: at most 10 items; each 1 to 30 characters, trimmed, lowercased, no duplicates (order kept).
Tag = Annotated[
    str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=1, max_length=30)
]
Tags = Annotated[list[Tag], Field(max_length=10), AfterValidator(_normalize_tags)]
# draft_version starts at 1 and never goes below 1.
DraftVersion = Annotated[int, Field(ge=1)]


class ArticleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    slug: Slug
    body: Body = ""
    tags: Tags = Field(default_factory=list)


class ArticleUpdate(BaseModel):
    """A partial edit: omitted fields keep their value. There is no slug field on purpose."""

    model_config = ConfigDict(extra="forbid")

    expected_draft_version: DraftVersion
    title: Title | None = None
    body: Body | None = None
    tags: Tags | None = None


class ArticleSummary(BaseModel):
    id: int
    slug: str
    status: ArticleStatus
    title: str
    draft_version: int
    updated_at: datetime


class ArticleDetail(BaseModel):
    id: int
    slug: str
    status: ArticleStatus
    draft_title: str
    draft_body: str
    draft_tags: list[str]
    draft_version: int
    published_at: datetime | None
    live_version_number: int | None
    created_at: datetime
    updated_at: datetime


class ExpectedVersion(BaseModel):
    """The body of the operations that must be based on the draft the writer was looking at."""

    model_config = ConfigDict(extra="forbid")

    expected_draft_version: DraftVersion


class PublishResult(BaseModel):
    created: bool
    version_number: int
    status: ArticleStatus
    published_at: datetime
    draft_version: int


class PublicArticleListItem(BaseModel):
    """What a reader sees in the list. Nothing else is serialized (an allow-list)."""

    slug: str
    title: str
    tags: list[str]
    published_at: datetime
    updated_at: datetime | None


class PublicArticle(BaseModel):
    slug: str
    title: str
    tags: list[str]
    body: str
    published_at: datetime
    live_created_at: datetime


class VersionSummary(BaseModel):
    """One row of the history: no body. `is_live` marks the protected snapshot."""

    id: int
    version_number: int
    title: str
    created_at: datetime
    is_live: bool


class VersionDetail(BaseModel):
    id: int
    version_number: int
    title: str
    body: str
    tags: list[str]
    created_at: datetime
    is_live: bool
