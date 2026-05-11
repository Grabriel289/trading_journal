from typing import List

from fastapi import APIRouter, Depends, HTTPException

from backend.api.dependencies import get_order_service, get_portfolio_service
from backend.api.schemas import (
    PortfolioCreate,
    PortfolioEditRequest,
    PortfolioOut,
    PortfolioOverviewOut,
    SubAccountCreate,
    SubAccountEditRequest,
    SubAccountOut,
    TradeOut,
)
from backend.services.order_service import OrderService
from backend.services.portfolio_service import PortfolioService

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.post("", response_model=PortfolioOut)
def create_portfolio(
    body: PortfolioCreate,
    service: PortfolioService = Depends(get_portfolio_service),
):
    portfolio = service.create_portfolio(
        name=body.name,
        base_currency=body.base_currency,
        inception_date=body.inception_date,
        benchmark=body.benchmark,
        management_fee_rate=body.management_fee_rate,
        performance_fee_rate=body.performance_fee_rate,
        description=body.description,
    )
    return portfolio


@router.get("", response_model=List[PortfolioOut])
def list_portfolios(service: PortfolioService = Depends(get_portfolio_service)):
    return service.list_portfolios()


@router.get("/{portfolio_id}", response_model=PortfolioOut)
def get_portfolio(portfolio_id: str, service: PortfolioService = Depends(get_portfolio_service)):
    portfolio = service.get_portfolio(portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return portfolio


@router.put("/{portfolio_id}", response_model=PortfolioOut)
def update_portfolio(
    portfolio_id: str,
    body: PortfolioEditRequest,
    service: PortfolioService = Depends(get_portfolio_service),
):
    try:
        return service.update_portfolio(
            portfolio_id,
            name=body.name,
            base_currency=body.base_currency,
            inception_date=body.inception_date,
            benchmark=body.benchmark,
            management_fee_rate=body.management_fee_rate,
            performance_fee_rate=body.performance_fee_rate,
            description=body.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{portfolio_id}", status_code=204)
def delete_portfolio(
    portfolio_id: str,
    service: PortfolioService = Depends(get_portfolio_service),
):
    try:
        service.delete_portfolio(portfolio_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{portfolio_id}/data")
def wipe_portfolio_data(
    portfolio_id: str,
    service: PortfolioService = Depends(get_portfolio_service),
):
    try:
        return service.wipe_portfolio_data(portfolio_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{portfolio_id}/sub-account", response_model=SubAccountOut)
def add_sub_account(
    portfolio_id: str,
    body: SubAccountCreate,
    service: PortfolioService = Depends(get_portfolio_service),
):
    try:
        sub = service.add_sub_account(
            portfolio_id=portfolio_id,
            name=body.name,
            type=body.type,
            initial_capital=body.initial_capital,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return sub


@router.put("/sub-account/{sub_account_id}", response_model=SubAccountOut)
def update_sub_account(
    sub_account_id: str,
    body: SubAccountEditRequest,
    service: PortfolioService = Depends(get_portfolio_service),
):
    try:
        return service.update_sub_account(
            sub_account_id, name=body.name, initial_capital=body.initial_capital
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/sub-account/{sub_account_id}", status_code=204)
def delete_sub_account(
    sub_account_id: str,
    service: PortfolioService = Depends(get_portfolio_service),
):
    try:
        service.delete_sub_account(sub_account_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{portfolio_id}/overview", response_model=PortfolioOverviewOut)
async def get_overview(
    portfolio_id: str,
    service: PortfolioService = Depends(get_portfolio_service),
):
    try:
        overview = await service.get_overview(portfolio_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return overview


@router.get("/{portfolio_id}/trades", response_model=List[TradeOut])
def list_trades(
    portfolio_id: str,
    orders: OrderService = Depends(get_order_service),
):
    try:
        trades = orders.list_trades_for_portfolio(portfolio_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [
        TradeOut(
            entry_order_id=t.entry_order_id,
            exit_order_id=t.exit_order_id,
            sub_account_id=t.sub_account_id,
            sub_account_type=t.sub_account_type,
            asset=t.asset,
            entry_datetime=t.entry_datetime,
            exit_datetime=t.exit_datetime,
            entry_price=t.entry_price,
            exit_price=t.exit_price,
            quantity=t.quantity,
            pnl_dollar=t.pnl_dollar,
            pnl_percent=t.pnl_percent,
            fee_total=t.fee_total,
            funding_pnl=t.funding_pnl,
            gross_pnl=t.gross_pnl,
            holding_seconds=int(t.holding_duration.total_seconds()),
            leverage=t.leverage,
            direction=t.direction,
            strategy_id=t.strategy_id,
        )
        for t in trades
    ]
