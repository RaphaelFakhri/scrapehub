"""Story schema for Hacker News Firebase API items."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class Story(BaseModel):
    """A Hacker News story item."""

    id: int = Field(gt=0)
    title: str = Field(min_length=1)
    by: str = Field(default="", description="Author username.")
    score: int = Field(default=0, ge=0)
    descendants: int = Field(default=0, ge=0, description="Comment count.")
    time: int = Field(default=0, ge=0, description="Unix epoch seconds.")
    url: str | None = None

    @field_validator("title", "by", mode="before")
    @classmethod
    def _strip(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("url", mode="before")
    @classmethod
    def _empty_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value
