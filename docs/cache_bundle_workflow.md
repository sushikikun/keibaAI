# 外部取得環境からHTMLキャッシュを持ち込む bundle ワークフロー

作成日: 2026-06-18

## 目的

現在のメインPCでは `keiba.go.jp` へのHTTPS取得が失敗しています。

- python: `WinError 10013`
- powershell: 接続不可
- curl: exit code 7

そのため、取得可能な別環境で公式成績HTMLを取得し、メインPCへ cache bundle として持ち込む流れを使います。

このワークフローでは `data/raw/nankan_past_races.csv` を直接変更しません。append CSV生成、検証、merge dry-run、apply はそれぞれ別手順で行います。

## 全体の流れ

1. メインPCでfetch jobを作る
2. 取得可能なPC/環境へjobを移す
3. 外部環境で `fetch_result_pages` を実行してHTMLをcacheする
4. 外部環境で `build_cache_bundle` を実行してzipを作る
5. メインPCへzipを戻す
6. メインPCで `import_cache_bundle` を実行してcacheへ取り込む
7. `build_append_from_cache` でappend CSVを生成する
8. `validate_append_csv` を実行する
9. `merge_append_csv` dry-runを実行する
10. 問題がなければ `merge_append_csv --apply` を実行する

## 1. メインPCでfetch jobを作る

例:

```powershell
python -m nankan_ai.export_fetch_job --track kawasaki --date-from 2025-09-08 --date-to 2025-09-08 --race-no-from 1 --race-no-to 12
```

出力:

```text
data/jobs/fetch_job_<job_id>.csv
data/jobs/fetch_job_<job_id>.json
```

`job_id` は `job_YYYYMMDD_HHMMSS` 形式です。

JSONには以下を記録します。

- `job_id`
- `created_at`
- `track`
- `date_from`
- `date_to`
- `race_count`
- `race_ids`
- `source`
- `raw_sha256_at_export`

既存rawにある `race_id` は除外されます。

## 2. 外部取得環境へjobを移す

以下2ファイルを、取得可能なPC/環境の同じプロジェクト構成へ移します。

```text
data/jobs/fetch_job_<job_id>.csv
data/jobs/fetch_job_<job_id>.json
```

## 3. 外部環境でHTMLを取得する

外部環境で、job CSVをfetch planとして使います。

```powershell
python -m nankan_ai.fetch_result_pages data/jobs/fetch_job_<job_id>.csv --apply --backend python
```

必要なら backend を切り替えます。

```powershell
python -m nankan_ai.fetch_result_pages data/jobs/fetch_job_<job_id>.csv --apply --backend powershell
python -m nankan_ai.fetch_result_pages data/jobs/fetch_job_<job_id>.csv --apply --backend curl
```

HTML保存先:

```text
data/cache/html/<race_id>.html
```

既にcacheがある場合は再取得しません。rate limit は維持します。

## 4. 外部環境でcache bundleを作る

```powershell
python -m nankan_ai.build_cache_bundle --job-id <job_id>
```

出力:

```text
data/cache/bundles/cache_bundle_<job_id>.zip
```

zipには以下を含みます。

- `html/<race_id>.html`
- `manifest.json`
- `fetch_log.csv` があれば同梱
- job CSV/JSON があれば `jobs/` に同梱

`manifest.json` には、各HTMLの `race_id`、bundle内path、SHA256、byte size、作成日時を記録します。

## 5. メインPCへzipを戻す

外部環境で作ったzipをメインPCへ戻します。

```text
data/cache/bundles/cache_bundle_<job_id>.zip
```

## 6. メインPCでbundleをimportする

```powershell
python -m nankan_ai.import_cache_bundle data/cache/bundles/cache_bundle_<job_id>.zip
```

import時の確認:

- `manifest.json` が存在するか
- `html/<race_id>.html` がmanifestにあるか
- `<race_id>.html` 形式か
- bundle内の `race_id` が重複していないか
- HTMLが空ファイルではないか
- SHA256がmanifestと一致しているか
- zip slipになる危険なpathがないか

既に `data/cache/html/` に同名HTMLがある場合は上書きしません。

import結果:

```text
data/cache/imports/import_cache_bundle_<timestamp>.md
```

このコマンドは raw CSVを変更しません。append CSVも自動生成しません。

## 7. append CSVを生成する

import後、通常のcacheからappend CSVを生成します。

```powershell
python -m nankan_ai.build_append_from_cache --fetch-plan-csv data/jobs/fetch_job_<job_id>.csv --validate
```

出力:

```text
data/incoming/nankan_past_races_append.csv
```

## 8. append CSVを検証する

```powershell
python -m nankan_ai.validate_append_csv data/incoming/nankan_past_races_append.csv
```

## 9. merge dry-runを実行する

まだrawへ反映しません。

```powershell
python -m nankan_ai.merge_append_csv data/incoming/nankan_past_races_append.csv
```

## 10. 問題がなければapplyする

確認後だけ実行します。

```powershell
python -m nankan_ai.merge_append_csv data/incoming/nankan_past_races_append.csv --apply
```

## 禁止事項

- raw CSVを直接編集しない。
- `merge_append_csv --apply` を勝手に実行しない。
- 取得対象をjob外へ広げない。
- 推測補完しない。
- 予想モデル、特徴量追加、自動投票に進まない。
- 危険なネットワーク回避処理を作らない。

