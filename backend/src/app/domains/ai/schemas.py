"""Input and output of the AI operations. The output follows the normal article rules."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.domains.articles.schemas import Tags, Title

# Notes: the text already in the body, up to 5,000 characters. Instructions: up to 1,000.
Notes = Annotated[str, Field(max_length=5000)]
Instructions = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]


class AiDraftRequest(BaseModel):
    """What the writer has already entered: the AI writes the body from it."""

    model_config = ConfigDict(extra="forbid")

    title: Title
    tags: Tags = Field(default_factory=list)
    notes: Notes = ""
    instructions: Instructions | None = None


class AiStatus(BaseModel):
    enabled: bool
