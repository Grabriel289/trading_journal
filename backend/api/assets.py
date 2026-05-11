from dataclasses import asdict
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from backend.api.dependencies import get_asset_service
from backend.api.schemas import (
    AssetCreate,
    AssetEditRequest,
    AssetOut,
    AssetSourceOut,
    BulkManualPriceRequest,
    BulkManualPriceResult,
    BulkManualPriceResultRow,
    ManualPriceEntryOut,
    ManualPriceRequest,
    SourceUpsertRequest,
)
from backend.models import SourceType
from backend.services.asset_service import AssetService

router = APIRouter(prefix="/api/assets", tags=["assets"])


def _to_out(svc: AssetService, asset) -> AssetOut:
    s = svc.summary(asset)
    return AssetOut(
        id=s.id, symbol=s.symbol, name=s.name, asset_type=s.asset_type,
        coingecko_id=s.coingecko_id, is_active=s.is_active, note=s.note,
        sources=[AssetSourceOut(**src) for src in s.sources],
        has_manual_price=s.has_manual_price,
        latest_manual_price=s.latest_manual_price,
        latest_manual_at=s.latest_manual_at,
        sector=s.sector, chain=s.chain, market_cap_tier=s.market_cap_tier,
    )


@router.get("", response_model=List[AssetOut])
def list_assets(svc: AssetService = Depends(get_asset_service)):
    return [_to_out(svc, a) for a in svc.list_assets()]


# Defined BEFORE the /{symbol}/... routes so FastAPI matches the literal path first.
@router.post("/manual-prices/bulk", response_model=BulkManualPriceResult)
def bulk_set_manual_prices(
    body: BulkManualPriceRequest,
    svc: AssetService = Depends(get_asset_service),
):
    rows: List[BulkManualPriceResultRow] = []
    updated = failed = 0
    for item in body.items:
        try:
            svc.set_manual_price(
                item.symbol,
                price=item.price,
                note=item.note,
                as_override=item.as_override,
            )
            rows.append(BulkManualPriceResultRow(symbol=item.symbol, ok=True))
            updated += 1
        except Exception as exc:
            rows.append(BulkManualPriceResultRow(symbol=item.symbol, ok=False, error=str(exc)))
            failed += 1
    return BulkManualPriceResult(updated=updated, failed=failed, items=rows)


@router.post("", response_model=AssetOut)
def create_asset(body: AssetCreate, svc: AssetService = Depends(get_asset_service)):
    asset = svc.ensure_asset(body.symbol, name=body.name)
    if body.coingecko_id:
        svc.update_asset(asset.symbol, coingecko_id=body.coingecko_id)
        asset = svc.get_asset(asset.symbol)
    return _to_out(svc, asset)


@router.get("/{symbol}", response_model=AssetOut)
def get_asset(symbol: str, svc: AssetService = Depends(get_asset_service)):
    asset = svc.get_asset(symbol)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"Asset {symbol} not found")
    return _to_out(svc, asset)


@router.put("/{symbol}", response_model=AssetOut)
def update_asset(
    symbol: str,
    body: AssetEditRequest,
    svc: AssetService = Depends(get_asset_service),
):
    try:
        asset = svc.update_asset(
            symbol,
            name=body.name,
            coingecko_id=body.coingecko_id,
            is_active=body.is_active,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_out(svc, asset)


@router.delete("/{symbol}", status_code=204)
def delete_asset(symbol: str, svc: AssetService = Depends(get_asset_service)):
    try:
        svc.delete_asset(symbol)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{symbol}/manual-price", response_model=AssetOut)
def set_manual_price(
    symbol: str,
    body: ManualPriceRequest,
    svc: AssetService = Depends(get_asset_service),
):
    try:
        svc.set_manual_price(
            symbol,
            price=body.price,
            note=body.note,
            as_override=body.as_override,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_out(svc, svc.get_asset(symbol))


@router.delete("/{symbol}/manual-price", response_model=AssetOut)
def clear_manual_price(symbol: str, svc: AssetService = Depends(get_asset_service)):
    try:
        svc.clear_manual_override(symbol)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_out(svc, svc.get_asset(symbol))


@router.get("/{symbol}/manual-price-history", response_model=List[ManualPriceEntryOut])
def manual_history(symbol: str, svc: AssetService = Depends(get_asset_service)):
    return svc.manual_history(symbol)


@router.post("/{symbol}/sources", response_model=AssetOut)
def upsert_source(
    symbol: str,
    body: SourceUpsertRequest,
    svc: AssetService = Depends(get_asset_service),
):
    try:
        source_type = SourceType(body.source_type.upper())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    svc.upsert_source(symbol, source_type, priority=body.priority, is_active=body.is_active)
    return _to_out(svc, svc.get_asset(symbol))


@router.delete("/{symbol}/sources/{source_type}", response_model=AssetOut)
def remove_source(
    symbol: str,
    source_type: str,
    svc: AssetService = Depends(get_asset_service),
):
    try:
        st = SourceType(source_type.upper())
        svc.remove_source(symbol, st)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_out(svc, svc.get_asset(symbol))
