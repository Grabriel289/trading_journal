from datetime import date as date_cls, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.dependencies import get_backfill_service, get_snapshot_service
from backend.api.schemas import EquitySnapshotOut
from backend.services.backfill_service import BackfillService
from backend.services.snapshot_service import SnapshotService

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


_RANGE_DAYS = {"1W": 7, "1M": 30, "3M": 90, "1Y": 365}


@router.get("/equity-curve", response_model=List[EquitySnapshotOut])
def equity_curve(
    portfolio_id: str = Query(...),
    range: Optional[str] = Query(default="ALL"),
    service: SnapshotService = Depends(get_snapshot_service),
):
    date_from: Optional[date_cls] = None
    if range and range.upper() in _RANGE_DAYS:
        date_from = date_cls.today() - timedelta(days=_RANGE_DAYS[range.upper()])
    elif range and range.upper() != "ALL":
        raise HTTPException(status_code=400, detail=f"Unknown range '{range}'")
    return service.list_snapshots(portfolio_id=portfolio_id, date_from=date_from)


@router.post("/snapshot", response_model=EquitySnapshotOut)
async def take_snapshot(
    portfolio_id: str = Query(...),
    service: SnapshotService = Depends(get_snapshot_service),
):
    try:
        snap = await service.take_snapshot(portfolio_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return snap


@router.post("/backfill")
async def backfill_snapshots(
    portfolio_id: str = Query(...),
    service: BackfillService = Depends(get_backfill_service),
):
    try:
        result = await service.backfill(portfolio_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "snapshots_upserted": result.snapshots_upserted,
        "first_date": result.first_date,
        "last_date": result.last_date,
        "assets_priced": result.assets_priced,
        "assets_skipped": result.assets_skipped,
    }
