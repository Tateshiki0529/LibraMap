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
        self._insert_test_data_if_empty()

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

    def _insert_test_data_if_empty(self) -> None:
        """データベースが空の場合に、動作検証用のテスト書籍データを投入する。"""
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM books").fetchone()
            if row is not None and row[0] > 0:
                return

        # 有名な日本語書籍11冊（通常書籍、禁帯出、異なるNDCなど）
        test_books = [
            BookRecord(
                isbn="9784820414131",
                title="日本十進分類法新訂10版",
                creator="日本図書館協会分類委員会",
                publisher="日本図書館協会",
                ndc="014.4",
                shelf_code="A-01",
                floor="1f",
                is_restricted=True,
                notes="参考図書（禁帯出）"
            ),
            BookRecord(
                isbn="9784003310212",
                title="学問のすすめ",
                creator="福沢諭吉",
                publisher="岩波書店",
                ndc="150",
                shelf_code="A-01",
                floor="1f",
                is_restricted=False,
                notes="名著"
            ),
            BookRecord(
                isbn="9784003115015",
                title="君たちはどう生きるか",
                creator="吉野源三郎",
                publisher="岩波書店",
                ndc="159",
                shelf_code="A-01",
                floor="1f",
                is_restricted=False,
                notes="名著"
            ),
            BookRecord(
                isbn="9784000801317",
                title="広辞苑 第七版",
                creator="新村出",
                publisher="岩波書店",
                ndc="813.1",
                shelf_code="B-01",
                floor="2f",
                is_restricted=True,
                notes="参考図書（禁帯出）"
            ),
            BookRecord(
                isbn="9784101010113",
                title="吾輩は猫である",
                creator="夏目漱石",
                publisher="新潮社",
                ndc="913.6",
                shelf_code="B-12",
                floor="2f",
                is_restricted=False,
                notes="名著"
            ),
            BookRecord(
                isbn="9784101010120",
                title="坊っちゃん",
                creator="夏目漱石",
                publisher="新潮社",
                ndc="913.6",
                shelf_code="B-12",
                floor="2f",
                is_restricted=True,
                notes="テスト用禁帯出設定"
            ),
            BookRecord(
                isbn="9784101010137",
                title="こころ",
                creator="夏目漱石",
                publisher="新潮社",
                ndc="913.6",
                shelf_code="B-12",
                floor="2f",
                is_restricted=False,
                notes="名著"
            ),
            BookRecord(
                isbn="9784101010151",
                title="人間失格",
                creator="太宰治",
                publisher="新潮社",
                ndc="913.6",
                shelf_code="B-12",
                floor="2f",
                is_restricted=False,
                notes="名著"
            ),
            BookRecord(
                isbn="9784101010168",
                title="走れメロス",
                creator="太宰治",
                publisher="新潮社",
                ndc="913.6",
                shelf_code="B-12",
                floor="2f",
                is_restricted=False,
                notes="名著"
            ),
            BookRecord(
                isbn="9784101024011",
                title="羅生門・鼻",
                creator="芥川龍之介",
                publisher="新潮社",
                ndc="913.6",
                shelf_code="B-12",
                floor="2f",
                is_restricted=False,
                notes="名著"
            ),
            BookRecord(
                isbn="9784101092058",
                title="銀河鉄道の夜",
                creator="宮沢賢治",
                publisher="新潮社",
                ndc="913.6",
                shelf_code="B-12",
                floor="2f",
                is_restricted=False,
                notes="名著"
            )
        ]

        for book in test_books:
            self.upsert(book)

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
