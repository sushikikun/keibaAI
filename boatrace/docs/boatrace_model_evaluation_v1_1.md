# ボートレース無オッズ確率モデル 評価契約 v1.1

## 1. 目的と固定範囲

この契約は、6艇レースの三連単120クラス確率を、オッズに依存せず再現可能に評価するための機械判定規則である。研究基盤v0ではデータ、対象レース、クラス順、予測検証、評価式を固定する。CatBoost、Transformer、Oracle等の実モデルは対象外とする。

機械可読な正本は `configs/boatrace_model_evaluation_v1_1.json` である。本書とJSONが矛盾する場合はJSONを優先する。

## 2. 予測時点と利用可能情報

予測cutoffは、公式の展示・直前情報を取得した後、公式締切時刻 `closed_at` より前である。入力できるのは、そのcutoffまでに利用可能になった公式情報だけである。

次の情報は、特徴量、教師、sample weight、校正、hyperparameter選択、モデル選択のどの段階にも使用しない。

- オッズ
- 人気・人気順
- 投票数・発売額・bet count
- 払戻・返還

正式complete corpusが完全性監査のためにオッズ・払戻を保有していても、snapshot builderはそのファイルを特徴量・教師生成のために読み込まない。

本番進入 `actual_course`、本番ST `actual_start_timing`、決まり手 `winning_technique_number`、4～6着はauxiliary targetとして保持できるが、推論入力にはできない。

## 3. 評価単位・対象状態

1レースを1サンプルとし、`race_key`を一意キーとする。

- `unique_order`: 6艇の `actual_finish` が1～6の置換であり、同着がない。主one-hot評価へ含める。
- `tied`: 6艇の有効な着順値に重複がある。主one-hot評価へ含めない。
- `void`: 不成立、結果不完全、無効な着順、6艇構造不成立等。主one-hot評価へ含めない。

予測カバレッジの分母は、結果状態を知らない時点で予測可能だった `prediction_input_eligible=true` の全レースである。主指標の分母は、そのうち `main_evaluation_eligible=true` のレースである。したがって、同着やvoidを予測提出後に除外してカバレッジを上げることはできない。

## 4. 三連単class map

艇のidentityは枠番 `lane` 1～6である。クラスは、1着、2着、3着の順に昇順nested loopで列挙する。

1. firstを1～6
2. secondをfirst以外の1～6
3. thirdをfirstとsecond以外の1～6

これにより class_id 0～119を固定する。正本は `configs/trifecta_class_map_v1.json` であり、classes配列のcanonical JSON SHA-256は `e5b36e44602700d1c50cbd2c839a20328fcc317abc0c7de8388ed1b91d410f50` である。実装は120件、連番、重複なし、encode/decode round-trip、mapping SHA-256を検証しなければならない。

## 5. 予測ファイル

予測ファイルはUTF-8 CSVまたはCSV.GZとし、次の列を持つ。

- `race_key`
- `p_000` ～ `p_119`

各行は長さ120の確率配列である。全値が有限、0以上1以下、合計が1でなければならない。合計の絶対許容誤差は `1e-10` とする。重複、欠落、余分な `race_key` は認めない。

NaN、Inf、負確率、範囲外確率、合計不正、配列長不正、カバレッジ不足は失格である。0確率自体は構造上の失格ではないが、観測クラスまたは観測条件事象へ0を与えたlog lossは正の無限大になる。

## 6. 指標

対数はすべて自然対数を使う。レース \(r\) の120確率を \(p_{r,k}\)、正解classを \(y_r\) とする。

- `trifecta_log_loss`: \(-\ln p_{r,y_r}\)
- `winner_log_loss`: 正解1着艇をfirstに持つ20クラスの確率和に対するlog loss
- `exacta_log_loss`: 正解1・2着順を持つ4クラスの確率和に対するlog loss
- `top3_set_log_loss`: 正解上位3艇集合の6順列に対応する確率和に対するlog loss
- `second_given_first_log_loss`: 正解exacta確率を正解winner確率で割った条件付き確率のlog loss
- `third_given_first_second_log_loss`: 正解三連単確率を正解exacta確率で割った条件付き確率のlog loss
- `trifecta_brier`: \(\sum_{k=0}^{119}(p_{r,k}-1[k=y_r])^2\)

集約は主評価対象レースの単純平均とし、オッズ、払戻、人気等による重み付けを行わない。

## 7. 一様モデルの受入値

各クラスを `1/120` とする一様モデルは、絶対誤差 `1e-12` 以内で次の値になる。

| 指標 | 期待値 |
|---|---:|
| trifecta log loss | 4.787491742782046 |
| winner log loss | 1.791759469228055 |
| exacta log loss | 3.401197381662156 |
| top3 set log loss | 2.995732273553991 |
| second given first log loss | 1.609437912434100 |
| third given first second log loss | 1.386294361119891 |
| standard 120-class Brier | 0.991666666666667 |

## 8. snapshotと監査

snapshotは正式complete corpusの `integrity_registry.sqlite` に記録されたcanonical `race_owners` を、単一read transactionで固定して生成する。source batchは `integrity_status=passed` かつ `hash_status=verified` でなければならない。各batch manifestと使用した `race_facts.csv`、`entry_facts.csv` のSHA-256を再検証する。

特徴量は明示allowlistで選び、名前の部分一致だけで列を推測しない。`race_features` と `boat_features` に禁止列がないことをvalidatorで再検査する。snapshot manifestはデータ成果物、設定、実装ファイル、source batchのSHA-256を記録する。manifest自身のhashを自身へ埋め込むことは循環になるため、self hashだけはmanifest外から計算する。

現行環境にPyArrow、DuckDB、FastParquetがない場合は、依存を追加せずCSV fallbackを使用する。Parquet化のために必要な依存は別途報告し、無断でインストールしない。
