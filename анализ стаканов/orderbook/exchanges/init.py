from .base import OrderbookFeed

_REGISTRY: dict[str, type[OrderbookFeed]] = {}


def get_exchange(name: str) -> type[OrderbookFeed]:
    name = name.lower()
    if name not in _REGISTRY:
        if name == "bybit":
            from .bybit import BybitFeed
            _REGISTRY["bybit"] = BybitFeed
        else:
            raise KeyError(f"Unknown exchange: {name}")
    return _REGISTRY[name]