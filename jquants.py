"""
J-Quants API V2 から東証銘柄リストを取得・キャッシュする。
trend_stock_search/data/fetch_stocks.py の実装を流用。
"""
import os
import logging
import requests
import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)

JQUANTS_BASE_V2 = "https://api.jquants.com/v2"

MARKET_BADGE = {
    "0111": ("P", "プライム"),
    "0112": ("S", "スタンダード"),
    "0113": ("G", "グロース"),
    "0114": ("S", "スタンダード"),
    "111":  ("P", "プライム"),
    "112":  ("S", "スタンダード"),
    "113":  ("G", "グロース"),
    "114":  ("S", "スタンダード"),
}


def to_yf_ticker(code: str) -> str:
    """J-Quants コード → yfinance ティッカー (例: "72030" or "7203" → "7203.T")"""
    code = str(code).strip()
    if len(code) == 5 and code.endswith("0"):
        code = code[:4]
    return f"{code}.T"


def _badge(market_code: str) -> str:
    badge, _ = MARKET_BADGE.get(str(market_code).strip(), ("?", "その他"))
    return badge


def _market_name(market_code: str) -> str:
    _, name = MARKET_BADGE.get(str(market_code).strip(), ("?", "その他"))
    return name


def _fetch_from_api(api_key: str) -> pd.DataFrame:
    all_rows: list[dict] = []
    params: dict = {}
    while True:
        resp = requests.get(
            f"{JQUANTS_BASE_V2}/equities/master",
            headers={"x-api-key": api_key},
            params=params,
            timeout=60,
        )
        resp.raise_for_status()
        body = resp.json()
        all_rows.extend(body.get("data", []))
        next_token = body.get("pagination_key")
        if not next_token:
            break
        params = {"pagination_key": next_token}

    df = pd.DataFrame(all_rows)
    df = df.rename(columns={
        "CoName":   "CompanyName",
        "CoNameEn": "CompanyNameEnglish",
        "Mkt":      "MarketCode",
        "MktNm":    "MarketCodeName",
        "S17":      "Sector17Code",
        "S17Nm":    "Sector17CodeName",
        "S33":      "Sector33Code",
        "S33Nm":    "Sector33CodeName",
        "ScaleCat": "ScaleCategory",
    })
    if "MarketCode" in df.columns:
        df = df[df["MarketCode"].isin(["0111", "0112", "0113", "0114"])]
    return df


def _sample_stocks() -> pd.DataFrame:
    rows = [
        ("7203",  "トヨタ自動車",        "0111", "プライム", "輸送用機器"),
        ("6758",  "ソニーグループ",       "0111", "プライム", "電気機器"),
        ("9984",  "ソフトバンクグループ", "0111", "プライム", "情報・通信業"),
        ("8035",  "東京エレクトロン",     "0111", "プライム", "電気機器"),
        ("6861",  "キーエンス",           "0111", "プライム", "電気機器"),
        ("4063",  "信越化学工業",         "0111", "プライム", "化学"),
        ("7011",  "三菱重工業",           "0111", "プライム", "機械"),
        ("8316",  "三井住友FG",           "0111", "プライム", "銀行業"),
        ("4519",  "中外製薬",             "0111", "プライム", "医薬品"),
        ("9432",  "NTT",                  "0111", "プライム", "情報・通信業"),
        ("5401",  "日本製鉄",             "0111", "プライム", "鉄鋼"),
        ("4385",  "メルカリ",             "0113", "グロース", "情報・通信業"),
        ("4478",  "フリー",               "0113", "グロース", "情報・通信業"),
    ]
    df = pd.DataFrame(rows, columns=["Code", "CompanyName", "MarketCode", "MarketCodeName", "Sector33CodeName"])
    df["Sector33Code"] = ""
    df["Sector17Code"] = ""
    df["Sector17CodeName"] = ""
    df["ScaleCategory"] = ""
    df["CompanyNameEnglish"] = ""
    return df


def _get_api_key() -> str:
    """st.secrets → 環境変数 の順で J-Quants APIキーを取得する。"""
    try:
        val = st.secrets.get("JQUANTS_API_KEY", "")
        if val:
            return val
    except Exception:
        pass
    return os.getenv("JQUANTS_API_KEY", "")


@st.cache_data(ttl=3600, show_spinner=False)
def load_stocks() -> pd.DataFrame:
    """銘柄リストを返す。CSV→API→サンプルの順にフォールバック。"""
    from config import STOCKS_CSV_PATH
    JQUANTS_API_KEY = _get_api_key()

    df: pd.DataFrame | None = None

    if os.path.exists(STOCKS_CSV_PATH):
        try:
            df = pd.read_csv(STOCKS_CSV_PATH, dtype={"Code": str, "MarketCode": str})
            logger.info(f"stocks.csv 読み込み: {len(df)} 銘柄")
        except Exception as e:
            logger.warning(f"stocks.csv 読み込み失敗: {e}")

    if df is None and JQUANTS_API_KEY:
        try:
            df = _fetch_from_api(JQUANTS_API_KEY)
            os.makedirs(os.path.dirname(STOCKS_CSV_PATH), exist_ok=True)
            df.to_csv(STOCKS_CSV_PATH, index=False, encoding="utf-8-sig")
            logger.info(f"J-Quants API から {len(df)} 銘柄取得")
        except Exception as e:
            logger.warning(f"J-Quants API エラー: {e}")

    if df is None or df.empty:
        logger.warning("サンプル銘柄リストを使用します")
        df = _sample_stocks()

    df["Badge"] = df["MarketCode"].apply(_badge)
    df["DisplayCode"] = df.apply(
        lambda r: f"[{r['Badge']}] {r['Code']} {r['CompanyName']}", axis=1
    )
    df["YfTicker"] = df["Code"].apply(to_yf_ticker)
    return df
