# Dev Memory

## 2026-06-02

- Issue #4 (`feat: NDC 3桁デコードマップ実装`) を `feat/issue-4-ndc-map` で実装。
- 実装方針: NDC 3次区分ラベルは **公式 PDF 優先**、欠落分のみ NDC Navi を補完利用。
- 追加ファイル:
  - `libramap/ndc_map.py`
  - `tests/test_ndc_map.py`
- テスト: `python -m unittest tests.test_ndc_map -v` を通過。
- コミット: `cf6d867`
- PR: https://github.com/Tateshiki0529/LibraMap/pull/7
