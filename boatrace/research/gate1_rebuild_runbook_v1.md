---
status: provisional
eligible_for_model_training: false
purpose: policy_execution_validation
runbook_id: boatrace_gate1_rebuild_runbook_v1
---

# Gate 1 再構築ランブック v1

この手順は20万レース超過後にだけ実行する。現時点では実行しない。

## Entry条件

1. candidate corpusが200,000レースを超えている。
2. 評価契約v1.1、class map v1、研究設計v2、temporal policy v1が不変である。
3. 収集処理のcutoffと最終対象日を宣言できる。
4. P0外部証拠の取得・使用権限とprovenanceが明示されている。

## 固定実行順

1. complete corpus registryをread transactionで固定し、入力status・registry・batch manifestのSHA-256を保存する。
2. v0/v0.1、研究設計v2、temporal policy v1のprotected anchorを再hashする。
3. candidate universeを再構築し、race_key重複・所有batch・入力完全性を検証する。
4. 機材証拠registryを更新する。A/Bだけでgeneration IDを発行し、Cは感度分析専用、DはNULLのままにする。
5. meeting policy v1をmaterializeし、episode_id/day number/confidence/exceptionを全raceへ出力する。
6. meeting例外を全件理由付きで解決または明示的にquarantineする。
7. same-day sequenceをprogramだけから再構築する。
8. prior same-day resultはtarget beforeinfo掲載と時点証拠を検証し、timestamp_confirmedまたは承認済semantic_confirmedだけを採用する。final resultの直接joinは禁止する。
9. subtitle review queueをrace coverage順に処理し、taxonomyの新versionとmanual review署名を固定する。
10. 公式集計10列とF/L 2列の一次仕様provenanceを添付する。既存値を再計算できない場合はその制約をmanifestへ残す。
11. Tier 1と監査通過したTier 2だけで最終feature snapshotを構築し、Tier 3を物理的に除外する。
12. unique/tied/void、target class decode、auxiliary-target separation、feature availabilityを全件再監査する。
13. class map hash、120確率validator、uniform/Oracle構造sanityを再確認する。モデル学習はまだ行わない。
14. snapshot・feature・target・eligibility・exception・source provenanceの全SHA-256 manifestを作成する。
15. 上記がpassした後にのみ、walk-forward境界、効果閾値、seed、tuning budgetを事前固定する。

## Fail-closed条件

- generation境界Dの埋め合わせ
- unresolved meeting episodeを高confidenceとして扱う
- target/later resultまたは公開時刻不明のsame-day result混入
- taxonomy raw値の消失
- allocation rollout推測値の予測特徴化
- Tier 3のfeature snapshot混入
- protected anchor差分

いずれかが発生した場合はGate 1をpassさせず、snapshot IDを発行しない。

## 実行記録

実行コマンド、入力snapshot/hash、例外件数、quarantine件数、採用Tier 2一覧、
未解決blocker、検証結果を一つのGate 1 manifestへ保存する。
