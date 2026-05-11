from fastapi import APIRouter, Depends, HTTPException

from backend.api.dependencies import get_price_service
from backend.api.schemas import PriceQuoteOut
from backend.services.price_service import PriceService

router = APIRouter(prefix="/api/prices", tags=["prices"])


@router.get("/{asset}/quote", response_model=PriceQuoteOut)
async def get_quote(
    asset: str,
    base: str = "USDT",
    service: PriceService = Depends(get_price_service),
):
    quote = await service.get_quote(asset, base)
    return PriceQuoteOut(
        asset=quote.asset, base=quote.base, price=quote.price,
        status=quote.status, source=quote.source,
        fetched_at=quote.fetched_at, note=quote.note,
    )


@router.get("/{asset}")
async def get_price(
    asset: str,
    base: str = "USDT",
    service: PriceService = Depends(get_price_service),
) -> dict:
    """Backwards-compatible: returns the price + status as a flat dict."""
    quote = await service.get_quote(asset, base)
    if quote.price is None:
        raise HTTPException(
            status_code=502,
            detail=f"No price available for {asset.upper()} (status: {quote.status})",
        )
    return {
        "asset": quote.asset,
        "base": quote.base,
        "price": str(quote.price),
        "status": quote.status,
        "source": quote.source,
    }
