from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class OrderBook:
    exchange: str
    symbol: str
    ts_local: float
    ts_exchange: int
    bids: list[tuple[float, float]]
    asks: list[tuple[float, float]]
    depth: int
    is_snapshot: bool
    seq: Optional[int] = None

    @property
    def best_bid(self) -> Optional[float]:
        return self.bids[0][0] if self.bids else None

    @property
    def best_ask(self) -> Optional[float]:
        return self.asks[0][0] if self.asks else None

    @property
    def mid(self) -> Optional[float]:
        bb, ba = self.best_bid, self.best_ask
        return (bb + ba) / 2 if bb is not None and ba is not None else None

    @property
    def spread(self) -> Optional[float]:
        bb, ba = self.best_bid, self.best_ask
        return ba - bb if bb is not None and ba is not None else None

    @property
    def spread_pct(self) -> Optional[float]:
        s, m = self.spread, self.mid
        return s / m * 100 if s is not None and m else None

    def to_jsonl_line(self) -> str:
        return json.dumps(
            {
                "exchange": self.exchange,
                "symbol": self.symbol,
                "ts_local": self.ts_local,
                "ts_exchange": self.ts_exchange,
                "bids": self.bids,
                "asks": self.asks,
                "depth": self.depth,
                "is_snapshot": self.is_snapshot,
                "seq": self.seq,
            },
            separators=(",", ":"),
        )

    @classmethod
    def from_jsonl_line(cls, line: str) -> "OrderBook":
        d = json.loads(line)
        d["bids"] = [tuple(x) for x in d["bids"]]
        d["asks"] = [tuple(x) for x in d["asks"]]
        return cls(**d)