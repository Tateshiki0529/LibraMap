# Dev Memory

## 2026-06-02

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
