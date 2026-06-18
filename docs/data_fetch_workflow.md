# 公式成績ページ取得・キャッシュ・append CSV生成ワークフロー

この文書は、南関東競馬AIのデータ基盤で、公式成績ページを指定範囲だけ取得し、既存rawを直接編集せずに `data/incoming/nankan_past_races_append.csv` を作るための手順です。

まだ予想モデル、特徴量追加、買い目生成は行いません。

## 基本方針

- `data/raw/nankan_past_races.csv` は直接編集しない。
- 取得対象は必ず fetch plan CSV に明示する。
- HTMLは必ず `data/cache/html/` に保存する。
- 取得ログは `data/cache/metadata/fetch_log.csv` に残す。
- 取得とパースを分離する。
- append CSV生成後の取り込みは、既存の `validate_append_csv` と `merge_append_csv` に任せる。
- `merge_append_csv --apply` は確認後にだけ実行する。
- 公式ページで空欄の値はCSVでも空欄にする。
- `passing_order` は引き続き空欄にする。
- 推測補完はしない。

## 1. 取得計画を作る

例: 川崎の指定日・指定Rだけを取得対象にする。

```powershell
python -m nankan_ai.fetch_plan --track kawasaki --date-from 2025-09-01 --date-to 2025-09-05 --race-no-from 1 --race-no-to 12
```

出力先:

```text
data/reports/fetch_plan_YYYYMMDD_HHMMSS.csv
```

fetch plan には以下が入ります。

- `race_id`
- `date`
- `track`
- `race_no`
- `official_url`
- `cache_html_path`

既定では、既存rawに含まれる `race_id` は除外します。既存分も計画に含めたい場合だけ `--include-existing` を使います。

## 2. dry-runで取得対象を確認する

`fetch_result_pages` は既定で dry-run です。HTMLは取得せず、対象とログだけを確認できます。

```powershell
python -m nankan_ai.fetch_result_pages data/reports/fetch_plan_YYYYMMDD_HHMMSS.csv
```

dry-runで確認すること:

- 対象レース数が意図通りか
- 川崎以外が混ざっていないか
- 既存rawの `race_id` が混ざっていないか
- `official_url` が公式 `RaceMarkTable` を向いているか

## 3. HTMLを取得してキャッシュする

実取得は `--apply` を付けた時だけ行います。

```powershell
python -m nankan_ai.fetch_result_pages data/reports/fetch_plan_YYYYMMDD_HHMMSS.csv --apply
```

既定では1レースごとに待機時間を入れます。必要な場合だけ低頻度の範囲内で変更します。

```powershell
python -m nankan_ai.fetch_result_pages data/reports/fetch_plan_YYYYMMDD_HHMMSS.csv --apply --delay-seconds 2
```

キャッシュ済みのHTMLがある場合は再取得しません。失敗した `race_id` はログに残し、処理は続行します。

## 4. cacheを確認する

HTMLキャッシュ:

```text
data/cache/html/<race_id>.html
```

取得ログ:

```text
data/cache/metadata/fetch_log.csv
```

取得ログの主な列:

- `fetched_at`
- `mode`
- `race_id`
- `official_url`
- `cache_html_path`
- `status`
- `http_status`
- `error`

`status=failed` がある場合は、append CSV生成前に対象レースを確認します。

## 5. append CSVを生成する

fetch plan に含まれるキャッシュだけから append CSV を生成します。

```powershell
python -m nankan_ai.build_append_from_cache --fetch-plan-csv data/reports/fetch_plan_YYYYMMDD_HHMMSS.csv
```

出力先:

```text
data/incoming/nankan_past_races_append.csv
```

既存rawと同じヘッダー順で出力します。既定では既存rawに含まれる `race_id` は除外します。

出力と同時にappend検証まで行う場合:

```powershell
python -m nankan_ai.build_append_from_cache --fetch-plan-csv data/reports/fetch_plan_YYYYMMDD_HHMMSS.csv --validate
```

## 6. append CSVを検証する

```powershell
python -m nankan_ai.validate_append_csv data/incoming/nankan_past_races_append.csv
```

確認すること:

- ヘッダーが既存rawと完全一致している
- 既存rawとの `race_id` 重複がない
- append CSV内の `race_id` 重複がない
- 同一 `race_id` 内の `horse_no` 重複がない
- `field_size` と行数が一致している
- `SCR` / `EXC` / `DNF` が既存ルール通りになっている

## 7. merge dry-runを実行する

まだrawには追記しません。

```powershell
python -m nankan_ai.merge_append_csv data/incoming/nankan_past_races_append.csv
```

dry-runで確認すること:

- 追加行数
- 追加レース数
- 追加後の見込み行数
- 追加後の見込みレース数
- batch logの記録

## 8. 問題がなければapplyする

```powershell
python -m nankan_ai.merge_append_csv data/incoming/nankan_past_races_append.csv --apply
```

`--apply` 時だけ以下を行います。

- raw追記前バックアップ作成
- raw追記
- `validate_csv`
- DuckDB保存
- `training_rows.csv` 出力
- `audit_dataset`
- dataset manifest作成
- append report作成
- batch log記録

## 失敗時の扱い

- fetch失敗: `data/cache/metadata/fetch_log.csv` の `status` と `error` を見る。
- parse失敗: `python -m nankan_ai.parse_result_pages <cache_html_path>` で対象HTMLだけ確認する。
- append検証失敗: rawにはmergeせず、対象行・対象列だけを確認する。
- apply後の異常: `data/backups/` のバックアップと `data/reports/append_report_*.md` を確認する。

## HTTPS取得が失敗した場合

`fetch_result_pages --apply` で `WinError 10013` などの通信エラーになった場合、無理に再試行を繰り返さず、まず診断コマンドで失敗箇所を確認します。

```powershell
python -m nankan_ai.diagnose_network_access
```

このコマンドは以下だけを確認します。

- DNS解決
- TCP 443接続
- HTTPS GET

raw CSVやHTMLキャッシュは変更しません。

診断後もローカル環境から公式ページを取得できない場合は、危険なファイアウォール回避や設定変更は行わず、手動HTMLキャッシュ投入に切り替えます。

### 手動HTMLキャッシュ投入

ブラウザ等で公式成績ページを手動保存し、ファイル名を `race_id.html` にして以下へ置きます。

```text
data/manual_html/<race_id>.html
```

例:

```text
data/manual_html/20250908_kawasaki_1.html
```

その後、次を実行します。

```powershell
python -m nankan_ai.import_manual_html_cache
```

このコマンドは、`data/manual_html/<race_id>.html` を `data/cache/html/<race_id>.html` にコピーし、結果を以下へ記録します。

```text
data/cache/metadata/manual_import_log.csv
```

既に `data/cache/html/` に同名ファイルがある場合は上書きしません。raw CSVも変更しません。

手動投入後は通常フローへ戻ります。

```powershell
python -m nankan_ai.build_append_from_cache --fetch-plan-csv data/reports/fetch_plan_YYYYMMDD_HHMMSS.csv --validate
python -m nankan_ai.validate_append_csv data/incoming/nankan_past_races_append.csv
python -m nankan_ai.merge_append_csv data/incoming/nankan_past_races_append.csv
```

## 未確定事項

- 公式HTMLの構造変更時のパース調整ルール
- 取得対象を競馬場別に進めるか、全場の日付順に進めるか
- オッズ欠損時に別の正規ソースを調査するか
- `passing_order` をいつ取得対象にするか

## backend切り替えの参照

Python標準のHTTPS取得が失敗する環境では、以下で取得backendを切り分けます。

```powershell
python -m nankan_ai.diagnose_fetch_backends
```

`fetch_result_pages` は backend を指定できます。

```powershell
python -m nankan_ai.fetch_result_pages data/reports/fetch_plan_YYYYMMDD_HHMMSS.csv --apply --backend python
python -m nankan_ai.fetch_result_pages data/reports/fetch_plan_YYYYMMDD_HHMMSS.csv --apply --backend powershell
python -m nankan_ai.fetch_result_pages data/reports/fetch_plan_YYYYMMDD_HHMMSS.csv --apply --backend curl
```

詳細は `docs/fetch_backend_strategy.md` を参照してください。
