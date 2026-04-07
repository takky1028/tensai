# Topic Monitor

トランプ発言や米国政策に関する話題を、X 検索とニュース RSS から定期収集し、Grok で日本語分析して Discord Webhook に通知する独立ワークフローです。既存の `tensai` 実装とは分離し、GitHub Actions / cron / Cloud Run Jobs に載せやすい単発ジョブ構成です。

## 特徴

- 複数トピックを `config/targets.yaml` で管理
- 4時間おき実行を前提にしたジョブ入口を用意
- X 検索と Google News RSS の複数ソースを収集
- SQLite で対象ごとの処理状態、収集履歴、分析履歴、通知履歴、エラーログを管理
- 新規アイテムのみ処理し、同一ソースの重複通知を防止
- ソース単位の API 失敗時も、他ソースと他ターゲットの処理は継続
- Grok の分析結果と Discord 通知は日本語

## ディレクトリ構成

```text
x_watch_monitor/
  config/
  src/x_watch_monitor/
    clients/
    jobs/
    models/
    repositories/
    services/
  tests/
  .env.example
  pyproject.toml
```

## 前提環境

- Python 3.11 以上
- X API Bearer Token
- xAI API Key
- Discord Incoming Webhook URL

## セットアップ

```powershell
cd x_watch_monitor
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .[dev]
Copy-Item .env.example .env
```

`.env` と `config/targets.yaml` を編集してください。

## 環境変数

- `X_BEARER_TOKEN`: X 検索 API 用 Bearer Token
- `X_API_BASE_URL`: 既定値 `https://api.x.com/2`
- `X_SEARCH_DEFAULT_LANG`: X 検索で使う言語指定。既定値 `ja`
- `GOOGLE_NEWS_RSS_BASE_URL`: 既定値 `https://news.google.com/rss/search`
- `GOOGLE_NEWS_GL`: 既定値 `JP`
- `GOOGLE_NEWS_HL`: 既定値 `ja`
- `GOOGLE_NEWS_CEID`: 既定値 `JP:ja`
- `XAI_API_KEY`: Grok 用 xAI API Key
- `DISCORD_WEBHOOK_URL_DEFAULT`: ターゲット設定で `${DISCORD_WEBHOOK_URL_DEFAULT}` として参照可能
- `DATABASE_PATH`: 既定値 `data/monitor.db`
- `CONFIG_PATH`: 既定値 `config/targets.yaml`
- `LOG_LEVEL`: `INFO`, `WARNING`, `ERROR`

## ターゲット設定

`config/targets.yaml` にトピックを追加するだけで監視対象を増やせます。

```yaml
targets:
  - target_id: trump-topic-watch
    display_name: "トランプ・米国政策トピック監視"
    keywords:
      - "FRB"
      - "トランプ"
      - "アメリカ大統領"
      - "米大統領"
      - "関税"
      - "戦争"
    enabled: true
    poll_interval_minutes: 120
    max_items: 20
    x_search_enabled: true
    news_enabled: true
    analysis_profile: "macro_policy"
    discord_webhook_url: "${DISCORD_WEBHOOK_URL_DEFAULT}"
```

## 実行方法

1 回実行:

```powershell
cd x_watch_monitor
.venv\Scripts\Activate.ps1
python -m x_watch_monitor.jobs.poll_targets
```

設定ファイルや DB パスを明示したい場合:

```powershell
python -m x_watch_monitor.jobs.poll_targets --config config/targets.yaml --db data/monitor.db
```

## 実装の流れ

1. トピックごとに `poll_interval_minutes` を確認
2. X 検索と Google News RSS からキーワード一致の新規アイテムを収集
3. 重複を除去して、新規アイテムだけを Grok に渡す
4. 日本語の構造化 JSON を保存
5. Discord に日本語で通知
6. 成功時のみ最終処理時刻を更新

## Grok の構造化出力

保存される分析 JSON は以下の形です。値も日本語で返す想定です。

```json
{
  "target_id": "",
  "target_name": "",
  "analyzed_at": "",
  "source_posts": [],
  "summary": "",
  "usd_bias": "",
  "equity_bias": "",
  "risk_regime": "",
  "rate_bias": "",
  "inflation_bias": "",
  "trade_policy_bias": "",
  "geopolitical_risk": "",
  "confidence": 0,
  "key_drivers": [],
  "notable_quotes": [],
  "raw_model_output": {}
}
```

## 定期実行例

Windows タスクスケジューラや cron、Cloud Run Jobs、GitHub Actions に載せやすい単発ジョブです。

cron 例:

```cron
0 */2 * * *
```

## GitHub Actions

リポジトリ直下の `.github/workflows/x_user_monitor.yml` を追加しています。4時間おき実行と手動実行に対応しています。

設定する Secrets 例:

- `X_BEARER_TOKEN`
- `XAI_API_KEY`
- `DISCORD_WEBHOOK_URL_DEFAULT`

## テスト

```powershell
cd x_watch_monitor
.venv\Scripts\Activate.ps1
pytest
```

## 補足

- X 検索が 402 や権限不足で失敗しても、ニュース RSS が取れれば処理は継続します。
- Grok API が不正な JSON を返した場合はそのターゲットのみ失敗として記録し、他ターゲットは継続します。
- 収集件数が 0 件でも安全に終了します。
- キーワードは設定ファイルだけで変更できます。
