# Dynamic entity strength model

> Gate 0の設計書。学習・暫定評価・champion選定は行わない。

## 問題定義

選手・機材の時間変化する潜在強度をas-of履歴から推定し三連単確率へ接続。

## 入力単位

時系列entity eventと対象レースの6 entity集合。

## 入力shape・出力shape

history: ragged [entity,event,time,fields]; race state: [batch,6,d]; output [batch,120].

## 確率正規化

最終120 logits softmax、または正規化済みtriple scorerへ接続。

## 主損失

評価主損失はnatural-log ordered-trifecta cross entropy。

## 補助損失候補

prior finish, exhibition residual, course/ST target heads（推論入力にはしない）。

## 艇の順序・艇番の扱い

entity stateとlane embeddingを分離し、race内ではlane 1..6を保持。

## 未知選手・新モーター

global/branch/class priorへ縮約。新機材はgeneration priorとofficial aggregate。

## 欠損処理

履歴長・cold-start flagを入力し、空履歴を学習可能なpriorへ写像。

## point-in-time要件

state updateはtarget cutoffより前のeventだけ。same-day resultは公開時刻の証拠が必須。

## 主なアブレーション

static aggregate; racer only; equipment only; no decay; scalar vs multidimensional.

## 想定する失敗理由

短い履歴、identity collision、非定常regime、event-time漏洩。

## 他モデルとの相補性

current-race relational encoderへ時間的priorを供給。

## 計算量の概算区分

high

## 共通契約

評価は`boatrace_model_evaluation_v1_1`の三連単120クラス自然対数Log Lossを主指標とする。オッズ・人気・投票数・払戻は特徴、教師、重み、校正、選定に使わない。
