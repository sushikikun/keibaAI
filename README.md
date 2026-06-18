# 南関東競馬AI データ層MVP

このプロジェクトは、南関東競馬AIのために、手動で集めた過去レースCSVを安全に保存・検証・変換するための最初の土台です。

まだ予測モデル、買い目生成、自動スクレイピング、リアルタイム取得は作りません。まずは過去レースCSVをDuckDBに保存し、AI学習に使える行データへ変換できる状態に集中します。

## 対象競馬場

`track` は次の4種類だけを使います。

| 競馬場 | track |
| --- | --- |
| 川崎 | `kawasaki` |
| 大井 | `oi` |
| 船橋 | `funabashi` |
| 浦和 | `urawa` |

## CSV入力ルール

最初に扱うCSVは次のファイルです。

```powershell
data/raw/nankan_past_races.csv
```

テンプレートは次の場所にあります。

```powershell
data/raw/nankan_past_races_template.csv
```

1行は「1頭・1レース」です。CSVヘッダーは必ず次の順番・名前で用意します。

```csv
race_id,date,track,race_no,race_name,distance,surface,weather,track_condition,class_name,field_size,horse_no,gate_no,horse_name,sex,age,carried_weight,jockey_name,trainer_name,body_weight,body_weight_diff,finish_position,finish_time,margin,passing_order,last_3f,popularity,win_odds_final
```

入力ルール:

- 不明値は空欄にします
- 取消は `finish_position = SCR`
- 除外は `finish_position = EXC`
- 中止は `finish_position = DNF`
- 通常の着順は数値で入力します
- `date` は `YYYY-MM-DD`
- `distance` は数値
- `horse_no`, `gate_no`, `age`, `field_size`, `popularity` は数値
- `win_odds_final` は小数可
- サンプルデータやfixtureを本物のデータのように扱わないでください

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

## セットアップ

Python 3.12以上を使います。まだ仮想環境がない場合は作成して有効化します。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

依存関係をインストールします。pipのバージョン確認で遅くなる場合があるため、Windowsでは次のようにしてから実行すると安定します。

```powershell
$env:PIP_DISABLE_PIP_VERSION_CHECK="1"
python -m pip install -e .
```

今回のローカル検証では、`duckdb 1.5.4` と `pytest 9.1.0` で動作確認しました。

## テスト実行

```powershell
python -m pytest
```

今回のローカル検証結果:

```text
6 passed
```

pytestは南関東MVP用のテストだけを集める設定にしています。既存の別プロジェクト用テストはこのMVPの検証対象外です。

## valid fixtureでの動作確認

テスト用fixtureは次の2つです。どちらも架空データであり、本物の競馬データとして扱わないでください。

```powershell
tests/fixtures/nankan_past_races_valid.csv
tests/fixtures/nankan_past_races_invalid.csv
```

valid fixtureの検証:

```powershell
python -m nankan_ai.validate_csv tests/fixtures/nankan_past_races_valid.csv
```

確認済み結果:

```text
OK: tests\fixtures\nankan_past_races_valid.csv (8 rows, 2 races)
```

DuckDBへ保存:

```powershell
python -m nankan_ai.load_to_duckdb tests/fixtures/nankan_past_races_valid.csv
```

確認済み結果:

```text
OK: loaded 8 rows into data\nankan.duckdb:past_race_rows
```

学習用CSVを出力:

```powershell
python -m nankan_ai.export_training_rows
```

確認済み結果:

```text
OK: exported 6 rows to data\processed\training_rows.csv
```

作成されるファイル:

```powershell
data/nankan.duckdb
data/processed/training_rows.csv
```

監査コマンド:

```powershell
python -m nankan_ai.audit_dataset
```

CSVだけを直接監査したい場合:

```powershell
python -m nankan_ai.audit_dataset --csv-path tests/fixtures/nankan_past_races_valid.csv
```

## 10レース入力後の確認フロー

本物の南関東過去レースを入力するときは、まず `data/raw/nankan_past_races.csv` に10レース分だけ入力します。入力ガイドは [docs/data_entry_guide.md](docs/data_entry_guide.md) にあります。

10レース分を入力したら、次の順番で確認します。

```powershell
python -m nankan_ai.validate_csv data/raw/nankan_past_races.csv
python -m nankan_ai.load_to_duckdb data/raw/nankan_past_races.csv
python -m nankan_ai.export_training_rows
python -m nankan_ai.audit_dataset
```

`audit_dataset` では、総行数、レース数、track別件数、欠損が多い列、着順内訳、`field_size` のズレ、`horse_no` 重複、日付範囲、基本フラグ件数を確認できます。ここで違和感がある場合は、100レースへ増やす前にCSVを直してください。

## 実データ投入メモ

2026-06-17 川崎1R〜10Rの公式成績CSV `nankan_20260617_kawasaki_1_10.csv` を `data/raw/nankan_past_races.csv` に取り込みました。

確認済み内容:

- raw CSV: 105行、10レース、`track = kawasaki` のみ
- `finish_position`: `EXC` が2頭、`SCR` が0頭、`DNF` が0頭
- `EXC`: 3R ササキンポピー、9R トニープリンス
- `passing_order`: 今回は全行空欄
- `validate_csv`: 成功
- `load_to_duckdb`: 成功、`past_race_rows` に105行
- `export_training_rows`: 成功、`EXC` 2頭を除外して103行
- `audit_dataset`: 成功
- `training_rows.csv`: `win_flag` 10件、`second_flag` 10件、`top3_flag` 30件

## 学習用CSVの扱い

`export_training_rows` は、DuckDBの `past_race_rows` から読み込み、元CSVの列に次の列を追加します。

- `win_flag`: `finish_position` が `1` なら `1`、それ以外は `0`
- `second_flag`: `finish_position` が `2` なら `1`、それ以外は `0`
- `top3_flag`: `finish_position` が `1`, `2`, `3` なら `1`、それ以外は `0`
- `is_scratched`: `SCR` または `EXC` なら `1`
- `is_dnf`: `DNF` なら `1`
- `distance_bucket`: `short` / `mile` / `middle` / `long`
- `body_weight_available`: `body_weight` が入っていれば `1`
- `odds_available`: `win_odds_final` が入っていれば `1`

取消 `SCR` と除外 `EXC` は学習用CSVから除外します。中止 `DNF` は除外せず、`is_dnf = 1` として残します。今回のfixture検証でも、`SCR` / `EXC` は除外され、`DNF` は残ることを確認済みです。

距離区分はMVPの仮ルールとして、`1400m` 以下を `short`、`1700m` 以下を `mile`、`2200m` 以下を `middle`、それより長い距離を `long` にしています。正式なしきい値は未確定事項です。

## バリデーション内容

`validate_csv.py` は次を確認します。

- 必須カラムが存在するか
- `race_id` 形式が正しいか
- `track` が `kawasaki` / `oi` / `funabashi` / `urawa` のどれか
- `date` 形式が正しいか
- 数値カラムが数値として読めるか
- `finish_position` が数値 / `SCR` / `EXC` / `DNF` / 空欄のどれか
- 同一 `race_id` 内の `field_size` と実際の行数が大きくズレていないか
- 同一 `race_id` 内で `horse_no` が重複していないか

`field_size` はMVPでは実際の行数との差が1頭以内なら許容し、2頭以上ズレたらエラーにします。この許容幅は未確定事項です。

## データを増やす順番

最初は10レース分だけ入力して、検証・DuckDB保存・学習用CSV出力が通ることを確認します。

次に100レース、500レースへ増やします。データ量を増やす前に、エラーが出たCSVの入力ルールを先に直してください。

## よくあるエラー

`python` が見つからない:
Python 3.12以上をインストールするか、利用しているPython実行ファイルで `.venv` を作成してから、仮想環境を有効化してください。

`pip install -e .` が遅い、または最後で止まったように見える:
次を設定してから再実行してください。

```powershell
$env:PIP_DISABLE_PIP_VERSION_CHECK="1"
python -m pip install -e .
```

pytestが一時フォルダの削除で失敗する:
このプロジェクトでは `.tmp/pytest` を使う設定にしています。古い `.pytest_run_tmp` やWindowsの一時フォルダに権限問題がある場合でも、通常は `python -m pytest` で動きます。

DuckDBファイルがロックされる:
`data/nankan.duckdb` を開いているアプリを閉じてから再実行してください。

OneDrive配下でDuckDB、pytest、Git、pipが遅い・ロックされる:
OneDriveの同期やファイルロックが原因になることがあります。問題が続く場合は、プロジェクトを `C:\work` 配下など同期対象外のフォルダへ移すことを推奨します。

## 未確定事項

- 馬IDをどうするか
- 騎手IDをどうするか
- 調教師IDをどうするか
- 払戻データをいつ追加するか
- 馬単オッズをいつ追加するか
- 自動取得をするかどうか
- 距離区分 `short` / `mile` / `middle` / `long` の正式なしきい値
- `field_size` と実際の行数のズレをどこまで許容するか
