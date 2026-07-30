# Relational shared triple scorer

> Gate 0の設計書。学習・暫定評価・champion選定は行わない。

## 問題定義

艇・ordered pair・ordered tripleの共有関数で120通りをscore。

## 入力単位

lane付き6艇集合と120 ordered triples。

## 入力shape・出力shape

boat states [batch,6,d]; triple states [batch,120,k]; logits/output [batch,120].

## 確率正規化

共有scoreから120-way softmax。

## 主損失

natural-log ordered-trifecta cross entropy。

## 補助損失候補

pairwise order、winner、course/ST headsを一度に一つ検証。

## 艇の順序・艇番の扱い

first/second/third role embeddingとlane identityを明示。

## 未知選手・新モーター

unknown entity embedding; pair/triple relationは利用可能特徴から生成。

## 欠損処理

boat-level maskとfeature-level missing indicator。

## point-in-time要件

relation生成にtarget-race後情報を含めない。

## 主なアブレーション

boat-only; +pair; +triple; handcrafted relative vs attention.

## 想定する失敗理由

120 score計算の過適合、役割対称性の誤指定、関係特徴の冗長化。

## 他モデルとの相補性

direct分類よりparameter sharingが強く、少数classへ一般化し得る。

## 計算量の概算区分

high

## 共通契約

評価は`boatrace_model_evaluation_v1_1`の三連単120クラス自然対数Log Lossを主指標とする。オッズ・人気・投票数・払戻は特徴、教師、重み、校正、選定に使わない。
