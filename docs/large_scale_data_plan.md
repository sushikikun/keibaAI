# 大量データ運用設計

作成日: 2026-06-18

## 目的

南関東競馬AIのデータ基盤を、最終的に約30,000レースまで安全に拡張するための運用設計です。

この計画では、予想モデル作成、特徴量追加、自動取得、自動投票、推測補完は行いません。

## 目標規模

| item | value |
| --- | ---: |
| 目標レース数 | 約30,000レース |
| 想定行数 | 約300,000〜400,000行 |
| 1 batch 推奨サイズ | 500〜1,000レース |
| 現在の規模 | 500レース / 5681行 |

1行はこれまで通り、1頭・1レースです。

## batch単位の基本方針

追加データは必ずbatch CSVとして `data/incoming/` に置きます。

標準ファイル:

- `data/incoming/nankan_past_races_append.csv`

rawは直接編集しません。追加は必ず次の流れで行います。

1. `validate_append_csv`
2. `merge_append_csv` dry-run
3. `merge_append_csv --apply`
4. `dataset_manifest`
5. `append_batches.csv` へのbatch log記録
6. 必要に応じて `docs/dataset_snapshot_<race_count>.md` を作成

## batch命名ルール

batch log上のID:

```text
append_YYYYMMDD_HHMMSS
```

例:

```text
append_20260618_030405
```

外部で作る追加CSVを保管する場合の推奨名:

```text
nankan_append_<track_scope>_<date_min>_<date_max>_<race_count>r.csv
```

例:

```text
nankan_append_kawasaki_20250101_20250331_720r.csv
```

実際に取り込む直前は、作業用として次の名前にコピーします。

```text
data/incoming/nankan_past_races_append.csv
```

## date range 管理ルール

各batchで必ず次を記録します。

- `track_scope`
- `date_min`
- `date_max`
- `race_count_expected`
- `race_count_actual`

`race_count_expected` は作業計画上のレース数です。未指定の場合は空欄にします。`race_count_actual` はCSVから実際に数えたレース数です。

date rangeは、同一batch内でなるべく連続した開催日になるようにします。中抜けがある場合は、append reportか作業メモに理由を残します。

## 集める順番

当面は競馬場別に集めます。

推奨順:

1. 川崎を1000レースまで拡張
2. 川崎をまとまった規模まで拡張し、欠損傾向と表記揺れを確認
3. 大井、船橋、浦和を同じ受け入れ手順で追加
4. 4場が揃った段階でtrack別の件数偏りを確認

理由:

- 競馬場ごとに距離体系、番組、表記、欠損傾向が異なる
- まず川崎で運用を固めると、他場追加時の問題を切り分けやすい
- いきなり日付順で4場を混ぜると、track別の品質問題を見つけにくい

ただし、最終的なモデル検討前には日付順の時系列管理が重要になります。データ投入は競馬場別でも、manifestとbatch logでは必ずdate rangeを残します。

## 実行フロー

追加CSV検証:

```bash
python -m nankan_ai.validate_append_csv data/incoming/nankan_past_races_append.csv
```

dry-run:

```bash
python -m nankan_ai.merge_append_csv data/incoming/nankan_past_races_append.csv --race-count-expected 500
```

apply:

```bash
python -m nankan_ai.merge_append_csv data/incoming/nankan_past_races_append.csv --race-count-expected 500 --apply
```

apply後の確認:

```bash
python -m nankan_ai.validate_csv data/raw/nankan_past_races.csv
python -m nankan_ai.load_to_duckdb data/raw/nankan_past_races.csv
python -m nankan_ai.export_training_rows
python -m nankan_ai.audit_dataset
python -m nankan_ai.dataset_manifest --label <race_count>
python -m pytest
```

## batch log

batch log:

- `data/reports/append_batches.csv`

記録する主な項目:

- batch_id
- mode: `dry_run` / `applied`
- append CSV path / SHA256
- raw CSV before / after SHA256
- before / after raw rows
- before / after race count
- added rows / races
- track_scope
- date_min / date_max
- race_count_expected / race_count_actual
- validation_status
- report_path

dry-runでもbatch logを残します。dry-runではrawは変わらないため、before/afterのraw SHA256と行数は同じです。

## 失敗時の戻し方

validate_append_csvで失敗した場合:

- rawは変更されない
- append reportとbatch logで失敗理由を確認
- 追加CSVを修正して再度validateする

dry-runで違和感がある場合:

- rawは変更されない
- `append_rows`、`append_races`、`date_min/date_max`、`track_scope` を確認
- 想定と違う場合は追加CSVを修正する

apply後に問題が見つかった場合:

1. 該当batchの `append_report_YYYYMMDD_HHMMSS.md` を確認
2. `append_batches.csv` でbatch_id、before/after SHA256、追加件数を確認
3. `data/backups/nankan_past_races_before_append_YYYYMMDD_HHMMSS.csv` を確認
4. rawを戻す場合は、必ず対象backupとbatch_idを確認してから行う
5. 戻した後は `validate_csv`、`load_to_duckdb`、`export_training_rows`、`audit_dataset`、`dataset_manifest` を再実行する

戻し作業も推測では行いません。どのbatchを戻すか、どのbackupへ戻すかを明確にします。

## rawを直接編集しないルール

`data/raw/nankan_past_races.csv` は、append pipeline以外で編集しません。

理由:

- raw SHA256で再現性を確認できなくなる
- batch logと実データの対応が崩れる
- 大量データでは手作業の差分追跡が困難になる

修正が必要な場合も、原則として修正用appendまたは別途定義した修正batchとして扱います。修正運用は未確定のため、勝手にrawを直接直しません。

## 取得元不明データの扱い

取得元が不明なデータは入れません。

各batchで最低限確認すること:

- 公式成績ページまたは正規の確認元に基づいている
- race_id、date、track、race_noが確認できる
- finish_position、SCR/EXC/DNFが確認できる
- `win_odds_final` が空欄の場合、空欄のまま維持する
- 不明値を推測で埋めていない

## 大量データ向け監査項目

大量投入では、通常のvalidateに加えて次を確認します。

- 月別レース数
- track別レース数
- race_id / race_noの連番欠落
- batch別追加件数
- raw CSV SHA256
- training_rows.csv SHA256
- date_min / date_max
- field_sizeズレ
- horse_no重複
- race_idの競走単位メタデータ矛盾
- `win_odds_final` 欠損数・欠損率
- `passing_order` 欠損数・欠損率

`audit_dataset` では月別レース数と日付内race_no欠落を確認します。`dataset_manifest` では月別レース数、race_no欠落、batch log要約、raw/training SHA256を記録します。

## 次に未確定のこと

- 修正batchの正式ルール
- 4場をどの順番で30,000レースまで増やすか
- `horse_id`、`jockey_id`、`trainer_id` の扱い
- オッズ欠損を別正規ソースで補うか
- `passing_order` をいつ入力対象にするか
