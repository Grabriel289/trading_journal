from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

import httpx

from backend.config import HTTP_TIMEOUT_SECONDS
from backend.exchange.base import BaseExchange, Kline


class KucoinExchange(BaseExchange):
    """Public REST endpoints — no API key required."""

    BASE_URL = "https://api.kucoin.com"

    _INTERVAL_MAP = {
        "1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min",
        "30m": "30min", "1h": "1hour", "2h": "2hour", "4h": "4hour",
        "6h": "6hour", "12h": "12hour", "1d": "1day", "1w": "1week",
    }

    def format_symbol(self, asset: str, base: str) -> str:
        return f"{asset.upper()}-{base.upper()}"

    async def get_price(self, asset: str, base: str = "USDT") -> Decimal:
        symbol = self.format_symbol(asset, base)
        url = f"{self.BASE_URL}/api/v1/market/orderbook/level1"
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            r = await client.get(url, params={"symbol": symbol})
            r.raise_for_status()
            payload = r.json()
        data = payload.get("data")
        if not data or "price" not in data:
            raise ValueError(f"Kucoin: no price for {symbol}")
        return Decimal(str(data["price"]))

    async def get_klines(
        self,
        asset: str,
        base: str,
        interval: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 500,
    ) -> List[Kline]:
        symbol = self.format_symbol(asset, base)
        kucoin_type = self._INTERVAL_MAP.get(interval, "1day")
        params: dict = {"symbol": symbol, "type": kucoin_type}
        if start_time is not None:
            params["startAt"] = int(_as_utc(start_time).timestamp())
        if end_time is not None:
            params["endAt"] = int(_as_utc(end_time).timestamp())
        url = f"{self.BASE_URL}/api/v1/market/candles"
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            payload = r.json()
        # Kucoin returns newest-first, [time, open, close, high, low, volume, turnover]
        rows = list(reversed(payload.get("data") or []))[:limit]
        return [
            Kline(
                open_time=datetime.fromtimestamp(int(r[0]), tz=timezone.utc),
                close_time=datetime.fromtimestamp(int(r[0]), tz=timezone.utc),
                open=Decimal(str(r[1])),
                close=Decimal(str(r[2])),
                high=Decimal(str(r[3])),
                low=Decimal(str(r[4])),
                volume=Decimal(str(r[5])),
            ) for r in rows
        ]


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
