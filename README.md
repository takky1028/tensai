# Discord Market Stats Bot

為替・指数・商品について、1時間足ベースの統計を計算して Discord Webhook に通知するBotです。

## 通知内容
各銘柄ごとに以下を通知します。
- H↑ / H↓: 時間帯ごとの陽線率・陰線率・EV
- W↑ / W↓: 曜日ごとの陽線率・陰線率・EV
- H×W↑ / H×W↓: 時間帯×曜日ごとの陽線率・陰線率・EV

※ EVは `終値 - 始値` の平均値です。  
※ データ取得は Twelve Data API を使用します（Yahoo Financeは使いません）。

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
$env:DRY_RUN="true"; python main.py
```

## GitHub Actions運用
`.github/workflows/discord_market_stats.yml` を使用します。

- 定期実行: 毎日 `23:00 UTC`（= `08:00 JST`）
- 手動実行: `workflow_dispatch`

### Secrets
以下を GitHub Secrets に設定してください。
- `DISCORD_WEBHOOK_URL`: Discord Incoming Webhook URL
- `TWELVEDATA_API_KEY`: Twelve Data API Key

## 環境変数
- `DISCORD_WEBHOOK_URL` (必須)
- `TWELVEDATA_API_KEY` (必須)
- `LOOKBACK_DAYS` (既定: `180`)
- `MIN_SAMPLES` (既定: `20`)
- `INCLUDE_RECOMMENDED` (既定: `true`)
- `DRY_RUN` (既定: `false`)
- `LOG_LEVEL` (既定: `INFO`)
- `API_MAX_RETRIES` (既定: `4`)
- `API_RETRY_WAIT_SEC` (既定: `8`)
- `API_TIMEOUT_SEC` (既定: `20`)
