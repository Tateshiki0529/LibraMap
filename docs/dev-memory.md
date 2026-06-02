# Dev Memory

## 2026-06-02

- Issue #8 (`bug: Editor 初期ウィンドウサイズでUI崩れ（レスポンシブ対応）`) を `fix/issue-8-editor-responsive-layout` で実装。
- 実装方針: Editor本体を `QSplitter` に変更し、右ペインをスクロール化、NDC 2段階セレクトを狭幅時に縦積み、セグメント表のカラム幅ポリシーを見直して初期サイズでも崩れにくくした。
- 追加ファイル:
  - `tests/test_editor_window.py`
- 更新ファイル:
  - `libramap_editor/ui/editor_window.py`
  - `docs/dev-memory.md`
- テスト:
  - `python -m unittest tests.test_editor_model tests.test_editor_window -v`

- `backup/local-master-before-sync` を確認し、現 `master` に欠けていた運用ファイルを `docs/restore-agent-workflow-files` で復元。
- 復元内容:
  - `AGENTS.md` を再追加
  - `.github/pull_request_template.md` を UTF-8 で再作成

- Issue #6 (`feat: レシート - NDC分類名印字`) を `feat/issue-6-receipt-ndc-label` で実装。
- 実装方針: レシート描画時に `ndc_map.get_ndc_label()` を使って NDC 行を整形し、分類名が取れない場合のみコード表示へフォールバック。
- 追加ファイル:
  - `tests/test_receipt_renderer.py`
- 更新ファイル:
  - `libramap/printing/receipt_renderer.py`
  - `docs/dev-memory.md`
- テスト:
  - `python -m unittest tests.test_ndc_map tests.test_receipt_renderer -v`
  - `python -m unittest tests.test_core.ReceiptRendererTest -v`

- Issue #4 (`feat: NDC 3桁デコードマップ実装`) を `feat/issue-4-ndc-map` で実装。
- 実装方針: NDC 3次区分ラベルは **公式 PDF 優先**、欠落分のみ NDC Navi を補完利用。
- 追加ファイル:
  - `libramap/ndc_map.py`
  - `tests/test_ndc_map.py`
- テスト: `python -m unittest tests.test_ndc_map -v` を通過。
- コミット: `cf6d867`
- PR: https://github.com/Tateshiki0529/LibraMap/pull/7

## GitHub本文運用ルール（恒久）

- GitHub（Issue / PR / コメント）の本文は **human-readable 最優先**。
- 本文更新時は `--body` 直指定を避け、**UTF-8 の本文ファイル**（`--body-file`）経由を基本とする。
- 投稿・更新後は `gh ... view --json body` で表示確認し、`\n` の生表示や文字化けがあれば即修正する。
- 作業用の一時本文ファイルは、反映確認後に削除する。

## ブランチ / PR / マージ運用ルール（恒久）

- 仕様変更・実装変更・運用変更を行うときは、**必ず作業用ブランチを切ってから着手する**。`master` 直作業は禁止。
- 作業完了後は、**必ず PR を作成する**。
- `master` へマージする前に、**対象 PR に競合がないことを確認する**。
- マージは **PR 経由のみ** とし、競合未解消のまま `master` へ直接反映しない。
- 迷った場合の標準手順は `origin/master` を取得 → 作業ブランチ作成 → 実装/検証 → push → PR 作成 → 競合確認 → `master` へマージ。
