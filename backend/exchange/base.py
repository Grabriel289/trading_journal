from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Optional


@dataclass(frozen=True)
class Kline:
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


@dataclass(frozen=True)
class FundingEvent:
    funding_time: datetime
    funding_rate: Decimal
    mark_price: Decimal


class BaseExchange(ABC):
    @abstractmethod
    async def get_price(self, asset: str, base: str = "USDT") -> Decimal:
        """Current market price."""

    @abstractmethod
    async def get_klines(
        self,
        asset: str,
        base: str,
        interval: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 500,
    ) -> List[Kline]:
        """Historical OHLCV candles."""

    async def get_funding_history(
        self,
        asset: str,
        base: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[FundingEvent]:
        """Historical funding-rate events for the perpetual futures symbol."""
        return []

    @abstractmethod
    def format_symbol(self, asset: str, base: str) -> str:
        """Format symbol for this exchange."""
