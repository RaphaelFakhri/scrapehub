"""Book schema for books.toscrape.com."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

_RATING_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
}


class Book(BaseModel):
    """A catalogue book with validated price/rating/availability."""

    title: str = Field(min_length=1)
    price: float = Field(ge=0, description="Price in GBP, currency stripped.")
    currency: str = Field(default="GBP", min_length=1, max_length=8)
    rating: int = Field(ge=0, le=5, description="Star rating 0-5.")
    availability: str = Field(min_length=1)
    in_stock: bool = True
    url: str = Field(min_length=1)

    @field_validator("title", "availability", mode="before")
    @classmethod
    def _strip(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("rating", mode="before")
    @classmethod
    def _coerce_rating(cls, value: object) -> object:
        """Accept word ratings ('Three') as produced by the site markup."""
        if isinstance(value, str):
            key = value.strip().lower()
            if key in _RATING_WORDS:
                return _RATING_WORDS[key]
        return value
