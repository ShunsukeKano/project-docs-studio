"""Field rules for the article schemas (the constraints quoted in the API contract)."""

import pytest
from pydantic import ValidationError

from app.domains.articles.schemas import ArticleCreate, ArticleUpdate


def create(**overrides: object) -> ArticleCreate:
    data: dict[str, object] = {"title": "A title", "slug": "a-title"}
    data.update(overrides)
    return ArticleCreate.model_validate(data)


class TestTitle:
    def test_is_trimmed(self) -> None:
        assert create(title="  Hello  ").title == "Hello"

    @pytest.mark.parametrize("title", ["", "   ", "\n\t"])
    def test_cannot_be_empty_or_only_whitespace(self, title: str) -> None:
        with pytest.raises(ValidationError):
            create(title=title)

    def test_at_most_200_characters(self) -> None:
        assert create(title="x" * 200)
        with pytest.raises(ValidationError):
            create(title="x" * 201)


class TestSlug:
    @pytest.mark.parametrize("slug", ["a", "getting-started", "v2-guide", "a1-b2-c3", "x" * 100])
    def test_accepts_lowercase_words_joined_by_single_hyphens(self, slug: str) -> None:
        assert create(slug=slug).slug == slug

    @pytest.mark.parametrize(
        "slug",
        [
            "",
            "Upper",
            "-lead",
            "trail-",
            "double--hyphen",
            "has space",
            "under_score",
            "\u65e5\u672c\u8a9e",
            "x" * 101,
        ],
    )
    def test_rejects_anything_else(self, slug: str) -> None:
        with pytest.raises(ValidationError):
            create(slug=slug)


class TestTags:
    def test_are_trimmed_lowercased_and_deduplicated_keeping_order(self) -> None:
        tags = create(tags=[" Python ", "API", "python", "api", "Docs"]).tags
        assert tags == ["python", "api", "docs"]

    def test_default_to_an_empty_list(self) -> None:
        assert create().tags == []

    def test_at_most_10_items(self) -> None:
        assert create(tags=[f"t{i}" for i in range(10)])
        with pytest.raises(ValidationError):
            create(tags=[f"t{i}" for i in range(11)])

    @pytest.mark.parametrize("tag", ["", "   ", "x" * 31])
    def test_each_is_1_to_30_characters_after_trimming(self, tag: str) -> None:
        with pytest.raises(ValidationError):
            create(tags=[tag])

    def test_30_characters_is_allowed(self) -> None:
        assert create(tags=["x" * 30]).tags == ["x" * 30]


class TestBody:
    def test_may_be_empty_in_a_draft(self) -> None:
        assert create(body="").body == ""
        assert create().body == ""

    def test_at_most_100000_characters(self) -> None:
        assert create(body="x" * 100_000)
        with pytest.raises(ValidationError):
            create(body="x" * 100_001)


class TestUpdate:
    def test_needs_the_expected_draft_version(self) -> None:
        with pytest.raises(ValidationError):
            ArticleUpdate.model_validate({"title": "New"})

    @pytest.mark.parametrize("version", [0, -1])
    def test_version_starts_at_1(self, version: int) -> None:
        with pytest.raises(ValidationError):
            ArticleUpdate.model_validate({"expected_draft_version": version})

    def test_the_slug_cannot_be_sent(self) -> None:
        with pytest.raises(ValidationError):
            ArticleUpdate.model_validate({"expected_draft_version": 1, "slug": "new"})

    def test_unknown_fields_are_refused(self) -> None:
        with pytest.raises(ValidationError):
            ArticleUpdate.model_validate({"expected_draft_version": 1, "status": "published"})

    def test_omitted_fields_stay_out_of_the_set_of_provided_fields(self) -> None:
        update = ArticleUpdate.model_validate({"expected_draft_version": 3, "body": ""})
        assert update.model_fields_set == {"expected_draft_version", "body"}

    def test_same_field_rules_apply(self) -> None:
        with pytest.raises(ValidationError):
            ArticleUpdate.model_validate({"expected_draft_version": 1, "title": "  "})
        update = ArticleUpdate.model_validate({"expected_draft_version": 1, "tags": [" A ", "a"]})
        assert update.tags == ["a"]
