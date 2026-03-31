import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
import yfinance as yf

JST = "Asia/Tokyo"

BASE_SYMBOLS: Dict[str, str] = {
    "USDJPY": "USDJPY=X",
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "AUDUSD": "AUDUSD=X",
    "GBPAUD": "GBPAUD=X",
    "GBPNZD": "GBPNZD=X",
    "XAUUSD": "XAUUSD=X",
    "US30": "^DJI",
    "WTIUSD": "CL=F",
}

RECOMMENDED_SYMBOLS: Dict[str, str] = {
    "EURJPY": "EURJPY=X",
    "GBPJPY": "GBPJPY=X",
    "AUDJPY": "AUDJPY=X",
    "NZDJPY": "NZDJPY=X",
    "EURGBP": "EURGBP=X",
    "EURNZD": "EURNZD=X",
    "AUDNZD": "AUDNZD=X",
    "XAGUSD": "XAGUSD=X",
    "NAS100": "^NDX",
    "SPX500": "^GSPC",
}

WEEKDAY_LABELS_JA = {0: "月", 1: "火", 2: "水", 3: "木", 4: "金", 5: "土", 6: "日"}


@dataclass
class Signal:
    label: str
    direction: str
    probability: float
    ev: float
    samples: int


@dataclass
class SymbolSignals:
    symbol: str
    hour: Optional[Signal]
    weekday: Optional[Signal]
    hour_weekday: Optional[Signal]
    note: Optional[str] = None


class StatsBot:
    def __init__(self) -> None:
        self.webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
        self.lookback_days = int(os.getenv("LOOKBACK_DAYS", "180"))
        self.min_samples = int(os.getenv("MIN_SAMPLES", "20"))
        include_recommended = os.getenv("INCLUDE_RECOMMENDED", "true").lower() == "true"
        self.symbols = dict(BASE_SYMBOLS)
        if include_recommended:
            self.symbols.update(RECOMMENDED_SYMBOLS)

    def fetch(self, ticker: str) -> pd.DataFrame:
        df = yf.download(
            tickers=ticker,
            interval="1h",
            period=f"{self.lookback_days}d",
            auto_adjust=False,
            progress=False,
            threads=False,
        )
        if df.empty:
            return df
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]

        df = df[["Open", "Close"]].dropna().copy()
        if df.empty:
            return df
        idx = df.index
        if idx.tz is None:
            df.index = idx.tz_localize("UTC").tz_convert(JST)
        else:
            df.index = idx.tz_convert(JST)
        return df

    def _best_signal(self, grouped: pd.DataFrame, label_builder) -> Optional[Signal]:
        if grouped.empty:
            return None
        valid = grouped[grouped["count"] >= self.min_samples].copy()
        if valid.empty:
            return None

        valid["up_prob"] = valid["up_count"] / valid["count"]
        valid["down_prob"] = 1 - valid["up_prob"]
        valid["direction"] = valid.apply(lambda r: "↑" if r["up_prob"] >= r["down_prob"] else "↓", axis=1)
        valid["prob"] = valid[["up_prob", "down_prob"]].max(axis=1)
        chosen = valid.sort_values(["prob", "count"], ascending=[False, False]).iloc[0]
        return Signal(
            label=label_builder(chosen.name),
            direction=str(chosen["direction"]),
            probability=float(chosen["prob"]),
            ev=float(chosen["mean_ret"]),
            samples=int(chosen["count"]),
        )

    def analyze_symbol(self, symbol: str, ticker: str) -> SymbolSignals:
        df = self.fetch(ticker)
        if df.empty:
            return SymbolSignals(symbol=symbol, hour=None, weekday=None, hour_weekday=None, note="データ取得不可")

        df["ret"] = df["Close"] - df["Open"]
        df["is_up"] = (df["ret"] > 0).astype(int)
        df["hour"] = df.index.hour
        df["weekday"] = df.index.weekday

        agg_spec = {"ret": ["mean", "count"], "is_up": "sum"}

        hour_stats = df.groupby("hour").agg(agg_spec)
        hour_stats.columns = ["mean_ret", "count", "up_count"]

        weekday_stats = df.groupby("weekday").agg(agg_spec)
        weekday_stats.columns = ["mean_ret", "count", "up_count"]

        hw_stats = df.groupby(["weekday", "hour"]).agg(agg_spec)
        hw_stats.columns = ["mean_ret", "count", "up_count"]

        hour_signal = self._best_signal(hour_stats, lambda h: f"{int(h):02d}時")
        weekday_signal = self._best_signal(weekday_stats, lambda w: f"{WEEKDAY_LABELS_JA.get(int(w), str(w))}曜")
        hw_signal = self._best_signal(
            hw_stats,
            lambda key: f"{WEEKDAY_LABELS_JA.get(int(key[0]), str(key[0]))}曜 {int(key[1]):02d}時",
        )

        return SymbolSignals(symbol=symbol, hour=hour_signal, weekday=weekday_signal, hour_weekday=hw_signal)

    @staticmethod
    def _fmt_signal(title: str, signal: Optional[Signal]) -> str:
        if signal is None:
            return f"{title}: n/a"
        return (
            f"{title}: {signal.label} {signal.direction} {signal.probability * 100:.0f}% "
            f"/ EV {signal.ev:+.5f} (n={signal.samples})"
        )

    def render_message(self, signals: List[SymbolSignals]) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
        lines = [f"📊 Market Stats ({now})", "```"]
        for s in signals:
            lines.append(f"{s.symbol}")
            lines.append(self._fmt_signal("H", s.hour))
            lines.append(self._fmt_signal("W", s.weekday))
            lines.append(self._fmt_signal("H×W", s.hour_weekday))
            if s.note:
                lines.append(f"note: {s.note}")
            lines.append("")
        lines.append("```")
        lines.append("Legend: H=時間帯 / W=曜日 / EV=平均(終値-始値)")
        return "\n".join(lines)

    def post_discord(self, content: str) -> None:
        if not self.webhook_url:
            raise RuntimeError("DISCORD_WEBHOOK_URL is not set")
        resp = requests.post(self.webhook_url, json={"content": content}, timeout=20)
        if resp.status_code >= 300:
            raise RuntimeError(f"Discord webhook failed: {resp.status_code} {resp.text}")

    def run(self) -> None:
        logging.info("start analysis symbols=%d lookback_days=%d min_samples=%d", len(self.symbols), self.lookback_days, self.min_samples)
        results = [self.analyze_symbol(symbol, ticker) for symbol, ticker in self.symbols.items()]
        message = self.render_message(results)

        dry_run = os.getenv("DRY_RUN", "false").lower() == "true"
        if dry_run:
            print(message)
            logging.info("dry-run finished")
            return

        self.post_discord(message)
        logging.info("discord notification sent")


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
    StatsBot().run()
