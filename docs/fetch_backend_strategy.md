# 取得バックエンド切り分けとfallback方針

作成日: 2026-06-18

## 目的

公式成績ページの取得で Python 標準のHTTPS取得が失敗する環境でも、raw CSVを変更せずに、取得可能なバックエンドを切り分けます。

この文書は取得層の運用メモです。予想モデル、特徴量追加、買い目生成には進みません。

## 現状

前回のネットワーク診断では以下でした。

- DNS: OK
- TCP 443: `WinError 10013`
- HTTPS GET: `WinError 10013`
- raw CSV: 変更なし
- 手動HTML投入ルート: 実装済み

## 診断対象バックエンド

`python -m nankan_ai.diagnose_fetch_backends` で、以下を1 URLだけ確認します。

- `python`: Python標準の `urllib`
- `powershell`: PowerShell `Invoke-WebRequest`
- `curl`: `curl.exe`

テストURLは、2025-09-08 川崎1Rの公式成績ページです。

```powershell
python -m nankan_ai.diagnose_fetch_backends
```

診断では以下を表示します。

- `available` / `unavailable`
- exit code
- status code
- error message

この診断は raw CSV と HTML cache を変更しません。PowerShell / curl の確認では一時ディレクトリだけを使います。

## 2026-06-18 実行結果

対象URL:

```text
https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/RaceMarkTable?k_raceDate=2025%2F09%2F08&k_raceNo=1&k_babaCode=21
```

結果:

| backend | state | exit code | status code | 主なエラー |
|---|---:|---:|---:|---|
| python | unavailable | 1 |  | `WinError 10013` |
| powershell | unavailable | 1 |  | `Invoke-WebRequest : リモート サーバーに接続できません。` |
| curl | unavailable | 7 | 000 | `Failed to connect to www.keiba.go.jp port 443` |

この環境では、現時点で自動取得backendとして使えそうなものはありません。手動HTMLキャッシュ投入ルートを使います。

## fetch_result_pages のbackend指定

既定は Python です。

```powershell
python -m nankan_ai.fetch_result_pages data/reports/fetch_plan_YYYYMMDD_HHMMSS.csv --apply --backend python
```

PowerShellで取得する場合:

```powershell
python -m nankan_ai.fetch_result_pages data/reports/fetch_plan_YYYYMMDD_HHMMSS.csv --apply --backend powershell
```

curlで取得する場合:

```powershell
python -m nankan_ai.fetch_result_pages data/reports/fetch_plan_YYYYMMDD_HHMMSS.csv --apply --backend curl
```

どのbackendでも、保存先は同じです。

```text
data/cache/html/<race_id>.html
```

既にcacheがある場合は再取得しません。rate limit も維持します。

## backend選択の優先順

まずは診断結果に基づき、利用可能なbackendだけを使います。

1. `python` が available なら `--backend python`
2. `python` が失敗し、`powershell` が available なら `--backend powershell`
3. `powershell` も失敗し、`curl` が available なら `--backend curl`
4. すべて unavailable なら手動HTML投入へ切り替える

## すべて失敗した場合

危険なネットワーク設定変更やファイアウォール回避は行いません。

公式成績ページをブラウザ等で手動保存し、以下に置きます。

```text
data/manual_html/<race_id>.html
```

その後、cacheへ取り込みます。

```powershell
python -m nankan_ai.import_manual_html_cache
```

以降は通常の cache からappend CSV生成へ進みます。

```powershell
python -m nankan_ai.build_append_from_cache --fetch-plan-csv data/reports/fetch_plan_YYYYMMDD_HHMMSS.csv --validate
python -m nankan_ai.validate_append_csv data/incoming/nankan_past_races_append.csv
python -m nankan_ai.merge_append_csv data/incoming/nankan_past_races_append.csv
```

## 禁止事項

- raw CSVを直接編集しない。
- `merge_append_csv --apply` を勝手に実行しない。
- 大量取得をしない。
- 取得対象をfetch plan外へ広げない。
- ファイアウォール回避や危険な設定変更をしない。
- 推測補完しない。
