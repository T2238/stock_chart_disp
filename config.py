import os
from dotenv import load_dotenv

load_dotenv()

JQUANTS_API_KEY = os.getenv("JQUANTS_API_KEY", "")

STOCKS_CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "stocks.csv")

# yfinance ティッカー: 日本株は "7203.T" 形式
INDICES: dict[str, str] = {
    "日経225":       "^N225",
    "TOPIX ETF":     "1306.T",
    "S&P500":        "^GSPC",
    "NASDAQ":        "^IXIC",
    "NYダウ":        "^DJI",
    "ドル円":        "JPY=X",
}

# J-Quants Sector17Code → (yfinance ティッカー, 業種名)
# NEXT FUNDS 東証業種別 ETF シリーズ (1615〜1631)
SECTOR17_ETF: dict[str, tuple[str, str]] = {
    "1":  ("1617.T", "食品 ETF"),
    "2":  ("1618.T", "エネルギー資源 ETF"),
    "3":  ("1619.T", "建設・資材 ETF"),
    "4":  ("1620.T", "素材・化学 ETF"),
    "5":  ("1621.T", "医薬品・バイオ ETF"),
    "6":  ("1622.T", "自動車・輸送機 ETF"),
    "7":  ("1623.T", "鉄鋼・非鉄 ETF"),
    "8":  ("1624.T", "機械 ETF"),
    "9":  ("1625.T", "電機・精密 ETF"),
    "10": ("1626.T", "情報通信・サービス ETF"),
    "11": ("1627.T", "電力・ガス ETF"),
    "12": ("1628.T", "運輸・物流 ETF"),
    "13": ("1629.T", "商社・卸売 ETF"),
    "14": ("1630.T", "小売 ETF"),
    "15": ("1615.T", "銀行 ETF"),
    "16": ("1631.T", "金融（除く銀行）ETF"),
    "17": ("1343.T", "J-REIT ETF"),
}

# J-Quants ScaleCategory → (yfinance ティッカー, 表示名)
# Core30のみ対応（Mid400・Small は現時点で対応ETF/指数なし）
SCALE_ETF: dict[str, tuple[str, str]] = {
    "TOPIX Core30": ("1311.T", "TOPIX Core30 ETF"),
}

# 移動平均線の設定 (window, color, label)
MA_CONFIGS: list[tuple[int, str, str]] = [
    (5,  "#F59E0B", "MA5"),
    (20, "#10B981", "MA20"),
    (75, "#8B5CF6", "MA75"),
]
