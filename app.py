"""
株価チャート表示アプリ
  - J-Quants API から東証全銘柄リストを取得
  - yfinance でローソク足データを取得（10年以上対応）
  - Plotly でインタラクティブなチャートを表示
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
import streamlit as st
import yfinance as yf

from config import INDICES, SECTOR17_ETF, SCALE_ETF
from jquants import load_stocks
from chart import build_candlestick_chart, build_comparison_chart, build_fundamental_chart
from index_members import load_index_members, get_memberships, INDEX_ETF
from fundamentals import fetch_fundamentals

# ---------------------------------------------------------------- ページ設定 --
st.set_page_config(
    page_title="株価チャート",
    page_icon="📈",
    layout="wide",
)

st.markdown("""
<style>
[data-testid="stSidebar"] { background-color: #111827; }
.stSelectbox label, .stMultiSelect label { font-size: 0.85rem; }
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------------------- データ取得 --
PERIOD_OPTIONS: dict[str, str] = {
    "1ヶ月":  "1mo",
    "3ヶ月":  "3mo",
    "6ヶ月":  "6mo",
    "1年":    "1y",
    "3年":    "3y",
    "5年":    "5y",
    "10年":   "10y",
    "最大":   "max",
}

INTERVAL_OPTIONS: dict[str, str] = {
    "日足": "1d",
    "週足": "1wk",
    "月足": "1mo",
}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_shares_outstanding(ticker: str) -> int | None:
    """発行済株式数を取得する。取得失敗時は None。"""
    try:
        info = yf.Ticker(ticker).info
        return info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def fetch_ohlcv(ticker: str, period: str, interval: str) -> pd.DataFrame:
    df = yf.download(ticker, period=period, interval=interval,
                     auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    return df


def parse_display_code(display_code: str) -> tuple[str, str]:
    """'[P] 7203 トヨタ自動車' → ('7203.T', 'トヨタ自動車')"""
    parts = display_code.split("]", 1)[1].strip().split(" ", 1)
    code = parts[0]
    name = parts[1] if len(parts) > 1 else code
    if len(code) == 5 and code.endswith("0"):
        code = code[:4]
    return f"{code}.T", name


# ---------------------------------------------------------------- サイドバー --
with st.sidebar:
    st.title("📈 株価チャート")
    st.divider()

    # 銘柄リスト・指数構成銘柄取得
    with st.spinner("銘柄リスト読み込み中..."):
        stocks_df = load_stocks()
    with st.spinner("指数構成銘柄取得中..."):
        index_members = load_index_members()

    all_options = stocks_df["DisplayCode"].tolist()

    # 市場フィルタ
    market_filter = st.multiselect(
        "市場フィルタ",
        ["P（プライム）", "S（スタンダード）", "G（グロース）"],
        default=["P（プライム）", "S（スタンダード）", "G（グロース）"],
        label_visibility="collapsed",
    )
    badge_filter = set()
    for m in market_filter:
        badge_filter.add(m[0])

    filtered_df = stocks_df[stocks_df["Badge"].isin(badge_filter)]
    filtered_options = filtered_df["DisplayCode"].tolist()

    # メイン銘柄
    st.subheader("メイン銘柄")
    default_idx = next(
        (i for i, o in enumerate(filtered_options) if "7203" in o), 0
    )
    main_display = st.selectbox(
        "銘柄を選択（名前・コードで検索可）",
        filtered_options,
        index=default_idx,
        label_visibility="collapsed",
    )
    main_ticker, main_name = parse_display_code(main_display)

    st.divider()

    # 比較モード
    st.subheader("比較（任意）")
    compare_mode = st.toggle("比較モード（リターン率）", value=False)

    # 選択銘柄の業種・規模・指数情報を事前に解決しておく
    main_row = stocks_df[stocks_df["DisplayCode"] == main_display]
    sector17_code = str(main_row.iloc[0].get("Sector17Code", "")).strip() if not main_row.empty else ""
    scale_cat     = str(main_row.iloc[0].get("ScaleCategory",  "")).strip() if not main_row.empty else ""
    raw_code      = str(main_row.iloc[0]["Code"]).strip() if not main_row.empty else ""
    code4         = raw_code[:4] if len(raw_code) >= 4 else raw_code
    sector_etf    = SECTOR17_ETF.get(sector17_code)
    scale_etf     = SCALE_ETF.get(scale_cat)
    memberships   = get_memberships(code4, index_members)  # 所属指数リスト

    compare_tickers: list[tuple[str, str]] = []
    if compare_mode:
        compare_stocks = st.multiselect(
            "比較銘柄（最大3つ）",
            [o for o in filtered_options if o != main_display],
            max_selections=3,
        )
        for cs in compare_stocks:
            ticker, name = parse_display_code(cs)
            compare_tickers.append((ticker, name))

        compare_indices = st.multiselect(
            "指数比較",
            list(INDICES.keys()),
            default=["日経225"],
        )
        for idx_name in compare_indices:
            compare_tickers.append((INDICES[idx_name], idx_name))

        # 業種別ETF
        if sector_etf:
            if st.checkbox(f"業種別ETFを追加　({sector_etf[1]})", value=True):
                compare_tickers.append(sector_etf)
        else:
            st.caption("業種別ETF: 対応なし（Sector17コード未取得）")

        # 規模別ETF
        if scale_etf:
            if st.checkbox(f"規模別ETFを追加　({scale_etf[1]})", value=False):
                compare_tickers.append(scale_etf)
        elif scale_cat:
            st.caption(f"規模別ETF: {scale_cat} は現時点で対応なし")

        # JPXプライム150・JPX日経400 ETF（構成銘柄の場合のみ表示）
        for idx_name in memberships:
            etf = INDEX_ETF.get(idx_name)
            if etf and st.checkbox(f"{idx_name} ETFを追加　({etf[1]})", value=False):
                compare_tickers.append(etf)

    st.divider()

    # 表示期間・足種
    st.subheader("初期表示期間")
    period_label = st.select_slider(
        "期間",
        options=list(PERIOD_OPTIONS.keys()),
        value="1年",
        label_visibility="collapsed",
    )
    # データは常に最大期間で取得し、チャート内ボタンで自由に切替可能にする
    period = "max"

    interval_label = st.radio(
        "足種",
        list(INTERVAL_OPTIONS.keys()),
        index=0,
        horizontal=True,
    )
    interval = INTERVAL_OPTIONS[interval_label]

    # テクニカル指標（通常モードのみ）
    if not compare_mode:
        st.divider()
        st.subheader("テクニカル指標")
        show_ma   = st.checkbox("移動平均 MA(5/20/75)", value=True)
        show_bb   = st.checkbox("ボリンジャーバンド (±2σ)", value=False)
        show_rsi  = st.checkbox("RSI (14)", value=False)
        show_macd = st.checkbox("MACD (12,26,9)", value=False)

    else:
        show_ma = show_bb = show_rsi = show_macd = False

    # ファンダメンタル分析（比較モード非依存）
    st.divider()
    show_fundamental = st.toggle("ファンダメンタル分析", value=False,
                                 help="売上・営業利益・PER・PBRの推移を表示")

# ---------------------------------------------------------------- データ取得 --
st.header(f"{main_name}　`{main_ticker}`　｜　{period_label} {interval_label}")

with st.spinner("データ取得中..."):
    main_df = fetch_ohlcv(main_ticker, period, interval)

if main_df.empty:
    st.error(f"データを取得できませんでした: **{main_ticker}**\n\n"
             "銘柄コードまたはティッカーが正しいか確認してください。")
    st.stop()

# ---------------------------------------------------------------- メトリクス --
if not compare_mode:
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    latest = main_df.iloc[-1]
    prev   = main_df.iloc[-2] if len(main_df) > 1 else latest

    close_now  = float(latest["Close"])
    close_prev = float(prev["Close"])
    change     = close_now - close_prev
    change_pct = change / close_prev * 100 if close_prev else 0

    shares = fetch_shares_outstanding(main_ticker)
    if shares:
        mktcap_oku = close_now * shares / 1e8
        if mktcap_oku >= 10000:
            mktcap_str = f"{mktcap_oku / 10000:,.0f} 兆円"
        else:
            mktcap_str = f"{mktcap_oku:,.0f} 億円"
    else:
        mktcap_str = "-"

    col1.metric("現在値",   f"¥{close_now:,.0f}", f"{change:+.0f}  ({change_pct:+.2f}%)")
    col2.metric("高値",     f"¥{float(latest['High']):,.0f}")
    col3.metric("安値",     f"¥{float(latest['Low']):,.0f}")
    col4.metric("出来高",   f"{float(latest['Volume']):,.0f}")
    col5.metric("時価総額", mktcap_str)
    col6.metric("データ件数", f"{len(main_df):,} 本")

# ---------------------------------------------------------------- チャート --
if compare_mode:
    all_dfs: dict[str, pd.DataFrame] = {main_name: main_df}
    for ticker, name in compare_tickers:
        with st.spinner(f"{name} 取得中..."):
            df = fetch_ohlcv(ticker, period, interval)
        if not df.empty:
            all_dfs[name] = df
        else:
            st.warning(f"{name} ({ticker}) のデータを取得できませんでした。")

    if len(all_dfs) < 2:
        st.info("比較対象を1つ以上選択してください。")

    fig = build_comparison_chart(all_dfs, period_label=period_label)
    st.caption(f"起点（期間開始日）を 0% として正規化したリターン率の推移")
else:
    fig = build_candlestick_chart(
        main_df, main_name,
        period_label=period_label,
        show_ma=show_ma,
        show_bb=show_bb,
        show_rsi=show_rsi,
        show_macd=show_macd,
    )

st.plotly_chart(fig, use_container_width=True, key=f"chart_{main_ticker}_{period_label}_{interval_label}")

# ---------------------------------------------------------------- 銘柄情報 --
if not compare_mode:
    row = stocks_df[stocks_df["DisplayCode"] == main_display]
    if not row.empty:
        r = row.iloc[0]
        info_cols = st.columns(4)
        info_cols[0].markdown(f"**市場**　{r.get('MarketCodeName', r.get('Badge', '-'))}")
        info_cols[1].markdown(f"**業種**　{r.get('Sector33CodeName', '-')}")
        info_cols[2].markdown(f"**規模**　{r.get('ScaleCategory', '-') or '-'}")
        info_cols[3].markdown(f"**ティッカー**　`{main_ticker}`")

    # 指数組入バッジ
    if memberships:
        badge_styles = {
            "JPXプライム150": "background:#1D4ED8;color:white",
            "JPX日経400":     "background:#065F46;color:white",
        }
        badges_html = " &nbsp;".join(
            f'<span style="{badge_styles.get(n, "background:#374151;color:white")};'
            f'padding:3px 10px;border-radius:4px;font-size:0.82rem;font-weight:600">'
            f'✓ {n}</span>'
            for n in memberships
        )
        st.markdown(badges_html, unsafe_allow_html=True)

    st.caption(
        f"データソース: Yahoo Finance (yfinance) ｜ "
        f"銘柄リスト: J-Quants API V2 ｜ "
        f"最終取得: {main_df.index[-1].strftime('%Y-%m-%d') if not main_df.empty else '-'}"
    )

# ---------------------------------------------------------------- ファンダメンタル --
if show_fundamental:
    st.subheader("ファンダメンタル分析")
    with st.spinner("財務データ取得中..."):
        fund = fetch_fundamentals(main_ticker)

    annual_df    = fund["annual_df"]
    quarterly_df = fund["quarterly_df"]

    if annual_df.empty and quarterly_df.empty:
        st.warning("財務データを取得できませんでした。")
    else:
        fund_fig = build_fundamental_chart(fund, main_df, main_name)
        st.plotly_chart(fund_fig, use_container_width=True,
                        key=f"fundamental_{main_ticker}")

        # データテーブル（展開式）
        with st.expander("財務データ（数値）"):
            col_a, col_q = st.columns(2)
            with col_a:
                st.caption("年次")
                show_cols = [c for c in ["Revenue", "OperatingIncome", "EPS", "Price", "PER"]
                             if c in annual_df.columns]
                if show_cols:
                    unit = fund["unit"]
                    divisor = 1e12 if unit == "兆円" else 1e8
                    disp = annual_df[show_cols].copy()
                    for c in ["Revenue", "OperatingIncome"]:
                        if c in disp.columns:
                            disp[c] = (disp[c] / divisor).map(lambda x: f"{x:,.2f}" if pd.notna(x) else "-")
                    for c in ["EPS", "Price"]:
                        if c in disp.columns:
                            disp[c] = disp[c].map(lambda x: f"{x:,.1f}" if pd.notna(x) else "-")
                    if "PER" in disp.columns:
                        disp["PER"] = disp["PER"].map(lambda x: f"{x:.1f}倍" if pd.notna(x) else "-")
                    disp.index = disp.index.strftime("%Y/%m")
                    st.dataframe(disp, use_container_width=True)
            with col_q:
                st.caption("四半期")
                show_cols_q = [c for c in ["PER", "PBR", "BPS", "Price"]
                               if c in quarterly_df.columns]
                if show_cols_q:
                    disp_q = quarterly_df[show_cols_q].copy()
                    for c in ["PER"]:
                        if c in disp_q.columns:
                            disp_q[c] = disp_q[c].map(lambda x: f"{x:.1f}倍" if pd.notna(x) else "-")
                    for c in ["PBR"]:
                        if c in disp_q.columns:
                            disp_q[c] = disp_q[c].map(lambda x: f"{x:.2f}倍" if pd.notna(x) else "-")
                    for c in ["BPS", "Price"]:
                        if c in disp_q.columns:
                            disp_q[c] = disp_q[c].map(lambda x: f"{x:,.0f}" if pd.notna(x) else "-")
                    disp_q.index = disp_q.index.strftime("%Y/%m")
                    st.dataframe(disp_q, use_container_width=True)
