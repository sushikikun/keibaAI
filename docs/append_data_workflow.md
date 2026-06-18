# 追加CSV受け入れワークフロー

作成日: 2026-06-18

## 目的

外部で手入力した追加CSVを、既存の `data/raw/nankan_past_races.csv` に安全に追記するための手順です。

このワークフローでは、予想モデル作成、特徴量追加、自動取得、公式ページ巡回、`win_odds_final` 補完は行いません。

## 入力ファイル

追加CSVは次の場所に置きます。

- `data/incoming/nankan_past_races_append.csv`

既存raw:

- `data/raw/nankan_past_races.csv`

## 追加CSVの入力ルール

- ヘッダーは既存rawと完全一致させる
- 1行 = 1頭・1レース
- 川崎のみを入力する
- 既存rawにある `race_id` は入れない
- 同一 `race_id` 内で `horse_no` を重複させない
- `field_size` は同一 `race_id` の行数と一致させる
- 不明値は空欄にする
- `passing_order` は空欄でよい
- `finish_position` は通常着順、`SCR`、`EXC`、`DNF` を使う
- `win_odds_final` は推測補完しない

同じ `race_id` は1レース内の各馬行で繰り返されるため、行として複数回出ること自体は正常です。このワークフローでは、既存rawとの `race_id` 衝突、同一 `race_id` 内の `horse_no` 重複、同じ `race_id` の競走単位メタデータ矛盾を検出します。

## 1. 追加CSVだけを検証

```bash
python -m nankan_ai.validate_append_csv data/incoming/nankan_past_races_append.csv
```

確認されること:

- 既存rawとのヘッダー完全一致
- 必須カラムの存在
- `race_id` 形式
- `track` が `kawasaki`
- 日付形式
- 数値カラム
- `finish_position`
- 既存rawとの `race_id` 重複
- 追加CSV内の `horse_no` 重複
- `field_size` と行数のズレ
- 追加CSV内の競走単位メタデータ矛盾

エラーがある場合は追記しません。

## 2. dry-run

```bash
python -m nankan_ai.merge_append_csv data/incoming/nankan_past_races_append.csv --race-count-expected 500
```

dry-runでは既存rawを変更しません。現在行数、追加行数、追加後見込み行数を確認します。

dry-runでも、確認履歴として次を残します。

- `data/reports/append_report_YYYYMMDD_HHMMSS.md`
- `data/reports/append_batches.csv`

## 3. apply

検証とdry-runに問題がなければ、`--apply` を付けます。

```bash
python -m nankan_ai.merge_append_csv data/incoming/nankan_past_races_append.csv --race-count-expected 500 --apply
```

`--apply` 時だけ次を行います。

1. 追記前バックアップ作成
2. 既存rawへ追記
3. `validate_csv`
4. `load_to_duckdb`
5. `export_training_rows`
6. `audit_dataset`
7. `dataset_manifest`
8. 追記レポート作成
9. batch log記録

バックアップ:

- `data/backups/nankan_past_races_before_append_YYYYMMDD_HHMMSS.csv`

追記レポート:

- `data/reports/append_report_YYYYMMDD_HHMMSS.md`

batch log:

- `data/reports/append_batches.csv`

batch logには、追加CSVの `track_scope`、`date_min`、`date_max`、`race_count_expected`、`race_count_actual` も記録されます。

manifest:

- `data/reports/dataset_manifest_<race_count>.json`

500レースから100レースを追加して600レースになった場合は、`dataset_manifest_600.json` が作成されます。最終的に1000レースへ到達した場合は、`dataset_manifest_1000.json` が作成されます。

## 4. 1000レース到達後

1000レースに到達したら、最終確認として次を実行します。

```bash
python -m nankan_ai.validate_csv data/raw/nankan_past_races.csv
python -m nankan_ai.load_to_duckdb data/raw/nankan_past_races.csv
python -m nankan_ai.export_training_rows
python -m nankan_ai.audit_dataset
python -m nankan_ai.dataset_manifest --label 1000
python -m pytest
```

その後、次を作成または更新します。

- `docs/dataset_status.md`
- `docs/dataset_snapshot_1000.md`
- `data/reports/dataset_manifest_1000.json`

## 注意

- dry-runでは既存rawは変更されません
- dry-runでもappend reportとbatch logは作成されます
- エラーがある場合はmergeしません
- `--apply` 前に必ずdry-runを確認します
- rawの既存500レース部分は編集しません
- 川崎以外を混ぜません
- 予想モデル、特徴量追加、自動取得には進みません

## apply途中停止時のresume

`merge_append_csv --apply` は、処理中に段階管理用のstate JSONを書き出します。

```text
data/reports/append_state_<batch_id>.json
```

stateには次の完了済みstepが記録されます。

- `backup_created`
- `raw_appended`
- `duckdb_loaded`
- `training_exported`
- `audit_done`
- `manifest_created`
- `batch_logged`

`raw_appended` 後に `--apply` が停止した場合、同じ `--apply` を再実行しません。
state JSONから後続処理だけを再開します。

```bash
python -m nankan_ai.merge_append_csv --resume data/reports/append_state_append_YYYYMMDD_HHMMSS.json
```

`--resume` は完了済みstepをスキップします。`raw_appended` が完了済みなら、rawへ二重追記せず、DuckDB更新、training CSV出力、audit、manifest、append report、batch logから再開します。

stateパスを省略した場合は、指定した追加CSVに対応する最新stateを探します。

```bash
python -m nankan_ai.merge_append_csv data/incoming/nankan_past_races_append.csv --resume
```

通常の `--apply` は、追加CSV内の全 `race_id` が既にrawに存在する場合は追記を拒否します。途中停止からの復旧では、再applyではなく `--resume` を使います。
