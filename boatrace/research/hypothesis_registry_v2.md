# ボートレースAI仮説台帳 v2

Gate 0の研究設計であり、学習結果・暫定Log Loss・固定split・Championを含まない。
主指標は評価契約v1.1のordered-trifecta Log Lossだけである。

| ID | Tier | Family | 仮説 | Data | Priority | Status |
|---|---|---|---|---|---|---|
| H001 | core_decision | racer_strength | 選手の長期能力 | B | P0 | planned |
| H002 | core_decision | racer_strength | 選手の短期フォーム | B | P1 | planned |
| H003 | core_decision | racer_strength | 選手能力の多次元分解 | B | P1 | planned |
| H004 | core_decision | equipment | モーター・ボート世代識別 | D | P0 | blocked_new_acquisition |
| H005 | core_decision | equipment | 機材基礎性能と今節状態の分離 | B | P0 | planned |
| H006 | core_decision | racer_strength | 選手の調整能力 | B | P1 | planned |
| H007 | core_decision | interaction | 選手×モーター相互作用 | B | P1 | planned |
| H008 | core_decision | interaction | 選手×場・選手×コース相互作用 | B | P1 | planned |
| H009 | core_decision | relational | 6艇内相対特徴 | B | P0 | planned |
| H010 | core_decision | relational | 6艇ペア関係 | B | P1 | planned |
| H011 | core_decision | relational | Set Attentionによる6艇表現 | A | P1 | planned |
| H012 | core_decision | exhibition | 場・時期別展示標準化 | B | P0 | planned |
| H013 | core_decision | context_state | venue-day状態 | B | P1 | planned |
| H014 | core_decision | context_state | meeting・同日状態 | B | P0 | planned |
| H015 | core_decision | output_factorization | 120直接Softmax | A | P0 | planned |
| H016 | core_decision | model_family | 表形式ニューラル対CatBoost | A | P1 | planned |
| H017 | core_decision | output_factorization | 自己回帰Top-3 | A | P1 | planned |
| H018 | core_decision | output_factorization | Plackett–Luce順位分解 | A | P1 | planned |
| H019 | core_decision | output_factorization | 共有トリプルスコアラー | B | P1 | planned |
| H020 | core_decision | output_factorization | 完全順位からTop-3周辺化 | A | P1 | planned |
| H021 | core_decision | dynamic_model | 履歴系列・動的能力モデル | B | P1 | planned |
| H022 | core_decision | gating | 場別・グレード別gating | B | P1 | planned |
| H023 | core_decision | ensemble | 異種モデル確率アンサンブル | A | P1 | planned |
| H024 | core_decision | oracle | 本番進入Oracle | A | P0 | diagnostic_only |
| H025 | core_decision | oracle | 本番ST Oracle | A | P0 | diagnostic_only |
| H026 | conditional | auxiliary_learning | 進入・ST補助学習 | A | P1 | planned |
| H027 | conditional | latent_process | 進入・ST潜在過程モデル | B | P1 | planned |
| H028 | conditional | distillation | 知識蒸留 | A | P1 | planned |
| H029 | conditional | auxiliary_learning | 決まり手・異常状態・4～6着補助 | A | P1 | planned |
| H030 | exploratory | late_unstructured | 公式テキストNLP | C | P2 | planned |
| H031 | exploratory | late_unstructured | 展示映像表現 | E | P2 | planned |
| H032 | exploratory | late_unstructured | オリジナル展示計時 | D | P2 | blocked_new_acquisition |
| H033 | exploratory | source_regime | 2026年機材割当source regime | D | P0 | blocked_documentation |

## 実行規則

- 各core仮説は対応するcore decision experimentで一度に1要素だけ変える。
- Gate 2はscreening、Gate 3の未使用future foldがconfirmationである。
- Oracleは価値上限の診断であり、本番入力やChampion候補ではない。
- 依存する上流仮説が棄却された枝はdependency graphに従って優先度を下げる。
- 詳細な帰無・対立仮説、棄却条件、交絡、漏洩リスクはJSONを正本とする。

## H001 選手の長期能力

- 変更要素: 長期as-of選手能力
- 必要データ: RF_RACER_LONG
- 前提: なし
- 棄却: Gate 2で改善方向がなく、またはGate 3で再現せず、95% paired bootstrap CIが0を跨ぐ/悪化側となる場合は棄却する。閾値はGate 1で事前固定する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H002 選手の短期フォーム

- 変更要素: 短期フォーム窓
- 必要データ: RF_RACER_SHORT
- 前提: H001
- 棄却: Gate 2で改善方向がなく、またはGate 3で再現せず、95% paired bootstrap CIが0を跨ぐ/悪化側となる場合は棄却する。閾値はGate 1で事前固定する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H003 選手能力の多次元分解

- 変更要素: 能力の多次元化
- 必要データ: RF_RACER_MULTI
- 前提: H001
- 棄却: Gate 2で改善方向がなく、またはGate 3で再現せず、95% paired bootstrap CIが0を跨ぐ/悪化側となる場合は棄却する。閾値はGate 1で事前固定する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H004 モーター・ボート世代識別

- 変更要素: 世代境界を含むequipment identity
- 必要データ: RF_MOTOR_GENERATION, RF_BOAT_GENERATION
- 前提: なし
- 棄却: 使用開始日または公式世代境界を回収できない、または世代分離後も将来fold Log Lossが改善しない場合は棄却する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H005 機材基礎性能と今節状態の分離

- 変更要素: equipment base/state分解
- 必要データ: RF_EQUIPMENT_BASE, RF_EQUIPMENT_MEETING_STATE
- 前提: H004
- 棄却: Gate 2で改善方向がなく、またはGate 3で再現せず、95% paired bootstrap CIが0を跨ぐ/悪化側となる場合は棄却する。閾値はGate 1で事前固定する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H006 選手の調整能力

- 変更要素: 選手別調整能力
- 必要データ: RF_ADJUSTMENT_SKILL
- 前提: H005
- 棄却: Gate 2で改善方向がなく、またはGate 3で再現せず、95% paired bootstrap CIが0を跨ぐ/悪化側となる場合は棄却する。閾値はGate 1で事前固定する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H007 選手×モーター相互作用

- 変更要素: racer-motor interaction
- 必要データ: RF_RACER_MOTOR
- 前提: H004, H005
- 棄却: Gate 2で改善方向がなく、またはGate 3で再現せず、95% paired bootstrap CIが0を跨ぐ/悪化側となる場合は棄却する。閾値はGate 1で事前固定する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H008 選手×場・選手×コース相互作用

- 変更要素: racer-venue/course interaction
- 必要データ: RF_RACER_VENUE, RF_RACER_COURSE
- 前提: H001
- 棄却: Gate 2で改善方向がなく、またはGate 3で再現せず、95% paired bootstrap CIが0を跨ぐ/悪化側となる場合は棄却する。閾値はGate 1で事前固定する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H009 6艇内相対特徴

- 変更要素: within-race relative transforms
- 必要データ: RF_RELATIVE_SIX
- 前提: H001
- 棄却: Gate 2で改善方向がなく、またはGate 3で再現せず、95% paired bootstrap CIが0を跨ぐ/悪化側となる場合は棄却する。閾値はGate 1で事前固定する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H010 6艇ペア関係

- 変更要素: pairwise relation features
- 必要データ: RF_PAIRWISE
- 前提: H009
- 棄却: Gate 2で改善方向がなく、またはGate 3で再現せず、95% paired bootstrap CIが0を跨ぐ/悪化側となる場合は棄却する。閾値はGate 1で事前固定する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H011 Set Attentionによる6艇表現

- 変更要素: set-attention encoder
- 必要データ: RF_CURRENT_V01_49
- 前提: H009
- 棄却: Gate 2で改善方向がなく、またはGate 3で再現せず、95% paired bootstrap CIが0を跨ぐ/悪化側となる場合は棄却する。閾値はGate 1で事前固定する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H012 場・時期別展示標準化

- 変更要素: venue-season exhibition normalization
- 必要データ: RF_EXHIBITION_STANDARDIZED
- 前提: なし
- 棄却: Gate 2で改善方向がなく、またはGate 3で再現せず、95% paired bootstrap CIが0を跨ぐ/悪化側となる場合は棄却する。閾値はGate 1で事前固定する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H013 venue-day状態

- 変更要素: as-of venue-day latent/context state
- 必要データ: RF_VENUE_DAY
- 前提: H012
- 棄却: Gate 2で改善方向がなく、またはGate 3で再現せず、95% paired bootstrap CIが0を跨ぐ/悪化側となる場合は棄却する。閾値はGate 1で事前固定する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H014 meeting・同日状態

- 変更要素: meeting/day/same-day features
- 必要データ: RF_MEETING, RF_SAME_DAY
- 前提: なし
- 棄却: Gate 2で改善方向がなく、またはGate 3で再現せず、95% paired bootstrap CIが0を跨ぐ/悪化側となる場合は棄却する。閾値はGate 1で事前固定する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H015 120直接Softmax

- 変更要素: direct 120-class softmax
- 必要データ: RF_CURRENT_V01_49
- 前提: なし
- 棄却: Gate 2で改善方向がなく、またはGate 3で再現せず、95% paired bootstrap CIが0を跨ぐ/悪化側となる場合は棄却する。閾値はGate 1で事前固定する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H016 表形式ニューラル対CatBoost

- 変更要素: tabular neural architecture
- 必要データ: RF_CURRENT_V01_49
- 前提: H015
- 棄却: Gate 2で改善方向がなく、またはGate 3で再現せず、95% paired bootstrap CIが0を跨ぐ/悪化側となる場合は棄却する。閾値はGate 1で事前固定する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H017 自己回帰Top-3

- 変更要素: autoregressive top-3 factorization
- 必要データ: RF_CURRENT_V01_49
- 前提: H015
- 棄却: Gate 2で改善方向がなく、またはGate 3で再現せず、95% paired bootstrap CIが0を跨ぐ/悪化側となる場合は棄却する。閾値はGate 1で事前固定する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H018 Plackett–Luce順位分解

- 変更要素: Plackett-Luce likelihood
- 必要データ: RF_CURRENT_V01_49
- 前提: H015
- 棄却: Gate 2で改善方向がなく、またはGate 3で再現せず、95% paired bootstrap CIが0を跨ぐ/悪化側となる場合は棄却する。閾値はGate 1で事前固定する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H019 共有トリプルスコアラー

- 変更要素: shared relational triple scorer
- 必要データ: RF_PAIRWISE
- 前提: H010, H015
- 棄却: Gate 2で改善方向がなく、またはGate 3で再現せず、95% paired bootstrap CIが0を跨ぐ/悪化側となる場合は棄却する。閾値はGate 1で事前固定する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H020 完全順位からTop-3周辺化

- 変更要素: full-order likelihood and marginalization
- 必要データ: RF_CURRENT_V01_49
- 前提: H015
- 棄却: Gate 2で改善方向がなく、またはGate 3で再現せず、95% paired bootstrap CIが0を跨ぐ/悪化側となる場合は棄却する。閾値はGate 1で事前固定する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H021 履歴系列・動的能力モデル

- 変更要素: time-evolving entity state
- 必要データ: RF_RACER_DYNAMIC, RF_EQUIPMENT_MEETING_STATE
- 前提: H001, H005
- 棄却: Gate 2で改善方向がなく、またはGate 3で再現せず、95% paired bootstrap CIが0を跨ぐ/悪化側となる場合は棄却する。閾値はGate 1で事前固定する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H022 場別・グレード別gating

- 変更要素: venue/grade gating
- 必要データ: RF_VENUE_GRADE_GATE
- 前提: H015
- 棄却: Gate 2で改善方向がなく、またはGate 3で再現せず、95% paired bootstrap CIが0を跨ぐ/悪化側となる場合は棄却する。閾値はGate 1で事前固定する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H023 異種モデル確率アンサンブル

- 変更要素: fixed heterogeneous probability blend
- 必要データ: RF_MODEL_PROBABILITIES
- 前提: H015, H017, H019
- 棄却: Gate 2で改善方向がなく、またはGate 3で再現せず、95% paired bootstrap CIが0を跨ぐ/悪化側となる場合は棄却する。閾値はGate 1で事前固定する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H024 本番進入Oracle

- 変更要素: actual-course oracle input
- 必要データ: RF_ORACLE_ACTUAL_COURSE
- 前提: H015
- 棄却: actual-course Oracleがbaselineに対して事前固定した実質差を示さなければ、進入潜在モデルをdeprioritizeする。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H025 本番ST Oracle

- 変更要素: actual-start-timing oracle input
- 必要データ: RF_ORACLE_ACTUAL_ST
- 前提: H015
- 棄却: actual-ST Oracleがbaselineに対して事前固定した実質差を示さなければ、ST潜在モデルをdeprioritizeする。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H026 進入・ST補助学習

- 変更要素: course/ST auxiliary heads
- 必要データ: RF_CURRENT_V01_49
- 前提: H024, H025
- 棄却: Gate 2で改善方向がなく、またはGate 3で再現せず、95% paired bootstrap CIが0を跨ぐ/悪化側となる場合は棄却する。閾値はGate 1で事前固定する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H027 進入・ST潜在過程モデル

- 変更要素: latent course/ST integration
- 必要データ: RF_LATENT_COURSE_ST
- 前提: H024, H025, H026
- 棄却: Gate 2で改善方向がなく、またはGate 3で再現せず、95% paired bootstrap CIが0を跨ぐ/悪化側となる場合は棄却する。閾値はGate 1で事前固定する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H028 知識蒸留

- 変更要素: teacher-to-student distillation
- 必要データ: RF_TEACHER_PROBABILITIES
- 前提: H016, H019, H021
- 棄却: Gate 2で改善方向がなく、またはGate 3で再現せず、95% paired bootstrap CIが0を跨ぐ/悪化側となる場合は棄却する。閾値はGate 1で事前固定する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H029 決まり手・異常状態・4～6着補助

- 変更要素: outcome auxiliary heads
- 必要データ: RF_CURRENT_V01_49
- 前提: H015
- 棄却: Gate 2で改善方向がなく、またはGate 3で再現せず、95% paired bootstrap CIが0を跨ぐ/悪化側となる場合は棄却する。閾値はGate 1で事前固定する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H030 公式テキストNLP

- 変更要素: official text representation
- 必要データ: RF_OFFICIAL_TEXT
- 前提: H015
- 棄却: Gate 2で改善方向がなく、またはGate 3で再現せず、95% paired bootstrap CIが0を跨ぐ/悪化側となる場合は棄却する。閾値はGate 1で事前固定する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H031 展示映像表現

- 変更要素: exhibition video representation
- 必要データ: RF_EXHIBITION_VIDEO
- 前提: H012
- 棄却: Gate 2で改善方向がなく、またはGate 3で再現せず、95% paired bootstrap CIが0を跨ぐ/悪化側となる場合は棄却する。閾値はGate 1で事前固定する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H032 オリジナル展示計時

- 変更要素: original exhibition fields
- 必要データ: RF_ORIGINAL_EXHIBITION
- 前提: H012
- 棄却: 必要な場・期間を取得できない、または取得後に将来foldで改善しない場合は棄却する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。

## H033 2026年機材割当source regime

- 変更要素: source-regime indicator
- 必要データ: RF_SOURCE_REGIME
- 前提: H004
- 棄却: 一次資料で制度変更を確認できない、またはregime分離が将来foldで改善しない場合は棄却する。
- 確認: Gate 2のexploratory結果だけでは採用しない。Gate 3の未使用future foldで同方向のLog Loss改善を確認し、構造的失格・coverage低下がないこと。
