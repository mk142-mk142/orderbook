# tests/__init__.py
# пустой

# tests/test_models.py
from orderbook.models import OrderBook


def test_serialization_roundtrip():
    book = OrderBook(
        exchange="bybit",
        symbol="BTCUSDT",
        ts_local=123.45,
        ts_exchange=123456,
        bids=[(100.0, 1.5), (99.5, 2.0)],
        asks=[(100.5, 1.0), (101.0, 3.0)],
        depth=2,
        is_snapshot=True,
        seq=42,
    )
    line = book.to_jsonl_line()
    restored = OrderBook.from_jsonl_line(line)
    assert restored == book