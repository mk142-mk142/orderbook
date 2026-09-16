from __future__ import annotations
import plotly.graph_objects as go
from .models import OrderBook


# Цвета как в TigerTrade / биржевых терминалах
GREEN = "#26a69a"   # bids
RED = "#ef5350"     # asks
BG = "#131722"      # тёмный фон
GRID = "#2a2e39"
TEXT = "#d1d4dc"


def plot_ladder(book: OrderBook, max_levels: int = 25) -> go.Figure:
    """
    Вертикальная лестница: цена сверху вниз, длина полосы = объём.
    Как в TigerTrade: центр — spread, сверху — asks, снизу — bids.
    """
    # Берём топ-N уровней, чтобы не рисовать 50 строк
    bids = book.bids[:max_levels]
    asks = book.asks[:max_levels]

    # Показываем сверху asks (от дальних к ближним), снизу bids (от ближних к дальним).
    # По оси Y — цена как число (для корректного масштаба).
    ask_prices = [p for p, _ in asks][::-1]   # дальний ask -> ближний ask
    ask_sizes = [s for _, s in asks][::-1]
    bid_prices = [p for p, _ in bids]
    bid_sizes = [s for _, s in bids]

    fig = go.Figure()

    # Asks — красные, "вытянуты" влево от центральной линии цены
    fig.add_trace(go.Bar(
        y=ask_prices,
        x=ask_sizes,
        orientation="h",
        marker=dict(color=RED, line=dict(width=0)),
        name="Asks",
        hovertemplate="Ask %{y}<br>Size: %{x:.3f}<extra></extra>",
    ))

    # Bids — зелёные
    fig.add_trace(go.Bar(
        y=bid_prices,
        x=bid_sizes,
        orientation="h",
        marker=dict(color=GREEN, line=dict(width=0)),
        name="Bids",
        hovertemplate="Bid %{y}<br>Size: %{x:.3f}<extra></extra>",
    ))

    # Линия mid price — как в TigerTrade по центру
    if book.mid is not None:
        fig.add_hline(
            y=book.mid,
            line=dict(color="#ffd54f", width=2, dash="dash"),
            annotation_text=f"Mid {book.mid:.2f}",
            annotation_position="right",
            annotation_font=dict(color="#ffd54f"),
        )

    # Заголовок с основной инфой
    spread_txt = f"{book.spread:.2f} ({book.spread_pct:.4f}%)" if book.spread is not None else "n/a"
    title = (
        f"{book.symbol}  ·  {book.exchange}<br>"
        f"<sub>Mid: {book.mid}  ·  Spread: {spread_txt}  ·  "
        f"Seq: {book.seq}  ·  Snapshot: {book.is_snapshot}</sub>"
    )

    fig.update_layout(
        title=title,
        xaxis_title="Volume",
        yaxis_title="Price",
        template="plotly_dark",
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        font=dict(color=TEXT, family="Consolas, monospace"),
        bargap=0.15,
        height=800,
        margin=dict(l=80, r=120, t=100, b=60),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)

    return fig