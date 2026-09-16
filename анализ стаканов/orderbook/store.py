from __future__ import annotations
from pathlib import Path
from typing import Iterator
from .models import OrderBook


def append_batch(path: str | Path, books: list[OrderBook]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        for b in books:
            f.write(b.to_jsonl_line())
            f.write("\n")


def read_range(
    path: str | Path,
    ts_start: float | None = None,
    ts_end: float | None = None,
) -> Iterator[OrderBook]:
    with open(path, encoding="utf-8") as f:
        for line in f:
            b = OrderBook.from_jsonl_line(line)
            if ts_start is not None and b.ts_local < ts_start:
                continue
            if ts_end is not None and b.ts_local > ts_end:
                break
            yield b