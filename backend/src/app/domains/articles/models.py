"""ORM mappings for the tables in db-automation-apply/001_schema.sql.

The schema is created by Alembic from that file, never by these classes.
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

STATUSES = ("draft", "published", "unpublished")


class Base(DeclarativeBase):
    pass


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    slug: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    draft_title: Mapped[str] = mapped_column(Text)
    draft_body: Mapped[str] = mapped_column(Text)
    draft_tags: Mapped[list[str]] = mapped_column(ARRAY(Text))
    draft_version: Mapped[int] = mapped_column(Integer)
    last_version_number: Mapped[int] = mapped_column(Integer)
    current_published_version_id: Mapped[int | None] = mapped_column(BigInteger)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ArticleVersion(Base):
    __tablename__ = "article_versions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    article_id: Mapped[int] = mapped_column(BigInteger)
    version_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
