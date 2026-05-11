import logging

from backend.db.database import SessionLocal
from backend.exchange.binance import BinanceExchange
from backend.models import Portfolio
from backend.services.portfolio_service import PortfolioService
from backend.services.price_service import PriceService
from backend.services.snapshot_service import SnapshotService


logger = logging.getLogger(__name__)


async def run_equity_snapshot_job(price_service: PriceService) -> int:
    """Take an equity snapshot for every portfolio. Returns the number snapshotted."""
    db = SessionLocal()
    try:
        portfolio_ids = [p.id for p in db.query(Portfolio).all()]
        portfolio_svc = PortfolioService(db=db, price_service=price_service)
        snap_svc = SnapshotService(db=db, portfolio_service=portfolio_svc)
        count = 0
        for pid in portfolio_ids:
            try:
                await snap_svc.take_snapshot(pid)
                count += 1
            except Exception as exc:
                logger.exception("Snapshot failed for portfolio %s: %s", pid, exc)
        logger.info("Equity snapshot job finished — %d portfolios", count)
        return count
    finally:
        db.close()
