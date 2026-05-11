from datetime import datetime
from decimal import Decimal
from typing import List, Optional

import httpx

from backend.config import HTTP_TIMEOUT_SECONDS
from backend.exchange.base import BaseExchange, Kline


# Common-coin shortcut. Anything else, the user must set `coingecko_id` on the asset.
SYMBOL_TO_ID = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "USDT": "tether",
    "USDC": "usd-coin",
    "BNB": "binancecoin",
    "XRP": "ripple",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "MATIC": "matic-network",
    "AVAX": "avalanche-2",
    "DOT": "polkadot",
    "LINK": "chainlink",
    "TRX": "tron",
    "LTC": "litecoin",
}


class CoinGeckoExchange(BaseExchange):
    """Public price endpoint — symbol must map to a CoinGecko coin id.

    Note: CoinGecko's free public API has a strict rate limit (~30 req/min),
    so this provider should be used as a fallback, not a primary cache-warmer.
    """

    BASE_URL = "https://api.coingecko.com/api/v3"

    def __init__(self, symbol_to_id: dict | None = None) -> None:
        self._map = symbol_to_id or SYMBOL_TO_ID

    def format_symbol(self, asset: str, base: str) -> str:
        return self._map.get(asset.upper(), asset.lower())

    def _resolve_id(self, asset: str, override_id: Optional[str] = None) -> str:
        if override_id:
            return override_id
        return self._map.get(asset.upper(), asset.lower())

    async def get_price(
        self,
        asset: str,
        base: str = "USDT",
        coingecko_id: Optional[str] = None,
    ) -> Decimal:
        coin_id = self._resolve_id(asset, coingecko_id)
        # USDT/USDC/USD all behave like USD pegged for CoinGecko purposes.
        vs = "usd" if base.upper() in ("USDT", "USDC", "USD") else base.lower()
        url = f"{self.BASE_URL}/simple/price"
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            r = await client.get(url, params={"ids": coin_id, "vs_currencies": vs})
            r.raise_for_status()
            payload = r.json()
        if coin_id not in payload or vs not in payload[coin_id]:
            raise ValueError(f"CoinGecko: no price for {coin_id} vs {vs}")
        return Decimal(str(payload[coin_id][vs]))

    async def get_klines(
        self,
        asset: str,
        base: str,
        interval: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 500,
    ) -> List[Kline]:
        # CoinGecko has historical OHLC but the API shape is different.
        # Out of scope for the MVP fallback — return empty list so callers can skip gracefully.
        return []
