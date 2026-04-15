"""Pydantic schemas for AI Summary Feedback."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    flag: str = Field(pattern=r"^(helpful|inaccurate|too_vague|other)$")
    comment: str | None = Field(default=None, max_length=1000)


class FeedbackResponse(BaseModel):
    id: int
    rating: int
    flag: str
    comment: str | None
    created_at: str
