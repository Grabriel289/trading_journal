"""Daily benchmark-price sync job. Runs ~5 min after the daily snapshot.

Fetches today's close (live price via PriceService) for each benchmark symbol
and upserts a BenchmarkPrice row. Used by performance analytics for alpha
calculation against BTC / ETH / SOL / BNB.
"""
import logging
from datetime import date as date_cls

from backend.db.database import SessionLocal
from backend.models import BenchmarkPrice
from backend.services.price_service import PriceService


logger = logging.getLogger(__name__)

BENCHMARKS = ("BTC", "ETH", "SOL", "BNB")


async def run_benchmark_sync_job(price_service: PriceService) -> int:
    today = date_cls.today()
    db = SessionLocal()
    inserted = 0
    try:
        for symbol in BENCHMARKS:
            existing = (
                db.query(BenchmarkPrice)
                .filter(BenchmarkPrice.symbol == symbol, BenchmarkPrice.date == today)
                .first()
            )
            if existing is not None:
                continue
            try:
                price = await price_service.get_price(symbol, "USDT")
            except Exception as exc:
                logger.warning("Benchmark sync skipped %s: %s", symbol, exc)
                continue
            db.add(BenchmarkPrice(symbol=symbol, date=today, close_price=price))
            inserted += 1
        db.commit()
        logger.info("Benchmark sync job — %d benchmark prices inserted", inserted)
        return inserted
    finally:
        db.close()
