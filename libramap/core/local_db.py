from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


DEFAULT_DB_PATH = Path("data") / "libramap.db"


@dataclass(frozen=True)
class BookRecord:
    isbn: str
    title: str = ""
    creator: str = ""
    publisher: str = ""
    ndc: str = ""
    shelf_code: str = ""
    floor: str = ""
    is_restricted: bool = False
    is_active: bool = True
    notes: str = ""


class LocalBookDatabase:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        self._seed_if_empty()

    def find_by_isbn(self, isbn: str) -> BookRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM books WHERE isbn = ?", (isbn,)).fetchone()
        return self._row_to_record(row) if row else None

    def upsert(self, record: BookRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO books (
                    isbn, title, creator, publisher, ndc, shelf_code, floor,
                    is_restricted, is_active, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(isbn) DO UPDATE SET
                    title = excluded.title,
                    creator = excluded.creator,
                    publisher = excluded.publisher,
                    ndc = excluded.ndc,
                    shelf_code = excluded.shelf_code,
                    floor = excluded.floor,
                    is_restricted = excluded.is_restricted,
                    is_active = excluded.is_active,
                    notes = excluded.notes
                """,
                (
                    record.isbn,
                    record.title,
                    record.creator,
                    record.publisher,
                    record.ndc,
                    record.shelf_code,
                    record.floor,
                    int(record.is_restricted),
                    int(record.is_active),
                    record.notes,
                ),
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS books (
                    isbn TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT '',
                    creator TEXT NOT NULL DEFAULT '',
                    publisher TEXT NOT NULL DEFAULT '',
                    ndc TEXT NOT NULL DEFAULT '',
                    shelf_code TEXT NOT NULL DEFAULT '',
                    floor TEXT NOT NULL DEFAULT '',
                    is_restricted INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    notes TEXT NOT NULL DEFAULT ''
                )
                """
            )

    def _seed_if_empty(self) -> None:
        with self._connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
        if count:
            return

        for record in [
            BookRecord(
                isbn="9784820414131",
                title="日本十進分類法 新訂10版",
                creator="日本図書館協会分類委員会",
                publisher="日本図書館協会",
                ndc="014.4",
                shelf_code="A-01",
                floor="1f",
                is_restricted=True,
                notes="参考図書",
            ),
            BookRecord(
                isbn="9784003310212",
                title="学問のすすめ",
                creator="福沢諭吉",
                publisher="岩波書店",
                ndc="150",
                shelf_code="A-01",
                floor="1f",
            ),
            BookRecord(
                isbn="9784101010113",
                title="吾輩は猫である",
                creator="夏目漱石",
                publisher="新潮社",
                ndc="913.6",
                shelf_code="B-12",
                floor="2f",
            ),
            BookRecord(
                isbn="9784101010151",
                title="人間失格",
                creator="太宰治",
                publisher="新潮社",
                ndc="913.6",
                shelf_code="B-12",
                floor="2f",
            ),
        ]:
            self.upsert(record)

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> BookRecord:
        return BookRecord(
            isbn=row["isbn"],
            title=row["title"],
            creator=row["creator"],
            publisher=row["publisher"],
            ndc=row["ndc"],
            shelf_code=row["shelf_code"],
            floor=row["floor"],
            is_restricted=bool(row["is_restricted"]),
            is_active=bool(row["is_active"]),
            notes=row["notes"],
        )
