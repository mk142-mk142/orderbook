from __future__ import annotations
import asyncio
import json
import logging
import time
from typing import AsyncIterator, Optional

import websockets
from websockets.exceptions import ConnectionClosed

from ..models import OrderBook
from .base import OrderbookFeed

log = logging.getLogger(__name__)

WS_URL = "wss://stream.bybit.com/v5/public/linear"
PING_INTERVAL = 20.0
RECONNECT_MIN = 1.0
RECONNECT_MAX = 30.0
SUBSCRIBE_CHUNK = 10


class BybitFeed(OrderbookFeed):
    def __init__(self, depth: int = 50):
        assert depth in (1, 50, 200, 500), "Bybit v5 supports 1/50/200/500"
        self.depth = depth
        self.symbols: list[str] = []
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._books: dict[str, dict] = {}
        self._queue: asyncio.Queue[OrderBook] = asyncio.Queue(maxsize=10_000)
        self._stop = asyncio.Event()

    async def connect(self) -> None:
        self._ws = await websockets.connect(
            WS_URL,
            ping_interval=None,
            ping_timeout=None,
            max_size=2 ** 22,
        )
        log.info("WS connected: %s", WS_URL)

    async def subscribe(self, symbols: list[str]) -> None:
        self.symbols = [s.upper() for s in symbols]
        topics = [f"orderbook.{self.depth}.{s}" for s in self.symbols]
        for i in range(0, len(topics), SUBSCRIBE_CHUNK):
            chunk = topics[i : i + SUBSCRIBE_CHUNK]
            await self._ws.send(json.dumps({"op": "subscribe", "args": chunk}))
            log.info("Subscribed: %s", chunk)

    async def stream(self) -> AsyncIterator[OrderBook]:
        reader = asyncio.create_task(self._reader_loop(), name="bybit-reader")
        pinger = asyncio.create_task(self._ping_loop(), name="bybit-pinger")
        try:
            while not self._stop.is_set():
                book = await self._queue.get()
                yield book
        finally:
            for t in (reader, pinger):
                t.cancel()
            await asyncio.gather(reader, pinger, return_exceptions=True)

    async def close(self) -> None:
        self._stop.set()
        if self._ws is not None:
            await self._ws.close()

    async def _ping_loop(self) -> None:
        try:
            while not self._stop.is_set():
                await asyncio.sleep(PING_INTERVAL)
                if self._ws is not None:
                    await self._ws.send(json.dumps({"op": "ping"}))
        except asyncio.CancelledError:
            raise

    async def _reader_loop(self) -> None:
        backoff = RECONNECT_MIN
        while not self._stop.is_set():
            try:
                async for raw in self._ws:
                    await self._handle_raw(raw)
                backoff = RECONNECT_MIN
            except ConnectionClosed as e:
                log.warning("WS closed: %s", e)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Reader loop error")

            if self._stop.is_set():
                return
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, RECONNECT_MAX)
            try:
                await self.connect()
                await self.subscribe(self.symbols)
                backoff = RECONNECT_MIN
            except Exception:
                log.exception("Reconnect failed")

    async def _handle_raw(self, raw: str) -> None:
        msg = json.loads(raw)
        topic = msg.get("topic")
        if not topic or not topic.startswith(f"orderbook.{self.depth}."):
            return
        data = msg["data"]
        book = self._apply(
            symbol=data["s"],
            mtype=msg["type"],
            ts_exchange=msg["ts"],
            data=data,
        )
        try:
            self._queue.put_nowait(book)
        except asyncio.QueueFull:
            log.warning("Queue full, dropped %s", book.symbol)

    def _apply(self, symbol: str, mtype: str, ts_exchange: int, data: dict) -> OrderBook:
        if mtype == "snapshot" or symbol not in self._books:
            state = {
                "bids": {float(p): float(s) for p, s in data["b"]},
                "asks": {float(p): float(s) for p, s in data["a"]},
                "seq": data.get("u"),
            }
            self._books[symbol] = state
        else:
            state = self._books[symbol]
            for key, side in (("b", "bids"), ("a", "asks")):
                for p, s in data[key]:
                    pf, sf = float(p), float(s)
                    if sf == 0:
                        state[side].pop(pf, None)
                    else:
                        state[side][pf] = sf
            state["seq"] = data.get("u")

        bids = sorted(state["bids"].items(), key=lambda x: -x[0])[: self.depth]
        asks = sorted(state["asks"].items(), key=lambda x: x[0])[: self.depth]

        return OrderBook(
            exchange="bybit",
            symbol=symbol,
            ts_local=time.time(),
            ts_exchange=ts_exchange,
            bids=bids,
            asks=asks,
            depth=len(bids),
            is_snapshot=(mtype == "snapshot"),
            seq=state["seq"],
        )