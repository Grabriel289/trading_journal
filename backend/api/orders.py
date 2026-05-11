from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.dependencies import get_order_service
from backend.db.database import get_db
from sqlalchemy.orm import Session
from backend.api.schemas import (
    BuyOrderRequest,
    FundingUpdateRequest,
    OrderEditRequest,
    OrderOut,
    SellOrderRequest,
)
from backend.models.enums import Side
from backend.services.order_service import BuyOrderInput, OrderService, SellOrderInput

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.post("/buy", response_model=OrderOut)
async def create_buy_order(
    body: BuyOrderRequest,
    service: OrderService = Depends(get_order_service),
):
    try:
        order = await service.create_buy(
            BuyOrderInput(
                sub_account_id=body.sub_account_id,
                asset=body.asset,
                quantity=body.quantity,
                price=body.price,
                fee=body.fee,
                note=body.note,
                when=body.when,
                leverage=body.leverage,
                direction=body.direction,
                funding_accumulated=body.funding_accumulated,
                strategy_id=body.strategy_id,
                order_type=body.order_type,
                execution_venue=body.execution_venue,
                exchange_order_id=body.exchange_order_id,
                exchange_trade_id=body.exchange_trade_id,
                expected_price=body.expected_price,
                fee_currency=body.fee_currency,
                maker_taker=body.maker_taker,
                tag_ids=body.tag_ids,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return order


@router.patch("/{order_id}/funding", response_model=OrderOut)
def update_funding(
    order_id: str,
    body: FundingUpdateRequest,
    service: OrderService = Depends(get_order_service),
):
    try:
        order = service.update_funding(order_id, body.funding_accumulated)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return order


@router.post("/sell", response_model=OrderOut)
async def create_sell_order(
    body: SellOrderRequest,
    service: OrderService = Depends(get_order_service),
):
    try:
        order = await service.create_sell(
            SellOrderInput(
                linked_buy_order_id=body.linked_buy_order_id,
                sell_quantity=body.sell_quantity,
                price=body.price,
                fee=body.fee,
                note=body.note,
                when=body.when,
                strategy_id=body.strategy_id,
                order_type=body.order_type,
                execution_venue=body.execution_venue,
                exchange_order_id=body.exchange_order_id,
                exchange_trade_id=body.exchange_trade_id,
                expected_price=body.expected_price,
                fee_currency=body.fee_currency,
                maker_taker=body.maker_taker,
                tag_ids=body.tag_ids,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return order


@router.get("/open-buys", response_model=List[OrderOut])
def list_open_buys(
    sub_account_id: str = Query(...),
    asset: Optional[str] = Query(default=None),
    service: OrderService = Depends(get_order_service),
):
    return service.get_open_buys(sub_account_id=sub_account_id, asset=asset)


@router.get("/{order_id}/confirmation")
def get_order_confirmation(order_id: str, db: Session = Depends(get_db)):
    """Immutable trade confirmation record snapshot taken at order creation."""
    from backend.models import TradeConfirmation
    confs = (
        db.query(TradeConfirmation)
        .filter(TradeConfirmation.order_id == order_id)
        .order_by(TradeConfirmation.confirmed_at)
        .all()
    )
    if not confs:
        raise HTTPException(status_code=404, detail=f"No confirmation for order {order_id}")
    # Usually one row per order; return them all if multiple (shouldn't happen)
    return [
        {
            "id": c.id,
            "order_id": c.order_id,
            "confirmed_at": c.confirmed_at.isoformat(),
            "portfolio_id": c.portfolio_id,
            "sub_account_id": c.sub_account_id,
            "sub_account_name": c.sub_account_name,
            "asset": c.asset,
            "side": c.side,
            "quantity": str(c.quantity),
            "price": str(c.price),
            "total_value": str(c.total_value),
            "fee": str(c.fee),
            "fee_currency": c.fee_currency,
            "order_type": c.order_type,
            "execution_venue": c.execution_venue,
            "exchange_order_id": c.exchange_order_id,
            "strategy_name": c.strategy_name,
            "leverage": c.leverage,
            "direction": c.direction,
            "margin_used": str(c.margin_used) if c.margin_used else None,
            "linked_buy_order_id": c.linked_buy_order_id,
            "raw_snapshot": c.raw_snapshot,
        }
        for c in confs
    ]


@router.get("/{order_id}/funding-payments")
def list_order_funding_payments(order_id: str, db: Session = Depends(get_db)):
    """Time-series of all funding events recorded against this order."""
    from backend.models import FundingPayment, Order
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    rows = (
        db.query(FundingPayment)
        .filter(FundingPayment.order_id == order_id)
        .order_by(FundingPayment.funding_time)
        .all()
    )
    return [
        {
            "id": r.id,
            "funding_time": r.funding_time.isoformat(),
            "funding_rate": str(r.funding_rate),
            "mark_price": str(r.mark_price),
            "position_size": str(r.position_size),
            "payment_amount": str(r.payment_amount),
            "note": r.note,
        }
        for r in rows
    ]


@router.get("", response_model=List[OrderOut])
def list_orders(
    sub_account_id: Optional[str] = Query(default=None),
    asset: Optional[str] = Query(default=None),
    side: Optional[Side] = Query(default=None),
    service: OrderService = Depends(get_order_service),
):
    return service.list_orders(sub_account_id=sub_account_id, asset=asset, side=side)


@router.put("/{order_id}", response_model=OrderOut)
def edit_order(
    order_id: str,
    body: OrderEditRequest,
    service: OrderService = Depends(get_order_service),
):
    try:
        order = service.update_order(
            order_id,
            when=body.when,
            price=body.price,
            fee=body.fee,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return order


@router.delete("/{order_id}", status_code=204)
def delete_order(
    order_id: str,
    service: OrderService = Depends(get_order_service),
):
    try:
        service.delete_order(order_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
