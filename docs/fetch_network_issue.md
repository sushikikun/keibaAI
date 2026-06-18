# 取得層ネットワーク問題メモ

作成日: 2026-06-18

## 概要

取得層MVPの実取得テストとして、未収録日の川崎1日分を対象にしました。

- 対象日: 2025-09-08
- 競馬場: 川崎
- 対象: 1Rから12R
- fetch plan: 12件作成成功
- fetch dry-run: 12件成功
- fetch `--apply`: 0件成功 / 12件失敗

## 発生した問題

`fetch_result_pages --apply` 実行時、12件すべてで以下の系統のエラーになりました。

```text
WinError 10013
アクセス許可で禁じられた方法でソケットにアクセスしようとしました。
```

このため、`data/cache/html/` に対象HTMLキャッシュは作成されませんでした。

## 記録済みの状態

- `data/raw/nankan_past_races.csv` は変更していません。
- `merge_append_csv --apply` は実行していません。
- `data/cache/metadata/fetch_log.csv` には dry-run 12件と failed 12件が記録されています。
- HTMLキャッシュが0件のため、append CSV生成には進めていません。

## 対応方針

1. `python -m nankan_ai.diagnose_network_access` でDNS、TCP 443、HTTPS GETのどこで失敗しているか確認します。
2. ローカル環境でHTTPS取得が使えない場合は、危険な設定変更や回避策は行いません。
3. ブラウザ等で公式成績ページを手動保存し、`data/manual_html/<race_id>.html` に置きます。
4. `python -m nankan_ai.import_manual_html_cache` で `data/cache/html/<race_id>.html` へ取り込みます。
5. その後は既存の `build_append_from_cache`、`validate_append_csv`、`merge_append_csv` dry-run に進みます。

## 禁止事項

- raw CSVを直接編集しない。
- `merge_append_csv --apply` を確認前に実行しない。
- ファイアウォール回避や危険なネットワーク設定変更をしない。
- 推測補完しない。
- 予想モデルや特徴量追加に進まない。

