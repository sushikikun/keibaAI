# 時系列主体ID・予想時利用可能性ポリシー v1

本書はGate 0の規則正本である。既存snapshot・契約・研究設計v2は変更しない。

## 機材世代ID

`venue_code + equipment_type + equipment_number`だけでは世代IDにしない。`generation_start_date`を含むA/B公式証拠が受理された場合だけ`<venue>:<type>:<number>:<start_date>`を生成する。

- A: 公式ページに使用開始日が明記
- B: 公式の新機材導入告知で日付・適用範囲が明記
- C: リセット・ギャップ・再利用からの推定。感度分析専用
- D: 境界不明。開始日とgeneration_idは必ずNULL

現ローカル観測3,240キーはすべてDである。これは外部公式証跡でも作れないという意味ではない。

## Meeting episode

公式scheduleを最優先し、なければvenue、保守的に正規化したtitle、初日/N日目の単調なanchorでepisodeを導出する。順延・中止・欠損を日数として自動加算しない。確証がなければepisode_id/day_numberはNULL。

必須出力: episode_id, meeting_day_number, derivation_confidence, exception_reason

## 同日前走結果

対象レース公式直前情報に印字された`prev_*`だけがsemantic availability候補になる。同日・同場・同一選手・前のrace_no・前走終了後・target cutoff以前をすべて要求する。
最終result tableをrace_no順だけで直結する経路は禁止する。

利用predicate数: 9、禁止経路数: 6。

## 公式集計期間

既存10列の実field mappingとF/L raw 2列をCSVに固定した。変更はprovenance提案だけで、v0.1 snapshot/audit/contractは更新していない。

## Race stage

595 raw subtitleをすべて保持し、manual seed・自動rule・unknownを区別する。unknownは有効なfallbackであり、無理なstage推測をしない。

## 2026 allocation process

2026年2月の全国rollout開始はprovenance markerとして記録する。場別日付は公式場別証拠がない限りunknownとし、全regime行は`role=provenance_only`、`prediction_feature_allowed=false`である。

## 研究開始判定

readinessは9軸で独立判定する。現時点のformal model researchはNOT_READY。
