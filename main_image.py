import io
import json
import logging
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Tuple, Union

import pandas as pd
import requests
from PIL import Image, ImageDraw, ImageFont

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

WEEKDAY_LABELS = {
    0: "Mon",
    1: "Tue",
    2: "Wed",
    3: "Thu",
    4: "Fri",
    5: "Sat",
    6: "Sun",
}


@dataclass
class TableImage:
    filename: str
    title: str
    content: bytes


class StatsBot:
    def __init__(self) -> None:
        self.webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
        self.twelve_data_api_key = os.getenv("TWELVEDATA_API_KEY", "").strip()
        self.lookback_days = int(os.getenv("LOOKBACK_DAYS", "180"))
        self.min_samples = int(os.getenv("MIN_SAMPLES", "20"))
        self.max_retries = int(os.getenv("API_MAX_RETRIES", "4"))
        self.retry_wait_sec = int(os.getenv("API_RETRY_WAIT_SEC", "8"))
        self.request_timeout = int(os.getenv("API_TIMEOUT_SEC", "20"))
        self.dry_run_dir = os.getenv("DRY_RUN_DIR", ".")
        self.include_weekends = os.getenv("INCLUDE_WEEKENDS", "false").lower() == "true"
        include_recommended = os.getenv("INCLUDE_RECOMMENDED", "true").lower() == "true"

        self.symbols = dict(BASE_SYMBOLS)
        if include_recommended:
            self.symbols.update(RECOMMENDED_SYMBOLS)

        self.session = requests.Session()
        self.body_font = ImageFont.load_default()
        self.title_font = ImageFont.load_default()

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

    def _prepare_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return frame.copy()

        df = frame.copy()
        df["ret"] = df["Close"] - df["Open"]
        df["is_up"] = (df["ret"] > 0).astype(int)
        df["hour"] = df.index.hour
        df["weekday"] = df.index.weekday
        if not self.include_weekends:
            df = df[df["weekday"] <= 4].copy()
        return df

    @staticmethod
    def _aggregate_stats(df: pd.DataFrame, keys: List[str]) -> pd.DataFrame:
        grouped = df.groupby(keys).agg(ret_count=("ret", "count"), up_count=("is_up", "sum"))
        grouped["up_prob"] = grouped["up_count"] / grouped["ret_count"]
        grouped["down_prob"] = 1 - grouped["up_prob"]
        return grouped

    def _format_probability_cell(self, stats: pd.DataFrame, key: Union[Tuple[int, ...], int], field: str) -> str:
        if key not in stats.index:
            return "-"
        row = stats.loc[key]
        if int(row["ret_count"]) < self.min_samples:
            return "-"
        probability = float(row[field]) * 100
        return f"{probability:.0f}%"

    def build_summary_tables(self, frame_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        hour_columns = [f"{hour:02d}" for hour in range(24)]
        weekday_order = [day for day in range(7) if self.include_weekends or day <= 4]
        weekday_columns = [WEEKDAY_LABELS[day] for day in weekday_order]
        hour_weekday_columns = [f"{WEEKDAY_LABELS[day]}-{hour:02d}" for day in weekday_order for hour in range(24)]

        tables: Dict[str, pd.DataFrame] = {
            "up_hour": pd.DataFrame(index=self.symbols.keys(), columns=hour_columns, dtype=object),
            "down_hour": pd.DataFrame(index=self.symbols.keys(), columns=hour_columns, dtype=object),
            "up_weekday": pd.DataFrame(index=self.symbols.keys(), columns=weekday_columns, dtype=object),
            "down_weekday": pd.DataFrame(index=self.symbols.keys(), columns=weekday_columns, dtype=object),
            "up_hour_weekday": pd.DataFrame(index=self.symbols.keys(), columns=hour_weekday_columns, dtype=object),
            "down_hour_weekday": pd.DataFrame(index=self.symbols.keys(), columns=hour_weekday_columns, dtype=object),
        }

        for symbol, market_symbol in self.symbols.items():
            df = self._prepare_frame(frame_map.get(market_symbol, pd.DataFrame()))
            if df.empty:
                logging.warning("no usable rows for symbol=%s market_symbol=%s", symbol, market_symbol)
                continue

            hour_stats = self._aggregate_stats(df, ["hour"])
            weekday_stats = self._aggregate_stats(df, ["weekday"])
            hour_weekday_stats = self._aggregate_stats(df, ["weekday", "hour"])

            for hour in range(24):
                label = f"{hour:02d}"
                tables["up_hour"].loc[symbol, label] = self._format_probability_cell(hour_stats, hour, "up_prob")
                tables["down_hour"].loc[symbol, label] = self._format_probability_cell(hour_stats, hour, "down_prob")

            for day in weekday_order:
                weekday_label = WEEKDAY_LABELS[day]
                tables["up_weekday"].loc[symbol, weekday_label] = self._format_probability_cell(
                    weekday_stats,
                    day,
                    "up_prob",
                )
                tables["down_weekday"].loc[symbol, weekday_label] = self._format_probability_cell(
                    weekday_stats,
                    day,
                    "down_prob",
                )

                for hour in range(24):
                    hw_label = f"{weekday_label}-{hour:02d}"
                    hw_key = (day, hour)
                    tables["up_hour_weekday"].loc[symbol, hw_label] = self._format_probability_cell(
                        hour_weekday_stats,
                        hw_key,
                        "up_prob",
                    )
                    tables["down_hour_weekday"].loc[symbol, hw_label] = self._format_probability_cell(
                        hour_weekday_stats,
                        hw_key,
                        "down_prob",
                    )

        return tables

    def render_table_images(self, tables: Dict[str, pd.DataFrame]) -> List[TableImage]:
        image_specs = [
            ("up_hour", "Bullish Rate by Symbol x Hour (bullish = positive candle rate)", "bullish_symbol_hour.png"),
            ("up_weekday", "Bullish Rate by Symbol x Weekday (bullish = positive candle rate)", "bullish_symbol_weekday.png"),
            ("up_hour_weekday", "Bullish Rate by Symbol x Weekday-Hour (bullish = positive candle rate)", "bullish_symbol_weekday_hour.png"),
            ("down_hour", "Bearish Rate by Symbol x Hour (bearish = negative candle rate)", "bearish_symbol_hour.png"),
            ("down_weekday", "Bearish Rate by Symbol x Weekday (bearish = negative candle rate)", "bearish_symbol_weekday.png"),
            ("down_hour_weekday", "Bearish Rate by Symbol x Weekday-Hour (bearish = negative candle rate)", "bearish_symbol_weekday_hour.png"),
        ]
        return [
            TableImage(filename=filename, title=title, content=self._render_table_image(title, tables[table_key]))
            for table_key, title, filename in image_specs
        ]

    def _render_table_image(self, title: str, table: pd.DataFrame) -> bytes:
        table = table.fillna("-")
        margin = 12
        title_height = 36
        header_height = 32
        row_height = 28
        row_header_width = 90
        min_cell_width = 44
        cell_padding_x = 8

        probe = Image.new("RGB", (1, 1))
        probe_draw = ImageDraw.Draw(probe)

        def text_width(value: str) -> int:
            bbox = probe_draw.textbbox((0, 0), value, font=self.body_font)
            return bbox[2] - bbox[0]

        col_widths: List[int] = []
        for col in table.columns:
            width = text_width(str(col))
            for value in table[col].tolist():
                width = max(width, text_width(str(value)))
            col_widths.append(max(min_cell_width, width + cell_padding_x * 2))

        image_width = margin * 2 + row_header_width + sum(col_widths)
        image_height = margin * 2 + title_height + header_height + row_height * len(table.index)

        image = Image.new("RGB", (image_width, image_height), "#ffffff")
        draw = ImageDraw.Draw(image)

        draw.text((margin, margin), title, fill="#111827", font=self.title_font)
        subtitle = f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M JST')} / min samples {self.min_samples}"
        draw.text((margin, margin + 14), subtitle, fill="#4b5563", font=self.body_font)

        top = margin + title_height
        draw.rectangle((margin, top, image_width - margin, top + header_height), fill="#e5eef9")
        draw.rectangle((margin, top, margin + row_header_width, top + header_height), outline="#cbd5e1", width=1)
        draw.text((margin + 8, top + 9), "Symbol", fill="#0f172a", font=self.body_font)

        x = margin + row_header_width
        for idx, col in enumerate(table.columns):
            width = col_widths[idx]
            draw.rectangle((x, top, x + width, top + header_height), outline="#cbd5e1", width=1)
            draw.text((x + 4, top + 9), str(col), fill="#0f172a", font=self.body_font)
            x += width

        y = top + header_height
        for row_idx, symbol in enumerate(table.index):
            row_bg = "#ffffff" if row_idx % 2 == 0 else "#f8fafc"
            draw.rectangle((margin, y, image_width - margin, y + row_height), fill=row_bg)
            draw.rectangle((margin, y, margin + row_header_width, y + row_height), outline="#e2e8f0", width=1)
            draw.text((margin + 8, y + 8), str(symbol), fill="#111827", font=self.body_font)

            x = margin + row_header_width
            for col_idx, col in enumerate(table.columns):
                width = col_widths[col_idx]
                value = str(table.loc[symbol, col])
                percent = self._parse_percent(value)
                fill = self._cell_fill_color(value)
                draw.rectangle((x, y, x + width, y + row_height), fill=fill, outline="#e2e8f0", width=1)
                text_fill = "#111827" if value == "-" or math.isnan(percent) or percent < 70 else "#ffffff"
                draw.text((x + 6, y + 8), value, fill=text_fill, font=self.body_font)
                x += width

            y += row_height

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    @staticmethod
    def _parse_percent(value: str) -> float:
        if not value.endswith("%"):
            return math.nan
        try:
            return float(value[:-1])
        except ValueError:
            return math.nan

    def _cell_fill_color(self, value: str) -> str:
        if value == "-":
            return "#f3f4f6"
        percent = self._parse_percent(value)
        if math.isnan(percent):
            return "#ffffff"
        if percent >= 75:
            return "#166534"
        if percent >= 65:
            return "#4ade80"
        if percent >= 55:
            return "#bbf7d0"
        if percent >= 45:
            return "#fef3c7"
        if percent >= 35:
            return "#fca5a5"
        return "#dc2626"

    def post_discord_images(self, images: List[TableImage]) -> None:
        if not self.webhook_url:
            raise RuntimeError("DISCORD_WEBHOOK_URL is not set")

        payload = {
            "content": "上がりそうか下がりそうか、しょうがないから教えてあげる。上手に使いなさいよ！"
        }
        files = {f"files[{idx}]": (image.filename, image.content, "image/png") for idx, image in enumerate(images)}
        response = self.session.post(
            self.webhook_url,
            data={"payload_json": json.dumps(payload)},
            files=files,
            timeout=60,
        )
        if response.status_code >= 300:
            raise RuntimeError(f"Discord webhook failed: {response.status_code} {response.text}")

    def save_images_locally(self, images: List[TableImage]) -> None:
        os.makedirs(self.dry_run_dir, exist_ok=True)
        for image in images:
            path = os.path.join(self.dry_run_dir, image.filename)
            with open(path, "wb") as f:
                f.write(image.content)
            logging.info("saved dry-run image: %s", path)

    def run(self) -> None:
        logging.info(
            "start analysis symbols=%d lookback_days=%d min_samples=%d include_weekends=%s",
            len(self.symbols),
            self.lookback_days,
            self.min_samples,
            self.include_weekends,
        )
        frame_map = self.fetch_all()
        tables = self.build_summary_tables(frame_map)
        images = self.render_table_images(tables)
        for image in images:
            logging.info("prepared image %s bytes=%d", image.filename, len(image.content))

        dry_run = os.getenv("DRY_RUN", "false").lower() == "true"
        if dry_run:
            self.save_images_locally(images)
            logging.info("dry-run finished")
            return

        self.post_discord_images(images)
        logging.info("discord notifications sent count=%d", len(images))


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
    StatsBot().run()
