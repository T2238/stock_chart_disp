"""
財務データ取得・整形モジュール
yfinance から売上・営業利益・EPS・BPS を取得し、
株価と組み合わせて PER・PBR を計算する。
"""
import warnings
import pandas as pd
import yfinance as yf
import streamlit as st

warnings.filterwarnings("ignore")

# 財務列の優先順位リスト（見つかった最初の列を使用）
_REVENUE_COLS    = ["Total Revenue", "Operating Revenue"]
_OP_INCOME_COLS  = ["Operating Income", "EBIT"]
_NET_INCOME_COLS = ["Net Income"]
_EPS_COLS        = ["Diluted EPS", "Basic EPS"]
_EQUITY_COLS     = ["Common Stock Equity", "Stockholders Equity"]


def _first(df: pd.DataFrame, candidates: list[str]) -> pd.Series | None:
    for col in candidates:
        if col in df.index:
            return df.loc[col]
    return None


def _safe_get(series: pd.Series | None, key) -> float | None:
    """Series から安全に値を取得する。キー不一致・NaN はすべて None を返す。"""
    if series is None:
        return None
    try:
        val = series.get(key)
        if val is None or pd.isna(val):
            return None
        return float(val)
    except Exception:
        return None


def _price_at(price_df: pd.DataFrame, date: pd.Timestamp) -> float | None:
    """指定日以前の直近終値を返す。"""
    close = price_df["Close"].squeeze()
    mask = close.index <= date
    if not mask.any():
        return None
    return float(close[mask].iloc[-1])


def _format_unit(series: pd.Series) -> tuple[pd.Series, str]:
    """金額 Series を適切な単位（億円/兆円）に変換して単位ラベルも返す。"""
    max_val = series.abs().max()
    if max_val >= 1e12:
        return series / 1e12, "兆円"
    return series / 1e8, "億円"


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_fundamentals(ticker: str) -> dict:
    """
    年次・四半期の財務データを取得して返す。
    戻り値:
      annual_df   : 年次 DataFrame (index=決算期末日)
      quarterly_df: 四半期 DataFrame (index=四半期末日)
      unit        : 売上・営業利益の単位ラベル ("億円" or "兆円")
    """
    t = yf.Ticker(ticker)

    inc_a = t.income_stmt
    inc_q = t.quarterly_income_stmt
    bs_q  = t.quarterly_balance_sheet
    info  = t.info
    shares = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding") or 1

    # 株価（最大期間）
    price_df = t.history(period="max", auto_adjust=True)
    if isinstance(price_df.columns, pd.MultiIndex):
        price_df.columns = price_df.columns.droplevel(1)
    price_df.index = price_df.index.tz_localize(None)

    # ---- 年次データ ----
    annual_rows = {}
    if not inc_a.empty:
        rev_a = _first(inc_a, _REVENUE_COLS)
        opi_a = _first(inc_a, _OP_INCOME_COLS)
        eps_a = _first(inc_a, _EPS_COLS)
        for date in inc_a.columns:
            d = pd.Timestamp(date).tz_localize(None)
            annual_rows[d] = {
                "Revenue":         _safe_get(rev_a, date),
                "OperatingIncome": _safe_get(opi_a, date),
                "EPS":             _safe_get(eps_a, date),
                "Price":           _price_at(price_df, d),
            }
    annual_df = pd.DataFrame(annual_rows).T.sort_index()
    annual_df["PER"] = annual_df["Price"] / annual_df["EPS"].replace(0, float("nan"))

    # ---- 四半期データ ----
    # 損益計算書と貸借対照表で日付が一致しない場合があるため _safe_get で安全アクセス
    quarterly_rows = {}
    if not inc_q.empty:
        eps_q = _first(inc_q, _EPS_COLS)
        rev_q = _first(inc_q, _REVENUE_COLS)
        opi_q = _first(inc_q, _OP_INCOME_COLS)
        eq_q  = _first(bs_q,  _EQUITY_COLS) if not bs_q.empty else None

        for date in inc_q.columns:
            d     = pd.Timestamp(date).tz_localize(None)
            eq_val = _safe_get(eq_q, date)
            quarterly_rows[d] = {
                "Revenue":         _safe_get(rev_q, date),
                "OperatingIncome": _safe_get(opi_q, date),
                "EPS_Q":           _safe_get(eps_q, date),
                "BPS":             eq_val / shares if eq_val is not None else None,
                "Price":           _price_at(price_df, d),
            }

    quarterly_df = pd.DataFrame(quarterly_rows).T.sort_index()

    # Trailing 12M EPS = 直近4四半期の EPS 合計 → PER
    if "EPS_Q" in quarterly_df.columns:
        quarterly_df["TTM_EPS"] = quarterly_df["EPS_Q"].rolling(4, min_periods=2).sum()
        quarterly_df["PER"] = quarterly_df["Price"] / quarterly_df["TTM_EPS"].replace(0, float("nan"))

    # PBR = Price / BPS
    if "BPS" in quarterly_df.columns and "Price" in quarterly_df.columns:
        quarterly_df["PBR"] = quarterly_df["Price"] / quarterly_df["BPS"].replace(0, float("nan"))

    # 単位を決定（年次売上の最大値で判断）
    if not annual_df.empty and "Revenue" in annual_df.columns:
        _, unit = _format_unit(annual_df["Revenue"].dropna())
    else:
        unit = "億円"

    return {
        "annual_df":    annual_df,
        "quarterly_df": quarterly_df,
        "unit":         unit,
    }
