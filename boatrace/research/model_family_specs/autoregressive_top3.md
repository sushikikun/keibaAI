# Autoregressive Top-3 model

> Gate 0の設計書。学習・暫定評価・champion選定は行わない。

## 問題定義

P(first)P(second|first)P(third|first,second)で三連単を因子分解。

## 入力単位

1レースと6艇集合、teacher-forced target prefix（学習時のみ）。

## 入力shape・出力shape

input [batch,6,d]; heads [6], [6 conditional], [6 conditional]; enumerated output [batch,120].

## 確率正規化

各段階で既選択艇をmaskしたsoftmax。120積確率の和は1。

## 主損失

3段階negative log likelihoodの和＝ordered-trifecta NLL。

## 補助損失候補

winner/exacta conditional lossesは診断内訳であり独自総合点にしない。

## 艇の順序・艇番の扱い

lane embeddingを保持し、選択済laneを厳密mask。

## 未知選手・新モーター

艇encoderのunknown entity embeddingとmissing indicator。

## 欠損処理

input missingをmask/indicator化。target prefix missingはmain学習から除外。

## point-in-time要件

推論時にactual first/secondを使わず全prefixを列挙。

## 主なアブレーション

shared vs stage-specific head; teacher forcing; relative features.

## 想定する失敗理由

early-stage error propagation、条件headのデータ偏り、校正不整合。

## 他モデルとの相補性

direct120と異なる因子分解でensemble候補。

## 計算量の概算区分

medium-to-high

## 共通契約

評価は`boatrace_model_evaluation_v1_1`の三連単120クラス自然対数Log Lossを主指標とする。オッズ・人気・投票数・払戻は特徴、教師、重み、校正、選定に使わない。
