"""Database base model."""

from sqlalchemy.orm import DeclarativeBase


# pylint: disable=too-few-public-methods
class Base(DeclarativeBase):
    """Declarative base for SQLAlchemy models."""
