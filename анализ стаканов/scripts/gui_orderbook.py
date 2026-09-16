from __future__ import annotations
import argparse
import asyncio
import math
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from queue import Queue, Empty

sys.path.insert(0, str(Path(__file__).parent.parent))

from orderbook.models import OrderBook
from orderbook.store import read_range


BG_MAIN    = "#0d1117"
BG_HEADER  = "#161b22"
FG_HEADER  = "#8b949e"
FG_TEXT    = "#ffffff"
COLOR_MID  = "#ffd54f"

MULTIPLIERS = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000]


class OrderbookLadderApp(tk.Tk):

    def __init__(self, source_path, live_symbols, symbol_filter=None):
        super().__init__()
        self.title("Orderbook Ladder")
        self.configure(bg=BG_MAIN)
        self.geometry("380x900")

        self.source_path = source_path
        self.live_symbols = live_symbols
        self.symbol_filter = symbol_filter

        self.queue = Queue(maxsize=200)
        self.current_book = None
        self.stats = {"received": 0, "dropped": 0}

        self.row_h = 15
        self.row_h_min = 10
        self.row_h_max = 30
        self.agg_level = 0

        self._base_tick = 0.0
        self._base_tick_symbol = None

        self._build_ui()
        self._start_source()
        self.after(20, self._tick)

    def _build_ui(self):
        header = tk.Frame(self, bg=BG_HEADER, height=24)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        self.lbl_symbol = tk.Label(
            header, text="—", bg=BG_HEADER, fg=FG_TEXT,
            font=("Consolas", 11, "bold"),
        )
        self.lbl_symbol.pack(side="left", padx=8)

        self.lbl_stats = tk.Label(
            header, text="", bg=BG_HEADER, fg=FG_HEADER,
            font=("Consolas", 8),
        )
        self.lbl_stats.pack(side="right", padx=8)

        cols = tk.Frame(self, bg=BG_HEADER)
        cols.pack(fill="x")

        tk.Label(
            cols, text="Size", bg=BG_HEADER, fg=FG_HEADER,
            font=("Consolas", 8, "bold"), anchor="w", width=10,
        ).pack(side="left", padx=(8, 0))

        tk.Label(
            cols, text="Price", bg=BG_HEADER, fg=FG_HEADER,
            font=("Consolas", 8, "bold"), anchor="e",
        ).pack(side="right", padx=(0, 8))

        self.canvas = tk.Canvas(self, bg=BG_MAIN, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        self.bind("<Configure>", lambda e: self._render())
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.bind("<MouseWheel>", self._on_wheel)

    def _on_wheel(self, event):
        step = int(event.delta / 120) if event.delta else 0
        if step == 0:
            return

        if event.state & 0x0001:
            new_h = self.row_h + step * 2
            new_h = max(self.row_h_min, min(self.row_h_max, new_h))
            if new_h != self.row_h:
                self.row_h = new_h
                self._render()
            return

        new_level = self.agg_level + step
        new_level = max(0, min(len(MULTIPLIERS) - 1, new_level))
        if new_level != self.agg_level:
            self.agg_level = new_level
            self._render()

    def _start_source(self):
        if self.source_path:
            threading.Thread(target=self._playback, daemon=True).start()
        elif self.live_symbols:
            threading.Thread(target=self._live, daemon=True).start()

    def _playback(self):
        prev_ts = None
        for book in read_range(self.source_path):
            if self.symbol_filter and book.symbol != self.symbol_filter:
                continue
            if prev_ts is not None:
                dt = book.ts_local - prev_ts
                if 0 < dt < 1.0:
                    time.sleep(dt)
            prev_ts = book.ts_local
            self._push(book)

    def _live(self):
        from orderbook.exchanges.bybit import BybitFeed

        async def _run():
            feed = BybitFeed(depth=50)
            async with feed:
                await feed.subscribe(self.live_symbols)
                async for book in feed.stream():
                    if self.symbol_filter and book.symbol != self.symbol_filter:
                        continue
                    self._push(book)

        try:
            asyncio.run(_run())
        except Exception as e:
            print(f"[live] error: {e}")

    def _push(self, book):
        self.stats["received"] += 1
        try:
            self.queue.put_nowait(book)
        except Exception:
            self.stats["dropped"] += 1

    def _tick(self):
        try:
            while True:
                self.current_book = self.queue.get_nowait()
        except Empty:
            pass

        if self.current_book is not None:
            self.lbl_symbol.config(text=self.current_book.symbol)
            self._ensure_base_tick(self.current_book)
            step = self._current_step()
            self.lbl_stats.config(
                text=f"seq={self.current_book.seq}  "
                     f"step={self._fmt_step(step)}  "
                     f"×{MULTIPLIERS[self.agg_level]}"
            )
            self._render()

        self.after(20, self._tick)

    def _ensure_base_tick(self, book):
        if self._base_tick_symbol == book.symbol and self._base_tick > 0:
            return
        self._base_tick = self._infer_base_tick(book)
        self._base_tick_symbol = book.symbol

    @staticmethod
    def _infer_base_tick(book):
        prices = [p for p, _ in book.bids[:40]] + [p for p, _ in book.asks[:40]]
        if len(prices) < 2:
            return 1e-4
        prices.sort()
        diffs = []
        for i in range(len(prices) - 1):
            d = prices[i + 1] - prices[i]
            if d > 1e-12:
                diffs.append(d)
        if not diffs:
            return 1e-4
        min_diff = min(diffs)
        k = round(math.log10(min_diff))
        tick = 10.0 ** k
        if tick <= 0:
            tick = 1e-4
        return tick

    def _current_step(self):
        return self._base_tick * MULTIPLIERS[self.agg_level]

    @staticmethod
    def _aggregate(levels, step, is_ask):
        buckets = {}
        for price, size in levels:
            if is_ask:
                key = math.ceil(price / step) * step
            else:
                key = math.floor(price / step) * step
            key = round(key, 12)
            buckets[key] = buckets.get(key, 0.0) + size

        if is_ask:
            return sorted(buckets.items(), key=lambda x: x[0])
        return sorted(buckets.items(), key=lambda x: -x[0])

    @staticmethod
    def _decimals_for_step(step):
        if step <= 0:
            return 4
        d = -int(math.floor(math.log10(step)))
        return max(0, min(d, 10))

    @staticmethod
    def _fmt_step(step):
        if step >= 1:
            return f"{step:.0f}"
        return f"{step:.10f}".rstrip("0").rstrip(".")

    def _render(self):
        c = self.canvas
        c.delete("all")
        book = self.current_book
        if book is None:
            return

        w = c.winfo_width()
        h = c.winfo_height()
        if w <= 1 or h <= 1:
            return

        self._ensure_base_tick(book)
        step = self._current_step()
        decimals = self._decimals_for_step(step)

        asks_agg = self._aggregate(book.asks, step, is_ask=True)
        bids_agg = self._aggregate(book.bids, step, is_ask=False)

        row_h = self.row_h
        mid_y = h // 2

        band_h = row_h
        half_band = band_h // 2
        top_of_band = mid_y - half_band
        bottom_of_band = mid_y + half_band

        usable_h = h - band_h
        n_per_side = max(3, (usable_h // row_h) // 2)

        asks = asks_agg[:n_per_side]
        bids = bids_agg[:n_per_side]

        all_sizes = [s for _, s in asks] + [s for _, s in bids]
        max_size = max(all_sizes) if all_sizes else 1.0

        font_size = max(6, int(row_h * 0.6))
        font = ("Consolas", font_size)
        font_bold = ("Consolas", font_size, "bold")

        # ASKS: idx 0 — лучший ask, прижат к верхней границе полосы.
        for i, (price, size) in enumerate(asks):
            y = top_of_band - (i + 1) * row_h
            self._draw_row(y, price, size, max_size, True,
                           w, row_h, font, decimals)

        # BIDS: idx 0 — лучший bid, прижат к нижней границе полосы.
        for i, (price, size) in enumerate(bids):
            y = bottom_of_band + i * row_h
            self._draw_row(y, price, size, max_size, False,
                           w, row_h, font, decimals)

        # Пустая полоса по центру, без разделительной линии.
        c.create_rectangle(0, top_of_band, w, bottom_of_band,
                           fill=BG_MAIN, outline="")

        if book.spread is not None and book.mid is not None:
            c.create_text(
                w // 2, mid_y,
                text=f"spread {book.spread:.{decimals}f}  ·  mid {book.mid:.{decimals}f}",
                fill=COLOR_MID, font=font_bold, anchor="center",
            )
        elif book.mid is not None:
            c.create_text(
                w // 2, mid_y,
                text=f"mid {book.mid:.{decimals}f}",
                fill=COLOR_MID, font=font_bold, anchor="center",
            )

    def _draw_row(self, y, price, size, max_size, is_ask,
                  w, row_h, font, decimals):
        c = self.canvas
        ratio = (size / max_size) ** 0.5

        if is_ask:
            r = int(48 + 140 * ratio)
            g = int(18 + 25 * ratio)
            b = int(18 + 25 * ratio)
        else:
            r = int(18 + 20 * ratio)
            g = int(48 + 90 * ratio)
            b = int(70 + 110 * ratio)

        bg = f"#{min(r,255):02x}{min(g,255):02x}{min(b,255):02x}"
        c.create_rectangle(0, y, w, y + row_h, fill=bg, outline="")
        c.create_line(0, y, w, y, fill="#050505", width=1)

        cy = y + row_h // 2

        c.create_text(
            8, cy,
            text=self._fmt_size(size),
            fill=FG_TEXT, font=font, anchor="w",
        )
        c.create_text(
            w - 8, cy,
            text=f"{price:.{decimals}f}",
            fill=FG_TEXT, font=font, anchor="e",
        )

    @staticmethod
    def _fmt_size(s):
        if s >= 1_000_000:
            return f"{s / 1_000_000:.1f}M"
        if s >= 1000:
            return f"{s / 1000:.1f}K"
        if s >= 100:
            return f"{s:.0f}"
        if s >= 1:
            return f"{s:.2f}"
        return f"{s:.3f}"


def main():
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?")
    ap.add_argument("--live")
    ap.add_argument("--symbol", default=None)
    args = ap.parse_args()

    if not args.path and not args.live:
        ap.error("Укажи путь к .jsonl или --live BTCUSDT,...")

    live_symbols = None
    if args.live:
        live_symbols = [s.strip().upper() for s in args.live.split(",") if s.strip()]

    symbol = args.symbol.upper() if args.symbol else None

    app = OrderbookLadderApp(
        source_path=args.path,
        live_symbols=live_symbols,
        symbol_filter=symbol,
    )
    app.mainloop()


if __name__ == "__main__":
    main()