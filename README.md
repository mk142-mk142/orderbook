# orderbook
ob
# Order Book Collector & Ladder

A small toolkit for collecting order book data from crypto exchanges
over WebSocket, storing it locally, and visualizing it in a terminal-style
vertical ladder.

Currently supports **Bybit v5** (USDT perpetuals). The architecture is
designed so additional exchanges can be plugged in later.

## Features

- Async WebSocket client for Bybit v5 order book stream (snapshot + delta).
- Local order book maintained in memory, updated on every delta.
- Batch writer to JSONL with configurable flush interval.
- Vertical price ladder GUI with dynamic price aggregation.
- Pure-Python analyzer functions: spread, imbalance, depth, wall detection.
- Tests with fixtures, no live network required.

## Project structure

```
orderbook/
├── models.py            # OrderBook dataclass, serialization
├── store.py             # JSONL writer / reader
├── pipeline.py          # feed → queue → writer
├── analyzer.py          # pure functions: spread, imbalance, depth
└── exchanges/
    ├── base.py          # OrderbookFeed abstract interface
    └── bybit.py         # Bybit v5 implementation

scripts/
├── collect_orderbook.py # start a collection session
└── gui_orderbook.py     # play back or stream into the ladder GUI

tests/                   # pytest tests, no network required
```

## Requirements

- Python 3.10 or newer
- `websockets >= 12.0`
- `pytest` (for tests)

## Install

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

## Collect data

```bash
python scripts/collect_orderbook.py --symbols BTCUSDT,ETHUSDT,SOLUSDT --duration 60
```

Options:

- `--symbols` — comma-separated list of tickers (required).
- `--depth` — `1`, `50`, `200` or `500` (default `50`).
- `--duration` — stop after N seconds. Omit to run until interrupted.
- `--output` — override output path. Default: `data/raw/bybit/<tag>_<date>.jsonl`.
- `-v` / `--verbose` — debug logging.

The collector stores every update (snapshot and delta) as one JSON object
per line. Example of a single line:

```json
{"exchange":"bybit","symbol":"BTCUSDT","ts_local":1789546754.258,"ts_exchange":1789546754129,"bids":[[75460.0,1.199]],"asks":[[75460.1,4.782]],"depth":50,"is_snapshot":true,"seq":152562443}
```

## Visualize

Play back a recorded file:

```bash
python scripts/gui_orderbook.py data/raw/bybit/3symbols_2026-09-16.jsonl --symbol BTCUSDT
```

Or connect to the live stream directly:

```bash
python scripts/gui_orderbook.py --live BTCUSDT,SOLUSDT --symbol BTCUSDT
```

The window opens as a native Tkinter application. No browser, no external
runtime.

### GUI controls

- **Mouse wheel** — price aggregation. Each notch groups levels into
  wider buckets (`×1, ×2, ×5, ×10, ×20, ×50, ×100, ...`).
- **Shift + mouse wheel** — row height (zoom without changing aggregation).
- The header shows the current symbol, sequence number, aggregation step,
  and multiplier.

## Analyze

Pure functions in `orderbook/analyzer.py`, no I/O, easy to unit test:

- `spread(book)` — best ask minus best bid.
- `imbalance(book, depth=10)` — order book imbalance in `[-1, 1]`.
- `depth_at_pct(book, pct=0.5)` — total bid/ask volume within ±pct% of mid.
- `detect_walls(book, sigma=3.0)` — levels larger than `mean + sigma * std`.

## Tests

```bash
python -m pytest tests/ -v
```

Tests use stored fixtures and do not require network access.

## Design notes

- **Exchange abstraction.** `exchanges/base.py` defines an `OrderbookFeed`
  interface (`connect`, `subscribe`, `stream`, `close`). The pipeline only
  depends on this interface, not on Bybit specifics. Adding a new exchange
  means adding one file, not refactoring the pipeline.
- **Local book.** Bybit sends deltas; the feed maintains a local `dict`
  keyed by price and applies deltas before emitting an `OrderBook`.
- **Backpressure.** The reader uses `put_nowait` and drops on queue-full
  rather than blocking the socket. This keeps the connection alive under load.
- **Batching.** The writer accumulates up to `batch_size` records or flushes
  every `flush_interval` seconds, whichever comes first. Reduces syscalls
  by an order of magnitude compared to per-record writes.
- **Reconnect with backoff.** Exponential 1 → 2 → 4 → ... → 30 s. Resets
  on a successful re-subscribe.

## License

MIT
