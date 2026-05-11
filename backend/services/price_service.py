import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Callable, Dict, List, Optional

from backend.exchange.base import BaseExchange, Kline
from backend.util.clock import utc_now


logger = logging.getLogger(__name__)


# Status codes used in the UI for the price freshness/source badge.
STATUS_LIVE         = "LIVE"          # fetched from API, fresh
STATUS_MANUAL       = "MANUAL"        # from a manual override entry, fresh
STATUS_STALE        = "STALE"         # cached or manual, but past freshness threshold
STATUS_DISCONNECTED = "DISCONNECTED"  # all sources failed, no fallback available
STATUS_NONE         = "NONE"          # asset has no usable price (caller should fall back)


@dataclass
class PriceQuote:
    asset: str
    base: str
    price: Optional[Decimal]      # None when status == NONE / DISCONNECTED w/o cache
    status: str
    source: Optional[str]
    fetched_at: Optional[datetime]
    note: Optional[str] = None


@dataclass
class _CachedPrice:
    price: Decimal
    fetched_at: float
    source: str


_LIVE_CACHE_TTL_SECONDS = 60

@dataclass
class _CachedKline:
    klines: List[Kline]
    fetched_at: float

_KLINE_CACHE_TTL_SECONDS = 3600  # 1 hour — kline history doesn't change

_MANUAL_FRESH_HOURS     = 24
_LIVE_STALE_HOURS       = 1


class PriceService:
    """Provider-aware price service.

    - If the asset is registered in the DB, we walk its `price_sources` ordered
      by priority and try each in turn. The first one that returns a price wins.
    - MANUAL source uses the most recent ManualPriceEntry from history.
    - Exchange sources call the matching adapter (Binance / Kucoin / CoinGecko).
    - On total failure we return whatever's in the in-memory cache as STALE,
      else a NONE quote — never raises to callers like the dashboard.

    Backwards compatibility: `get_price()` returns just the Decimal as before;
    new callers that need the source/status use `get_quote()`.
    """

    def __init__(
        self,
        primary: BaseExchange,
        kucoin: Optional[BaseExchange] = None,
        coingecko: Optional[BaseExchange] = None,
        session_factory: Optional[Callable] = None,
        cache_ttl: float = _LIVE_CACHE_TTL_SECONDS,
    ) -> None:
        self._primary = primary
        self._kucoin = kucoin
        self._coingecko = coingecko
        self._sf = session_factory
        self._cache: Dict[str, _CachedPrice] = {}
        self._cache_ttl = cache_ttl
        self._kline_cache: Dict[str, _CachedKline] = {}

    # ---------------------------------------------------------------- caching
    @staticmethod
    def _key(asset: str, base: str) -> str:
        return f"{asset.upper()}/{base.upper()}"

    def _cache_get(self, asset: str, base: str) -> Optional[_CachedPrice]:
        return self._cache.get(self._key(asset, base))

    def _cache_set(self, asset: str, base: str, price: Decimal, source: str) -> None:
        self._cache[self._key(asset, base)] = _CachedPrice(
            price=price, fetched_at=time.time(), source=source,
        )

    # ---------------------------------------------------------------- public
    async def get_price(self, asset: str, base: str = "USDT") -> Decimal:
        """Compatibility shim — returns Decimal or raises if nothing usable."""
        quote = await self.get_quote(asset, base)
        if quote.price is None:
            raise ValueError(f"No price available for {asset}/{base}")
        return quote.price

    async def get_quote(self, asset: str, base: str = "USDT") -> PriceQuote:
        asset_u = asset.upper()
        base_u = base.upper()

        # Fast path: serve a fresh in-memory cache hit
        cached = self._cache_get(asset_u, base_u)
        now_ts = time.time()
        if cached and (now_ts - cached.fetched_at) < self._cache_ttl:
            return PriceQuote(
                asset=asset_u, base=base_u, price=cached.price,
                status=STATUS_LIVE, source=cached.source,
                fetched_at=datetime.fromtimestamp(cached.fetched_at, tz=timezone.utc),
            )

        # Walk the provider chain defined for this asset (or fall back to default)
        chain = self._resolve_chain(asset_u)
        coingecko_id_override = self._coingecko_id_override(asset_u)
        last_error: Optional[Exception] = None

        for source_type in chain:
            try:
                if source_type == "MANUAL":
                    return self._manual_quote(asset_u, base_u)
                price = await self._fetch_from(source_type, asset_u, base_u, coingecko_id_override)
                self._cache_set(asset_u, base_u, price, source_type.title())
                return PriceQuote(
                    asset=asset_u, base=base_u, price=price,
                    status=STATUS_LIVE, source=source_type.title(),
                    fetched_at=datetime.now(tz=timezone.utc),
                )
            except _NoManualPrice:
                continue  # manual source exists but no entry yet — try next
            except Exception as exc:
                last_error = exc
                logger.debug("price source %s failed for %s/%s: %s",
                             source_type, asset_u, base_u, exc)
                continue

        # All providers failed. Serve stale cache if we have it.
        if cached is not None:
            return PriceQuote(
                asset=asset_u, base=base_u, price=cached.price,
                status=STATUS_STALE, source=cached.source,
                fetched_at=datetime.fromtimestamp(cached.fetched_at, tz=timezone.utc),
                note="Cached value — providers unreachable",
            )

        return PriceQuote(
            asset=asset_u, base=base_u, price=None,
            status=STATUS_DISCONNECTED, source=None, fetched_at=None,
            note=str(last_error) if last_error else "No price source available",
        )

    async def get_batch_prices(
        self, assets: List[str], base: str = "USDT"
    ) -> Dict[str, Decimal]:
        out: Dict[str, Decimal] = {}
        for asset in assets:
            quote = await self.get_quote(asset, base)
            if quote.price is not None:
                out[asset] = quote.price
        return out

    async def refresh(
        self, assets: List[str], base: str = "USDT",
    ) -> Dict[str, Decimal]:
        """Force-refresh — used by the price-cache job. Manual-only assets are skipped."""
        out: Dict[str, Decimal] = {}
        for asset in assets:
            try:
                # Direct primary fetch bypassing the chain
                price = await self._primary.get_price(asset, base)
                self._cache_set(asset.upper(), base.upper(), price, "Binance")
                out[asset] = price
            except Exception:
                # Try the full chain (will respect manual / kucoin / coingecko)
                try:
                    quote = await self.get_quote(asset, base)
                    if quote.price is not None:
                        out[asset] = quote.price
                except Exception:
                    logger.warning("refresh failed for %s/%s", asset, base)
        return out

    @staticmethod
    def _kline_key(
        asset: str, base: str, interval: str,
        start_time: Optional[datetime], end_time: Optional[datetime],
    ) -> str:
        st = int(start_time.timestamp()) if start_time else 0
        et = int(end_time.timestamp()) if end_time else 0
        return f"{asset.upper()}/{base.upper()}/{interval}/{st}/{et}"

    async def get_klines(
        self,
        asset: str,
        base: str,
        interval: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 500,
    ) -> List[Kline]:
        key = self._kline_key(asset, base, interval, start_time, end_time)
        cached = self._kline_cache.get(key)
        now = time.time()
        if cached and (now - cached.fetched_at) < _KLINE_CACHE_TTL_SECONDS:
            return cached.klines
        klines = await self._primary.get_klines(
            asset=asset, base=base, interval=interval,
            start_time=start_time, end_time=end_time, limit=limit,
        )
        self._kline_cache[key] = _CachedKline(klines=klines, fetched_at=now)
        return klines

    # ---------------------------------------------------------------- internals
    def _resolve_chain(self, asset: str) -> List[str]:
        """Return source-type strings in priority order for this asset."""
        if self._sf is None:
            return ["BINANCE"]
        try:
            from backend.models import Asset, PriceSource
            with self._sf() as db:
                asset_row = db.query(Asset).filter_by(symbol=asset).one_or_none()
                if asset_row is None:
                    return ["BINANCE", "KUCOIN", "COINGECKO"]
                rows = (
                    db.query(PriceSource)
                    .filter_by(asset_id=asset_row.id, is_active=True)
                    .order_by(PriceSource.priority)
                    .all()
                )
                if not rows:
                    return ["BINANCE", "KUCOIN", "COINGECKO"]
                return [r.source_type.value for r in rows]
        except Exception:
            return ["BINANCE"]

    def _coingecko_id_override(self, asset: str) -> Optional[str]:
        if self._sf is None:
            return None
        try:
            from backend.models import Asset
            with self._sf() as db:
                asset_row = db.query(Asset).filter_by(symbol=asset).one_or_none()
                return asset_row.coingecko_id if asset_row else None
        except Exception:
            return None

    def _manual_quote(self, asset: str, base: str) -> PriceQuote:
        if self._sf is None:
            raise _NoManualPrice()
        from backend.models import Asset, ManualPriceEntry
        with self._sf() as db:
            asset_row = db.query(Asset).filter_by(symbol=asset).one_or_none()
            if asset_row is None:
                raise _NoManualPrice()
            entry = (
                db.query(ManualPriceEntry)
                .filter_by(asset_id=asset_row.id)
                .order_by(ManualPriceEntry.created_at.desc())
                .first()
            )
            if entry is None:
                raise _NoManualPrice()
            age_hours = (utc_now() - entry.created_at).total_seconds() / 3600
            status = STATUS_MANUAL if age_hours < _MANUAL_FRESH_HOURS else STATUS_STALE
            return PriceQuote(
                asset=asset, base=base, price=Decimal(entry.price),
                status=status, source="Manual",
                fetched_at=entry.created_at.replace(tzinfo=timezone.utc),
                note=entry.note,
            )

    async def _fetch_from(
        self,
        source_type: str,
        asset: str,
        base: str,
        coingecko_id: Optional[str],
    ) -> Decimal:
        if source_type == "BINANCE":
            return await self._primary.get_price(asset, base)
        if source_type == "KUCOIN":
            if self._kucoin is None:
                raise RuntimeError("Kucoin adapter not configured")
            return await self._kucoin.get_price(asset, base)
        if source_type == "COINGECKO":
            if self._coingecko is None:
                raise RuntimeError("CoinGecko adapter not configured")
            return await self._coingecko.get_price(
                asset, base, coingecko_id=coingecko_id,
            )
        raise RuntimeError(f"Unknown source type: {source_type}")


class _NoManualPrice(Exception):
    pass
