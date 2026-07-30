# Probability ensemble

> Gate 0の設計書。学習・暫定評価・champion選定は行わない。

## 問題定義

確認済み異種モデルの120確率を固定手順で統合。

## 入力単位

同一race_keyのvalidな120確率ベクトル群。

## 入力shape・出力shape

input [batch,models,120]; output [batch,120].

## 確率正規化

nonnegative fixed weights後に再正規化。各入力もcontract validatorを通す。

## 主損失

weight選択の主基準はordered-trifecta Log Lossのみ。

## 補助損失候補

なし。diversity/calibrationは診断で、独自総合点にしない。

## 艇の順序・艇番の扱い

全componentのclass-map hash一致を必須化。

## 未知選手・新モーター

component欠落は禁止。coverage 100%を満たさなければ失格。

## 欠損処理

race/model確率欠損を補間しない。

## point-in-time要件

out-of-fold/future-fold predictionだけでweightを決め、final foldを見ない。

## 主なアブレーション

equal weight; pair blends; probability vs logit blend; one component removal.

## 想定する失敗理由

誤差相関、weight過適合、class-map mismatch、coverage差。

## 他モデルとの相補性

direct/autoregressive/relational/dynamicの異なる誤差を利用。

## 計算量の概算区分

low after component training

## 共通契約

評価は`boatrace_model_evaluation_v1_1`の三連単120クラス自然対数Log Lossを主指標とする。オッズ・人気・投票数・払戻は特徴、教師、重み、校正、選定に使わない。
