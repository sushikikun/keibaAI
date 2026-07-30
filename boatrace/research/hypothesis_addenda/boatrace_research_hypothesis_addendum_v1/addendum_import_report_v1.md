---
status: provisional
eligible_for_model_training: false
purpose: hypothesis_addendum_sidecar_review_only
---

# 追加研究仮説 H034～H109 sidecar addendum 取込 v1

## 取込内容

会話由来の追加研究仮説76件（H034～H109）を、既存の正式正本H001～H033とは分離して取り込んだ。source packageは `source_package/boatrace_research_hypothesis_addendum_v1/` にバイト不変で配置しており、既存 `hypothesis_registry_v2.json` へのmerge、再採番、削除、正式採択は一切行っていない。

## 検証結果

- H034～H109は連番76件で、ID重複とH001～H033との衝突は0件。
- 全件 `status=proposed_addendum_unregistered`、`eligible_for_model_training=false`。
- 全件が評価契約v1.1の三連単Log Loss（`trifecta_log_loss`）を主指標として参照する。
- 追加仮説間の親子DAG cycleは0件、parent ID不在は0件、orphan候補は0件。
- 意味的review件数: new distinct=10、variant=60、merge candidate=6、duplicate reject=0。

## 提案の扱い

`core_addendum` 35件は既存core decision experimentへ追加せず、比較実験proposalとしてのみ出力した。readiness・data gap・feature mapも既存台帳を更新せず、全76件についてproposal-onlyのsidecarを作成した。merge candidateは元IDを残したまま将来の統合検討先を記録したものであり、統合は実行していない。

## 今回行っていない処理

モデル学習、Log Loss等の性能計算、Walk-forward、Champion選定、外部Webアクセス、外部依存追加、commit、pushは行っていない。正式corpus、research_v0/v0.1、既存仮説・依存グラフ・core実験・readiness・data gap・feature map・評価契約への変更も0である。

## 次の正式作業

各proposalをGate 1のデータ可用性・時点規則・機材世代provenance監査後に、個別の実験設計として審査する。sidecarのclassificationは正式採択ではなく、H001～H033を保護したままの比較・統合検討用記録である。
