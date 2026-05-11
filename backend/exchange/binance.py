from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

import httpx

from backend.config import BINANCE_BASE_URL, BINANCE_FAPI_URL, HTTP_TIMEOUT_SECONDS
from backend.exchange.base import BaseExchange, FundingEvent, Kline


class BinanceExchange(BaseExchange):
    def __init__(
        self,
        base_url: str = BINANCE_BASE_URL,
        fapi_url: str = BINANCE_FAPI_URL,
    ) -> None:
        self._base_url = base_url
        self._fapi_url = fapi_url
        # Shared client for connection pooling (lazy-init)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS)
        return self._client

    def format_symbol(self, asset: str, base: str) -> str:
        return f"{asset.upper()}{base.upper()}"

    async def get_price(self, asset: str, base: str = "USDT") -> Decimal:
        symbol = self.format_symbol(asset, base)
        url = f"{self._base_url}/api/v3/ticker/price"
        client = await self._get_client()
        response = await client.get(url, params={"symbol": symbol})
        response.raise_for_status()
        data = response.json()
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
        params: dict = {"symbol": symbol, "interval": interval, "limit": min(limit, 1000)}
        if start_time is not None:
            params["startTime"] = int(_as_utc(start_time).timestamp() * 1000)
        if end_time is not None:
            params["endTime"] = int(_as_utc(end_time).timestamp() * 1000)
        url = f"{self._base_url}/api/v3/klines"
        client = await self._get_client()
        response = await client.get(url, params=params)
        response.raise_for_status()
        rows = response.json()
        return [
            Kline(
                open_time=datetime.fromtimestamp(r[0] / 1000, tz=timezone.utc),
                close_time=datetime.fromtimestamp(r[6] / 1000, tz=timezone.utc),
                open=Decimal(str(r[1])),
                high=Decimal(str(r[2])),
                low=Decimal(str(r[3])),
                close=Decimal(str(r[4])),
                volume=Decimal(str(r[5])),
            )
            for r in rows
        ]


    async def get_funding_history(
        self,
        asset: str,
        base: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[FundingEvent]:
        symbol = self.format_symbol(asset, base)
        params: dict = {"symbol": symbol, "limit": min(limit, 1000)}
        if start_time is not None:
            params["startTime"] = int(_as_utc(start_time).timestamp() * 1000)
        if end_time is not None:
            params["endTime"] = int(_as_utc(end_time).timestamp() * 1000)
        url = f"{self._fapi_url}/fapi/v1/fundingRate"
        client = await self._get_client()
        response = await client.get(url, params=params)
        response.raise_for_status()
        rows = response.json()
        return [
            FundingEvent(
                funding_time=datetime.fromtimestamp(r["fundingTime"] / 1000, tz=timezone.utc),
                funding_rate=Decimal(str(r["fundingRate"])),
                mark_price=Decimal(str(r.get("markPrice", "0"))),
            )
            for r in rows
        ]

    async def close(self) -> None:
        """Close the shared HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
