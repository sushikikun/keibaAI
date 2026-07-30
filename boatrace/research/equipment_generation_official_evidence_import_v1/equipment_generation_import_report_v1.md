---
status: provisional
eligible_for_model_training: false
purpose: official_evidence_import_sidecar_only
---

# 機材世代境界・公式証拠パッケージ取込 v1

## 取り込んだもの

ChatGPT が BOAT RACE 公式一次資料から作成した「モーター・ボート世代境界 公式証拠収集 v1」を、既存研究基盤と分離した read-only sidecar として取り込んだ。パッケージ本体は `research/equipment_generation_official_evidence_v1/` にバイト不変で配置し、入力 ZIP は import sidecar の `source_package/` に同一 SHA-256 で保存した。

## 入力の真正性とローカル照合

- ZIP SHA-256、内部 Manifest SHA-256、Manifest の artifact-set SHA-256 はすべて期待値と一致した。
- パッケージ内の入力4ファイルは、ローカルの evidence batch queue（48件）、equipment evidence registry（3,240キー）、hypothesis readiness（33件）、upload manifest と SHA-256・サイズ・ヘッダー・行数・ID集合・BOM まで一致した。
- 43件の公式証拠 source は、HTTPS の宣言済み official domain、raw ファイルの SHA-256、および PDF の `%PDF-` magic を検証済みである。

## 証拠の意味

- 現行 boundary resolution 48件の内訳は A=43、B=4、C=1 である。A/B が確認できた現行境界は 47/48 であり、これは「現行世代の開始候補が公式証拠である」ことだけを示す。全履歴を機材世代として確定した意味ではない。
- A/B boundary candidate は54件（現行47件、historical 7件。candidate内訳 A=49、B=5）である。いずれも Gate 1 用の候補であり、formal generation ID は0件である。
- 48 batch-period のうち full batch-period coverage は2件だけで、蒲郡の motor と boat が該当する。開始日前の履歴を同じ世代へ遡及接続していない。
- unresolved batch period は46件のまま保持した。桐生 boat は C 証拠のみで未確定であり、C 証拠から boundary candidate や generation ID は作成していない。

## Gate 1でのみ可能になる処理

54候補すべてについて、race date と実際の equipment number を再照合し、公式開始日以後のローカル race だけを対象に materialize 可否を再監査できる。`generation_boundary_gate1_materialization_plan_v1.csv` は全54件を `planned_not_applied` とし、開始日前の観測は未解決のまま除外する方針である。

## 今回行っていない処理

正式 corpus、complete corpus、snapshot、既存 equipment registry、既存 hypothesis readiness、既存 blocker matrix への更新は行っていない。generation ID の発行、機材世代特徴量の生成、モデル学習、Log Loss 等の評価、Walk-forward split、Champion 選定、外部Webアクセス、外部依存追加、commit、push はいずれも行っていない。

## 依然として blocked の研究

既存 readiness は変更せず、H004、H005、H006、H007、H021には `partial_gate1_candidate` の提案のみを作成した。46未解決期間、桐生 boat の C-only 状態、各候補の date-and-number materialization 未監査により、全履歴の機材世代を前提とする研究は引き続き blocked である。H033 は制度 provenance のため unchanged とした。

## 次の正式作業

Gate 1 で候補ごとに race date・equipment number・公式開始日を再監査し、適用可能な日付範囲だけを新しい研究 snapshot へ materialize する。その際も既存成果物を書き換えず、46未解決期間を推測で補完せず、別の provenance 付き成果物として扱う。
