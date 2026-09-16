from __future__ import annotations
import asyncio
import logging
from .exchanges.base import OrderbookFeed
from .models import OrderBook
from .store import append_batch

log = logging.getLogger(__name__)


async def run_collector(
    feed: OrderbookFeed,
    symbols: list[str],
    output_path: str,
    batch_size: int = 100,
    flush_interval: float = 1.0,
) -> None:
    queue: asyncio.Queue[OrderBook | None] = asyncio.Queue(
        maxsize=200 * max(len(symbols), 1)
    )
    stats = {"received": 0, "written": 0, "dropped": 0}

    async def writer() -> None:
        batch: list[OrderBook] = []
        while True:
            try:
                book = await asyncio.wait_for(queue.get(), timeout=flush_interval)
            except asyncio.TimeoutError:
                if batch:
                    append_batch(output_path, batch)
                    stats["written"] += len(batch)
                    batch.clear()
                continue
            if book is None:
                if batch:
                    append_batch(output_path, batch)
                    stats["written"] += len(batch)
                return
            batch.append(book)
            if len(batch) >= batch_size:
                append_batch(output_path, batch)
                stats["written"] += len(batch)
                batch.clear()

    writer_task = asyncio.create_task(writer(), name="orderbook-writer")

    try:
        async with feed:
            await feed.subscribe(symbols)
            async for book in feed.stream():
                stats["received"] += 1
                try:
                    queue.put_nowait(book)
                except asyncio.QueueFull:
                    stats["dropped"] += 1
    finally:
        try:
            queue.put_nowait(None)
        except asyncio.QueueFull:
            pass
        try:
            await asyncio.wait_for(writer_task, timeout=5.0)
        except asyncio.TimeoutError:
            writer_task.cancel()
        log.info("Collector stats: %s", stats)