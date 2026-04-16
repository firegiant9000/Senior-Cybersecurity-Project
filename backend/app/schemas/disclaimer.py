"""Pydantic schema for the centralized disclaimer block."""

from __future__ import annotations

from pydantic import BaseModel


class DisclaimerBlock(BaseModel):
    primary_text: str
    confidence_text: str
    data_source_attribution: str
    transparency_note: str
