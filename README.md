# LibraMap

図書館返却支援システム

## プロジェクト概要

返却された資料のバーコード（ISBN-13 / JANコード）をスキャンし、
NDL Search API および館内蔵書データベースを照合することで、
日本十進分類法（NDC）に基づく書架返却位置を視覚的に提示する司書支援システムです。

本システムは「完全自動配架」を目的とせず、司書による最終判断を前提とした補助ツールです。

---

## 関連プロジェクト構成

| プロジェクト | 役割 |
|---|---|
| LibraMap（本体） | 配架支援メインアプリケーション |
| LibraMap Editor | 書架マップ編集ツール |
| LibraMap Builder | 蔵書DB生成・検証・デバッグ補助ツール |

---

## 技術スタック

| 用途 | 技術 |
|---|---|
| 実装言語 | Python |
| GUI | PySide6 |
| API取得 | requests |
| XML解析 | lxml |
| 画像描画 | Pillow |
| 印刷 | python-escpos |
| キャッシュDB | SQLite |
| データ定義 | JSON |

---

## セットアップ

```bash
# 仮想環境の作成
python -m venv .venv

# 仮想環境の有効化 (Windows)
.venv\Scripts\activate

# 依存ライブラリのインストール
pip install -r requirements.txt
```

---

## 実行方法

```bash
python -m libramap.main
```

---

## ブランチ構成

| ブランチ | 用途 |
|---|---|
| master | 安定版 |
| develop | 開発統合 |
| feature/* | 機能開発 |
| fix/* | バグ修正 |
| experimental/* | 実験実装 |

---

## ライセンス

本プロジェクトは実装指示書 (specs.md) に基づき開発されています。
