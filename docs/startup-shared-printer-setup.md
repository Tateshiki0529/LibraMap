# Startup Setup (Shared Printer Fixed)

この手順は、担当者が最初に一度だけ実施して、LibraMap の共有プリンタ運用を固定するためのものです。

## 対象
- Windows + PowerShell
- 共有プリンタ `\\localhost\RECEIPT` を使用

## 1. 実験モードを無効化（必須）
`cut` 実験モードが有効だと複数カットが発生するため、必ず無効化します。

```powershell
Remove-Item Env:LIBRAMAP_PRINTER_CUT_EXPERIMENT -ErrorAction SilentlyContinue
```

## 2. 共有プリンタ向け cut コマンドを固定
環境依存を減らすため、使用する cut コマンドを固定します。

推奨値:
- `gs_v_42_00`（現状の既定）

```powershell
$env:LIBRAMAP_SHARED_CUT_CMD = "gs_v_42_00"
```

切れない場合の代替候補:
- `gs_v_00`
- `gs_v_01`
- `gs_v_41_00`

## 3. デバッグ出力（必要時のみ）
通常は無効で運用し、障害調査時のみ有効化します。

有効化:
```powershell
$env:LIBRAMAP_PRINTER_DEBUG = "1"
```

無効化:
```powershell
Remove-Item Env:LIBRAMAP_PRINTER_DEBUG -ErrorAction SilentlyContinue
```

## 4. 起動
```powershell
python -m libramap.main
```

## 5. 運用ルール
- 通常運用では `LIBRAMAP_PRINTER_CUT_EXPERIMENT` を使わない。
- `LIBRAMAP_SHARED_CUT_CMD` は担当内で1つに固定して運用する。
- 切れ方が変わった場合のみデバッグを有効にしてログを採取する。

## 備考
- UI のプリンタ選択は、起動時に共有プリンタがデフォルト選択になります。
- 共有経路は Windows スプーラ/ドライバの影響を受けるため、機種変更時は再検証してください。
