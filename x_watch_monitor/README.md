# X User Monitor

X 上の特定ユーザー投稿を定期取得し、Grok で構造化分析し、Discord Webhook に通知する独立ワークフローです。既存の `tensai` 実装とは分離し、将来的に GitHub Actions / cron / Cloud Run Jobs に載せやすい構成にしています。

## 特徴

- 複数ターゲットを `config/targets.yaml` で管理
- 2時間おき実行を前提にしたジョブ入口を用意
- SQLite で対象ごとの処理状態、投稿履歴、分析履歴、通知履歴、エラーログを管理
- 新規投稿のみ処理し、同一投稿の重複通知を防止
- API 失敗時も他ターゲットの処理は継続
- X / Grok / Discord をクライアント層で分離し、差し替えやすい構造

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

- `X_BEARER_TOKEN`: X API Bearer Token
- `X_API_BASE_URL`: 既定値 `https://api.x.com/2`
- `XAI_API_KEY`: Grok 用 xAI API Key
- `GROK_API_BASE_URL`: 既定値 `https://api.x.ai/v1`
- `GROK_MODEL`: 既定値 `grok-4.20-beta-latest-non-reasoning`
- `DISCORD_WEBHOOK_URL_DEFAULT`: ターゲット設定で `${DISCORD_WEBHOOK_URL_DEFAULT}` として参照可能
- `DATABASE_PATH`: 既定値 `data/monitor.db`
- `CONFIG_PATH`: 既定値 `config/targets.yaml`
- `LOG_LEVEL`: `INFO`, `WARNING`, `ERROR`

## ターゲット設定

`config/targets.yaml` にターゲットを追加するだけで監視対象を増やせます。

```yaml
targets:
  - target_id: macro-watch
    display_name: "Macro Account"
    x_user: "example_user"
    enabled: true
    poll_interval_minutes: 120
    max_posts: 10
    include_replies: false
    include_threads: true
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

1. 対象ごとに `poll_interval_minutes` を確認
2. X から `since_id` ベースで投稿を取得
3. 返信 / スレッド設定に応じてフィルタ
4. 未通知の新規投稿のみを Grok に渡して分析
5. 構造化 JSON を保存
6. Discord に通知
7. 成功時のみ最終処理投稿 ID を更新

## Grok の構造化出力

保存される分析 JSON は以下の形です。

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

リポジトリ直下の `.github/workflows/x_user_monitor.yml` を追加しています。2時間おき実行と手動実行に対応しています。

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

- Grok API が不正な JSON を返した場合はそのターゲットのみ失敗として記録し、他ターゲットは継続します。
- 投稿が 0 件でも安全に終了します。
- コード内に特定ユーザー名は埋め込んでいません。
