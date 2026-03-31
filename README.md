# Discord Market Stats Bot

為替・指数・商品について、1時間足ベースの統計を計算して Discord Webhook に通知するBotです。

## 通知内容
各銘柄ごとに以下を通知します。
- H: 時間帯ごとの優勢方向（陽線/陰線）確率・EV
- W: 曜日ごとの優勢方向確率・EV
- H×W: 時間帯×曜日ごとの優勢方向確率・EV

※ EVは `終値 - 始値` の平均値です。  
※ データは Yahoo Finance を使用し、`yfinance` 失敗時は `yahooquery` にフォールバックします。

## 対象銘柄
- ベース: `USDJPY EURUSD GBPUSD AUDUSD GBPAUD GBPNZD XAUUSD US30 WTIUSD`
- 追加候補（デフォルト有効）: `EURJPY GBPJPY AUDJPY NZDJPY EURGBP EURNZD AUDNZD XAGUSD NAS100 SPX500`

## ローカル実行
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Discord送信せず内容だけ確認
DRY_RUN=true python main.py
```

PowerShell の場合:
```powershell
$env:DRY_RUN=\"true\"; python main.py
```

## GitHub Actions運用
`.github/workflows/discord_market_stats.yml` を使用します。

- 定期実行: 毎日 `23:00 UTC`（= `08:00 JST`）
- 手動実行: `workflow_dispatch`

### Secrets
以下を GitHub Secrets に設定してください。
- `DISCORD_WEBHOOK_URL`: Discord Incoming Webhook URL

## 環境変数
- `DISCORD_WEBHOOK_URL` (必須)
- `LOOKBACK_DAYS` (既定: `180`)
- `MIN_SAMPLES` (既定: `20`)
- `INCLUDE_RECOMMENDED` (既定: `true`)
- `DRY_RUN` (既定: `false`)
- `LOG_LEVEL` (既定: `INFO`)
- `YF_MAX_RETRIES` (既定: `4`)
- `YF_RETRY_WAIT_SEC` (既定: `8`)
- `YF_BATCH_SIZE` (既定: `6`)
