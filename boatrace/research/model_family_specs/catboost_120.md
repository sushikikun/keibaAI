# CatBoost 120-class direct model

> Gate 0の設計書。学習・暫定評価・champion選定は行わない。

## 問題定義

6艇レースから固定class mapの三連単120確率を直接推定する表形式baseline。

## 入力単位

1レース。race特徴1行とlane順に並べたboat特徴6行を固定長へ展開。

## 入力shape・出力shape

input: [batch, race_fields + 6 × boat_fields]; output logits: [batch, 120]

## 確率正規化

120 logitsへ単一softmax。class map v1の0..119順を維持。

## 主損失

natural-log 120-class cross entropy; main population is unique_order only.

## 補助損失候補

原則なし。比較時にcourse/ST/決まり手headを一つずつ追加可能。

## 艇の順序・艇番の扱い

lane 1..6で固定し、laneを落とさない。120 classはlane identity。

## 未知選手・新モーター

unknown racer category; generation-safe unknown motor/boat bucket; numeric history has missing flag.

## 欠損処理

CatBoost native missing/category handlingと明示missing indicatorを比較。

## point-in-time要件

全特徴のsource max time < race cutoff。actual_*やresult_*は入力禁止。

## 主なアブレーション

current49; +relative; +history; +meeting; category encoding.

## 想定する失敗理由

120 classの疎性、lane展開による対称性不足、世代衝突、過適合。

## 他モデルとの相補性

自己回帰・triple scorerとは異なる直接分類誤差を持つ候補。

## 計算量の概算区分

low-to-medium

## 共通契約

評価は`boatrace_model_evaluation_v1_1`の三連単120クラス自然対数Log Lossを主指標とする。オッズ・人気・投票数・払戻は特徴、教師、重み、校正、選定に使わない。
