# ボートレースAI研究仮説 Addendum v1

## 状態

- 正式正本は **H001～H033** のままです。
- 本書は会話内で追加検討した **H034～H109（76件）** を実ファイル化したsidecar addendumです。
- 現時点ではローカル研究台帳へ未登録で、モデル学習・評価・仮説採否には使用していません。
- Codex取込後も、既存正本へ上書きせずaddendumとして保持する前提です。

## 件数

- 正式正本: 33件
- 追加候補: 76件
- 概念上の合計: 109件
- proposed tier: `conditional` 33件, `core_addendum` 35件, `exploratory` 8件

## 固定ルール

- 主評価は評価契約v1.1の未来三連単Log Loss。
- オッズ・人気・払戻は無オッズモデルの入力・教師・損失重み・校正・モデル選定に使わない。
- H034～H109は新規候補であり、H001～H033を変更しない。
- 研究開始前に重複・依存関係・必要データ・実験順をCodexで機械検証する。

## 追加仮説一覧

| ID | Tier | Family | 仮説 | 概要 | 最小比較 | 主なリスク |
|---|---|---|---|---|---|---|
| H034 | core_addendum | probability_update | 段階的確率更新モデル | 出走表・過去能力から事前三連単確率を作り、展示・直前情報による対数確率補正を加えて最終分布を得る。 | 全情報一括入力モデルとの比較。事前branchと展示更新branchを同条件で評価する。 | 段階分離が不適切だと展示前後の相互作用を失う。 |
| H035 | core_addendum | exhibition_residual | 展示サプライズ残差モデル | 展示タイム等の生値ではなく、選手・機材・場・気象から予測した期待展示値との差を当日状態として使う。 | 展示生値・場内順位・期待値残差の比較。 | 期待展示モデルの誤差を主モデルへ伝播する。 |
| H036 | core_addendum | output_factorization | Top-3集合→順序分解モデル | まず上位3艇集合20通りを予測し、選ばれた集合内の6順序を条件付き予測して120確率を構成する。 | 120直接Softmax、自己回帰Top-3との比較。 | 集合予測の誤りが順序予測を制限する。 |
| H037 | core_addendum | structured_energy | 厳密正規化Permutation CRF／Energy Model | 艇・着順の単項、艇間順序、三艇相互作用から120候補のenergyを作り、全列挙Softmaxで厳密正規化する。 | 直接120 head、共有トリプルスコアラーとの比較。 | 高次項が過学習しやすい。 |
| H038 | core_addendum | random_utility | 相関ランダム効用モデル | 艇効用の誤差を独立とせず、共通展開ショックや艇間相関を持つ順位確率モデルにする。 | Plackett–Luce、文脈依存自己回帰との比較。 | 相関構造の識別が不安定になり得る。 |
| H039 | core_addendum | multi_granularity_consistency | 多粒度確率整合学習 | 1着、二連単、Top-3集合、三連単を同時学習し、最終120分布から導く周辺確率と補助headを整合させる。 | 三連単単独学習との比較。 | 補助headの誤差が主分布を歪める。 |
| H040 | conditional | mixture_of_experts | 潜在レース型Mixture-of-Experts | イン安定型、外圧型、進入変化型等の潜在レース型ごとに専門家を持ち、予想時特徴から混合する。 | 単一モデル、固定場別専門家との比較。 | 専門家の崩壊・ゲート過学習。 |
| H041 | core_addendum | retrieval | 類似レース検索拡張モデル | 時点厳守で似た過去レースを検索し、近傍の表現・結果分布を現在モデルへ統合する。 | 検索なし表形式／構造モデルとの比較。 | 近傍検索に未来情報や同一主体の過近接漏洩が入りやすい。 |
| H042 | core_addendum | interaction_factorization | 低ランク交差相互作用モデル | 選手×機材×場×コース等の高次相互作用を低ランク因子へ分解し、疎な組合せでも共有学習する。 | 単純加算、完全交差embeddingとの比較。 | 低ランク仮定が複雑な相性を表現できない。 |
| H043 | conditional | self_supervised | 自己教師あり事前学習 | 特徴マスク復元、破損検出、同一主体の対比学習等で艇表現を事前学習してから三連単へfine-tuneする。 | 教師ありゼロ初期化との比較。 | 事前課題が最終Top-3に無関係な表現を学ぶ。 |
| H044 | conditional | partial_label | 部分ラベル・多品質学習 | 同着・異常結果・Gold未満レースを一意one-hotに潰さず、集合尤度や品質別ノイズモデルで利用する。 | Gold uniqueのみとの比較。 | 品質差のモデル化が誤ると主学習を汚染する。 |
| H045 | core_addendum | cold_start | コールドスタート階層モデル | 新人・履歴不足選手・新機材を級・支部・場・全体平均へ部分プーリングし、能力不確実性を保持する。 | ID embedding、単純平均補完との比較。 | 階層定義が不適切だと過度に平均へ寄せる。 |
| H046 | conditional | temporal_graph | 時系列主体グラフメモリ | 選手・モーター・ボート・場を動的グラフの主体として、レースイベントごとにmemoryを更新する。 | 主体別rolling／RNNとの比較。 | 複雑性と世代ID依存が大きい。 |
| H047 | conditional | robust_generalization | 場・時代横断ロバスト学習 | 場・年度で変わる相関への依存を抑え、未来期間でも維持される表現を学習する。 | 通常ERM、場別adapterとの比較。 | 不変性仮定が誤ると有用な場固有信号を消す。 |
| H048 | core_addendum | pairwise_reconstruction | 15ペア勝敗→120通り再構成モデル | 6艇15ペアの勝敗確率を学び、整合制約付きでTop-3の120分布へ再構成する。 | 直接120、Plackett–Luceとの比較。 | ペア確率が非推移的になり、射影誤差が生じる。 |
| H049 | conditional | uncertainty | 確率分布そのものの不確実性モデル | 120個の点確率に加え、モデル間・重み・潜在状態による確率分布の不確実性を推定する。 | Softmax、Deep Ensembleとの比較。 | 不確実性指標が真の誤差と対応しない可能性。 |
| H050 | core_addendum | continuous_time_state | 連続時間・主体別状態空間モデル | 不規則な出走間隔を考慮し、選手・機材の潜在状態を連続時間で減衰・更新する。 | rolling特徴、GRUとの比較。 | 状態推定が複雑で識別しにくい。 |
| H051 | conditional | regime_switching | 変化点付きレジーム切替状態モデル | 滑らかな能力変化だけでなく、部品交換・休養・F保有等による急な潜在レジーム切替を許す。 | H050の滑らかな状態遷移との比較。 | レジームが過剰分割される。 |
| H052 | conditional | meta_learning | 少数履歴から能力分布を作るメタ学習 | 少数の過去イベント集合から現在能力の事後分布を推定し、新人・新機材へ迅速適応する。 | 階層縮約、通常embeddingとの比較。 | episode設計が実運用分布と合わない。 |
| H053 | core_addendum | multi_task_optimization | 補助教師間の勾配衝突制御 | 進入・ST・決まり手等の補助損失が主損失と競合する際、PCGrad・GradNorm等で干渉を抑える。 | 固定loss weightとの比較。 | 勾配制御が主タスクの有用な共有を弱める。 |
| H054 | conditional | curriculum | 1着→二連単→三連単の段階学習 | 1着・Top-3集合・二連単等の易しい課題から表現を学び、最後に三連単へfine-tuneする。 | 最初から三連単end-to-endとの比較。 | 前段課題へ表現が固定される。 |
| H055 | core_addendum | multi_view | 複数情報ビューの整合学習 | 履歴、環境、展示、全情報を別branchで予測し、役割を保ちながら確率整合を学ぶ。 | 全特徴一括入力との比較。 | 過度な整合制約が展示の新情報を消す。 |
| H056 | core_addendum | tensor_factorization | 低ランク・テンソル分解型三連単スコアラー | 1着・2着・3着の役割項、ペア項、低ランク三艇項を合成して120候補を共有採点する。 | 独立120 head、共有MLPスコアラーとの比較。 | 低ランク制約が高次展開を欠落させる。 |
| H057 | exploratory | contrastive | 同一レース内ハードネガティブ対比学習 | 同じ集合・同じ1着等の紛らわしい不正解候補を補助的に分離する。 | Log Loss単独との比較。 | 順位分離を強めすぎて確率校正を壊す。 |
| H058 | core_addendum | st_distribution | 6艇STの相関分布モデル | 艇別独立STでなく、レース共通・スロー／ダッシュ共通ショックを含む6次元ST分布を予測する。 | 独立Gaussian ST、点予測との比較。 | 相関分布の推定誤差がTop-3へ伝播する。 |
| H059 | conditional | hypernetwork | 場・環境条件で重みを変えるHypernetwork | 場・気象・グレードから小型adapterやheadの重みを生成し、共通学習と専門化を両立する。 | venue embedding、場別adapterとの比較。 | 自由度が高く場固有過学習しやすい。 |
| H060 | conditional | group_robust | 場・期間・グレードGroup-Robust学習 | 平均損失だけでなく、事前定義groupの最悪損失や分散を抑える。 | 通常ERMとの比較。 | 全体Log Lossを犠牲にする可能性。 |
| H061 | exploratory | evidential | Dirichlet型の二階確率・証拠モデル | 三連単確率に対するDirichlet分布を出し、期待確率と証拠量を推定する。 | Softmax、Deep Ensembleとの比較。 | 証拠量が真の不確実性を反映しない。 |
| H062 | conditional | predictive_pretraining | 次走・数走先を予測する自己教師あり学習 | 現在の主体状態から次走ST・進入・Top-3等を予測し、将来予測に有用な履歴表現を事前学習する。 | masked-feature事前学習、教師あり学習との比較。 | 将来課題が最終レース予測とずれる。 |
| H063 | conditional | representation_disentanglement | 長期能力と短期状態の分離正則化 | 安定した能力embeddingと短期変動embeddingの役割重複を制約で抑える。 | 単純加算embeddingとの比較。 | 分離制約が実際の相互依存を壊す。 |
| H064 | core_addendum | residual_modeling | 統計モデル＋ニューラル残差モデル | 安定した無オッズ統計／順位logitを基礎とし、ニューラルは複雑な残差だけを学ぶ。 | 純統計、純ニューラルとの比較。 | 基礎モデルの偏りを残差で回収できない場合がある。 |
| H065 | conditional | dynamic_ensemble | レースごとの動的アンサンブルゲート | 場・能力差・不確実性等からモデル重みをレースごとに変更する。 | 単純平均、固定重みとの比較。 | ゲートが過学習し極端なモデル選択を行う。 |
| H066 | core_addendum | causal_equipment | 抽選割当を利用した機材効果分離 | 同一開催内のモーター・ボート抽選構造を利用し、選手力と機材効果の混同を抑える。 | 通常embedding・公式率との比較。 | 割当が分析上十分に無作為でない可能性。 |
| H067 | core_addendum | orthogonalization | Cross-fitting型・直交化機材効果学習 | 選手・枠等で予測したOOF残差を機材で説明し、機材効果推定を直交化する。 | 通常joint学習との比較。 | 第1段階誤差や残差定義に敏感。 |
| H068 | core_addendum | hierarchical_bayes | 交差階層ベイズ統合戦力モデル | 選手・モーター・ボート・場・コース・相互作用を部分プーリングして能力分布を推定する。 | 固定効果、ID embeddingとの比較。 | 計算負荷とモデル識別性。 |
| H069 | conditional | context_surface | 文脈依存能力曲面モデル | 選手・機材能力を場・コース・風・グレード等の連続／カテゴリ文脈関数として表す。 | 単一能力値、低ランク交互作用との比較。 | データの薄い文脈で不安定。 |
| H070 | conditional | probabilistic_circuit | 厳密推論可能な確率回路・因子グラフ | 進入・ST・展開・着順を因子分解し、可能な範囲で潜在状態を厳密周辺化する。 | 直接Softmax、Monte Carlo周辺化との比較。 | 構造仮定が強すぎる可能性。 |
| H071 | conditional | simulation | 潜在レース生成シミュレーター | 進入・ST・展開・潜在走力を多数生成し、シミュレーション頻度から120確率を作る。 | 直接モデルとの比較。 | 中間生成過程の誤指定・高計算量。 |
| H072 | core_addendum | latent_performance | 6艇相関・潜在パフォーマンス分布 | ST以後も含む当日パフォーマンスを6次元相関分布として生成し順位化する。 | 独立効用・直接Softmaxとの比較。 | 潜在量の識別が難しい。 |
| H073 | core_addendum | assignment_model | 6×6位置割当モデル | 艇×着順の6×6スコア行列から720完全順位を厳密列挙し、Top-3へ周辺化する。 | 120直接、自己回帰との比較。 | 下位順位学習が主目的を希釈する。 |
| H074 | exploratory | permutation_code | Lehmer code・Insertion Vector型順列モデル | 完全順位またはTop-3を別の一対一順列コードで自己回帰生成する。 | 1着→2着→3着分解との比較。 | コード順序が不自然な帰納バイアスを持つ。 |
| H075 | exploratory | permutation_diffusion | 順列Diffusion・Flow Matching | 順列全体を反復更新して多峰な順位分布を生成する。 | 直接120 Softmax、順列codeとの比較。 | 120候補の小問題に対して過剰設計。 |
| H076 | conditional | invariant_learning | 場・時代を越える不変メカニズム学習 | 場・年度を当てにくい共有表現と環境固有残差を分け、分布変化へ耐える。 | 通常ERM、adapterとの比較。 | 環境差に含まれる有用信号を消す。 |
| H077 | conditional | counterfactual_consistency | 選手・機材入替え反実仮想整合学習 | 機材を仮想交換した表現へ可逆性・役割分離の整合制約を掛ける。 | 通常end-to-endとの比較。 | 未観測反実仮想の仮定が誤る。 |
| H078 | exploratory | bayesian_nonparametric | ベイズノンパラメトリック・レース型モデル | 潜在レース型の数を固定せず、データ・時代に応じて増減させる。 | 固定K MoEとの比較。 | 推論不安定・専門家増殖。 |
| H079 | core_addendum | stacking | 予測分布Stacking | OOF対数スコアを最大化する非負重みで異種モデルの予測分布を統合する。 | 単純平均、固定logit平均との比較。 | 候補モデル数が多いと重みが検証期間へ過適合。 |
| H080 | conditional | missing_marginalization | 欠損特徴の厳密周辺化モデル | 欠損を一点補完せず、観測特徴条件付きの欠損分布を積分して予測する。 | 補完＋欠損フラグとの比較。 | 欠損モデルの誤指定。 |
| H081 | conditional | causal_modular | 因果グラフ制約付きモジュールモデル | 選手・機材・展示・進入・ST・結果の明らかに不可能な情報経路を構造的に禁止する。 | 全特徴自由結合、弱制約、強固定DAGとの比較。 | 誤った因果制約で性能を落とす。 |
| H082 | core_addendum | consistency_projection | 複数粒度予測の厳密確率整合・射影 | 専門モデルの1着・二連単・Top-3集合・三連単確率を、整合した120分布へKL射影する。 | 三連単単独、soft consistencyとの比較。 | 弱い周辺モデルへ合わせると悪化。 |
| H083 | conditional | shape_constraint | 潜在戦力への形状制約・単調制約 | 分離済み潜在能力に限定して単調・逓減・補完等の形状制約を適用する。 | 制約なしモデルとの比較。 | 制約が現実の非単調性を否定する。 |
| H084 | core_addendum | neural_additive | Neural Additive＋選択的相互作用モデル | 非線形主効果を加算で分離し、事前選択または学習された少数相互作用だけを追加する。 | CatBoost、大型Transformerとの比較。 | 重要な高次相互作用を落とす。 |
| H085 | conditional | gbdt_shrinkage | GBDTの階層的縮約 | 少数例の深い葉予測を親ノード側へ信頼度に応じて縮約する。 | 通常CatBoost、浅い木、強正則化との比較。 | 縮約が有用な局所パターンを消す。 |
| H086 | core_addendum | hierarchical_calibration | 場・グレード・時期の階層的確率校正 | 全体校正を基礎に場・グレード・時期別補正を部分プーリングする。 | global temperature、個別校正との比較。 | 校正期間不足・group過学習。 |
| H087 | core_addendum | weight_averaging | SWA／SWAGによる重み空間平均 | 学習後半のcheckpoint平均または低ランク重み分布から予測平均を作る。 | best checkpoint、Deep Ensembleとの比較。 | 学習軌跡が単一モードを十分覆わない。 |
| H088 | conditional | multi_window | 複数時間窓モデルの同時利用 | 全履歴・直近3年・1年・6か月・時間減衰モデルを独立学習して統合する。 | 単一expanding／rolling windowとの比較。 | モデル数増加による選択過学習。 |
| H089 | core_addendum | evidence_adaptive_shrinkage | 証拠量に応じた統計事前分布への縮約 | 履歴量・OOD度・モデル不一致に応じてニューラル残差の強さを変え、必要時は統計基礎へ戻す。 | 固定残差強度との比較。 | 縮約ゲートが誤ると有効補正を抑える。 |
| H090 | conditional | venue_day_filter | 逐次更新型venue-day潜在状態フィルター | 当日過去レースと気象からイン有利度・ST尺度等の潜在水面状態を逐次更新する。 | 手作業venue-day集計との比較。 | Point-in-Time利用可能性と状態誤推定。 |
| H091 | conditional | physics_hybrid | 1マーク物理過程＋ニューラル残差 | 進入・相関ST・加速・旋回能力から1マーク中間状態を簡易生成し、残差でTop-3を補正する。 | 純ニューラル、純生成との比較。 | 簡易物理仮定が誤る。 |
| H092 | conditional | measurement_error | 観測誤差込み潜在特徴モデル | 公式率・展示・気象を潜在状態のノイズ付き観測として扱い、標本数・source別に不確実性を推定する。 | 観測値を真値扱いするモデルとの比較。 | 観測誤差分布を識別できない。 |
| H093 | conditional | robust_augmentation | 現実的な特徴摂動による頑健学習 | 場別計測誤差・丸め・欠損など実データ由来の摂動で訓練する。 | 摂動なし、一般Gaussian noiseとの比較。 | 実信号を損なう過度な摂動。 |
| H094 | core_addendum | self_distillation | 通常モデルensembleからの自己蒸留 | 実運用可能な複数OOFモデルのsoft分布をstudentへ蒸留する。 | teacher ensemble、hard-label studentとの比較。 | studentが多様性を圧縮しすぎる。 |
| H095 | core_addendum | proper_scoring | Log Loss＋Brierのproper-score複合学習 | 主評価はLog Lossのまま、学習時に少量の多クラスBrierを補助し極端logitを抑える。 | Log Loss単独との比較。 | Brier重みが大きいと主評価を悪化。 |
| H096 | exploratory | robust_likelihood | 微小ラベル汚染を仮定する頑健尤度 | 警告付きデータに限り微小汚染率を仮定した混合尤度を比較する。 | 通常尤度との比較。 | 難しい正例をノイズ扱いする危険。 |
| H097 | core_addendum | sequential_boosting | Cross-fitted逐次logit boosting | 統計→GBDT→関係モデル→時系列モデルの順にOOF残差logitを学習する。 | 独立学習平均、単一残差との比較。 | 段階誤差伝播と複雑なCross-fitting。 |
| H098 | core_addendum | label_graph | 三連単120クラスの出力ラベルグラフ | 同じ1着・二連単・集合・一艇置換等の関係をedge typeとして120ラベル間message passingする。 | ラベルグラフなし共有スコアラーとの比較。 | 過度な平滑化で順序差をぼかす。 |
| H099 | conditional | label_embedding | 三連単の合成ラベル埋め込み・疎符号化 | 三連単ラベルを1着・2着・3着・集合・ペア順序の合成埋め込みで表現する。 | one-hot label、集合→順序分解との比較。 | 符号化の帰納バイアスが誤る。 |
| H100 | core_addendum | equivariant_calibration | 艇番号置換に同変な構造化校正器 | 同じ関数を全120候補へ共有し、艇役割・元確率・レース特徴から校正logitを出す。 | global／階層temperature、vector scalingとの比較。 | 自由度が高いと校正期間へ過学習。 |
| H101 | conditional | pac_bayes | PAC-Bayes型の事後予測分布 | 重みの事後分布を複雑度正則化付きで学び、モデル平均確率を出す。 | 単一checkpoint、SWAG、Deep Ensembleとの比較。 | 事前・複雑度設定に敏感。 |
| H102 | core_addendum | sharpness_aware | Sharpness-Awareな確率モデル学習 | 重み近傍の最悪損失も抑えるSAM系最適化で未来Log Lossの一般化を狙う。 | AdamW、SWAとの比較。 | 計算増と、sharpnessが汎化を保証しない点。 |
| H103 | core_addendum | rdrop | R-Drop型120確率整合正則化 | 同一入力の異なるdropout forward間で120分布の双方向KLを小さくする。 | 通常dropoutとの比較。 | 正則化過多で表現力低下。 |
| H104 | conditional | manifold_mixup | ボートレース構造を保つMixup | 生IDを混ぜず、役割対応した艇埋め込みや中間race表現だけを条件内でmixする。 | Mixupなし、通常Mixupとの比較。 | 混合ラベルが現実確率と対応しない。 |
| H105 | exploratory | semi_supervised | 高信頼疑似ラベルによる半教師あり学習 | Gold未満レースへOOF教師確率を付け、十分低不確実性の例だけ整合学習へ使う。 | Gold教師のみとの比較。 | 教師誤差の自己増幅。 |
| H106 | conditional | temporal_point_process | Marked Temporal Point Process主体状態モデル | 出走イベントの時刻間隔と場・枠・ST・着順等のmarkを同時に主体状態encoderへ入れる。 | 固定長履歴、連続時間状態モデルとの比較。 | 出走スケジュール生成機構との交絡。 |
| H107 | conditional | temporal_hypergraph | 6艇レース・時系列ハイパーグラフ | 1レース6艇を一つのordered hyperedgeとして、主体memoryを時系列更新する。 | pairwise temporal graphとの比較。 | 実装複雑性・世代ID依存。 |
| H108 | core_addendum | error_specialist | Cross-fitted苦手レース専門家 | OOF損失を1着失敗・順序失敗・cold-start等へ分類し、予想時特徴で選ぶ残差専門家を学ぶ。 | 一般MoE、動的ensembleとの比較。 | 誤差型の後知恵情報がゲートへ漏れる危険。 |
| H109 | exploratory | generative_discriminative | 特徴分布も学ぶ生成・識別ハイブリッド | 三連単条件付き分布と入力特徴の尤度／復元を共有表現で同時学習する。 | 識別モデル単独との比較。 | 入力生成に容量を使い主予測を悪化。 |

## 主要研究軸

- **確率出力・構造化順位**: `H036`, `H037`, `H038`, `H039`, `H048`, `H056`, `H070`, `H073`, `H074`, `H075`, `H082`, `H098`, `H099`
- **選手・機材能力分離**: `H042`, `H045`, `H052`, `H063`, `H066`, `H067`, `H068`, `H069`, `H077`, `H083`, `H084`
- **時系列・状態推定**: `H046`, `H050`, `H051`, `H062`, `H088`, `H090`, `H106`, `H107`
- **進入・ST・展開生成**: `H058`, `H071`, `H072`, `H091`
- **学習安定化・正則化**: `H053`, `H054`, `H057`, `H087`, `H093`, `H095`, `H102`, `H103`, `H104`
- **不確実性・校正**: `H049`, `H061`, `H080`, `H086`, `H089`, `H092`, `H100`, `H101`
- **統合・残差・アンサンブル**: `H064`, `H065`, `H079`, `H094`, `H097`, `H108`
- **追加データ活用・半教師あり**: `H043`, `H044`, `H105`, `H109`

## 現時点の統合本命仮説

1. 交差階層ベイズ・動的状態モデルで選手・機材の安定した基礎能力分布を作る。
2. 展示サプライズ、気象、6艇相対関係をSet Attentionで表現する。
3. 必要なら進入分布・6艇相関ST・潜在パフォーマンスを周辺化する。
4. 統計基礎logitへ共有トリプルスコアラーのニューラル残差を加える。
5. R-Drop、勾配衝突制御、SWA/SWAG、proper-score補助で学習を安定化する。
6. 1着・二連単・Top-3集合との整合射影と階層・構造化校正を行う。
7. CatBoost、階層能力、6艇関係、展開モデルをPredictive Stackingで統合する。
