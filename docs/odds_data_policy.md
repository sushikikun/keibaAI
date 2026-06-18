# win_odds_final データ方針

作成日: 2026-06-18

## 目的

この文書は、南関東競馬AIデータ層MVPにおける `win_odds_final` の扱いを明文化するものです。予想モデル、特徴量追加、自動取得、既存CSVの補完は行いません。

## 基本方針

- 公式成績ページの単勝オッズ欄が空欄なら、CSVの `win_odds_final` も空欄にする。
- `win_odds_final` は推測で補完しない。
- 空欄の理由は、少なくとも `page_has_no_odds` と `input_missing` を区別する。
- 2025-10〜2026-01の `win_odds_final` 欠損は `page_has_no_odds` の可能性が高いが、全件を断定しない。
- オッズを補う場合は、公式成績ページ以外の正規ソース、公式サイト内の別導線、保存期間、または別ページの調査が必要。
- 既存の `data/raw/nankan_past_races.csv` は、この方針文書だけでは修正しない。

## 欠損理由の分類

| 分類 | 意味 | CSV修正方針 |
| --- | --- | --- |
| `page_has_no_odds` | 公式成績ページに単勝オッズ列はあるが値が空欄、または確認できる公式ページ上に値がない | 空欄のまま維持 |
| `input_missing` | 公式ページ上に単勝オッズ値が存在するのにCSVが空欄 | 公式値を確認した上で修正候補にする |
| `different_source_needed` | 成績ページには値がなく、別の正規ソース確認が必要 | 元CSVは空欄のまま、入力元ルールを決めてから対応 |
| `unknown` | 未確認または分類不能 | 空欄のまま維持し、手動確認対象にする |

## 500レース時点の確認結果

500レース時点では、`win_odds_final` 欠損は2577行、欠損率は45.36%です。

代表10レースを手動確認した結果、すべて次の状態でした。

- 公式成績ページには `単勝オッズ` 列がある
- ただし値は全頭空欄
- `OddsTanFuku` URLも対象レースではエラーページ
- 既存CSVの空欄は `input_missing` とは見なさない
- 分類は `page_has_no_odds`

詳細:

- `docs/odds_manual_check_10.md`
- `docs/odds_missing_investigation_500.md`

## needs_manual_check 26レースの追加確認結果

`reason_candidate = needs_manual_check` だった26レースを追加で確認しました。

詳細:

- `docs/odds_manual_check_needs_26.md`

確認結果:

- 26レースすべて `page_has_no_odds`
- 対象欠損行は27行
- SCR: 18
- EXC: 9
- DNF: 0
- 通常出走馬の欠損: 0
- `input_missing`: 0
- `different_source_needed`: 0
- `unknown`: 0

今回の26件は、成績ページにも `OddsTanFuku` にも欠損対象馬の行は存在しましたが、該当馬の単勝オッズ値は空欄でした。そのため、既存CSVの `win_odds_final` は補完しません。

## reason_candidate 付き派生レポート

`data/reports/missing_win_odds_races.csv` は上書きせず、分類候補を追加した派生CSVを作成しています。

- `data/reports/missing_win_odds_races_classified.csv`
- `data/reports/missing_win_odds_races_classified_v2.csv`

`reason_candidate` の分類:

| reason_candidate | 意味 |
| --- | --- |
| `manual_checked_page_has_no_odds` | 代表10レースとして手動確認済み。公式成績ページで単勝オッズ値が空欄 |
| `likely_page_has_no_odds_period` | 2025-10〜2026-01の欠損。手動確認10件と同傾向の可能性が高いが未断定 |
| `needs_manual_check` | 上記以外。追加の手動確認が必要 |

分類件数:

- `manual_checked_page_has_no_odds`: 10
- `likely_page_has_no_odds_period`: 214
- `needs_manual_check`: 26

`missing_win_odds_races_classified_v2.csv` では、分類値を次の4種類だけに整理しています。

- `page_has_no_odds`
- `input_missing`
- `different_source_needed`
- `unknown`

v2の分類件数:

- `page_has_no_odds`: 36
- `input_missing`: 0
- `different_source_needed`: 0
- `unknown`: 214

v2では、手動確認済みの代表10レースと今回確認した26レースだけを `page_has_no_odds` として確定分類しています。2025-10〜2026-01の214レースは `page_has_no_odds` の可能性が高いものの、全件確認済みではないため `unknown` として残しています。

## モデル・特徴量に関する注意

- `win_odds_final` 欠損が多いため、現時点でオッズを使うモデルには進まない。
- オッズあり行だけで学習すると、期間やレース条件の偏りが入る可能性がある。
- `win_odds_final` を使う場合は、利用可能時点が `final_odds` であることを明示し、予測時点と混同しない。
- 予測モデルに進む前に、オッズを使わない方針、オッズ欠損行を除外する方針、別ソースで補う方針のどれにするか決める。

## 次に確認すること

1. `likely_page_has_no_odds_period` の214レースから追加サンプルを確認し、期間全体の傾向として扱えるか判断する。
2. オッズを補う場合、公式成績ページではなくどの正規ソースを参照するか決める。
3. 方針が決まるまで `win_odds_final` は補完しない。
