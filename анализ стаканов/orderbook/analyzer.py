from __future__ import annotations
from .models import OrderBook


def spread(book: OrderBook) -> float | None:
    return book.spread


def imbalance(book: OrderBook, depth: int = 10) -> float:
    bid_vol = sum(size for _, size in book.bids[:depth])
    ask_vol = sum(size for _, size in book.asks[:depth])
    total = bid_vol + ask_vol
    if total == 0:
        return 0.0
    return (bid_vol - ask_vol) / total


def depth_at_pct(book: OrderBook, pct: float = 0.5) -> tuple[float, float]:
    if book.mid is None:
        return 0.0, 0.0
    threshold_bid = book.mid * (1 - pct / 100)
    threshold_ask = book.mid * (1 + pct / 100)

    bid_vol = sum(size for price, size in book.bids if price >= threshold_bid)
    ask_vol = sum(size for price, size in book.asks if price <= threshold_ask)
    return bid_vol, ask_vol


def detect_walls(book: OrderBook, sigma: float = 3.0) -> list[tuple[float, float, str]]:
    sizes = [s for _, s in book.bids] + [s for _, s in book.asks]
    if not sizes:
        return []
    avg = sum(sizes) / len(sizes)
    var = sum((s - avg) ** 2 for s in sizes) / len(sizes)
    std = var ** 0.5
    threshold = avg + sigma * std

    walls = []
    for price, size in book.bids:
        if size > threshold:
            walls.append((price, size, "bid"))
    for price, size in book.asks:
        if size > threshold:
            walls.append((price, size, "ask"))
    return walls