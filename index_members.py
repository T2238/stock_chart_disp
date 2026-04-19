"""
JPXプライム150・JPX日経400 の構成銘柄リストを JPX 公式 CSV から取得する。
取得結果は 24 時間 Streamlit キャッシュに保持する。
"""
import io
import logging
import requests
import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)

_URLS: dict[str, str] = {
    "JPXプライム150": "https://www.jpx.co.jp/automation/markets/indices/jpx-prime150/files/jpxprime150weight_j.csv",
    "JPX日経400":     "https://www.jpx.co.jp/markets/indices/jpx-nikkei400/tvdivq00000031dd-att/jpx_nikkei_index_400_weight_jp.csv",
}

# 各指数の ETF ティッカー (比較用)
INDEX_ETF: dict[str, tuple[str, str]] = {
    "JPXプライム150": ("2080.T", "JPXプライム150 ETF"),
    "JPX日経400":     ("1592.T", "JPX日経400 ETF"),
}


def _fetch_codes(url: str) -> set[str]:
    """CSV を取得して 4 桁証券コードの set を返す。失敗時は空 set。"""
    try:
        resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        resp.encoding = "shift_jis"
        df = pd.read_csv(io.StringIO(resp.text), dtype=str)

        # コード列を探す（列名がCSVによって異なる場合に対応）
        code_col = next(
            (c for c in df.columns if "コード" in c or "code" in c.lower() or "Code" in c),
            None,
        )
        if code_col is None:
            logger.warning(f"コード列が見つかりません。列: {df.columns.tolist()}")
            return set()

        codes = (
            df[code_col]
            .dropna()
            .astype(str)
            .str.strip()
            .str.replace(r"\D", "", regex=True)   # 数字のみ抽出
            .str[:4]                               # 4 桁に統一
        )
        return set(codes[codes.str.len() == 4].tolist())

    except Exception as e:
        logger.warning(f"構成銘柄 CSV 取得失敗 ({url}): {e}")
        return set()


@st.cache_data(ttl=86400, show_spinner=False)
def load_index_members() -> dict[str, set[str]]:
    """指数名 → 4 桁証券コード set の dict を返す。"""
    return {name: _fetch_codes(url) for name, url in _URLS.items()}


def get_memberships(code4: str, members: dict[str, set[str]]) -> list[str]:
    """4 桁コードが所属する指数名リストを返す。"""
    return [name for name, codes in members.items() if code4 in codes]
