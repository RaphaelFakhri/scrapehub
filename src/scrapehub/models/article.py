"""Article schema for Wikipedia REST API page summaries."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class Article(BaseModel):
    """A Wikipedia page summary."""

    title: str = Field(min_length=1)
    extract: str = Field(default="")
    description: str | None = None
    url: str = Field(min_length=1)
    lang: str = Field(default="en", min_length=2, max_length=8)

    @field_validator("title", "extract", mode="before")
    @classmethod
    def _strip(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value
