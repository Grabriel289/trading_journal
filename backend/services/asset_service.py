"""Asset registry + price-source management.

Assets are auto-registered on first reference (e.g. when an order or import
mentions a symbol). New assets get a default source chain:
  Binance (priority 10) → Kucoin (priority 20) → CoinGecko (priority 30)

Manual override is added on demand via `set_manual_price`. The Manual source
is given priority 5 so it takes precedence over the exchange chain.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.models import (
    Asset,
    AssetType,
    Chain,
    ManualPriceEntry,
    PriceSource,
    Sector,
    SourceType,
)


DEFAULT_SOURCE_PRIORITIES = [
    (SourceType.BINANCE, 10),
    (SourceType.KUCOIN, 20),
    (SourceType.COINGECKO, 30),
]
MANUAL_OVERRIDE_PRIORITY = 5
MANUAL_FALLBACK_PRIORITY = 99


# Phase 2 Step 8: known-asset classification used for sector/chain/tier auto-backfill.
KNOWN_ASSETS: dict = {
    # Layer 1
    "BTC":   {"sector": Sector.LAYER_1, "chain": Chain.BITCOIN,    "tier": "MEGA",  "name": "Bitcoin"},
    "ETH":   {"sector": Sector.LAYER_1, "chain": Chain.ETHEREUM,   "tier": "MEGA",  "name": "Ethereum"},
    "SOL":   {"sector": Sector.LAYER_1, "chain": Chain.SOLANA,     "tier": "LARGE", "name": "Solana"},
    "AVAX":  {"sector": Sector.LAYER_1, "chain": Chain.AVALANCHE,  "tier": "LARGE", "name": "Avalanche"},
    "ADA":   {"sector": Sector.LAYER_1, "chain": Chain.OTHER,      "tier": "LARGE", "name": "Cardano"},
    "DOT":   {"sector": Sector.LAYER_1, "chain": Chain.OTHER,      "tier": "LARGE", "name": "Polkadot"},
    # Exchange / Layer 1
    "BNB":   {"sector": Sector.EXCHANGE, "chain": Chain.BNB_CHAIN, "tier": "LARGE", "name": "BNB"},
    # Layer 2
    "ARB":   {"sector": Sector.LAYER_2, "chain": Chain.ARBITRUM,   "tier": "MID",   "name": "Arbitrum"},
    "OP":    {"sector": Sector.LAYER_2, "chain": Chain.OPTIMISM,   "tier": "MID",   "name": "Optimism"},
    "MATIC": {"sector": Sector.LAYER_2, "chain": Chain.POLYGON,    "tier": "MID",   "name": "Polygon"},
    "BASE":  {"sector": Sector.LAYER_2, "chain": Chain.BASE,       "tier": "MID",   "name": "Base"},
    # Infrastructure / DeFi / AI
    "LINK":  {"sector": Sector.INFRASTRUCTURE, "chain": Chain.MULTI_CHAIN, "tier": "LARGE", "name": "Chainlink"},
    "UNI":   {"sector": Sector.DEFI, "chain": Chain.ETHEREUM, "tier": "MID",  "name": "Uniswap"},
    "AAVE":  {"sector": Sector.DEFI, "chain": Chain.MULTI_CHAIN, "tier": "MID",  "name": "Aave"},
    "RNDR":  {"sector": Sector.AI,   "chain": Chain.SOLANA, "tier": "MID",  "name": "Render"},
    "FET":   {"sector": Sector.AI,   "chain": Chain.ETHEREUM, "tier": "MID",  "name": "Fetch.ai"},
    # Meme
    "DOGE":  {"sector": Sector.MEME, "chain": Chain.OTHER, "tier": "LARGE", "name": "Dogecoin"},
    "SHIB":  {"sector": Sector.MEME, "chain": Chain.ETHEREUM, "tier": "MID",  "name": "Shiba Inu"},
    "PEPE":  {"sector": Sector.MEME, "chain": Chain.ETHEREUM, "tier": "MID",  "name": "Pepe"},
    # Stablecoins
    "USDT":  {"sector": Sector.STABLECOIN, "chain": Chain.MULTI_CHAIN, "tier": "MEGA", "name": "Tether USD"},
    "USDC":  {"sector": Sector.STABLECOIN, "chain": Chain.MULTI_CHAIN, "tier": "MEGA", "name": "USD Coin"},
    "DAI":   {"sector": Sector.STABLECOIN, "chain": Chain.ETHEREUM,   "tier": "LARGE", "name": "Dai"},
    # Others
    "TON":   {"sector": Sector.LAYER_1, "chain": Chain.OTHER, "tier": "LARGE", "name": "Toncoin"},
    "XRP":   {"sector": Sector.OTHER, "chain": Chain.OTHER, "tier": "LARGE", "name": "XRP"},
    "TRX":   {"sector": Sector.LAYER_1, "chain": Chain.OTHER, "tier": "LARGE", "name": "TRON"},
    "LTC":   {"sector": Sector.OTHER, "chain": Chain.OTHER, "tier": "MID",   "name": "Litecoin"},
}


@dataclass
class AssetSummary:
    id: str
    symbol: str
    name: str
    asset_type: str
    coingecko_id: Optional[str]
    is_active: bool
    note: Optional[str]
    sources: List[dict]
    has_manual_price: bool
    latest_manual_price: Optional[Decimal]
    latest_manual_at: Optional[datetime]
    sector: Optional[str] = None
    chain: Optional[str] = None
    market_cap_tier: Optional[str] = None


class AssetService:
    def __init__(self, db: Session) -> None:
        self._db = db

    # ---------- registry ----------
    def list_assets(self) -> List[Asset]:
        return list(self._db.query(Asset).order_by(Asset.symbol).all())

    def get_asset(self, symbol: str) -> Optional[Asset]:
        return (
            self._db.query(Asset).filter(Asset.symbol == symbol.upper()).one_or_none()
        )

    def ensure_asset(self, symbol: str, *, name: Optional[str] = None) -> Asset:
        symbol = symbol.upper().strip()
        if not symbol:
            raise ValueError("symbol is required")
        known = KNOWN_ASSETS.get(symbol, {})
        existing = self.get_asset(symbol)
        if existing is not None:
            # Backfill classification if missing on an asset registered earlier
            changed = False
            if existing.sector is None and known.get("sector"):
                existing.sector = known["sector"]; changed = True
            if existing.chain is None and known.get("chain"):
                existing.chain = known["chain"]; changed = True
            if existing.market_cap_tier is None and known.get("tier"):
                existing.market_cap_tier = known["tier"]; changed = True
            if changed:
                self._db.commit()
                self._db.refresh(existing)
            return existing
        asset = Asset(
            symbol=symbol,
            name=name or known.get("name") or symbol,
            asset_type=AssetType.CRYPTO,
            sector=known.get("sector"),
            chain=known.get("chain"),
            market_cap_tier=known.get("tier"),
        )
        self._db.add(asset)
        self._db.flush()
        for source_type, prio in DEFAULT_SOURCE_PRIORITIES:
            self._db.add(PriceSource(
                asset_id=asset.id, source_type=source_type, priority=prio, is_active=True,
            ))
        self._db.commit()
        self._db.refresh(asset)
        return asset

    def update_asset(
        self,
        symbol: str,
        *,
        name: Optional[str] = None,
        coingecko_id: Optional[str] = None,
        is_active: Optional[bool] = None,
        note: Optional[str] = None,
    ) -> Asset:
        asset = self.get_asset(symbol)
        if asset is None:
            raise ValueError(f"Asset {symbol} not found")
        if name is not None: asset.name = name
        if coingecko_id is not None: asset.coingecko_id = coingecko_id or None
        if is_active is not None: asset.is_active = is_active
        if note is not None: asset.note = note or None
        self._db.commit()
        self._db.refresh(asset)
        return asset

    def delete_asset(self, symbol: str) -> None:
        asset = self.get_asset(symbol)
        if asset is None:
            raise ValueError(f"Asset {symbol} not found")
        self._db.delete(asset)  # cascades sources + manual prices
        self._db.commit()

    # ---------- sources ----------
    def upsert_source(
        self, symbol: str, source_type: SourceType, priority: int, is_active: bool = True,
    ) -> PriceSource:
        asset = self.ensure_asset(symbol)
        existing = (
            self._db.query(PriceSource)
            .filter_by(asset_id=asset.id, source_type=source_type)
            .one_or_none()
        )
        if existing is None:
            existing = PriceSource(
                asset_id=asset.id, source_type=source_type,
                priority=priority, is_active=is_active,
            )
            self._db.add(existing)
        else:
            existing.priority = priority
            existing.is_active = is_active
        self._db.commit()
        self._db.refresh(existing)
        return existing

    def remove_source(self, symbol: str, source_type: SourceType) -> None:
        asset = self.get_asset(symbol)
        if asset is None:
            raise ValueError(f"Asset {symbol} not found")
        (
            self._db.query(PriceSource)
            .filter_by(asset_id=asset.id, source_type=source_type)
            .delete(synchronize_session=False)
        )
        self._db.commit()

    # ---------- manual price ----------
    def set_manual_price(
        self,
        symbol: str,
        price: Decimal,
        *,
        note: Optional[str] = None,
        as_override: bool = True,
    ) -> ManualPriceEntry:
        asset = self.ensure_asset(symbol)
        if Decimal(price) <= 0:
            raise ValueError("price must be positive")
        # Append to history (never mutate prior entries)
        entry = ManualPriceEntry(
            asset_id=asset.id, price=Decimal(price), note=note or None,
        )
        self._db.add(entry)
        # Ensure a Manual source exists. Priority 5 = override exchanges, 99 = fallback only.
        prio = MANUAL_OVERRIDE_PRIORITY if as_override else MANUAL_FALLBACK_PRIORITY
        existing = (
            self._db.query(PriceSource)
            .filter_by(asset_id=asset.id, source_type=SourceType.MANUAL)
            .one_or_none()
        )
        if existing is None:
            self._db.add(PriceSource(
                asset_id=asset.id, source_type=SourceType.MANUAL,
                priority=prio, is_active=True,
            ))
        else:
            existing.priority = prio
            existing.is_active = True
        self._db.commit()
        self._db.refresh(entry)
        return entry

    def clear_manual_override(self, symbol: str) -> None:
        """Disable Manual as an override but keep history."""
        asset = self.get_asset(symbol)
        if asset is None:
            raise ValueError(f"Asset {symbol} not found")
        manual = (
            self._db.query(PriceSource)
            .filter_by(asset_id=asset.id, source_type=SourceType.MANUAL)
            .one_or_none()
        )
        if manual is not None:
            manual.is_active = False
            self._db.commit()

    def latest_manual_entry(self, asset_id: str) -> Optional[ManualPriceEntry]:
        return (
            self._db.query(ManualPriceEntry)
            .filter(ManualPriceEntry.asset_id == asset_id)
            .order_by(ManualPriceEntry.created_at.desc())
            .first()
        )

    def manual_history(self, symbol: str, limit: int = 50) -> List[ManualPriceEntry]:
        asset = self.get_asset(symbol)
        if asset is None:
            return []
        return list(
            self._db.query(ManualPriceEntry)
            .filter(ManualPriceEntry.asset_id == asset.id)
            .order_by(ManualPriceEntry.created_at.desc())
            .limit(limit)
            .all()
        )

    # ---------- summaries ----------
    def summary(self, asset: Asset) -> AssetSummary:
        sources = sorted(asset.sources, key=lambda s: s.priority)
        latest = self.latest_manual_entry(asset.id)
        return AssetSummary(
            id=asset.id,
            symbol=asset.symbol,
            name=asset.name,
            asset_type=asset.asset_type.value,
            coingecko_id=asset.coingecko_id,
            is_active=asset.is_active,
            note=asset.note,
            sources=[
                {
                    "source_type": s.source_type.value,
                    "priority": s.priority,
                    "is_active": s.is_active,
                } for s in sources
            ],
            has_manual_price=latest is not None,
            latest_manual_price=Decimal(latest.price) if latest else None,
            latest_manual_at=latest.created_at if latest else None,
            sector=asset.sector.value if asset.sector else None,
            chain=asset.chain.value if asset.chain else None,
            market_cap_tier=asset.market_cap_tier,
        )
