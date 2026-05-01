"""Database connection helpers for analysis modules."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError


load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


class DatabaseConfigError(RuntimeError):
    """Raised when database configuration is missing or invalid."""


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Create a pooled SQLAlchemy engine from DATABASE_URL."""

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise DatabaseConfigError("DATABASE_URL is not set in .env or environment")

    try:
        return create_engine(
            database_url,
            pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
            pool_pre_ping=True,
            pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),
            future=True,
        )
    except SQLAlchemyError as exc:
        logger.exception("Failed to create SQLAlchemy engine")
        raise DatabaseConfigError(str(exc)) from exc


def get_df(sql: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
    """Run SQL and return the result as a DataFrame."""

    try:
        with get_engine().connect() as conn:
            return pd.read_sql_query(text(sql), conn, params=params or {})
    except SQLAlchemyError as exc:
        logger.exception("Database query failed")
        raise RuntimeError(f"Database query failed: {exc}") from exc


def get_scalar(sql: str, params: dict[str, Any] | None = None) -> Any:
    """Run SQL and return a single scalar value."""

    try:
        with get_engine().connect() as conn:
            return conn.execute(text(sql), params or {}).scalar_one_or_none()
    except SQLAlchemyError as exc:
        logger.exception("Database scalar query failed")
        raise RuntimeError(f"Database scalar query failed: {exc}") from exc
