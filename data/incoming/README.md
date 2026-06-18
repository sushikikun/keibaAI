# incoming CSV

追加投入用の手入力CSVを置く場所です。

## 置くファイル

- `data/incoming/nankan_past_races_append.csv`

## ルール

- ヘッダーは `data/raw/nankan_past_races.csv` と完全一致させる
- 1行 = 1頭・1レース
- 川崎のみを入れる
- 既存rawにある `race_id` は入れない
- 同一 `race_id` 内で `horse_no` を重複させない
- `field_size` は同一 `race_id` の行数と一致させる
- 不明値は空欄にする
- `passing_order` は空欄でよい
- SCR / EXC / DNF は既存ルールどおり入力する
- `win_odds_final` は推測補完しない

## 実行

まず検証:

```bash
python -m nankan_ai.validate_append_csv data/incoming/nankan_past_races_append.csv
```

dry-run:

```bash
python -m nankan_ai.merge_append_csv data/incoming/nankan_past_races_append.csv
```

実際に追記:

```bash
python -m nankan_ai.merge_append_csv data/incoming/nankan_past_races_append.csv --apply
```
