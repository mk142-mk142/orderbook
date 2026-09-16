from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from orderbook.store import read_range
from orderbook.visualizer import plot_ladder


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="Путь к .jsonl файлу")
    ap.add_argument("--symbol", default=None, help="Фильтр по символу")
    ap.add_argument("--index", type=int, default=0, help="Какую по счёту книгу показать")
    ap.add_argument("--levels", type=int, default=25, help="Сколько уровней показать с каждой стороны")
    ap.add_argument("--out", default="orderbook.html", help="Куда сохранить HTML")
    args = ap.parse_args()

    shown = 0
    for book in read_range(args.path):
        if args.symbol and book.symbol != args.symbol:
            continue
        if shown < args.index:
            shown += 1
            continue

        print(f"Рисую: {book.symbol} seq={book.seq} snapshot={book.is_snapshot}")
        fig = plot_ladder(book, max_levels=args.levels)
        fig.write_html(args.out, auto_open=True)
        print(f"Сохранено: {args.out}")
        return

    print("Не нашёл подходящих книг")


if __name__ == "__main__":
    main()