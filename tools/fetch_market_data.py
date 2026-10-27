"""Historical OHLCV data access with local parquet caching and incremental refresh.

Binance's public klines endpoint is used for BTC/USDT; yfinance for the ETF proxies
SPY/QQQ/GLD (SP500/Nasdaq/Gold respectively — see the approved implementation plan for
why ETFs were chosen over raw index/futures tickers: real intraday volume, and directly
tradable by a retail user).

Canonical timeframe strings used throughout this project: "5m", "15m", "1h", "4h", "1d",
"1w" (see docs/development/workflows/generate_strategy.md's timeframe profiles). Binance supports all six
natively. yfinance has no native 4h interval, so 4h bars are derived by resampling cached
1h data — never cached separately, so there's exactly one source of truth per pair.
"""

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

from tools.schemas import Pair

CACHE_DIR = Path(__file__).resolve().parent.parent / "data_cache"

YF_TICKERS = {
    Pair.SP500: "SPY",
    Pair.NASDAQ: "QQQ",
    Pair.GOLD: "GLD",
}

BINANCE_SYMBOL = "BTCUSDT"
BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"

# canonical timeframe -> (Binance interval, yfinance interval or None if unsupported)
TIMEFRAME_SPECS = {
    "5m": ("5m", "5m"),
    "15m": ("15m", "15m"),
    "1h": ("1h", "60m"),
    "4h": ("4h", None),
    "1d": ("1d", "1d"),
    "1w": ("1w", "1wk"),
}

# Per-timeframe staleness threshold before an incremental refresh is triggered.
STALENESS = {
    "5m": timedelta(minutes=15),
    "15m": timedelta(minutes=45),
    "1h": timedelta(hours=3),
    "4h": timedelta(hours=12),
    "1d": timedelta(days=2),
    "1w": timedelta(days=7),
}

OHLCV_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]

# Default history per timeframe. Intraday windows are capped by what yfinance serves
# (5m/15m: last 60 days; 60m: last 730 days) so every pair gets the same depth; daily and
# weekly go back ~8 years so the weekly EMA confirmation has room to warm up.
LOOKBACK_DAYS = {
    "5m": 59,
    "15m": 59,
    "1h": 729,
    "4h": 729,
    "1d": 3000,
    "1w": 3000,
}

# A cache whose last full fetch asked for a window starting this much later than the one
# requested now (i.e. it was built with a shorter lookback) is rebuilt instead of only
# topped up. Comparing requested starts, not the first cached bar, avoids refetching
# forever when the source simply has no older data (e.g. BTC/USDT before Aug 2017).
COVERAGE_TOLERANCE = timedelta(days=7)


class DataFetchError(Exception):
    pass


def fetch_ohlcv(pair: Pair, timeframe: str, lookback_days: int | None = None) -> pd.DataFrame:
    """Freshest available OHLCV data for `pair`/`timeframe` (UTC DatetimeIndex, columns
    Open/High/Low/Close/Volume), using a local parquet cache with incremental refresh.
    `lookback_days` defaults to LOOKBACK_DAYS for the timeframe."""
    if timeframe not in TIMEFRAME_SPECS:
        raise DataFetchError(f"unsupported timeframe '{timeframe}'")
    if lookback_days is None:
        lookback_days = LOOKBACK_DAYS[timeframe]

    if timeframe == "4h" and pair != Pair.BTC_USDT:
        base = fetch_ohlcv(pair, "1h", lookback_days)
        return _resample_to_4h(base)

    cached = _load_cache(pair, timeframe)
    wanted_start = _utcnow() - timedelta(days=lookback_days)
    if cached is not None and not cached.empty:
        covered_since = _load_requested_start(pair, timeframe) or cached.index[0]
        if covered_since > wanted_start + COVERAGE_TOLERANCE:
            cached = None  # built for a shorter window: rebuild instead of topping up
    if cached is None or cached.empty or (_utcnow() - cached.index[-1]) > STALENESS[timeframe]:
        cached = _refresh(pair, timeframe, cached, lookback_days)
    if cached.empty:
        raise DataFetchError(f"no {timeframe} market data returned for {pair.value}")
    return cached


def get_available_range(df: pd.DataFrame) -> tuple[str, str]:
    """Actual first/last timestamp covered by `df`, so callers can surface it instead of
    silently backtesting over a shorter window than requested."""
    if df.empty:
        return ("", "")
    return (df.index[0].isoformat(), df.index[-1].isoformat())


def _refresh(pair: Pair, timeframe: str, cached_df: pd.DataFrame | None, lookback_days: int) -> pd.DataFrame:
    if cached_df is not None and not cached_df.empty:
        since = cached_df.index[-1]
        new_rows = _fetch_from_source(pair, timeframe, since)
        merged = pd.concat([cached_df, new_rows])
        merged = merged[~merged.index.duplicated(keep="last")].sort_index()
    else:
        since = _utcnow() - timedelta(days=lookback_days)
        merged = _fetch_from_source(pair, timeframe, since)
        _save_requested_start(pair, timeframe, since)

    _save_cache(pair, timeframe, merged)
    return merged


def _fetch_from_source(pair: Pair, timeframe: str, since: datetime) -> pd.DataFrame:
    if pair == Pair.BTC_USDT:
        return _fetch_binance(timeframe, since)
    return _fetch_yfinance(pair, timeframe, since)


def _fetch_binance(timeframe: str, since: datetime) -> pd.DataFrame:
    interval, _ = TIMEFRAME_SPECS[timeframe]
    start_ms = int(since.timestamp() * 1000)
    rows = []
    try:
        while True:
            resp = requests.get(
                BINANCE_KLINES_URL,
                params={"symbol": BINANCE_SYMBOL, "interval": interval, "startTime": start_ms, "limit": 1000},
                timeout=15,
            )
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            rows.extend(batch)
            start_ms = batch[-1][0] + 1
            if len(batch) < 1000:
                break
            time.sleep(0.2)
    except requests.RequestException as exc:
        raise DataFetchError(
            f"Binance klines request failed ({exc}). Note: api.binance.com is geo-blocked "
            "in some regions (e.g. the US) — this is a known open risk, not necessarily a bug."
        ) from exc

    if not rows:
        return pd.DataFrame(columns=OHLCV_COLUMNS)

    df = pd.DataFrame(
        rows,
        columns=[
            "open_time", "Open", "High", "Low", "Close", "Volume", "close_time",
            "quote_volume", "trades", "taker_base", "taker_quote", "ignore",
        ],
    )
    df.index = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    return df[OHLCV_COLUMNS].astype(float)


def _fetch_yfinance(pair: Pair, timeframe: str, since: datetime) -> pd.DataFrame:
    ticker = YF_TICKERS[pair]
    _, interval = TIMEFRAME_SPECS[timeframe]
    if interval is None:
        raise DataFetchError(f"yfinance has no native interval for timeframe '{timeframe}'")

    try:
        data = yf.Ticker(ticker).history(start=since, interval=interval, auto_adjust=False)
    except Exception as exc:  # yfinance raises assorted exception types on network failure
        raise DataFetchError(f"yfinance request for '{ticker}' failed: {exc}") from exc

    if data.empty:
        return pd.DataFrame(columns=OHLCV_COLUMNS)

    data.index = pd.to_datetime(data.index, utc=True)
    return data[OHLCV_COLUMNS]


def _resample_to_4h(df_1h: pd.DataFrame) -> pd.DataFrame:
    if df_1h.empty:
        return df_1h
    return (
        df_1h.resample("4h")
        .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
        .dropna()
    )


def _cache_path(pair: Pair, timeframe: str) -> Path:
    safe_pair = pair.value.replace("/", "_")
    return CACHE_DIR / f"{safe_pair}_{timeframe}.parquet"


def _load_cache(pair: Pair, timeframe: str) -> pd.DataFrame | None:
    path = _cache_path(pair, timeframe)
    if not path.exists():
        return None
    return pd.read_parquet(path)


def _save_cache(pair: Pair, timeframe: str, df: pd.DataFrame) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(_cache_path(pair, timeframe))


def _requested_start_path(pair: Pair, timeframe: str) -> Path:
    return _cache_path(pair, timeframe).with_suffix(".since")


def _load_requested_start(pair: Pair, timeframe: str) -> datetime | None:
    path = _requested_start_path(pair, timeframe)
    if not path.exists():
        return None
    return datetime.fromisoformat(path.read_text(encoding="utf-8").strip())


def _save_requested_start(pair: Pair, timeframe: str, since: datetime) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _requested_start_path(pair, timeframe).write_text(since.isoformat(), encoding="utf-8")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
