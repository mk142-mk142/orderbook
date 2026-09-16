from __future__ import annotations
from abc import ABC, abstractmethod
from typing import AsyncIterator
from ..models import OrderBook


class OrderbookFeed(ABC):
    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def subscribe(self, symbols: list[str]) -> None: ...

    @abstractmethod
    def stream(self) -> AsyncIterator[OrderBook]: ...

    @abstractmethod
    async def close(self) -> None: ...

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *exc):
        await self.close()