"""
libramap.core.cache

SQLite キャッシュ管理モジュール。

NDL Search API のレスポンスをローカルにキャッシュし、
API 負荷軽減・応答速度改善・オフライン耐性を実現する。

仕様参照: specs.md §15
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path


# デフォルトのキャッシュ DB ファイルパス
DEFAULT_CACHE_PATH = Path("data") / "cache.db"


class CacheManager:
    """
    NDL Search API レスポンスキャッシュ管理クラス。

    ISBN をキーとして書誌情報（タイトル・著者・NDC）を SQLite に保存し、
    再スキャン時の API 呼び出しを省略する。

    キャッシュ対象:
        - ISBN
        - タイトル
        - 著者
        - NDC
        - 最終取得日時
    """

    def __init__(self, cache_path: Path = DEFAULT_CACHE_PATH) -> None:
        """
        キャッシュ DB を初期化する。

        DB ファイルが存在しない場合は新規作成する。

        Args:
            cache_path: SQLite キャッシュファイルのパス
        """
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path = cache_path
        self._init_schema()

    def _init_schema(self) -> None:
        """キャッシュテーブルが存在しない場合に作成する。"""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ndl_cache (
                    isbn        TEXT PRIMARY KEY,
                    title       TEXT NOT NULL DEFAULT '',
                    creator     TEXT NOT NULL DEFAULT '',
                    ndc         TEXT NOT NULL DEFAULT '',
                    fetched_at  TEXT NOT NULL
                )
            """)

    def _connect(self) -> sqlite3.Connection:
        """
        SQLite キャッシュ DB へ接続する。

        Returns:
            sqlite3.Connection: DB 接続オブジェクト
        """
        conn = sqlite3.connect(self._cache_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get(self, isbn: str) -> dict | None:
        """
        ISBN に対応するキャッシュエントリを取得する。

        Args:
            isbn: 検索対象の ISBN-13

        Returns:
            dict | None: キャッシュが存在する場合はフィールド辞書、存在しない場合は None
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM ndl_cache WHERE isbn = ?", (isbn,)
            ).fetchone()

        if row is None:
            return None

        return {
            "isbn": row["isbn"],
            "title": row["title"],
            "creator": row["creator"],
            "ndc": row["ndc"],
            "fetched_at": row["fetched_at"],
        }

    def set(self, isbn: str, title: str, creator: str, ndc: str) -> None:
        """
        書誌情報をキャッシュに保存する（上書き可）。

        Args:
            isbn: ISBN-13
            title: タイトル
            creator: 著者
            ndc: NDC 文字列
        """
        fetched_at = datetime.now().isoformat()

        with self._connect() as conn:
            conn.execute("""
                INSERT INTO ndl_cache (isbn, title, creator, ndc, fetched_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(isbn) DO UPDATE SET
                    title      = excluded.title,
                    creator    = excluded.creator,
                    ndc        = excluded.ndc,
                    fetched_at = excluded.fetched_at
            """, (isbn, title, creator, ndc, fetched_at))

    def delete(self, isbn: str) -> None:
        """
        指定 ISBN のキャッシュエントリを削除する。

        Args:
            isbn: 削除対象の ISBN-13
        """
        with self._connect() as conn:
            conn.execute("DELETE FROM ndl_cache WHERE isbn = ?", (isbn,))

    def clear_all(self) -> None:
        """キャッシュ全件を削除する。"""
        with self._connect() as conn:
            conn.execute("DELETE FROM ndl_cache")
