"""
テクニカル指標モジュール (stock_recommend/indicators.py から流用)
"""
import pandas as pd


def calc_ma(close: pd.Series, window: int) -> pd.Series:
    return close.rolling(window).mean()


def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calc_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Returns (macd, signal_line, histogram)"""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line, macd - signal_line


def calc_bollinger(close: pd.Series, window: int = 20, num_std: float = 2.0):
    """Returns (upper, middle, lower, pct_b)"""
    ma = close.rolling(window).mean()
    std = close.rolling(window).std()
    upper = ma + num_std * std
    lower = ma - num_std * std
    band_width = upper - lower
    pct_b = (close - lower) / band_width.replace(0, float("nan"))
    return upper, ma, lower, pct_b
