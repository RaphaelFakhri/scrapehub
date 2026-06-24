"""Quote schema for quotes.toscrape.com (static / js / scroll)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class Quote(BaseModel):
    """A quote with author and de-duplicated, normalized tags."""

    text: str = Field(min_length=1)
    author: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)

    @field_validator("text", "author", mode="before")
    @classmethod
    def _strip(cls, value: object) -> object:
        if isinstance(value, str):
            # The site wraps quote text in typographic quotes; trim those too.
            return value.strip().strip("“”‘’").strip()
        return value

    @field_validator("tags", mode="before")
    @classmethod
    def _normalize_tags(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        seen: set[str] = set()
        result: list[str] = []
        for tag in value:
            if not isinstance(tag, str):
                continue
            cleaned = tag.strip().lower()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                result.append(cleaned)
        return result
