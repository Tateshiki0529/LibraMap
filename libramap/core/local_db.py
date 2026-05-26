"""
libramap.core.local_db

ローカル蔵書データベース連携モジュール。

SQLite ベースの館内蔵書 DB を管理する。
NDL Search API から取得した書誌情報を補助入力として使用し、
図書館固有の書架位置・禁帯出フラグ・運用フラグを保持する。

仕様参照: specs.md §8
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path


# デフォルトのデータベースファイルパス
DEFAULT_DB_PATH = Path("data") / "libramap.db"


@dataclass
class BookRecord:
    """
    ローカル蔵書 DB の 1 レコードを表すデータクラス。

    Attributes:
        isbn: ISBN-13 文字列
        title: タイトル（NDL Search API より取得）
        creator: 著者（NDL Search API より取得）
        publisher: 出版社（NDL Search API より取得）
        ndc: 日本十進分類番号（文字列管理）
        shelf_code: 書架コード（図書館ローカル設定）
        floor: 階数（図書館ローカル設定）
        is_restricted: 禁帯出フラグ（True = 禁帯出資料）
        is_active: 配架支援対象フラグ（False = 対象外）
        notes: 運用メモ（自由記述）
    """
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
    """
    ローカル蔵書データベースクラス。

    SQLite を使用して館内蔵書情報を管理する。
    本クラスは配架支援本体（LibraMap）から利用される中核 DB として機能し、
    DB 生成・大量登録・デバッグ用途は LibraMap Builder 側に委ねる。

    仕様:
        - 館内蔵書 DB に存在しない資料は配架支援対象外とする
        - 禁帯出フラグを保持し、配架判定エンジンへ渡す
        - NDL Search API からの情報を補助入力として受け入れる
    """

    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        """
        ローカル蔵書 DB を初期化する。

        DB ファイルが存在しない場合は新規作成する。

        Args:
            db_path: SQLite データベースファイルのパス
        """
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._init_schema()

    def _init_schema(self) -> None:
        """データベーススキーマを初期化（テーブルが存在しない場合のみ作成）する。"""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS books (
                    isbn        TEXT PRIMARY KEY,
                    title       TEXT NOT NULL DEFAULT '',
                    creator     TEXT NOT NULL DEFAULT '',
                    publisher   TEXT NOT NULL DEFAULT '',
                    ndc         TEXT NOT NULL DEFAULT '',
                    shelf_code  TEXT NOT NULL DEFAULT '',
                    floor       TEXT NOT NULL DEFAULT '',
                    is_restricted INTEGER NOT NULL DEFAULT 0,
                    is_active   INTEGER NOT NULL DEFAULT 1,
                    notes       TEXT NOT NULL DEFAULT ''
                )
            """)

    def _connect(self) -> sqlite3.Connection:
        """
        SQLite データベースへ接続する。

        Returns:
            sqlite3.Connection: DB 接続オブジェクト（コンテキストマネージャとして使用可能）
        """
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def find_by_isbn(self, isbn: str) -> BookRecord | None:
        """
        ISBN で蔵書を検索する。

        Args:
            isbn: 検索対象の ISBN-13

        Returns:
            BookRecord: 該当レコード。存在しない場合は None。
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM books WHERE isbn = ?", (isbn,)
            ).fetchone()

        if row is None:
            return None

        return self._row_to_record(row)

    def is_registered(self, isbn: str) -> bool:
        """
        ISBN が館内蔵書 DB に登録されているかどうかを確認する。

        仕様: 未登録資料は配架支援対象外とする（specs.md §8.2）

        Args:
            isbn: 確認対象の ISBN-13

        Returns:
            bool: 登録済みの場合 True
        """
        return self.find_by_isbn(isbn) is not None

    def upsert(self, record: BookRecord) -> None:
        """
        蔵書レコードを登録または更新する。

        ISBN が存在しない場合は INSERT、存在する場合は UPDATE を行う。

        Args:
            record: 登録・更新する BookRecord
        """
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO books
                    (isbn, title, creator, publisher, ndc,
                     shelf_code, floor, is_restricted, is_active, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(isbn) DO UPDATE SET
                    title       = excluded.title,
                    creator     = excluded.creator,
                    publisher   = excluded.publisher,
                    ndc         = excluded.ndc,
                    shelf_code  = excluded.shelf_code,
                    floor       = excluded.floor,
                    is_restricted = excluded.is_restricted,
                    is_active   = excluded.is_active,
                    notes       = excluded.notes
            """, (
                record.isbn, record.title, record.creator, record.publisher,
                record.ndc, record.shelf_code, record.floor,
                int(record.is_restricted), int(record.is_active), record.notes,
            ))

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> BookRecord:
        """
        sqlite3.Row を BookRecord へ変換する。

        Args:
            row: データベースから取得した行データ

        Returns:
            BookRecord: 変換後のレコード
        """
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
