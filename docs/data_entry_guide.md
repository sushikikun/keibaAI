# 南関東競馬AI 手動CSV入力ガイド

このガイドは、本物の南関東過去レースをまず10レース分だけ手動CSVへ入力するためのものです。予想モデル、自動取得、買い目生成はまだ作りません。

## 基本ルール

- 1行 = 1頭・1レース
- まず10レース分だけ入力する
- 入力先は `data/raw/nankan_past_races.csv`
- `data/raw/nankan_past_races_template.csv` はテンプレートとして残す
- 不明値は空欄にする
- 架空データやfixtureを本物のデータとして混ぜない

## 競馬場表記ルール

`track` は次の4種類だけを使います。

| 競馬場 | track |
| --- | --- |
| 川崎 | `kawasaki` |
| 大井 | `oi` |
| 船橋 | `funabashi` |
| 浦和 | `urawa` |

## race_idルール

`race_id` は次の形式にします。

```text
YYYYMMDD_track_R
```

例:

```text
20260616_kawasaki_10
20260616_oi_08
20260616_funabashi_11
20260616_urawa_06
```

注意:

- 日付部分は開催日を `YYYYMMDD` で書く
- `track` は上の表記ルールに合わせる
- レース番号は公式のレース番号を使う
- `race_no` は数値列として別に入力する

## SCR / EXC / DNF の扱い

`finish_position` は次のように入力します。

- 取消: `SCR`
- 除外: `EXC`
- 中止: `DNF`
- 通常の着順: 数値
- 不明: 空欄

学習用CSVでは、`SCR` と `EXC` は除外されます。`DNF` は除外せず、`is_dnf = 1` として残します。

## 公式サイトから取る列

公式サイトのページ構成や表示名は変わる可能性があります。迷った場合は空欄にし、未確定事項として残してください。自動スクレイピングはまだ作りません。

| CSV列 | 取る場所の目安 | 入力メモ |
| --- | --- | --- |
| `race_id` | 手入力で作成 | `YYYYMMDD_track_R` |
| `date` | 開催日・レース日 | `YYYY-MM-DD` |
| `track` | 開催場 | `kawasaki` / `oi` / `funabashi` / `urawa` |
| `race_no` | レース番号 | 数値 |
| `race_name` | レース名 | 表示どおり |
| `distance` | 距離 | 数値だけ。例: `1600` |
| `surface` | コース種別 | 例: `dirt`。迷う場合は空欄 |
| `weather` | 天候 | 表示どおり |
| `track_condition` | 馬場状態 | 表示どおり |
| `class_name` | 条件・クラス | 表示どおり。迷う場合は空欄 |
| `field_size` | 出走頭数 | 取消・除外をどう数えるか迷う場合は公式表示を優先 |
| `horse_no` | 馬番 | 数値 |
| `gate_no` | 枠番 | 数値 |
| `horse_name` | 馬名 | 表示どおり |
| `sex` | 性別 | 表示どおり |
| `age` | 馬齢 | 数値 |
| `carried_weight` | 負担重量 | 小数可。例: `56.0` |
| `jockey_name` | 騎手名 | 表示どおり |
| `trainer_name` | 調教師名 | 表示どおり |
| `body_weight` | 馬体重 | 数値。不明なら空欄 |
| `body_weight_diff` | 馬体重増減 | 数値。増減なしは `0` |
| `finish_position` | 着順 | 数値 / `SCR` / `EXC` / `DNF` |
| `finish_time` | 走破時計 | 表示どおり。不明なら空欄 |
| `margin` | 着差 | 表示どおり。不明なら空欄 |
| `passing_order` | 通過順 | 表示どおり。不明なら空欄 |
| `last_3f` | 上がり3F | 小数可。不明なら空欄 |
| `popularity` | 人気 | 数値。不明なら空欄 |
| `win_odds_final` | 最終単勝オッズ | 小数可。不明なら空欄 |

## 入力時に迷いやすい項目

- `field_size`: 公式サイトの出走頭数とCSVの行数がズレることがあります。まずは公式表示を入力し、バリデーションと監査で確認します。
- `surface`: 南関東は基本的にダートですが、公式表記が確認できない場合は空欄でも構いません。
- `class_name`: 条件名、格、組、特別戦名などの切り分けは未確定です。迷ったら公式表示をそのまま入れるか空欄にします。
- `margin`: 着差の表記揺れがあり得ます。まずは公式表示どおりに入れます。
- `passing_order`: 公式表示がない場合は空欄にします。
- `body_weight_diff`: `+2` のような表示は `2`、`-4` は `-4`、増減なしは `0` にします。
- `win_odds_final`: 単勝オッズが取れない場合は空欄にします。馬単オッズはまだ追加しません。

## 入力後に実行するコマンド

10レース分を入力したら、次の順番で確認します。

```powershell
python -m nankan_ai.validate_csv data/raw/nankan_past_races.csv
python -m nankan_ai.load_to_duckdb data/raw/nankan_past_races.csv
python -m nankan_ai.export_training_rows
python -m nankan_ai.audit_dataset
```

CSVだけを監査したい場合:

```powershell
python -m nankan_ai.audit_dataset --csv-path data/raw/nankan_past_races.csv
```

エラーが出た場合は、データ量を増やす前にCSVを直してください。

## 実データ投入メモ

2026-06-17 川崎1R〜10Rの公式成績CSV `nankan_20260617_kawasaki_1_10.csv` を `data/raw/nankan_past_races.csv` に取り込みました。

確認済み内容:

- raw CSVは105行、10レース
- `track` は `kawasaki` のみ
- 3Rのササキンポピー、9Rのトニープリンスは `finish_position = EXC`
- `SCR` は0頭
- `DNF` は0頭
- `passing_order` は今回は空欄
- `training_rows.csv` は `EXC` 2頭を除外して103行
- `win_flag` は10件
- `second_flag` は10件
- `top3_flag` は30件
