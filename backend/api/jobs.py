from fastapi import APIRouter, Depends

from backend.api.dependencies import get_price_service
from backend.exchange.binance import BinanceExchange
from backend.jobs.equity_snapshot import run_equity_snapshot_job
from backend.jobs.funding_rate import run_funding_sync_job
from backend.jobs.price_cache import run_price_cache_job
from backend.services.price_service import PriceService

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("/price-cache")
async def trigger_price_cache(
    prices: PriceService = Depends(get_price_service),
):
    refreshed = await run_price_cache_job(prices)
    return {"refreshed_pairs": refreshed}


@router.post("/equity-snapshot")
async def trigger_equity_snapshot(
    prices: PriceService = Depends(get_price_service),
):
    count = await run_equity_snapshot_job(prices)
    return {"portfolios_snapshotted": count}


@router.post("/funding-sync")
async def trigger_funding_sync():
    updated = await run_funding_sync_job(BinanceExchange())
    return {"orders_updated": updated}
