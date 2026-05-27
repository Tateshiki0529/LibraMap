# LibraMap

図書館の返却業務を支援するデスクトップアプリです。ISBN-13または192系JANを入力し、館内蔵書DB、NDL Search API、書架マップ定義を使って、おおよその返却位置と58mmレシート画像を提示します。

## MVP機能

- ISBN-13 / 192系JANの判定
- 館内蔵書SQLite DB照合
- NDL Search OpenSearch APIによる補助書誌取得
- NDC範囲による書架判定
- PySide6 GUIでの返却先表示
- Pillowによる58mmレシート画像生成
- ESC/POSプリンタ接続、未接続時のシミュレーション保存

## セットアップ

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## 起動

```powershell
python -m libramap.main
```

初期状態ではプリンタはシミュレーションです。生成画像は `data/receipts/` に保存されます。

## Editor 起動

```powershell
python -m libramap_editor.main
```

書架マップJSONをGUIで編集する管理者向けツールです。

## データ

- 書架定義: `libramap/data/schema.json`
- 館内蔵書DB: `data/libramap.db`
- NDLキャッシュ: `data/cache.db`

`data/*.db` と `data/receipts/` は生成物としてGit管理対象外です。

## Git運用

- `master`: 安定版
- `develop`: 開発統合
- `feature/*`: 機能開発
- `fix/*`: 不具合修正

変更はPull Requestで統合する前提です。
