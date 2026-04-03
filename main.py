import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
import requests

JST = "Asia/Tokyo"
TWELVE_DATA_URL = "https://api.twelvedata.com/time_series"

BASE_SYMBOLS: Dict[str, str] = {
    "USDJPY": "USD/JPY",
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "AUDUSD": "AUD/USD",
    "GBPAUD": "GBP/AUD",
    "GBPNZD": "GBP/NZD",
    "XAUUSD": "XAU/USD",
    "US30": "DJI",
    "WTIUSD": "WTI",
}

RECOMMENDED_SYMBOLS: Dict[str, str] = {
    "EURJPY": "EUR/JPY",
    "GBPJPY": "GBP/JPY",
    "AUDJPY": "AUD/JPY",
    "NZDJPY": "NZD/JPY",
    "EURGBP": "EUR/GBP",
    "EURNZD": "EUR/NZD",
    "AUDNZD": "AUD/NZD",
    "XAGUSD": "XAG/USD",
    "NAS100": "NDX",
    "SPX500": "SPX",
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
    hour_up: Optional[Signal]
    hour_down: Optional[Signal]
    weekday_up: Optional[Signal]
    weekday_down: Optional[Signal]
    hour_weekday_up: Optional[Signal]
    hour_weekday_down: Optional[Signal]
    note: Optional[str] = None


class StatsBot:
    discord_limit = 1900

    def __init__(self) -> None:
        self.webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
        self.twelve_data_api_key = os.getenv("TWELVEDATA_API_KEY", "").strip()
        self.lookback_days = int(os.getenv("LOOKBACK_DAYS", "180"))
        self.min_samples = int(os.getenv("MIN_SAMPLES", "20"))
        self.max_retries = int(os.getenv("API_MAX_RETRIES", "4"))
        self.retry_wait_sec = int(os.getenv("API_RETRY_WAIT_SEC", "8"))
        self.request_timeout = int(os.getenv("API_TIMEOUT_SEC", "20"))
        include_recommended = os.getenv("INCLUDE_RECOMMENDED", "true").lower() == "true"

        self.symbols = dict(BASE_SYMBOLS)
        if include_recommended:
            self.symbols.update(RECOMMENDED_SYMBOLS)

        self.session = requests.Session()

    @staticmethod
    def _normalize_index(df: pd.DataFrame) -> pd.DataFrame:
        idx = df.index
        if idx.tz is None:
            df.index = idx.tz_localize("UTC").tz_convert(JST)
        else:
            df.index = idx.tz_convert(JST)
        return df

    def fetch_symbol(self, market_symbol: str) -> pd.DataFrame:
        if not self.twelve_data_api_key:
            raise RuntimeError("TWELVEDATA_API_KEY is not set")

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(
                    TWELVE_DATA_URL,
                    params={
                        "symbol": market_symbol,
                        "interval": "1h",
                        "outputsize": str(min(self.lookback_days * 24, 5000)),
                        "timezone": "UTC",
                        "apikey": self.twelve_data_api_key,
                    },
                    timeout=self.request_timeout,
                )
                response.raise_for_status()
                payload = response.json()
                if "values" not in payload or not payload["values"]:
                    raise RuntimeError(f"empty values: {payload.get('message', payload.get('status', 'unknown'))}")

                df = pd.DataFrame(payload["values"])
                df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
                df["open"] = pd.to_numeric(df["open"], errors="coerce")
                df["close"] = pd.to_numeric(df["close"], errors="coerce")
                df = df.dropna(subset=["open", "close"]).copy()
                if df.empty:
                    raise RuntimeError("all rows are NaN after numeric conversion")

                df = df.set_index("datetime")[["open", "close"]].sort_index()
                df.columns = ["Open", "Close"]
                return self._normalize_index(df)
            except Exception as exc:
                is_last = attempt == self.max_retries
                logging.warning(
                    "twelvedata retry %d/%d failed for symbol=%s err=%s",
                    attempt,
                    self.max_retries,
                    market_symbol,
                    exc,
                )
                if is_last:
                    logging.error("twelvedata failed after retries for symbol=%s", market_symbol)
                else:
                    time.sleep(self.retry_wait_sec * attempt)
        return pd.DataFrame()

    def fetch_all(self) -> Dict[str, pd.DataFrame]:
        frames: Dict[str, pd.DataFrame] = {}
        for market_symbol in self.symbols.values():
            frames[market_symbol] = self.fetch_symbol(market_symbol)
        return frames

    def _best_signal(self, grouped: pd.DataFrame, label_builder, direction: str) -> Optional[Signal]:
        if grouped.empty:
            return None
        valid = grouped[grouped["count"] >= self.min_samples].copy()
        if valid.empty:
            return None

        valid["up_prob"] = valid["up_count"] / valid["count"]
        valid["down_prob"] = 1 - valid["up_prob"]
        if direction == "up":
            valid["direction"] = "↑"
            valid["prob"] = valid["up_prob"]
        elif direction == "down":
            valid["direction"] = "↓"
            valid["prob"] = valid["down_prob"]
        else:
            raise ValueError(f"unknown direction: {direction}")
        chosen = valid.sort_values(["prob", "count"], ascending=[False, False]).iloc[0]
        return Signal(
            label=label_builder(chosen.name),
            direction=str(chosen["direction"]),
            probability=float(chosen["prob"]),
            ev=float(chosen["mean_ret"]),
            samples=int(chosen["count"]),
        )

    def analyze_symbol(self, symbol: str, market_symbol: str, frame_map: Dict[str, pd.DataFrame]) -> SymbolSignals:
        df = frame_map.get(market_symbol, pd.DataFrame())
        if df.empty:
            return SymbolSignals(
                symbol=symbol,
                hour_up=None,
                hour_down=None,
                weekday_up=None,
                weekday_down=None,
                hour_weekday_up=None,
                hour_weekday_down=None,
                note="データ取得不可",
            )

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

        hour_up_signal = self._best_signal(hour_stats, lambda h: f"{int(h):02d}時", direction="up")
        hour_down_signal = self._best_signal(hour_stats, lambda h: f"{int(h):02d}時", direction="down")
        weekday_up_signal = self._best_signal(
            weekday_stats,
            lambda w: f"{WEEKDAY_LABELS_JA.get(int(w), str(w))}曜",
            direction="up",
        )
        weekday_down_signal = self._best_signal(
            weekday_stats,
            lambda w: f"{WEEKDAY_LABELS_JA.get(int(w), str(w))}曜",
            direction="down",
        )
        hw_up_signal = self._best_signal(
            hw_stats,
            lambda key: f"{WEEKDAY_LABELS_JA.get(int(key[0]), str(key[0]))}曜 {int(key[1]):02d}時",
            direction="up",
        )
        hw_down_signal = self._best_signal(
            hw_stats,
            lambda key: f"{WEEKDAY_LABELS_JA.get(int(key[0]), str(key[0]))}曜 {int(key[1]):02d}時",
            direction="down",
        )

        return SymbolSignals(
            symbol=symbol,
            hour_up=hour_up_signal,
            hour_down=hour_down_signal,
            weekday_up=weekday_up_signal,
            weekday_down=weekday_down_signal,
            hour_weekday_up=hw_up_signal,
            hour_weekday_down=hw_down_signal,
        )

    @staticmethod
    def _fmt_signal(title: str, signal: Optional[Signal]) -> str:
        if signal is None:
            return f"{title}: n/a"
        return (
            f"{title}: {signal.label} {signal.direction} {signal.probability * 100:.0f}% "
            f"/ EV {signal.ev:+.5f} (n={signal.samples})"
        )

    def _build_direction_sections(self, signals: List[SymbolSignals], direction: str) -> List[str]:
        if direction == "up":
            header = "Bullish Market Stats"
            legend = "Legend: H=Time window / W=Weekday / Up=Bullish probability / EV=Average(Close-Open)"
            signal_rows = [
                ("H Up", "hour_up"),
                ("W Up", "weekday_up"),
                ("HxW Up", "hour_weekday_up"),
            ]
        elif direction == "down":
            header = "Bearish Market Stats"
            legend = "Legend: H=Time window / W=Weekday / Down=Bearish probability / EV=Average(Close-Open)"
            signal_rows = [
                ("H Down", "hour_down"),
                ("W Down", "weekday_down"),
                ("HxW Down", "hour_weekday_down"),
            ]
        else:
            raise ValueError(f"unknown direction: {direction}")

        now = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
        sections: List[str] = []
        for s in signals:
            section = [s.symbol]
            for title, attr in signal_rows:
                section.append(self._fmt_signal(title, getattr(s, attr)))
            if s.note:
                section.append(f"note: {s.note}")
            sections.append("\n".join(section))

        return [f"Market Stats ({header}, {now})", *sections, legend]

    def _chunk_sections(self, title: str, sections: List[str], legend: str) -> List[str]:
        messages: List[str] = []
        current_sections: List[str] = []

        def build_message(parts: List[str]) -> str:
            body = "\n\n".join(parts)
            return f"{title}\n```\n{body}\n```\n{legend}"

        for section in sections:
            candidate_parts = [*current_sections, section]
            if current_sections and len(build_message(candidate_parts)) > self.discord_limit:
                messages.append(build_message(current_sections))
                current_sections = [section]
            else:
                current_sections = candidate_parts

        if current_sections:
            messages.append(build_message(current_sections))

        return messages

    def render_messages(self, signals: List[SymbolSignals]) -> List[str]:
        messages: List[str] = []
        for direction in ("up", "down"):
            title, *body_sections, legend = self._build_direction_sections(signals, direction)
            messages.extend(self._chunk_sections(title, body_sections, legend))
        return messages

    def post_discord(self, content: str) -> None:
        if not self.webhook_url:
            raise RuntimeError("DISCORD_WEBHOOK_URL is not set")
        resp = requests.post(self.webhook_url, json={"content": content}, timeout=20)
        if resp.status_code >= 300:
            raise RuntimeError(f"Discord webhook failed: {resp.status_code} {resp.text}")

    def run(self) -> None:
        logging.info("start analysis symbols=%d lookback_days=%d min_samples=%d", len(self.symbols), self.lookback_days, self.min_samples)
        frame_map = self.fetch_all()
        results = [self.analyze_symbol(symbol, market_symbol, frame_map) for symbol, market_symbol in self.symbols.items()]
        messages = self.render_messages(results)
        for index, message in enumerate(messages, start=1):
            logging.info("prepared discord message %d/%d length=%d", index, len(messages), len(message))

        dry_run = os.getenv("DRY_RUN", "false").lower() == "true"
        if dry_run:
            for index, message in enumerate(messages, start=1):
                print(f"--- message {index}/{len(messages)} ---")
                print(message)
            logging.info("dry-run finished")
            return

        for message in messages:
            self.post_discord(message)
        logging.info("discord notifications sent count=%d", len(messages))


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
    StatsBot().run()
