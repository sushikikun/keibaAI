# 川崎500レース データセットスナップショット

作成日: 2026-06-18

## 目的

川崎500レース時点のデータ基盤を、後から再現・比較できるように固定記録するためのスナップショットです。

このスナップショットでは、予想モデル作成、特徴量追加、raw CSV修正、`win_odds_final` 補完、自動取得は行いません。

## スナップショットファイル

- manifest: `data/reports/dataset_manifest_500.json`
- raw CSV: `data/raw/nankan_past_races.csv`
- DuckDB: `data/nankan.duckdb`
- training CSV: `data/processed/training_rows.csv`

manifest作成日時:

- `2026-06-18T02:13:47+09:00`

## 主要数値

| item | value |
| --- | ---: |
| raw行数 | 5681 |
| レース数 | 500 |
| training_rows.csv行数 | 5622 |
| track | kawasakiのみ |
| date最小 | 2025-10-13 |
| date最大 | 2026-06-17 |
| EXC | 24 |
| SCR | 35 |
| DNF | 19 |
| `win_odds_final` 欠損数 | 2577 |
| `win_odds_final` 欠損率 | 45.36% |
| `passing_order` 欠損数 | 5681 |
| `passing_order` 欠損率 | 100.00% |

track別:

| track | races | rows |
| --- | ---: | ---: |
| kawasaki | 500 | 5681 |

## 整合性チェック

| check | result |
| --- | --- |
| field_size と race_idごとの行数のズレ | なし |
| 同一race_id内のhorse_no重複 | なし |
| race_idの競走単位メタデータ矛盾 | なし |
| `passing_order` 全欠損 | true |
| DuckDBファイル存在 | true |
| pytest | 11 passed in 3.00s |

race_idは1レース内の全出走馬行で繰り返されるため、raw CSV上で同じrace_idが複数行に出ること自体は正常です。manifestでは、同じrace_idに対して日付・競馬場・レース番号・距離・馬場・クラス・field_sizeなどの競走単位メタデータが矛盾していないかを確認しています。

## 欠損上位列

| column | missing_count | missing_rate |
| --- | ---: | ---: |
| `passing_order` | 5681 | 100.00% |
| `win_odds_final` | 2577 | 45.36% |
| `margin` | 559 | 9.84% |
| `body_weight_diff` | 148 | 2.61% |
| `finish_time` | 78 | 1.37% |
| `last_3f` | 78 | 1.37% |
| `popularity` | 59 | 1.04% |
| `body_weight` | 37 | 0.65% |

`passing_order` は全5681行で空欄です。今回までの入力方針として空欄のまま維持しており、脚質・展開系特徴量にはまだ進みません。

`win_odds_final` 欠損は2577行です。欠損分類は `data/reports/missing_win_odds_races_classified_v2.csv` まで作成済みですが、オッズ値の補完は行っていません。

## SHA256

| file | sha256 |
| --- | --- |
| `data/raw/nankan_past_races.csv` | `3c1e862d7b0ba90944f89a9758b21b7f08c89beaf1494b8f103adecfd23a9ab2` |
| `data/processed/training_rows.csv` | `2a8e24ed71f39cc075371f1f6e7113cbd6fbf67416881dd1ac5b84a3ca1d8e0f` |

## 実行コマンド

実行済み:

- `python -m nankan_ai.dataset_manifest`
- `python -m pytest`

pytest結果をmanifestへ記録するため、テスト後に次のコマンドも実行しています。

- `python -m nankan_ai.dataset_manifest --pytest-result "11 passed in 3.00s"`

## 参照レポート

- `docs/dataset_status.md`
- `docs/dataset_quality_report_500.md`
- `docs/odds_missing_investigation_500.md`
- `docs/odds_manual_check_10.md`
- `docs/odds_manual_check_needs_26.md`
- `docs/odds_data_policy.md`

## 次に進む前の注意

- raw CSVはこのスナップショット作成では修正していません。
- `win_odds_final` は推測補完していません。
- `passing_order` は全欠損のままです。
- 予想モデル、特徴量追加、自動取得、買い目生成にはまだ進みません。
