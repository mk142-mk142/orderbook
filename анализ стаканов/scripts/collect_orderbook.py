from __future__ import annotations
import argparse
import asyncio
import logging
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from orderbook.exchanges.bybit import BybitFeed
from orderbook.pipeline import run_collector


def _default_output(symbols: list[str]) -> str:
    date = time.strftime("%Y-%m-%d")
    tag = symbols[0] if len(symbols) == 1 else f"{len(symbols)}symbols"
    return f"data/raw/bybit/{tag}_{date}.jsonl"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", required=True)
    ap.add_argument("--output", default=None)
    ap.add_argument("--depth", type=int, default=50, choices=[1, 50, 200, 500])
    ap.add_argument("--duration", type=float, default=None)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    output = args.output or _default_output(symbols)

    feed = BybitFeed(depth=args.depth)

    async def _run() -> None:
        coro = run_collector(feed, symbols, output)
        if args.duration:
            try:
                await asyncio.wait_for(coro, timeout=args.duration)
            except asyncio.TimeoutError:
                logging.info("Duration reached, stopping")
        else:
            await coro

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logging.info("Interrupted by user")


if __name__ == "__main__":
    main()