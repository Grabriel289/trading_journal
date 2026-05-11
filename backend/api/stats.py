from dataclasses import asdict
from datetime import date as date_cls
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.api.dependencies import (
    get_db,
    get_portfolio_service,
    get_stats_service,
)
from backend.api.schemas import (
    AssetBreakdownOut,
    AssetPerformanceRowOut,
    AvgWinLossOut,
    BenchmarkMetricsOut,
    BestWorstOut,
    ConcentrationOut,
    CorrelationMatrixOut,
    CorrelationPairOut,
    DailyBucketOut,
    DrawdownOut,
    DurationPointOut,
    DurationStatsOut,
    ExcursionPointOut,
    ExposureAnalysisOut,
    FundingAnalyticsOut,
    FundingByPositionOut,
    FundingDailySummaryOut,
    HourlyBucketOut,
    MaeMfeDataOut,
    PerCoinRowOut,
    PnLWaterfallOut,
    RiskMetricsOut,
    RollingPointOut,
    RoRLevelOut,
    SectorExposureOut,
    SlippageByGroupOut,
    SlippageStatsOut,
    StaticRiskMetricsOut,
    StrategyAttributionOut,
    StrategyPerformanceOut,
    StreaksOut,
    SummaryStatsOut,
    WinRateOut,
)
from backend.services.portfolio_service import PortfolioService
from backend.services.stats_service import StatsFilter, StatsService

router = APIRouter(prefix="/api/stats", tags=["stats"])


def _filter(
    portfolio_id: str,
    sub_account_id: Optional[str],
    date_from: Optional[date_cls],
    date_to: Optional[date_cls],
) -> StatsFilter:
    return StatsFilter(
        portfolio_id=portfolio_id,
        sub_account_id=sub_account_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/summary", response_model=SummaryStatsOut)
def get_summary(
    portfolio_id: str = Query(...),
    sub_account_id: Optional[str] = Query(default=None),
    date_from: Optional[date_cls] = Query(default=None),
    date_to: Optional[date_cls] = Query(default=None),
    service: StatsService = Depends(get_stats_service),
):
    try:
        s = service.get_summary(_filter(portfolio_id, sub_account_id, date_from, date_to))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SummaryStatsOut(
        win_rate=WinRateOut(**asdict(s.win_rate)),
        long_win_rate=WinRateOut(**asdict(s.long_win_rate)),
        short_win_rate=WinRateOut(**asdict(s.short_win_rate)),
        profit_factor=s.profit_factor,
        avg_win_loss=AvgWinLossOut(**asdict(s.avg_win_loss)),
        best_worst=BestWorstOut(**asdict(s.best_worst)),
        streaks=StreaksOut(**asdict(s.streaks)),
        std_deviation=s.std_deviation,
        z_score=s.z_score,
        z_score_probability=s.z_score_probability,
        ahpr=s.ahpr,
        ghpr=s.ghpr,
        recovery_factor=s.recovery_factor,
        total_net_profit=s.total_net_profit,
        drawdown=DrawdownOut(**asdict(s.drawdown)),
        sharpe=s.sharpe,
        sortino=s.sortino,
        calmar=s.calmar,
        annual_return=s.annual_return,
        cumulative_twr=s.cumulative_twr,
        annualized_twr=s.annualized_twr,
        mwr=s.mwr,
        var_95=s.var_95,
        cvar_95=s.cvar_95,
        parametric_var_95=s.parametric_var_95,
        tail_ratio=s.tail_ratio,
        max_dd_recovery_days=s.max_dd_recovery_days,
    )


@router.get("/trades-breakdown", response_model=List[AssetBreakdownOut])
def get_trades_breakdown(
    portfolio_id: str = Query(...),
    sub_account_id: Optional[str] = Query(default=None),
    date_from: Optional[date_cls] = Query(default=None),
    date_to: Optional[date_cls] = Query(default=None),
    service: StatsService = Depends(get_stats_service),
):
    try:
        rows = service.get_trades_breakdown(
            _filter(portfolio_id, sub_account_id, date_from, date_to)
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [AssetBreakdownOut(**asdict(r)) for r in rows]


@router.get("/hourly", response_model=List[HourlyBucketOut])
def get_hourly(
    portfolio_id: str = Query(...),
    sub_account_id: Optional[str] = Query(default=None),
    date_from: Optional[date_cls] = Query(default=None),
    date_to: Optional[date_cls] = Query(default=None),
    service: StatsService = Depends(get_stats_service),
):
    try:
        rows = service.get_hourly(_filter(portfolio_id, sub_account_id, date_from, date_to))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [HourlyBucketOut(**asdict(r)) for r in rows]


@router.get("/daily", response_model=List[DailyBucketOut])
def get_daily(
    portfolio_id: str = Query(...),
    sub_account_id: Optional[str] = Query(default=None),
    date_from: Optional[date_cls] = Query(default=None),
    date_to: Optional[date_cls] = Query(default=None),
    service: StatsService = Depends(get_stats_service),
):
    try:
        rows = service.get_daily(_filter(portfolio_id, sub_account_id, date_from, date_to))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [DailyBucketOut(**asdict(r)) for r in rows]


@router.get("/risk-of-ruin", response_model=List[RoRLevelOut])
def get_risk_of_ruin(
    portfolio_id: str = Query(...),
    sub_account_id: Optional[str] = Query(default=None),
    date_from: Optional[date_cls] = Query(default=None),
    date_to: Optional[date_cls] = Query(default=None),
    service: StatsService = Depends(get_stats_service),
):
    try:
        rows = service.get_risk_of_ruin(
            _filter(portfolio_id, sub_account_id, date_from, date_to)
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [RoRLevelOut(**asdict(r)) for r in rows]


@router.get("/duration", response_model=DurationStatsOut)
def get_duration(
    portfolio_id: str = Query(...),
    sub_account_id: Optional[str] = Query(default=None),
    date_from: Optional[date_cls] = Query(default=None),
    date_to: Optional[date_cls] = Query(default=None),
    service: StatsService = Depends(get_stats_service),
):
    try:
        d = service.get_duration(_filter(portfolio_id, sub_account_id, date_from, date_to))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DurationStatsOut(
        points=[DurationPointOut(**asdict(p)) for p in d.points],
        avg_seconds=d.avg_seconds,
        median_seconds=d.median_seconds,
        longest_seconds=d.longest_seconds,
        shortest_seconds=d.shortest_seconds,
        avg_winner_seconds=d.avg_winner_seconds,
        avg_loser_seconds=d.avg_loser_seconds,
    )


# ── Performance tab redesign ─────────────────────────────────────────


@router.get("/asset-performance", response_model=List[AssetPerformanceRowOut])
async def get_asset_performance(
    portfolio_id: str = Query(...),
    db: Session = Depends(get_db),
    portfolio_service: PortfolioService = Depends(get_portfolio_service),
):
    from backend.services.asset_performance_service import AssetPerformanceService

    svc = AssetPerformanceService(db, portfolio_service)
    try:
        rows = await svc.get_rows(portfolio_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [AssetPerformanceRowOut(**asdict(r)) for r in rows]


@router.get("/per-coin-breakdown", response_model=List[PerCoinRowOut])
def get_per_coin_breakdown(
    portfolio_id: str = Query(...),
    db: Session = Depends(get_db),
):
    from backend.services.per_coin_service import PerCoinService

    svc = PerCoinService(db)
    try:
        rows = svc.get_rows(portfolio_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [PerCoinRowOut(**asdict(r)) for r in rows]


@router.get("/risk-metrics", response_model=RiskMetricsOut)
def get_risk_metrics(
    portfolio_id: str = Query(...),
    db: Session = Depends(get_db),
):
    from backend.services.risk_metrics_service import RiskMetricsService

    svc = RiskMetricsService(db)
    try:
        m = svc.get_metrics(portfolio_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RiskMetricsOut(
        static=StaticRiskMetricsOut(**asdict(m.static)),
        rolling_sharpe_30d=[RollingPointOut(**asdict(p)) for p in m.rolling_sharpe_30d],
        rolling_volatility_30d=[RollingPointOut(**asdict(p)) for p in m.rolling_volatility_30d],
        sample_size=m.sample_size,
    )


# ── Phase 3 endpoints ────────────────────────────────────────────────


@router.get("/funding-analytics", response_model=FundingAnalyticsOut)
def get_funding_analytics(
    portfolio_id: str = Query(...),
    date_from: Optional[date_cls] = Query(default=None),
    date_to: Optional[date_cls] = Query(default=None),
    db: Session = Depends(get_db),
):
    from backend.calculators.funding_calc import calc_funding_analytics
    from backend.models import FundingPayment, Order, Portfolio

    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    sub_ids = [s.id for s in portfolio.sub_accounts]
    if not sub_ids:
        return FundingAnalyticsOut(
            daily=[], by_position=[],
            total_paid=0, total_received=0, net_funding=0,
            avg_daily_cost=None,
        )

    orders = (
        db.query(Order)
        .filter(Order.sub_account_id.in_(sub_ids), Order.direction.isnot(None))
        .all()
    )
    order_ids = [o.id for o in orders]
    orders_by_id = {o.id: o for o in orders}

    if not order_ids:
        return FundingAnalyticsOut(
            daily=[], by_position=[],
            total_paid=0, total_received=0, net_funding=0,
            avg_daily_cost=None,
        )

    q = db.query(FundingPayment).filter(FundingPayment.order_id.in_(order_ids))
    if date_from:
        q = q.filter(FundingPayment.funding_time >= date_from)
    if date_to:
        q = q.filter(FundingPayment.funding_time <= date_to)
    payments = q.order_by(FundingPayment.funding_time).all()

    fa = calc_funding_analytics(payments, orders_by_id)
    return FundingAnalyticsOut(
        daily=[FundingDailySummaryOut(**asdict(d)) for d in fa.daily],
        by_position=[FundingByPositionOut(**asdict(p)) for p in fa.by_position],
        total_paid=fa.total_paid,
        total_received=fa.total_received,
        net_funding=fa.net_funding,
        avg_daily_cost=fa.avg_daily_cost,
    )


@router.get("/pnl-waterfall", response_model=PnLWaterfallOut)
def get_pnl_waterfall(
    portfolio_id: str = Query(...),
    date_from: Optional[date_cls] = Query(default=None),
    date_to: Optional[date_cls] = Query(default=None),
    db: Session = Depends(get_db),
    service: StatsService = Depends(get_stats_service),
):
    from dataclasses import asdict as _asdict
    from decimal import Decimal as D

    from backend.calculators.cost_calc import calc_trade_costs
    from backend.calculators.pnl_waterfall import calc_pnl_waterfall
    from backend.models import EquitySnapshot, Order, Portfolio

    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    trades = service._trades(_filter(portfolio_id, None, date_from, date_to))

    # Aggregate slippage across trades that have expected_price data
    total_slippage = D("0")
    if trades:
        order_ids = {t.entry_order_id for t in trades} | {t.exit_order_id for t in trades}
        orders = db.query(Order).filter(Order.id.in_(order_ids)).all()
        by_id = {o.id: o for o in orders}
        for t in trades:
            eo = by_id.get(t.entry_order_id)
            xo = by_id.get(t.exit_order_id)
            if eo is None or xo is None:
                continue
            costs = calc_trade_costs(
                entry_price=t.entry_price,
                exit_price=t.exit_price,
                quantity=t.quantity,
                entry_fee=eo.fee or D("0"),
                exit_fee=xo.fee or D("0"),
                funding=t.funding_pnl,
                entry_expected_price=(
                    D(str(eo.expected_price)) if eo.expected_price is not None else None
                ),
                exit_expected_price=(
                    D(str(xo.expected_price)) if xo.expected_price is not None else None
                ),
            )
            if costs.total_slippage is not None:
                total_slippage += costs.total_slippage

    # Period NAVs from EquitySnapshot
    snaps_q = (
        db.query(EquitySnapshot)
        .filter(EquitySnapshot.portfolio_id == portfolio_id)
        .order_by(EquitySnapshot.date)
    )
    if date_from:
        snaps_q = snaps_q.filter(EquitySnapshot.date >= date_from)
    if date_to:
        snaps_q = snaps_q.filter(EquitySnapshot.date <= date_to)
    snaps = snaps_q.all()

    if snaps:
        period_start_nav = D(str(snaps[0].total_equity))
        period_end_nav = D(str(snaps[-1].total_equity))
        period_days = (snaps[-1].date - snaps[0].date).days
    else:
        period_start_nav = period_end_nav = D("0")
        period_days = 0

    result = calc_pnl_waterfall(
        trades=trades,
        management_fee_rate=(
            D(str(portfolio.management_fee_rate))
            if portfolio.management_fee_rate is not None else None
        ),
        performance_fee_rate=(
            D(str(portfolio.performance_fee_rate))
            if portfolio.performance_fee_rate is not None else None
        ),
        period_start_nav=period_start_nav,
        period_end_nav=period_end_nav,
        high_water_mark=(
            D(str(portfolio.high_water_mark))
            if portfolio.high_water_mark is not None else None
        ),
        period_days=period_days,
        total_slippage=total_slippage,
    )
    return PnLWaterfallOut(**_asdict(result))


@router.get("/exposure", response_model=ExposureAnalysisOut)
async def get_exposure(
    portfolio_id: str = Query(...),
    db: Session = Depends(get_db),
    portfolio_service: PortfolioService = Depends(get_portfolio_service),
):
    from dataclasses import asdict as _asdict

    from backend.calculators.exposure_calc import calc_exposure
    from backend.models import Asset

    try:
        overview = await portfolio_service.get_overview(portfolio_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    positions = [p for s in overview.sub_accounts for p in s.open_positions]
    symbols = list({p.asset for p in positions})

    sector_map: dict = {}
    if symbols:
        rows = db.query(Asset).filter(Asset.symbol.in_(symbols)).all()
        for a in rows:
            sector_val = a.sector.value if a.sector is not None else "OTHER"
            sector_map[a.symbol] = sector_val

    result = calc_exposure(positions, sector_map, overview.total_equity)
    return ExposureAnalysisOut(
        total_nav=result.total_nav,
        gross_exposure=result.gross_exposure,
        net_exposure=result.net_exposure,
        leverage_ratio=result.leverage_ratio,
        long_exposure=result.long_exposure,
        short_exposure=result.short_exposure,
        long_short_ratio=result.long_short_ratio,
        sectors=[SectorExposureOut(**_asdict(s)) for s in result.sectors],
        concentration=ConcentrationOut(**_asdict(result.concentration)),
    )


@router.get("/correlations", response_model=CorrelationMatrixOut)
def get_correlations(
    portfolio_id: str = Query(...),
    date_from: Optional[date_cls] = Query(default=None),
    date_to: Optional[date_cls] = Query(default=None),
    service: StatsService = Depends(get_stats_service),
):
    try:
        result = service.get_asset_correlations(
            _filter(portfolio_id, None, date_from, date_to)
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CorrelationMatrixOut(
        labels=result["labels"],
        matrix=result["matrix"],
        high_correlations=[CorrelationPairOut(**hc) for hc in result["high_correlations"]],
    )


@router.get("/benchmark", response_model=BenchmarkMetricsOut)
def get_benchmark_metrics(
    portfolio_id: str = Query(...),
    date_from: Optional[date_cls] = Query(default=None),
    date_to: Optional[date_cls] = Query(default=None),
    db: Session = Depends(get_db),
):
    from dataclasses import asdict as _asdict

    from backend.services.benchmark_service import BenchmarkService

    svc = BenchmarkService(db)
    try:
        m = svc.get_metrics(portfolio_id, date_from, date_to)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BenchmarkMetricsOut(**_asdict(m))


@router.get("/strategy-attribution", response_model=StrategyAttributionOut)
def get_strategy_attribution(
    portfolio_id: str = Query(...),
    date_from: Optional[date_cls] = Query(default=None),
    date_to: Optional[date_cls] = Query(default=None),
    db: Session = Depends(get_db),
):
    from backend.services.strategy_stats_service import StrategyStatsService

    svc = StrategyStatsService(db)
    try:
        result = svc.get_attribution(
            StatsFilter(portfolio_id=portfolio_id, date_from=date_from, date_to=date_to)
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return StrategyAttributionOut(
        strategies=[StrategyPerformanceOut(**asdict(s)) for s in result.strategies],
        total_pnl=result.total_pnl,
        untagged_pnl=result.untagged_pnl,
        strategy_count=result.strategy_count,
    )


@router.get("/slippage", response_model=SlippageStatsOut)
def get_slippage(
    portfolio_id: str = Query(...),
    date_from: Optional[date_cls] = Query(default=None),
    date_to: Optional[date_cls] = Query(default=None),
    db: Session = Depends(get_db),
    service: StatsService = Depends(get_stats_service),
):
    from decimal import Decimal as D

    from backend.calculators.cost_calc import calc_slippage_stats, calc_trade_costs
    from backend.models import Order

    trades = service._trades(_filter(portfolio_id, None, date_from, date_to))
    if not trades:
        return SlippageStatsOut(
            total_slippage_cost=D("0"),
            avg_slippage_per_trade=None,
            avg_slippage_bps=None,
            slippage_by_venue=[],
            slippage_by_order_type=[],
            worst_slippage_trade=None,
            trades_with_slippage_data=0,
            trades_without_slippage_data=0,
        )

    order_ids = {t.entry_order_id for t in trades} | {t.exit_order_id for t in trades}
    orders = db.query(Order).filter(Order.id.in_(order_ids)).all()
    by_id = {o.id: o for o in orders}

    rows = []
    for t in trades:
        eo = by_id.get(t.entry_order_id)
        xo = by_id.get(t.exit_order_id)
        if eo is None or xo is None:
            continue
        costs = calc_trade_costs(
            entry_price=t.entry_price,
            exit_price=t.exit_price,
            quantity=t.quantity,
            entry_fee=eo.fee or D("0"),
            exit_fee=xo.fee or D("0"),
            funding=t.funding_pnl,
            entry_expected_price=(
                D(str(eo.expected_price)) if eo.expected_price is not None else None
            ),
            exit_expected_price=(
                D(str(xo.expected_price)) if xo.expected_price is not None else None
            ),
            entry_maker_taker=eo.maker_taker.value if eo.maker_taker else None,
            exit_maker_taker=xo.maker_taker.value if xo.maker_taker else None,
        )
        rows.append({"trade": t, "costs": costs, "entry_order": eo, "exit_order": xo})

    stats = calc_slippage_stats(rows)
    return SlippageStatsOut(
        total_slippage_cost=stats.total_slippage_cost,
        avg_slippage_per_trade=stats.avg_slippage_per_trade,
        avg_slippage_bps=stats.avg_slippage_bps,
        slippage_by_venue=[SlippageByGroupOut(**asdict(g)) for g in stats.slippage_by_venue],
        slippage_by_order_type=[SlippageByGroupOut(**asdict(g)) for g in stats.slippage_by_order_type],
        worst_slippage_trade=stats.worst_slippage_trade,
        trades_with_slippage_data=stats.trades_with_slippage_data,
        trades_without_slippage_data=stats.trades_without_slippage_data,
    )


@router.get("/mae-mfe", response_model=MaeMfeDataOut)
async def get_mae_mfe(
    portfolio_id: str = Query(...),
    sub_account_id: Optional[str] = Query(default=None),
    date_from: Optional[date_cls] = Query(default=None),
    date_to: Optional[date_cls] = Query(default=None),
    service: StatsService = Depends(get_stats_service),
):
    try:
        d = await service.get_mae_mfe(
            _filter(portfolio_id, sub_account_id, date_from, date_to)
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return MaeMfeDataOut(
        points=[ExcursionPointOut(**asdict(p)) for p in d.points],
        avg_mae_pct=d.avg_mae_pct,
        avg_mfe_pct=d.avg_mfe_pct,
        skipped=d.skipped,
    )
