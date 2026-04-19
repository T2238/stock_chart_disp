"""
Plotly チャート生成モジュール
"""
from datetime import timedelta

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from indicators import calc_ma, calc_bollinger, calc_rsi, calc_macd
from config import MA_CONFIGS

# サイドバーの期間ラベル → 初期表示の遡り日数
_PERIOD_DAYS: dict[str, int | None] = {
    "1ヶ月":  31,
    "3ヶ月":  92,
    "6ヶ月":  183,
    "1年":    365,
    "3年":    365 * 3,
    "5年":    365 * 5,
    "10年":   365 * 10,
    "最大":   None,
}


def _xrange(index: pd.Index, period_label: str) -> list[str] | None:
    """Plotly の初期 x 軸範囲 [start, end] を返す。最大の場合は None。"""
    days = _PERIOD_DAYS.get(period_label)
    if days is None:
        return None
    end   = index[-1]
    start = end - timedelta(days=days)
    return [str(start.date()), str(end.date())]

# 陽線: 赤、陰線: 青（日本標準）
COLOR_UP   = "#EF4444"
COLOR_DOWN = "#3B82F6"
COLOR_GRID = "rgba(255,255,255,0.05)"

COMPARISON_COLORS = ["#EF4444", "#3B82F6", "#10B981", "#F59E0B", "#8B5CF6", "#EC4899"]

RANGE_BUTTONS = [
    dict(count=1,  label="1M",  step="month", stepmode="backward"),
    dict(count=3,  label="3M",  step="month", stepmode="backward"),
    dict(count=6,  label="6M",  step="month", stepmode="backward"),
    dict(count=1,  label="1Y",  step="year",  stepmode="backward"),
    dict(count=3,  label="3Y",  step="year",  stepmode="backward"),
    dict(count=5,  label="5Y",  step="year",  stepmode="backward"),
    dict(count=10, label="10Y", step="year",  stepmode="backward"),
    dict(step="all", label="Max"),
]


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    """yfinance が MultiIndex を返す場合に対応"""
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.droplevel(1)
    return df


def _ohlcv(df: pd.DataFrame):
    df = _normalize_df(df)
    return (
        df["Open"].squeeze(),
        df["High"].squeeze(),
        df["Low"].squeeze(),
        df["Close"].squeeze(),
        df["Volume"].squeeze(),
    )


def _bar_colors(open_s: pd.Series, close_s: pd.Series) -> list[str]:
    return [COLOR_UP if float(c) >= float(o) else COLOR_DOWN
            for o, c in zip(open_s, close_s)]


def build_candlestick_chart(
    df: pd.DataFrame,
    name: str,
    period_label: str = "1年",
    show_ma: bool = True,
    show_bb: bool = False,
    show_rsi: bool = False,
    show_macd: bool = False,
) -> go.Figure:
    open_s, high_s, low_s, close_s, vol_s = _ohlcv(df)

    # サブプロット構成
    row_map: dict[str, int] = {"main": 1, "volume": 2}
    row_heights = [400, 80]

    if show_rsi:
        row_map["rsi"] = len(row_map) + 1
        row_heights.append(100)
    if show_macd:
        row_map["macd"] = len(row_map) + 1
        row_heights.append(100)

    total = sum(row_heights)
    rel_heights = [h / total for h in row_heights]
    fig_height = min(900, 500 + 100 * (len(row_map) - 2))

    fig = make_subplots(
        rows=len(row_map),
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=rel_heights,
    )

    # ローソク足
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=open_s, high=high_s, low=low_s, close=close_s,
        name=name,
        increasing_line_color=COLOR_UP,
        decreasing_line_color=COLOR_DOWN,
        increasing_fillcolor=COLOR_UP,
        decreasing_fillcolor=COLOR_DOWN,
        hovertext=name,
    ), row=1, col=1)

    # 移動平均線
    if show_ma:
        for window, color, label in MA_CONFIGS:
            if len(close_s) >= window:
                ma = calc_ma(close_s, window)
                fig.add_trace(go.Scatter(
                    x=df.index, y=ma,
                    name=label,
                    line=dict(color=color, width=1.2),
                    hovertemplate=f"{label}: %{{y:,.0f}}<extra></extra>",
                ), row=1, col=1)

    # ボリンジャーバンド
    if show_bb and len(close_s) >= 20:
        upper, middle, lower, _ = calc_bollinger(close_s)
        fig.add_trace(go.Scatter(
            x=df.index, y=upper,
            name="BB+2σ",
            line=dict(color="rgba(148,163,184,0.6)", width=1, dash="dot"),
            showlegend=False,
            hovertemplate="BB上限: %{y:,.0f}<extra></extra>",
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=lower,
            name="BB-2σ",
            line=dict(color="rgba(148,163,184,0.6)", width=1, dash="dot"),
            fill="tonexty",
            fillcolor="rgba(148,163,184,0.08)",
            showlegend=False,
            hovertemplate="BB下限: %{y:,.0f}<extra></extra>",
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=middle,
            name="BB中央",
            line=dict(color="rgba(148,163,184,0.4)", width=1),
            showlegend=False,
        ), row=1, col=1)

    # 出来高
    fig.add_trace(go.Bar(
        x=df.index,
        y=vol_s,
        name="出来高",
        marker_color=_bar_colors(open_s, close_s),
        showlegend=False,
        hovertemplate="出来高: %{y:,.0f}<extra></extra>",
    ), row=row_map["volume"], col=1)

    # RSI
    if show_rsi and len(close_s) >= 14:
        rsi = calc_rsi(close_s)
        fig.add_trace(go.Scatter(
            x=df.index, y=rsi,
            name="RSI(14)",
            line=dict(color="#F59E0B", width=1.5),
            hovertemplate="RSI: %{y:.1f}<extra></extra>",
        ), row=row_map["rsi"], col=1)
        fig.add_hrect(y0=70, y1=100, fillcolor="rgba(239,68,68,0.06)",
                      line_width=0, row=row_map["rsi"], col=1)
        fig.add_hrect(y0=0, y1=30, fillcolor="rgba(59,130,246,0.06)",
                      line_width=0, row=row_map["rsi"], col=1)
        for level, color in [(70, "rgba(239,68,68,0.4)"), (30, "rgba(59,130,246,0.4)")]:
            fig.add_hline(y=level, line_dash="dash", line_color=color,
                          line_width=1, row=row_map["rsi"], col=1)
        fig.update_yaxes(title_text="RSI", range=[0, 100],
                         row=row_map["rsi"], col=1)

    # MACD
    if show_macd and len(close_s) >= 26:
        macd, sig, hist = calc_macd(close_s)
        hist_colors = [COLOR_UP if v >= 0 else COLOR_DOWN for v in hist]
        fig.add_trace(go.Bar(
            x=df.index, y=hist,
            name="ヒスト",
            marker_color=hist_colors,
            showlegend=False,
            hovertemplate="ヒスト: %{y:.2f}<extra></extra>",
        ), row=row_map["macd"], col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=macd,
            name="MACD",
            line=dict(color="#F59E0B", width=1.5),
            hovertemplate="MACD: %{y:.2f}<extra></extra>",
        ), row=row_map["macd"], col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=sig,
            name="Signal",
            line=dict(color="#8B5CF6", width=1.5),
            hovertemplate="Signal: %{y:.2f}<extra></extra>",
        ), row=row_map["macd"], col=1)
        fig.update_yaxes(title_text="MACD", row=row_map["macd"], col=1)

    # レイアウト共通設定
    fig.update_layout(
        height=fig_height,
        template="plotly_dark",
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        legend=dict(
            orientation="v", yanchor="bottom", y=0.02,
            xanchor="right", x=0.99,
            bgcolor="rgba(15,23,42,0.75)",
            bordercolor="rgba(255,255,255,0.1)",
            borderwidth=1,
        ),
        margin=dict(l=70, r=20, t=50, b=20),
    )

    # レンジセレクタをチャート上部（row=1）に配置
    fig.update_xaxes(
        rangeselector=dict(
            buttons=RANGE_BUTTONS,
            bgcolor="#1F2937",
            activecolor="#374151",
        ),
        gridcolor=COLOR_GRID,
        row=1, col=1,
    )
    for i in range(2, len(row_map) + 1):
        fig.update_xaxes(gridcolor=COLOR_GRID, showticklabels=(i == len(row_map)),
                         row=i, col=1)

    # 初期表示範囲: row/col 指定なしで全 x 軸（アンカー含む）に一括適用
    xr = _xrange(df.index, period_label)
    if xr:
        fig.update_xaxes(range=xr)

    fig.update_yaxes(title_text="株価 (¥)", tickformat=",", gridcolor=COLOR_GRID,
                     row=1, col=1)
    fig.update_yaxes(title_text="出来高", gridcolor=COLOR_GRID,
                     row=row_map["volume"], col=1)

    return fig


def build_comparison_chart(dfs: dict[str, pd.DataFrame], period_label: str = "1年") -> go.Figure:
    """複数銘柄・指数のリターン率比較チャート（起点=0%）"""
    fig = go.Figure()

    for (name, df), color in zip(dfs.items(), COMPARISON_COLORS):
        if df is None or df.empty:
            continue
        df = _normalize_df(df)
        close = df["Close"].squeeze().dropna()
        if close.empty:
            continue
        base = float(close.iloc[0])
        if base == 0:
            continue
        returns = (close / base - 1) * 100
        formatted = returns.apply(lambda v: f"{v:+.1f}")
        fig.add_trace(go.Scatter(
            x=close.index,
            y=returns,
            name=name,
            customdata=formatted,
            line=dict(color=color, width=2),
            hovertemplate=f"{name}: %{{customdata}}%<extra></extra>",
        ))

    fig.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.25)", line_width=1)

    fig.update_layout(
        height=600,
        template="plotly_dark",
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        yaxis_title="リターン率 (%)",
        yaxis_tickformat="+.1f",
        hovermode="x unified",
        legend=dict(
            orientation="v", yanchor="bottom", y=0.02,
            xanchor="right", x=0.99,
            bgcolor="rgba(15,23,42,0.75)",
            bordercolor="rgba(255,255,255,0.1)",
            borderwidth=1,
        ),
        margin=dict(l=70, r=20, t=80, b=20),
        xaxis=dict(
            rangeselector=dict(
                buttons=RANGE_BUTTONS,
                bgcolor="#1F2937",
                activecolor="#374151",
            ),
            gridcolor=COLOR_GRID,
        ),
        yaxis=dict(gridcolor=COLOR_GRID),
    )

    # 初期表示範囲を layout.xaxis.range に直接設定
    first_df = next((df for df in dfs.values() if df is not None and not df.empty), None)
    if first_df is not None:
        idx = _normalize_df(first_df)["Close"].squeeze().dropna().index
        xr = _xrange(idx, period_label)
        if xr:
            fig.update_layout(xaxis_range=xr)

    return fig


# ---------------------------------------------------------------- ファンダメンタル --

def build_fundamental_chart(
    fundamentals: dict,
    price_df: pd.DataFrame,
    name: str,
) -> go.Figure:
    """
    3段構成のファンダメンタルチャートを返す。
      Row1: 株価（折れ線）+ 決算期末の縦線
      Row2: 売上・営業利益（年次棒グラフ）
      Row3: PER（折れ線）+ PBR（折れ線、右軸）
    """
    annual_df    = fundamentals["annual_df"]
    quarterly_df = fundamentals["quarterly_df"]
    unit         = fundamentals["unit"]

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=False,
        vertical_spacing=0.08,
        row_heights=[0.35, 0.35, 0.30],
        subplot_titles=["株価推移（決算期末●）", f"売上・営業利益（年次 / {unit}）", "PER・PBR（四半期）"],
    )

    # ---- Row1: 株価折れ線 ----
    price_close = _normalize_df(price_df)["Close"].squeeze().dropna()
    # 財務データのある期間に絞る
    if not annual_df.empty:
        start = annual_df.index.min() - pd.Timedelta(days=90)
        price_close = price_close[price_close.index >= start]

    fig.add_trace(go.Scatter(
        x=price_close.index, y=price_close,
        name="株価",
        line=dict(color="#94A3B8", width=1.5),
        hovertemplate="株価: ¥%{y:,.0f}<extra></extra>",
    ), row=1, col=1)

    # 決算期末に縦線マーカー
    for d in annual_df.index:
        fig.add_vline(
            x=d.timestamp() * 1000,
            line=dict(color="rgba(251,191,36,0.4)", width=1, dash="dot"),
            row=1, col=1,
        )
    # 決算期末の株価をマーカーで表示
    prices_at_term = annual_df["Price"].dropna()
    fig.add_trace(go.Scatter(
        x=prices_at_term.index, y=prices_at_term,
        name="決算期末株価",
        mode="markers",
        marker=dict(color="#FBBF24", size=8, symbol="circle"),
        hovertemplate="決算期末: ¥%{y:,.0f}<extra></extra>",
    ), row=1, col=1)

    # ---- Row2: 売上・営業利益（年次棒グラフ）----
    divisor = 1e12 if unit == "兆円" else 1e8

    if "Revenue" in annual_df.columns:
        rev = annual_df["Revenue"].dropna() / divisor
        fig.add_trace(go.Bar(
            x=rev.index.strftime("%Y/%m"),
            y=rev,
            name=f"売上（{unit}）",
            marker_color="rgba(59,130,246,0.7)",
            hovertemplate=f"売上: %{{y:,.2f}}{unit}<extra></extra>",
        ), row=2, col=1)

    if "OperatingIncome" in annual_df.columns:
        opi = annual_df["OperatingIncome"].dropna() / divisor
        fig.add_trace(go.Bar(
            x=opi.index.strftime("%Y/%m"),
            y=opi,
            name=f"営業利益（{unit}）",
            marker_color="rgba(16,185,129,0.8)",
            hovertemplate=f"営業利益: %{{y:,.2f}}{unit}<extra></extra>",
        ), row=2, col=1)

    # ---- Row3: PER・PBR（四半期折れ線）----
    per_src = quarterly_df if ("PER" in quarterly_df.columns and not quarterly_df["PER"].dropna().empty) \
              else annual_df

    if "PER" in per_src.columns:
        per = per_src["PER"].dropna()
        fig.add_trace(go.Scatter(
            x=per.index, y=per,
            name="PER（倍）",
            line=dict(color="#EF4444", width=2),
            hovertemplate="PER: %{y:.1f}倍<extra></extra>",
        ), row=3, col=1)

    if "PBR" in quarterly_df.columns:
        pbr = quarterly_df["PBR"].dropna()
        fig.add_trace(go.Scatter(
            x=pbr.index, y=pbr,
            name="PBR（倍）",
            line=dict(color="#3B82F6", width=2, dash="dot"),
            yaxis="y6",
            hovertemplate="PBR: %{y:.2f}倍<extra></extra>",
        ), row=3, col=1)
        # PBR 用の右 y 軸を追加
        fig.update_layout(
            yaxis6=dict(
                title="PBR（倍）",
                overlaying="y5",
                side="right",
                showgrid=False,
                color="#3B82F6",
            )
        )

    # ---- 共通レイアウト ----
    fig.update_layout(
        height=750,
        template="plotly_dark",
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        barmode="group",
        hovermode="x unified",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="left", x=0, bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(l=70, r=70, t=80, b=20),
    )
    fig.update_yaxes(gridcolor=COLOR_GRID)
    fig.update_yaxes(title_text="株価（¥）", tickformat=",", row=1, col=1)
    fig.update_yaxes(title_text=unit, row=2, col=1)
    fig.update_yaxes(title_text="PER（倍）", color="#EF4444", row=3, col=1)

    return fig
