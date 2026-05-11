import logging

from backend.db.database import SessionLocal
from backend.models import Order, Portfolio, OrderStatus, Side
from backend.services.price_service import PriceService


logger = logging.getLogger(__name__)


async def run_price_cache_job(price_service: PriceService) -> int:
    """Refresh cached prices for every asset that has an open buy order."""
    db = SessionLocal()
    try:
        portfolios = db.query(Portfolio).all()
        # Map base_currency -> set of held asset symbols
        held: dict[str, set[str]] = {}
        for portfolio in portfolios:
            base = portfolio.base_currency.value
            for sub in portfolio.sub_accounts:
                rows = (
                    db.query(Order)
                    .filter(Order.sub_account_id == sub.id)
                    .filter(Order.side == Side.BUY)
                    .filter(Order.status != OrderStatus.CLOSED)
                    .filter(Order.remaining_quantity > 0)
                    .all()
                )
                for o in rows:
                    held.setdefault(base, set()).add(o.asset)
        refreshed = 0
        for base, assets in held.items():
            updated = await price_service.refresh(sorted(assets), base=base)
            refreshed += len(updated)
        if refreshed:
            logger.debug("Price cache job: refreshed %d (asset, base) pairs", refreshed)
        return refreshed
    finally:
        db.close()
