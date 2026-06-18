# 追加CSV batch管理

作成日: 2026-06-18

## 目的

追加CSVを検証・追記するたびに、どのファイルを、いつ、どの状態で処理したかを記録します。

この仕組みでは、予想モデル作成、特徴量追加、自動取得、公式ページ巡回、`win_odds_final` 補完は行いません。

## batch log

batch logは次のCSVに追記されます。

- `data/reports/append_batches.csv`

dry-runでも `dry_run` として1行記録します。`--apply` を付けた場合は `applied` として記録します。

## batch_id

`batch_id` は次の形式です。

```text
append_YYYYMMDD_HHMMSS
```

例:

```text
append_20260618_030405
```

同じ実行のレポート名にも同じ時刻部分を使います。

## append_batches.csv の列

| column | meaning |
| --- | --- |
| `batch_id` | `append_YYYYMMDD_HHMMSS` 形式の実行ID |
| `created_at` | 実行日時 |
| `mode` | `dry_run` または `applied` |
| `append_csv_path` | 追加CSVのパス |
| `append_csv_sha256` | 追加CSVのSHA256 |
| `before_raw_sha256` | 実行前raw CSVのSHA256 |
| `after_raw_sha256` | 実行後raw CSVのSHA256。dry-runでは実行前と同じ |
| `before_raw_rows` | 実行前raw行数 |
| `after_raw_rows` | 実行後raw行数。dry-runでは実行前と同じ |
| `before_race_count` | 実行前レース数 |
| `after_race_count` | 実行後レース数。dry-runでは実行前と同じ |
| `added_rows` | 追加CSVの行数。検証失敗時は0 |
| `added_races` | 追加CSVのレース数。検証失敗時は0 |
| `track_scope` | 追加CSVに含まれるtrack。複数ある場合は`;`区切り |
| `date_min` | 追加CSV内の最小date |
| `date_max` | 追加CSV内の最大date |
| `race_count_expected` | 予定していた追加レース数。未指定なら空欄 |
| `race_count_actual` | 追加CSVから実際に数えたレース数 |
| `validation_status` | `passed` / `failed` / `failed_after_append` |
| `report_path` | 対応するappend reportのパス |

## dry-run の扱い

dry-runでは既存rawを変更しません。

ただし、次は作成・追記されます。

- `data/reports/append_report_YYYYMMDD_HHMMSS.md`
- `data/reports/append_batches.csv`

dry-runの `after_raw_sha256`、`after_raw_rows`、`after_race_count` は、rawが変わらないため実行前と同じ値になります。

`track_scope`、`date_min`、`date_max`、`race_count_actual` は追加CSVから自動で記録されます。`race_count_expected` は `--race-count-expected` を指定した場合に記録されます。

## applied の扱い

`--apply` 時は次を行います。

1. 追加CSVを検証
2. 追記前rawをバックアップ
3. rawへ追記
4. raw全体を再検証
5. DuckDBを更新
6. training_rows.csvを更新
7. audit_datasetを実行
8. dataset_manifestを作成
9. append reportを作成
10. batch logへ `applied` として記録

バックアップ:

- `data/backups/nankan_past_races_before_append_YYYYMMDD_HHMMSS.csv`

append report:

- `data/reports/append_report_YYYYMMDD_HHMMSS.md`

## 検証失敗時

追加CSVの検証に失敗した場合、rawへ追記しません。

この場合も、失敗した試行を追えるように次を残します。

- append report
- batch log行

`validation_status` は `failed` になります。

## 注意

- batch logはデータの取り込み履歴であり、予想モデルの実験管理ではありません。
- raw CSVの列は増やしません。
- `win_odds_final` は推測補完しません。
- 川崎以外の追加CSVは受け入れません。
- 約30,000レース規模では、月別レース数、track別レース数、race_no欠落、batch別追加件数、raw/training SHA256を必ず確認します。

## append stateとresume

`--apply` 実行時は、`append_batches.csv` とは別に段階管理用のstate JSONを作成します。

```text
data/reports/append_state_<batch_id>.json
```

このファイルはbatch logが確定する前から随時更新されます。raw追記後、DuckDB更新やtraining出力の前に停止した場合の復旧に使います。

記録するstep:

- `backup_created`
- `raw_appended`
- `duckdb_loaded`
- `training_exported`
- `audit_done`
- `manifest_created`
- `batch_logged`

復旧コマンド:

```bash
python -m nankan_ai.merge_append_csv --resume data/reports/append_state_append_YYYYMMDD_HHMMSS.json
```

`--resume` は完了済みstepをスキップします。`completed_steps` に `raw_appended` がある場合、rawへ二重追記しません。バックアップはstateに記録済みの既存パスを使います。

通常の `--apply` は、追加CSV内の全 `race_id` が既にrawに存在する場合、追記を拒否します。これにより、途中停止後の誤った二重追記を防ぎます。

stateに `batch_logged` があり、batch log行が `mode=applied` かつ `validation_status=passed` の場合に、そのbatchを完了扱いにします。
