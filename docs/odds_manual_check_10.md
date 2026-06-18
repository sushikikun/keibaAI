# win_odds_final 欠損 代表10レース手動確認

作成日: 2026-06-18

## 目的

`win_odds_final` 欠損が多い代表10レースについて、公式成績ページ上の単勝オッズ表示を確認するためのメモです。既存CSVの修正、`win_odds_final` の補完、予想モデル作成、特徴量追加、自動取得は行いません。

## 確認方法

対象10レースについて、地方競馬情報サイトの公式成績ページを確認しました。

- 成績ページ: `RaceMarkTable`
- 参考確認: `OddsTanFuku`

確認した観点:

- 公式成績ページに `単勝オッズ` 列が存在するか
- 成績ページ上で各馬の単勝オッズ値が表示されているか
- CSV上の欠損が入力漏れと見なせるか
- 公式の標準オッズページで別途確認できるか

## 結論

代表10レースはすべて、公式成績ページに `単勝オッズ` 列は存在しますが、値は全頭空欄でした。

CSVでも該当10レースは全頭 `win_odds_final` が空欄です。成績ページ上の値も空欄だったため、現時点では `input_missing` とは分類しません。

また、同じ公式サイトの `OddsTanFuku` URLも確認しましたが、対象10レースではオッズ表ではなくエラーページが返り、単勝・複勝オッズ表は確認できませんでした。

したがって、10レースの分類はすべて `page_has_no_odds` とします。オッズを復元したい場合は、公式サイト内の別導線、保存期間、別ページ、または別の正規データソースを改めて確認する必要があります。

## 10レース確認結果

| race_id | date | race_no | race_name | 成績ページの単勝オッズ列 | 成績ページの単勝オッズ値 | CSV入力漏れか | OddsTanFuku確認 | 分類 |
| --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| `20251014_kawasaki_7` | 2025-10-14 | 7 | 材木座賞Ｃ２四 五 六 | あり | 全14頭空欄 | いいえ | エラーページでオッズ表なし | `page_has_no_odds` |
| `20251014_kawasaki_10` | 2025-10-14 | 10 | 大磯まつり２０２５記念Ｂ２二Ｂ３一 | あり | 全14頭空欄 | いいえ | エラーページでオッズ表なし | `page_has_no_odds` |
| `20251014_kawasaki_12` | 2025-10-14 | 12 | 西御門賞Ｃ１六 七 | あり | 全14頭空欄 | いいえ | エラーページでオッズ表なし | `page_has_no_odds` |
| `20251015_kawasaki_5` | 2025-10-15 | 5 | 山ノ内賞Ｃ２七 八 九 | あり | 全14頭空欄 | いいえ | エラーページでオッズ表なし | `page_has_no_odds` |
| `20251015_kawasaki_7` | 2025-10-15 | 7 | 和田塚賞Ｃ２選定馬 | あり | 全14頭空欄 | いいえ | エラーページでオッズ表なし | `page_has_no_odds` |
| `20251015_kawasaki_10` | 2025-10-15 | 10 | 源氏山特別Ｂ３三 | あり | 全14頭空欄 | いいえ | エラーページでオッズ表なし | `page_has_no_odds` |
| `20251015_kawasaki_12` | 2025-10-15 | 12 | 雪ノ下賞Ｃ１四 五 | あり | 全14頭空欄 | いいえ | エラーページでオッズ表なし | `page_has_no_odds` |
| `20251016_kawasaki_6` | 2025-10-16 | 6 | ＹＪＳトライアルラウンド川崎 第１戦Ｃ３選定馬 | あり | 全14頭空欄 | いいえ | エラーページでオッズ表なし | `page_has_no_odds` |
| `20251016_kawasaki_8` | 2025-10-16 | 8 | ＹＪＳトライアルラウンド川崎 第２戦Ｃ２選定馬 | あり | 全14頭空欄 | いいえ | エラーページでオッズ表なし | `page_has_no_odds` |
| `20251017_kawasaki_5` | 2025-10-17 | 5 | 木菟賞３歳１ | あり | 全14頭空欄 | いいえ | エラーページでオッズ表なし | `page_has_no_odds` |

## 公式URL

| race_id | 成績ページ | 参考: OddsTanFuku |
| --- | --- | --- |
| `20251014_kawasaki_7` | https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/RaceMarkTable?k_raceDate=2025%2F10%2F14&k_raceNo=7&k_babaCode=21 | https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/OddsTanFuku?k_raceDate=2025%2F10%2F14&k_raceNo=7&k_babaCode=21 |
| `20251014_kawasaki_10` | https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/RaceMarkTable?k_raceDate=2025%2F10%2F14&k_raceNo=10&k_babaCode=21 | https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/OddsTanFuku?k_raceDate=2025%2F10%2F14&k_raceNo=10&k_babaCode=21 |
| `20251014_kawasaki_12` | https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/RaceMarkTable?k_raceDate=2025%2F10%2F14&k_raceNo=12&k_babaCode=21 | https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/OddsTanFuku?k_raceDate=2025%2F10%2F14&k_raceNo=12&k_babaCode=21 |
| `20251015_kawasaki_5` | https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/RaceMarkTable?k_raceDate=2025%2F10%2F15&k_raceNo=5&k_babaCode=21 | https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/OddsTanFuku?k_raceDate=2025%2F10%2F15&k_raceNo=5&k_babaCode=21 |
| `20251015_kawasaki_7` | https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/RaceMarkTable?k_raceDate=2025%2F10%2F15&k_raceNo=7&k_babaCode=21 | https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/OddsTanFuku?k_raceDate=2025%2F10%2F15&k_raceNo=7&k_babaCode=21 |
| `20251015_kawasaki_10` | https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/RaceMarkTable?k_raceDate=2025%2F10%2F15&k_raceNo=10&k_babaCode=21 | https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/OddsTanFuku?k_raceDate=2025%2F10%2F15&k_raceNo=10&k_babaCode=21 |
| `20251015_kawasaki_12` | https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/RaceMarkTable?k_raceDate=2025%2F10%2F15&k_raceNo=12&k_babaCode=21 | https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/OddsTanFuku?k_raceDate=2025%2F10%2F15&k_raceNo=12&k_babaCode=21 |
| `20251016_kawasaki_6` | https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/RaceMarkTable?k_raceDate=2025%2F10%2F16&k_raceNo=6&k_babaCode=21 | https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/OddsTanFuku?k_raceDate=2025%2F10%2F16&k_raceNo=6&k_babaCode=21 |
| `20251016_kawasaki_8` | https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/RaceMarkTable?k_raceDate=2025%2F10%2F16&k_raceNo=8&k_babaCode=21 | https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/OddsTanFuku?k_raceDate=2025%2F10%2F16&k_raceNo=8&k_babaCode=21 |
| `20251017_kawasaki_5` | https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/RaceMarkTable?k_raceDate=2025%2F10%2F17&k_raceNo=5&k_babaCode=21 | https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/OddsTanFuku?k_raceDate=2025%2F10%2F17&k_raceNo=5&k_babaCode=21 |

## 欠損の主原因候補

この10レースについては、CSV入力漏れよりも、公式成績ページ上で単勝オッズ値が表示されていないことが主原因候補です。

ただし、これは「公式サイトのどこにも存在しない」と断定するものではありません。少なくとも確認した `RaceMarkTable` では値がなく、確認した `OddsTanFuku` URLでもオッズ表は確認できませんでした。

## 次に取るべき対応

1. `page_has_no_odds` を `win_odds_final` 欠損理由の有力分類として扱う。
2. 2025-10から2026-01の欠損レースで、同じ傾向が広く出ているか確認する。
3. オッズを使う方針にする場合は、成績ページ以外の正規データソースまたは公式内の別導線を検討する。
4. 現CSVの `win_odds_final` はまだ補完しない。
5. オッズ欠損のままモデルへ進む場合は、オッズ列を使わない方針を明記する。

