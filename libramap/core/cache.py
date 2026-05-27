from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


DEFAULT_CACHE_PATH = Path("data") / "cache.db"


@dataclass(frozen=True)
class CachedBook:
    isbn: str
    title: str
    creator: str
    publisher: str
    ndc: str
    fetched_at: str


class CacheManager:
    def __init__(self, cache_path: Path = DEFAULT_CACHE_PATH) -> None:
        self._cache_path = cache_path
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def get(self, isbn: str) -> CachedBook | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM ndl_cache WHERE isbn = ?", (isbn,)).fetchone()
        if not row:
            return None
        return CachedBook(
            isbn=row["isbn"],
            title=row["title"],
            creator=row["creator"],
            publisher=row["publisher"],
            ndc=row["ndc"],
            fetched_at=row["fetched_at"],
        )

    def set(self, isbn: str, title: str, creator: str, ndc: str, publisher: str = "") -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ndl_cache (isbn, title, creator, publisher, ndc, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(isbn) DO UPDATE SET
                    title = excluded.title,
                    creator = excluded.creator,
                    publisher = excluded.publisher,
                    ndc = excluded.ndc,
                    fetched_at = excluded.fetched_at
                """,
                (isbn, title, creator, publisher, ndc, datetime.now().isoformat(timespec="seconds")),
            )

    def clear_all(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM ndl_cache")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._cache_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ndl_cache (
                    isbn TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT '',
                    creator TEXT NOT NULL DEFAULT '',
                    publisher TEXT NOT NULL DEFAULT '',
                    ndc TEXT NOT NULL DEFAULT '',
                    fetched_at TEXT NOT NULL
                )
                """
            )
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(ndl_cache)").fetchall()
            }
            if "publisher" not in columns:
                conn.execute("ALTER TABLE ndl_cache ADD COLUMN publisher TEXT NOT NULL DEFAULT ''")
