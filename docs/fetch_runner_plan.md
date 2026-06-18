# 取得用ランナー運用計画

作成日: 2026-06-18

## 目的

現PCでは `keiba.go.jp:443` へのCLI取得が失敗するため、HTML取得だけを別環境で行い、取得済みHTMLを `cache bundle` としてメインPCへ戻します。

この運用では `data/raw/nankan_past_races.csv` を直接変更しません。メインPCに戻した後も、既存の `import_cache_bundle`、`build_append_from_cache`、`validate_append_csv`、`merge_append_csv` dry-run、必要時のみ `merge_append_csv --apply` の順で進めます。

## 取得用ランナー候補

| 候補 | 向いている点 | 注意点 |
| --- | --- | --- |
| GitHub Actions | 手動実行、成果物artifact保存、作業履歴が残る | リポジトリまたはartifactにfetch job/worker packageを用意する必要がある |
| GitHub Codespaces | ブラウザ/ターミナルで状態を見ながら作業しやすい | 起動時間と利用枠に注意する |
| VPS | 大量batchを安定して処理しやすい | 環境管理、費用、アクセス制限の確認が必要 |
| 別PC | 既存のworker zipをそのまま使いやすい | 手順の属人化、成果物の戻し忘れに注意する |

## 推奨案

最初は GitHub Actions を推奨します。

理由:

- 手動実行 `workflow_dispatch` に限定できる
- 取得結果をartifactとして保存できる
- どのjobをいつ取得したか履歴が残る
- メインPCでHTTPS取得できない問題を回避できる
- raw mergeをworkflowに含めなければ、データ投入と取得を分離できる

ただし、GitHub Actionsで `keiba.go.jp:443` に接続できるかは初回実行で確認が必要です。接続できない場合は、Codespaces、VPS、別PCへ切り替えます。

## 取得環境に必要な条件

既存のworker packageを使う場合は、次のzipを取得環境へ渡します。

```text
data/jobs/packages/external_fetch_worker_job_20260618_120030.zip
```

取得環境には次が必要です。

- Python 3.12以上を利用できる
- `keiba.go.jp:443` へHTTPS接続できる
- zipを展開できる
- `python -m pip install -e .` を実行できる
- `data/cache/html/` にHTMLを書き込める
- `data/cache/bundles/` にcache bundle zipを書き込める
- 作成したcache bundle zipをメインPCへ戻せる

取得環境では次をしません。

- `data/raw/nankan_past_races.csv` の編集
- `merge_append_csv --apply`
- 予想モデル作成
- 特徴量追加
- 不明値の推測補完

## GitHub Actions最小workflow案

追加したworkflow:

```text
.github/workflows/fetch_cache_bundle.yml
```

このworkflowは手動実行のみです。

処理内容:

1. repositoryをcheckoutする
2. Pythonをセットアップする
3. 任意でworker package zipを展開する
4. `pip install -e .` を実行する
5. fetch job CSVを使って `fetch_result_pages --apply` を実行する
6. `build_cache_bundle` を実行する
7. `cache_bundle_<job_id>.zip` をartifactとして保存する

デフォルトでは既存jobを対象にします。

```text
job_id: job_20260618_120030
job_csv_path: data/jobs/fetch_job_job_20260618_120030.csv
job_json_path: data/jobs/fetch_job_job_20260618_120030.json
worker_package_path: data/jobs/packages/external_fetch_worker_job_20260618_120030.zip
backend: python
```

Python backendが失敗する場合は、手動実行時に `backend` を `powershell` または `curl` に変えて再試行します。既存backendは `powershell.exe` / `curl.exe` を使うため、workflowは `windows-latest` を使います。

## 実行前に必要な準備

GitHub Actionsで実行する前に、次を確認します。

- `.github/workflows/fetch_cache_bundle.yml` がリポジトリに含まれている
- fetch job CSV/JSONがリポジトリに含まれている、またはworker package zipに含まれている
- `external_fetch_worker_job_20260618_120030.zip` を使う場合、zipがリポジトリに含まれている
- workflowの対象 `job_id` とfetch job CSV/JSONの名前が一致している
- 取得対象race_idがメインPCのrawに既に入っていない
- 取得後のartifactをメインPCへ戻す手順を決めている

## GitHub Actions実行前チェック

workflowファイルは、リポジトリ直下の次のパスに置きます。

```text
.github/workflows/fetch_cache_bundle.yml
```

次のように、プロジェクトフォルダ名と `.github` がつながった場所に置かれている場合は誤りです。

```text
New project.github/workflows/fetch_cache_bundle.yml
```

Actions実行に必要なファイル:

- `pyproject.toml`
- `src/nankan_ai/`
- `data/jobs/fetch_job_job_20260618_120030.csv`
- `data/jobs/fetch_job_job_20260618_120030.json`
- `.github/workflows/fetch_cache_bundle.yml`

Gitに含めない方がよいローカル成果物:

- `data/raw/nankan_past_races.csv`
- `data/nankan.duckdb`
- `data/processed/training_rows.csv`
- `data/cache/html/*.html`
- `data/cache/bundles/*.zip`
- `data/backups/*.csv`
- `.venv/`
- `__pycache__/`
- `.pytest_cache/`

workflow_dispatchで確認する主な入力:

- `job_id`
- `backend`
- `job_csv_path`
- `job_json_path`

初回は `backend=python` で実行し、失敗した場合に `powershell` または `curl` に切り替えます。workflowはcache bundle artifactを作るだけで、raw取り込みや `merge_append_csv --apply` は実行しません。

## メインPCへ戻した後の流れ

取得完了後、GitHub Actions artifactから `cache_bundle_<job_id>.zip` をダウンロードし、メインPCの次の場所に置きます。

```text
data/cache/bundles/cache_bundle_<job_id>.zip
```

その後、メインPCで次を実行します。

```powershell
python -m nankan_ai.import_cache_bundle data/cache/bundles/cache_bundle_<job_id>.zip
python -m nankan_ai.build_append_from_cache --fetch-plan-csv data/jobs/fetch_job_<job_id>.csv --validate
python -m nankan_ai.validate_append_csv data/incoming/nankan_past_races_append.csv
python -m nankan_ai.merge_append_csv data/incoming/nankan_past_races_append.csv
```

dry-runに問題がない場合だけ、別途明示的にapplyします。

```powershell
python -m nankan_ai.merge_append_csv data/incoming/nankan_past_races_append.csv --apply
```

## 失敗時の扱い

- fetchが失敗した場合、rawは変更されません
- HTMLが一部だけ取得できた場合、bundleには取得済みHTMLだけが入ります
- `build_cache_bundle` はHTMLが0件なら失敗します
- メインPCではimport後に必ずappend CSV検証とmerge dry-runを行います
- 途中で疑わしいデータがあれば、rawへapplyせずfetch jobまたはHTMLを確認します

## 今回の位置づけ

2025-09-08 川崎2R〜12Rは、現PCではcacheが0件です。ここでは手動HTML保存を増やさず、取得用ランナーでHTMLを取得してbundleとして戻す方針に切り替えます。
