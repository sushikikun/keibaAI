# 南関東競馬AI データセット状態メモ

最終更新: 2026-06-18

## 目的

このメモは、川崎500レース投入時点のデータ状態を記録するためのものです。まだ予想モデル、自動取得、特徴量追加、列追加、データ補完は行いません。

## 500レース時点の集計

対象ファイル:

- `data/raw/nankan_past_races.csv`
- `data/nankan.duckdb`
- `data/processed/training_rows.csv`
- `data/reports/dataset_manifest_500.json`

集計:

- raw行数: 5681
- レース数: 500
- track: `kawasaki` のみ
- 期間: 2025-10-13 から 2026-06-17
- training_rows.csv: 5622行
- EXC: 24
- SCR: 35
- DNF: 19
- field_size と race_id ごとの行数のズレ: なし
- 同一 race_id 内の horse_no 重複: なし
- race_id の種類: 500
- 想定外の track: なし
- pytest: 11 passed

## 500レース時点のスナップショット

再現・比較用のmanifestと説明文書:

- `data/reports/dataset_manifest_500.json`
- `docs/dataset_snapshot_500.md`

記録済み:

- raw CSV SHA256
- training_rows.csv SHA256
- raw行数、レース数、training行数
- track別件数
- date最小/最大
- EXC/SCR/DNF件数
- 欠損上位列
- `win_odds_final` 欠損数・欠損率
- `passing_order` 全欠損
- field_sizeズレ、horse_no重複、race_idメタデータ矛盾の有無
- pytest結果

## audit_dataset 要約

`python -m nankan_ai.audit_dataset` の結果では、総行数、レース数、track別集計、着順内訳、field_sizeズレ、horse_no重複、基本フラグ件数が確認できています。

track別:

- kawasaki: 500レース / 5681行

finish_position 内訳:

- 1着: 500
- 2着: 500
- 3着: 501
- 4着: 500
- 5着: 500
- 6着: 497
- 7着: 488
- 8着: 475
- 9着: 452
- 10着: 402
- 11着: 349
- 12着: 275
- 13着: 97
- 14着: 67
- SCR: 35
- EXC: 24
- DNF: 19

基本フラグ:

- win_flag: 500
- second_flag: 500
- top3_flag: 1501
- is_scratched: 59
- is_dnf: 19

`top3_flag` が1500ではなく1501なのは、3着扱いが合計501行あるためです。推測補正はしていません。

## 欠損が多い列

`audit_dataset` で欠損数が多い列:

| column | missing_count | メモ |
| --- | ---: | --- |
| `passing_order` | 5681 | 現時点では全行空欄 |
| `win_odds_final` | 2577 | 公式成績ページで単勝オッズ欄が空欄の行が多く、推測補完していない |
| `margin` | 559 | 1着、SCR/EXC/DNFなどで空欄になりやすい |
| `body_weight_diff` | 148 | 公式成績で増減が取れない行がある |
| `finish_time` | 78 | SCR/EXC/DNFなどで空欄 |
| `last_3f` | 78 | SCR/EXC/DNFなどで空欄 |
| `popularity` | 59 | SCR/EXCなどで空欄 |
| `body_weight` | 37 | SCRの一部などで空欄 |

`passing_order` は500レース時点で全5681行が空欄です。これは今回までの入力方針どおりであり、公式ページに通過順が表示されている行でもCSVには入れていません。

## 500レース投入時の実行結果

実行済みコマンド:

- `python -m nankan_ai.validate_csv data/raw/nankan_past_races.csv`
- `python -m nankan_ai.load_to_duckdb data/raw/nankan_past_races.csv`
- `python -m nankan_ai.export_training_rows`
- `python -m nankan_ai.audit_dataset`
- `python -m pytest`

結果:

- validate_csv: 成功
- DuckDB保存: 成功
- training_rows.csv出力: 成功
- audit_dataset: 成功
- pytest: 11 passed

## 次に進む前の注意点

- `win_odds_final` の欠損が大きいので、オッズを使う判断や特徴量化にはまだ進まない。
- `passing_order` は全行空欄のため、脚質や通過順を使う分析にはまだ進まない。
- `finish_position`、`finish_time`、`margin`、`last_3f` はレース後情報なので、将来モデルを作る場合は特徴量として混入させない。
- DNFは学習用CSVに残り、SCR/EXCは学習用CSVから除外される現行ルールを維持する。
- 川崎500レースのみなので、南関東4場全体へ広げる場合は track別の偏りを必ず記録する。
- 追加投入を続ける場合も、50から100レース程度のバッチに分け、各バッチ後に検証する。
- 予想モデル、特徴量追加、自動取得、買い目生成にはまだ進まない。
