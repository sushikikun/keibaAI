# Latent race process model

> Gate 0の設計書。学習・暫定評価・champion選定は行わない。

## 問題定義

未知の本番進入・STを潜在変数として予測しTop-3確率へ周辺化。

## 入力単位

1レース、6艇、潜在course permutationとST distribution。

## 入力shape・出力shape

input [batch,6,d]; latent samples/states; marginalized output [batch,120].

## 確率正規化

潜在分布と条件付き120分布をそれぞれ正規化し、厳密和または検証済みMCで周辺化。

## 主損失

主損失はmarginal ordered-trifecta NLL。

## 補助損失候補

actual_course/ST supervisionはtraining targetのみ。

## 艇の順序・艇番の扱い

laneは事前identity、courseは潜在結果。両者を混同しない。

## 未知選手・新モーター

hierarchical priorとbroad uncertainty。

## 欠損処理

actual course/ST欠損はaux loss mask。主Top-3学習は契約population。

## point-in-time要件

actual course/STは推論入力禁止。Oracleは別診断で混ぜない。

## 主なアブレーション

course only; ST only; deterministic plug-in; exact vs sampled marginal.

## 想定する失敗理由

Oracle価値が小さい、識別不能、計算分散、latent collapse。

## 他モデルとの相補性

Oracleが示した価値を実運用可能な確率積分へ変換。

## 計算量の概算区分

very-high

## 共通契約

評価は`boatrace_model_evaluation_v1_1`の三連単120クラス自然対数Log Lossを主指標とする。オッズ・人気・投票数・払戻は特徴、教師、重み、校正、選定に使わない。
