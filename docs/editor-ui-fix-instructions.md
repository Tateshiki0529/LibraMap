# LibraMap Editor UI視認性修正指示

## 背景

Editor MVPの実機確認で、複数の入力部品・ダイアログに視認不可または視認困難な箇所がある。

原因は、Qt/Windowsのネイティブスタイルや未指定のサブコントロール色が、アプリ側QSSの淡色UI方針と噛み合っていないためと考えられる。

## 対象ブランチ

- `feature/editor-mvp`

## 修正対象

- `libramap_editor/ui/editor_window.py`
- 必要に応じてEditor UI専用のスタイル定義ファイルを追加してよい
- 本体アプリ `libramap/ui/main_window.py` は今回の対象外

## 確認済みの問題

### 1. オブジェクト属性フォームが黒背景になる

スクリーンショット右側の属性フォーム全体が黒背景になっている。

問題:

- `ID`、`種別`、`X`、`Y`、`幅`、`高さ`、`段数`、`列数` のラベルが黒背景上で読みづらい
- 入力欄は白背景だが、周辺背景が暗く、Editor全体の淡色UIと不整合
- `QSpinBox` の上下ボタン領域が不自然に暗く表示されている

期待:

- 右側フォーム全体を白または淡色背景に統一する
- ラベル文字色は `#111827` など濃色で明示する
- `QSpinBox` は入力テキスト、ボタン、矢印、枠線の色を明示する
- 右側パネルの背景と入力欄の境界が自然に見える

### 2. NDC範囲テーブルのヘッダーが視認困難

スクリーンショット右下の `NDC範囲` テーブルで、ヘッダー行が暗背景に暗めの文字で読みにくい。

問題:

- `段`、`開始列`、`終了列`、`NDC開始`、`NDC終了` のヘッダーが低コントラスト
- 空テーブル時の表示領域が白く、ヘッダーだけ浮いて見える

期待:

- `QHeaderView::section` の背景色、文字色、枠線を明示する
- ヘッダーは淡色背景または濃色背景のどちらかに統一し、十分なコントラストを確保する
- テーブルセルの文字色、選択色も明示する

### 3. エラーダイアログ本文が視認不可

エラーダイアログで本文 `書架を選択してください。` が黒背景に黒文字で表示されている。

問題:

- `QMessageBox` の本文文字がほぼ読めない
- OKボタンだけは見えるが、エラー理由が伝わらない

期待:

- `QMessageBox`、`QDialog`、`QLabel`、`QPushButton` の色をEditor用QSSで明示する
- ダイアログ背景は白または淡色、本文文字は濃色にする
- 警告アイコン周辺でも本文が読めること

### 4. 右パネルのラベル幅・入力欄幅が詰まり気味

属性フォームのラベルと入力欄が狭く、視認性と操作性に余裕がない。

期待:

- 右パネルの最小幅を確保する
- 入力欄の高さを一定にする
- ラベル列と入力列の余白を調整する
- 数値入力のスピンボタンがテキストを覆わないようにする

### 5. ラベル文字に不要な枠が付く

修正後の確認で、`LibraMap Editor`、`フロア`、`プレビュー`、属性フォームの `ID` など、単なる文字ラベルの周囲に薄い枠が表示されている。

原因:

- Qtでは `QLabel` が `QFrame` を継承している。
- そのため `QFrame { border: ... }` のような全体指定を行うと、`QLabel` にも枠線・角丸・背景が適用される。

問題:

- ラベルが入力部品やグループ枠のように見える
- UIの階層構造が分かりにくい
- 本来強調すべき入力欄やパネルとの区別が弱くなる

期待:

- 通常の `QLabel` には枠線を付けない
- 枠が必要なパネルだけに明示的な `objectName` を付けてスタイル指定する
- 見出しラベル、フォームラベル、リスト見出し、ダイアログ本文は枠なしで表示する

## 実装方針

1. Editor全体は淡色UIで統一する。
2. `QApplication` のスタイルやOSテーマに依存しないよう、必要なQSSを明示する。
3. `QFrame` の全体指定は避け、枠が必要なフレームだけ `setObjectName(...)` して `QFrame#objectName` で指定する。
4. `QLabel` は `QFrame` 指定を拾わないよう、枠線・角丸・余白を明示的にリセットする。
5. `QGroupBox`、`QMessageBox`、`QDialog`、`QTableWidget`、`QHeaderView`、`QSpinBox`、`QComboBox` のサブコントロールまで指定する。
6. 黒背景を使う場合は、文字色を白に明示する。ただしEditorでは基本的に黒背景を避ける。
7. UI文言や機能追加は最小限にし、視認性修正に集中する。

## 推奨QSS要件

以下を満たすQSSへ更新すること。

- `QWidget#central`: `background: #f5f7fb; color: #111827;`
- `QFrame`: 全体指定は禁止。枠が必要なものだけ `QFrame#objectFormFrame` のように限定指定
- `QLabel`: `color: #111827; background: transparent; border: none; border-radius: 0; padding: 0;`
- `QLineEdit`, `QSpinBox`, `QComboBox`: 白背景、濃色文字、淡い枠線
- `QSpinBox::up-button`, `QSpinBox::down-button`: 淡色背景、枠線または幅を明示
- `QTableWidget`: 白背景、濃色文字、グリッド線
- `QHeaderView::section`: 低コントラストにならない背景・文字色
- `QListWidget::item:selected`, `QTableWidget::item:selected`: 選択色と選択文字色を明示
- `QMessageBox`, `QDialog`: 白背景、濃色本文、ボタン視認可
- `QMessageBox QLabel`, `QDialog QLabel`: 枠なし、透明背景、濃色本文

## 手動確認項目

修正後、以下を実機または通常起動で確認する。

```powershell
python -m libramap_editor.main
```

### V-01 属性フォーム

- 右側フォーム背景が黒くない
- ラベルが読める
- `QSpinBox` の数値が選択しなくても読める
- スピンボタンが入力値を隠していない

### V-02 NDC範囲テーブル

- ヘッダー文字が読める
- 空テーブルでもヘッダーが低コントラストにならない
- 行追加後のセル文字が読める
- 選択行の文字が読める

### V-03 エラーダイアログ

1. 書架以外、または未選択状態で `NDC範囲 > 行追加` を押す。
2. エラーダイアログを確認する。

期待:

- `書架を選択してください。` が読める
- OKボタンが読める
- ダイアログ全体がEditorの淡色UIと大きく矛盾しない

### V-04 回帰確認

### V-04 ラベル枠線確認

- `LibraMap Editor` タイトルに枠が付いていない
- `フロア`、`オブジェクト`、`プレビュー`、`NDC範囲` の見出しに枠が付いていない
- フォームラベル `ID`、`種別`、`X`、`Y`、`幅`、`高さ`、`段数`、`列数` に枠が付いていない
- エラーダイアログ本文に枠が付いていない
- 枠が必要な右側パネル、プレビュー領域、一覧、入力欄には適切な枠が残っている

### V-05 回帰確認

```powershell
python -m unittest discover -s tests
python -m compileall libramap libramap_editor tests
```

期待:

- 既存テストが全て成功する
- Editor起動時に例外が出ない

## Codexへの作業指示

以下の方針で実装すること。

1. `libramap_editor/ui/editor_window.py` の `STYLE_SHEET` を中心に修正する。
2. 右側属性フォームが黒背景になる問題を解消する。
3. `QSpinBox`、`QComboBox`、`QTableWidget`、`QHeaderView`、`QMessageBox` の視認性をQSSで明示する。
4. `QFrame` の全体指定によって `QLabel` に枠が付く問題を解消する。
5. 枠が必要なフレームには `objectName` を付け、`QFrame#...` で限定的に指定する。
6. `QLabel` と `QMessageBox QLabel` には `border: none; border-radius: 0; padding: 0;` を明示する。
7. 機能追加やレイアウト大改造は行わない。
8. 必要であれば右パネルの最小幅、フォーム余白、入力欄高さを微調整する。
9. 修正後に `docs/editor-manual-test-plan.md` の該当確認項目へ、視認性確認を追記する。
10. 自動テストと構文チェックを実行し、結果を報告する。

## 非対象

- ドラッグ配置
- リサイズハンドル
- SVG/アイコン追加
- 書架JSONスキーマ変更
- LibraMap本体UIの変更
