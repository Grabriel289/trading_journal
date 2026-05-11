from datetime import date as date_cls, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.models.enums import (
    BaseCurrency,
    DepositType,
    Direction,
    ExecutionVenue,
    MakerTaker,
    OrderStatus,
    OrderType,
    Side,
    SubAccountType,
)


class PortfolioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    base_currency: BaseCurrency = BaseCurrency.USDT
    # Phase 2 Step 6
    inception_date: Optional[date_cls] = None
    benchmark: Optional[str] = Field(default=None, max_length=20)
    management_fee_rate: Optional[Decimal] = Field(default=None, ge=0, le=1)
    performance_fee_rate: Optional[Decimal] = Field(default=None, ge=0, le=1)
    description: Optional[str] = None


class SubAccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: SubAccountType
    initial_capital: Decimal = Field(ge=0)


class SubAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    portfolio_id: str
    name: str
    type: SubAccountType
    initial_capital: Decimal
    created_at: datetime


class PortfolioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    base_currency: BaseCurrency
    inception_date: Optional[date_cls] = None
    benchmark: Optional[str] = None
    high_water_mark: Optional[Decimal] = None
    management_fee_rate: Optional[Decimal] = None
    performance_fee_rate: Optional[Decimal] = None
    description: Optional[str] = None
    created_at: datetime
    sub_accounts: List[SubAccountOut] = []


MAX_PRICE = Decimal("10_000_000")
MAX_QUANTITY = Decimal("1_000_000_000")
FUTURE_DT_TOLERANCE_SECONDS = 5  # allow tiny clock skew


def _no_future_datetime(v: Optional[datetime]) -> Optional[datetime]:
    if v is None:
        return v
    # Normalize to naive UTC for comparison (existing rows are naive UTC)
    v_naive = v.replace(tzinfo=None) if v.tzinfo else v
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if v_naive > now + timedelta(seconds=FUTURE_DT_TOLERANCE_SECONDS):
        raise ValueError("datetime cannot be in the future")
    return v


def _price_within_sanity(v: Optional[Decimal]) -> Optional[Decimal]:
    if v is None:
        return v
    if v > MAX_PRICE:
        raise ValueError(
            f"price {v} exceeds sanity cap ${MAX_PRICE:,} — "
            f"if intentional, raise MAX_PRICE in backend/api/schemas.py"
        )
    return v


def _quantity_within_sanity(v: Decimal) -> Decimal:
    if v > MAX_QUANTITY:
        raise ValueError(
            f"quantity {v} exceeds sanity cap {MAX_QUANTITY:,} — "
            f"if intentional, raise MAX_QUANTITY in backend/api/schemas.py"
        )
    return v


class BuyOrderRequest(BaseModel):
    sub_account_id: str
    asset: str = Field(min_length=1, max_length=20)
    quantity: Decimal = Field(gt=0)
    price: Optional[Decimal] = Field(default=None, gt=0)
    fee: Decimal = Field(default=Decimal("0"), ge=0)
    note: Optional[str] = None
    when: Optional[datetime] = None
    leverage: Optional[int] = Field(default=None, ge=1, le=125)
    direction: Optional[Direction] = None
    funding_accumulated: Decimal = Field(default=Decimal("0"))

    # Phase 2 Step 1
    strategy_id: Optional[str] = None
    # Phase 2 Step 2
    order_type: Optional[OrderType] = None
    execution_venue: Optional[ExecutionVenue] = None
    exchange_order_id: Optional[str] = Field(default=None, max_length=100)
    exchange_trade_id: Optional[str] = Field(default=None, max_length=100)
    expected_price: Optional[Decimal] = Field(default=None, gt=0)
    fee_currency: Optional[str] = Field(default=None, max_length=20)
    maker_taker: Optional[MakerTaker] = None
    # Phase 2 Step 9: tags
    tag_ids: List[str] = Field(default_factory=list)

    _v_when           = field_validator("when")(_no_future_datetime)
    _v_price          = field_validator("price")(_price_within_sanity)
    _v_quantity       = field_validator("quantity")(_quantity_within_sanity)
    _v_expected_price = field_validator("expected_price")(_price_within_sanity)


class FundingUpdateRequest(BaseModel):
    funding_accumulated: Decimal


class OrderEditRequest(BaseModel):
    when: Optional[datetime] = None
    price: Optional[Decimal] = Field(default=None, gt=0)
    fee: Optional[Decimal] = Field(default=None, ge=0)
    note: Optional[str] = None

    _v_when  = field_validator("when")(_no_future_datetime)
    _v_price = field_validator("price")(_price_within_sanity)


class PortfolioEditRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    base_currency: Optional[BaseCurrency] = None
    # Phase 2 Step 6
    inception_date: Optional[date_cls] = None
    benchmark: Optional[str] = Field(default=None, max_length=20)
    management_fee_rate: Optional[Decimal] = Field(default=None, ge=0, le=1)
    performance_fee_rate: Optional[Decimal] = Field(default=None, ge=0, le=1)
    description: Optional[str] = None


class SubAccountEditRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    initial_capital: Optional[Decimal] = Field(default=None, ge=0)


class SellOrderRequest(BaseModel):
    linked_buy_order_id: str
    sell_quantity: Decimal = Field(gt=0)
    price: Optional[Decimal] = Field(default=None, gt=0)
    fee: Decimal = Field(default=Decimal("0"), ge=0)
    note: Optional[str] = None
    when: Optional[datetime] = None

    # Phase 2 Step 2
    strategy_id: Optional[str] = None
    order_type: Optional[OrderType] = None
    execution_venue: Optional[ExecutionVenue] = None
    exchange_order_id: Optional[str] = Field(default=None, max_length=100)
    exchange_trade_id: Optional[str] = Field(default=None, max_length=100)
    expected_price: Optional[Decimal] = Field(default=None, gt=0)
    fee_currency: Optional[str] = Field(default=None, max_length=20)
    maker_taker: Optional[MakerTaker] = None
    # Phase 2 Step 9
    tag_ids: List[str] = Field(default_factory=list)

    _v_when           = field_validator("when")(_no_future_datetime)
    _v_price          = field_validator("price")(_price_within_sanity)
    _v_sell_quantity  = field_validator("sell_quantity")(_quantity_within_sanity)
    _v_expected_price = field_validator("expected_price")(_price_within_sanity)


class TagBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    color: str


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    sub_account_id: str
    datetime: datetime
    asset: str
    side: Side
    quantity: Decimal
    price: Decimal
    total_value: Decimal
    fee: Decimal
    note: Optional[str] = None
    status: OrderStatus
    remaining_quantity: Decimal
    linked_buy_order_id: Optional[str] = None
    sell_quantity: Optional[Decimal] = None
    leverage: Optional[int] = None
    direction: Optional[Direction] = None
    margin_used: Optional[Decimal] = None
    liquidation_price: Optional[Decimal] = None
    funding_accumulated: Optional[Decimal] = None
    # Phase 2
    strategy_id: Optional[str] = None
    order_type: Optional[OrderType] = None
    execution_venue: Optional[ExecutionVenue] = None
    exchange_order_id: Optional[str] = None
    exchange_trade_id: Optional[str] = None
    expected_price: Optional[Decimal] = None
    slippage: Optional[Decimal] = None
    fee_currency: Optional[str] = None
    maker_taker: Optional[MakerTaker] = None
    is_deleted: bool = False
    tags: List[TagBrief] = Field(default_factory=list)


class TradeOut(BaseModel):
    entry_order_id: str
    exit_order_id: str
    sub_account_id: str
    sub_account_type: SubAccountType
    asset: str
    entry_datetime: datetime
    exit_datetime: datetime
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal
    pnl_dollar: Decimal     # net (after fees + funding)
    pnl_percent: Decimal
    fee_total: Decimal      # commission only
    funding_pnl: Decimal = Decimal("0")
    gross_pnl: Decimal = Decimal("0")
    holding_seconds: int
    leverage: Optional[int] = None
    direction: Optional[Direction] = None
    strategy_id: Optional[str] = None


class OpenPositionOut(BaseModel):
    order_id: str
    asset: str
    quantity: Decimal
    entry_price: Decimal
    current_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    leverage: Optional[int] = None
    direction: Optional[Direction] = None
    margin_locked: Optional[Decimal] = None
    liquidation_price: Optional[Decimal] = None
    funding_accumulated: Optional[Decimal] = None
    price_status: Optional[str] = None
    price_source: Optional[str] = None


class SubAccountOverviewOut(BaseModel):
    id: str
    name: str
    type: SubAccountType
    initial_capital: Decimal
    deposits_total: Decimal
    withdrawals_total: Decimal
    cash: Decimal
    market_value: Decimal
    equity: Decimal
    unrealized_pnl: Decimal
    open_positions: List[OpenPositionOut]


class PortfolioOverviewOut(BaseModel):
    id: str
    name: str
    base_currency: BaseCurrency
    total_balance: Decimal
    total_market_value: Decimal
    total_equity: Decimal
    total_unrealized_pnl: Decimal
    total_deposited: Decimal
    open_trades: int
    sub_accounts: List[SubAccountOverviewOut]


class DepositCreate(BaseModel):
    sub_account_id: str
    amount: Decimal = Field(gt=0)
    type: DepositType
    note: Optional[str] = None
    when: Optional[datetime] = None


class DepositOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    sub_account_id: str
    datetime: datetime
    amount: Decimal
    type: DepositType
    note: Optional[str] = None


class EquitySnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    portfolio_id: str
    date: date_cls
    total_equity: Decimal
    total_balance: Decimal
    total_deposited: Decimal
    drawdown_pct: Decimal
    sub_account_data: Any


# ---------------- Stats ----------------

class WinRateOut(BaseModel):
    total: int
    winners: int
    losers: int
    breakeven: int
    win_rate: Optional[Decimal] = None


class AvgWinLossOut(BaseModel):
    avg_win_dollar: Optional[Decimal] = None
    avg_loss_dollar: Optional[Decimal] = None
    avg_win_pct: Optional[Decimal] = None
    avg_loss_pct: Optional[Decimal] = None
    expectancy_dollar: Optional[Decimal] = None


class BestWorstOut(BaseModel):
    best_dollar: Optional[Decimal] = None
    worst_dollar: Optional[Decimal] = None
    best_at: Optional[str] = None
    worst_at: Optional[str] = None


class StreaksOut(BaseModel):
    max_consecutive_wins: int
    max_consecutive_losses: int


class DrawdownOut(BaseModel):
    current_dd_pct: Decimal
    max_dd_pct: Decimal
    max_dd_dollar: Decimal
    peak_equity: Decimal
    max_dd_date: Optional[date_cls] = None
    max_dd_duration_days: int


class SummaryStatsOut(BaseModel):
    win_rate: WinRateOut
    long_win_rate: WinRateOut
    short_win_rate: WinRateOut
    profit_factor: Optional[Decimal] = None
    avg_win_loss: AvgWinLossOut
    best_worst: BestWorstOut
    streaks: StreaksOut
    std_deviation: Optional[Decimal] = None
    z_score: Optional[float] = None
    z_score_probability: Optional[float] = None
    ahpr: Optional[Decimal] = None
    ghpr: Optional[Decimal] = None
    recovery_factor: Optional[Decimal] = None
    total_net_profit: Decimal
    drawdown: DrawdownOut
    sharpe: Optional[float] = None
    sortino: Optional[float] = None
    calmar: Optional[float] = None
    annual_return: Optional[float] = None
    # Phase 3
    cumulative_twr: Optional[float] = None
    annualized_twr: Optional[float] = None
    mwr: Optional[float] = None
    var_95: Optional[float] = None
    cvar_95: Optional[float] = None
    parametric_var_95: Optional[float] = None
    tail_ratio: Optional[float] = None
    max_dd_recovery_days: int = 0


class AssetBreakdownOut(BaseModel):
    asset: str
    longs_count: int
    longs_pnl: Decimal
    longs_win_rate: Optional[Decimal] = None
    shorts_count: int
    shorts_pnl: Decimal
    shorts_win_rate: Optional[Decimal] = None
    total_count: int
    total_pnl: Decimal
    total_win_rate: Optional[Decimal] = None


class HourlyBucketOut(BaseModel):
    hour: int
    count: int
    profit: Decimal


class DailyBucketOut(BaseModel):
    weekday: int
    name: str
    winners: int
    losers: int
    profit: Decimal


class RoRLevelOut(BaseModel):
    loss_pct: float
    consecutive_losses: Optional[int] = None
    probability: Optional[float] = None


class DurationPointOut(BaseModel):
    asset: str
    duration_seconds: int
    pnl_dollar: Decimal
    pnl_percent: Decimal
    direction: Optional[str] = None
    exit_datetime: Optional[str] = None


class DurationStatsOut(BaseModel):
    points: List[DurationPointOut]
    avg_seconds: Optional[float] = None
    median_seconds: Optional[float] = None
    longest_seconds: Optional[int] = None
    shortest_seconds: Optional[int] = None
    avg_winner_seconds: Optional[float] = None
    avg_loser_seconds: Optional[float] = None


class ExcursionPointOut(BaseModel):
    asset: str
    direction: Optional[str] = None
    entry_price: Decimal
    exit_price: Decimal
    pnl_pct: Decimal
    mae_pct: Decimal
    mfe_pct: Decimal
    exit_datetime: Optional[str] = None


class MaeMfeDataOut(BaseModel):
    points: List[ExcursionPointOut]
    avg_mae_pct: Optional[Decimal] = None
    avg_mfe_pct: Optional[Decimal] = None
    skipped: int


# ---------------- Assets / Pricing ----------------

class AssetSourceOut(BaseModel):
    source_type: str
    priority: int
    is_active: bool


class AssetOut(BaseModel):
    id: str
    symbol: str
    name: str
    asset_type: str
    coingecko_id: Optional[str] = None
    is_active: bool
    note: Optional[str] = None
    sources: List[AssetSourceOut]
    has_manual_price: bool
    latest_manual_price: Optional[Decimal] = None
    latest_manual_at: Optional[datetime] = None
    sector: Optional[str] = None
    chain: Optional[str] = None
    market_cap_tier: Optional[str] = None


class AssetCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=40)
    name: Optional[str] = None
    coingecko_id: Optional[str] = None


class AssetEditRequest(BaseModel):
    name: Optional[str] = None
    coingecko_id: Optional[str] = None
    is_active: Optional[bool] = None
    note: Optional[str] = None


class ManualPriceRequest(BaseModel):
    price: Decimal = Field(gt=0)
    note: Optional[str] = None
    as_override: bool = True


class ManualPriceEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    price: Decimal
    note: Optional[str] = None
    set_by: str
    created_at: datetime


class SourceUpsertRequest(BaseModel):
    source_type: str
    priority: int = 10
    is_active: bool = True


class PriceQuoteOut(BaseModel):
    asset: str
    base: str
    price: Optional[Decimal] = None
    status: str
    source: Optional[str] = None
    fetched_at: Optional[datetime] = None
    note: Optional[str] = None


class BulkManualPriceItem(BaseModel):
    """Per-item validation is done inside the handler so a single bad row
    doesn't cause Pydantic to 422 the whole batch — failures report per-row."""
    symbol: str
    price: Decimal
    note: Optional[str] = None
    as_override: bool = True


class BulkManualPriceRequest(BaseModel):
    items: List[BulkManualPriceItem]


class BulkManualPriceResultRow(BaseModel):
    symbol: str
    ok: bool
    error: Optional[str] = None


class BulkManualPriceResult(BaseModel):
    updated: int
    failed: int
    items: List[BulkManualPriceResultRow]


# ── Phase 3: Analytics response schemas ──

class FundingDailySummaryOut(BaseModel):
    date: date_cls
    total_paid: Decimal
    payment_count: int
    positions_affected: int


class FundingByPositionOut(BaseModel):
    order_id: str
    asset: str
    direction: str
    total_funding: Decimal
    annualized_rate: Optional[float] = None
    payment_count: int
    avg_payment: Decimal
    max_single_payment: Decimal
    holding_days: int


class FundingAnalyticsOut(BaseModel):
    daily: List[FundingDailySummaryOut]
    by_position: List[FundingByPositionOut]
    total_paid: Decimal
    total_received: Decimal
    net_funding: Decimal
    avg_daily_cost: Optional[Decimal] = None


class StrategyPerformanceOut(BaseModel):
    strategy_id: Optional[str] = None
    strategy_name: str
    trade_count: int
    winners: int
    losers: int
    win_rate: Optional[Decimal] = None
    total_pnl: Decimal
    gross_pnl: Decimal
    total_commission: Decimal
    total_funding: Decimal
    avg_pnl_per_trade: Decimal
    profit_factor: Optional[Decimal] = None
    best_trade: Optional[Decimal] = None
    worst_trade: Optional[Decimal] = None
    avg_holding_seconds: Optional[float] = None
    std_deviation: Optional[Decimal] = None
    max_consecutive_wins: int
    max_consecutive_losses: int
    sharpe_estimate: Optional[float] = None


class StrategyAttributionOut(BaseModel):
    strategies: List[StrategyPerformanceOut]
    total_pnl: Decimal
    untagged_pnl: Decimal
    strategy_count: int


class BenchmarkMetricsOut(BaseModel):
    alpha: Optional[float] = None
    beta: Optional[float] = None
    r_squared: Optional[float] = None
    tracking_error: Optional[float] = None
    information_ratio: Optional[float] = None
    up_capture: Optional[float] = None
    down_capture: Optional[float] = None
    capture_ratio: Optional[float] = None
    portfolio_cumulative: float
    benchmark_cumulative: float
    excess_return: float
    correlation: Optional[float] = None


class CorrelationPairOut(BaseModel):
    asset_a: str
    asset_b: str
    correlation: float


class CorrelationMatrixOut(BaseModel):
    labels: List[str]
    matrix: List[List[Optional[float]]]
    high_correlations: List[CorrelationPairOut]


class SectorExposureOut(BaseModel):
    sector: str
    gross_value: Decimal
    net_value: Decimal
    pct_of_nav: Decimal
    position_count: int
    assets: List[str]


class ConcentrationOut(BaseModel):
    herfindahl_index: float
    top_1_pct: Decimal
    top_3_pct: Decimal
    top_5_pct: Decimal
    effective_positions: float


class ExposureAnalysisOut(BaseModel):
    total_nav: Decimal
    gross_exposure: Decimal
    net_exposure: Decimal
    leverage_ratio: Decimal
    long_exposure: Decimal
    short_exposure: Decimal
    long_short_ratio: Optional[Decimal] = None
    sectors: List[SectorExposureOut]
    concentration: ConcentrationOut


class PnLWaterfallOut(BaseModel):
    gross_trading_pnl: Decimal
    total_commission: Decimal
    total_funding: Decimal
    total_slippage: Decimal
    net_trading_pnl: Decimal
    management_fee: Decimal
    performance_fee: Decimal
    net_portfolio_pnl: Decimal
    commission_drag_bps: Optional[float] = None
    funding_drag_bps: Optional[float] = None
    slippage_drag_bps: Optional[float] = None
    total_cost_ratio: Optional[float] = None
    winning_trades: int
    losing_trades: int
    total_notional_traded: Decimal


class SlippageByGroupOut(BaseModel):
    group: str
    avg_slippage_bps: float
    trade_count: int


class SlippageStatsOut(BaseModel):
    total_slippage_cost: Decimal
    avg_slippage_per_trade: Optional[Decimal] = None
    avg_slippage_bps: Optional[float] = None
    slippage_by_venue: List[SlippageByGroupOut]
    slippage_by_order_type: List[SlippageByGroupOut]
    worst_slippage_trade: Optional[str] = None
    trades_with_slippage_data: int
    trades_without_slippage_data: int


# ── Performance tab redesign (replaces Institutional) ──

class AssetPerformanceRowOut(BaseModel):
    symbol: str
    total_trades: int
    open_trades: int
    closed_trades: int
    total_invested: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_pnl: Decimal
    current_value: Decimal
    return_pct: Decimal
    contribution_pct: Decimal


class PerCoinRowOut(BaseModel):
    symbol: str
    trades: int
    wins: int
    win_rate: Decimal
    total_pnl: Decimal
    avg_pnl: Decimal
    avg_hold_seconds: float
    best_pnl: Decimal
    worst_pnl: Decimal


class StaticRiskMetricsOut(BaseModel):
    sharpe: Optional[float] = None
    sortino: Optional[float] = None
    calmar: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    var_95: Optional[float] = None
    var_99: Optional[float] = None
    annualized_return: Optional[float] = None
    annualized_volatility: Optional[float] = None
    downside_deviation: Optional[float] = None
    skewness: Optional[float] = None
    kurtosis: Optional[float] = None
    best_day_pct: Optional[float] = None
    worst_day_pct: Optional[float] = None


class RollingPointOut(BaseModel):
    date: date_cls
    value: float


class RiskMetricsOut(BaseModel):
    static: StaticRiskMetricsOut
    rolling_sharpe_30d: List[RollingPointOut]
    rolling_volatility_30d: List[RollingPointOut]
    sample_size: int
