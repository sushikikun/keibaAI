---
status: provisional
eligible_for_model_training: false
purpose: canonical_adjudication_sidecar_only
---

# Canonical Adjudication v1 取込報告

## 取込内容

ChatGPT作成のCanonical Adjudication v1を、人手裁定のproposal-only sidecarとして取り込んだ。source packageは `source_package/boatrace_research_hypothesis_adjudication_v1/` にバイト不変で配置し、H001～H033の正式正本、raw H034～H109 addendum、既存review、readiness、data gap、feature map、core experimentsには変更を加えていない。

## 裁定集計

- source ID H034～H109: 76件連番、削除0。
- top-level candidate: 10件。正式採択ではない。
- parentへ接続するvariant: 60件。
- merge decision付きvariant: 6件。source IDを保持した統合先は H061→H049、H062→H043、H078→H040、H082→H039、H099→H019、H101→H049。
- 43件を正式上位仮説として採択していない。既存33件＋追加top-level候補10件は概念上の候補数にすぎない。

## Decision program

35件の既存core proposalを15件のdecision programへ一意に割り当てた。全programは `proposal_only_not_applied` であり、既存 `core_decision_experiments_v1.json` には追加していない。program member合計は35件である。

## 整合性と安全性

6入力CSVはローカル正本とSHA-256、サイズ、ヘッダー、行数、ID集合、BOMまで一致した。primary parent ID不在0、primary-parent cycle 0、artifact hash mismatch 0、保護anchor差分0である。全recordの主指標は評価契約v1.1の三連単Log Lossを参照し、`formal_registry_action=not_applied` である。

## 今回行っていない処理と次段階

モデル学習、Log Loss計算、Walk-forward、Champion選定、外部Webアクセス、依存追加、commit、pushは行っていない。Gate 1後に、top-level候補・variant・15 programを正式登録審査へ個別に持ち込む。今回の裁定sidecarは正式registryへのmergeではない。
