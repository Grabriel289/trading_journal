from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.calculators.futures_calc import (
    calc_futures_raw_pnl,
    calc_unrealized_futures_pnl,
)
from backend.calculators.spot_calc import calc_position_value, calc_unrealized_pnl
from backend.models import (
    BaseCurrency,
    Deposit,
    DepositType,
    Direction,
    Order,
    OrderStatus,
    Portfolio,
    Side,
    SubAccount,
    SubAccountType,
)
from backend.services.price_service import PriceService


@dataclass
class OpenPosition:
    order_id: str
    asset: str
    quantity: Decimal
    entry_price: Decimal
    current_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    # Futures-only metadata (None for spot)
    leverage: Optional[int] = None
    direction: Optional[Direction] = None
    margin_locked: Optional[Decimal] = None
    liquidation_price: Optional[Decimal] = None
    funding_accumulated: Optional[Decimal] = None
    # Price freshness/source signal (None = couldn't fetch, fell back to entry)
    price_status: Optional[str] = None
    price_source: Optional[str] = None


@dataclass
class SubAccountOverview:
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
    open_positions: List[OpenPosition]


@dataclass
class PortfolioOverview:
    id: str
    name: str
    base_currency: BaseCurrency
    total_balance: Decimal
    total_market_value: Decimal
    total_equity: Decimal
    total_unrealized_pnl: Decimal
    total_deposited: Decimal  # cumulative deposits - withdrawals + initial capital
    open_trades: int
    sub_accounts: List[SubAccountOverview]


class PortfolioService:
    def __init__(self, db: Session, price_service: PriceService) -> None:
        self._db = db
        self._prices = price_service

    def create_portfolio(
        self,
        name: str,
        base_currency: BaseCurrency = BaseCurrency.USDT,
        *,
        inception_date=None,
        benchmark: Optional[str] = None,
        management_fee_rate: Optional[Decimal] = None,
        performance_fee_rate: Optional[Decimal] = None,
        description: Optional[str] = None,
    ) -> Portfolio:
        portfolio = Portfolio(
            name=name, base_currency=base_currency,
            inception_date=inception_date,
            benchmark=benchmark,
            management_fee_rate=management_fee_rate,
            performance_fee_rate=performance_fee_rate,
            description=description,
        )
        self._db.add(portfolio)
        self._db.commit()
        self._db.refresh(portfolio)
        return portfolio

    def add_sub_account(
        self,
        portfolio_id: str,
        name: str,
        type: SubAccountType,
        initial_capital: Decimal,
    ) -> SubAccount:
        portfolio = self._db.get(Portfolio, portfolio_id)
        if portfolio is None:
            raise ValueError(f"Portfolio {portfolio_id} not found")
        sub = SubAccount(
            portfolio_id=portfolio_id,
            name=name,
            type=type,
            initial_capital=initial_capital,
        )
        self._db.add(sub)
        self._db.commit()
        self._db.refresh(sub)
        return sub

    def list_portfolios(self) -> List[Portfolio]:
        return list(self._db.query(Portfolio).order_by(Portfolio.created_at).all())

    def get_portfolio(self, portfolio_id: str) -> Optional[Portfolio]:
        return self._db.get(Portfolio, portfolio_id)

    def update_portfolio(
        self,
        portfolio_id: str,
        *,
        name: Optional[str] = None,
        base_currency: Optional[BaseCurrency] = None,
        inception_date=None,
        benchmark: Optional[str] = None,
        management_fee_rate: Optional[Decimal] = None,
        performance_fee_rate: Optional[Decimal] = None,
        description: Optional[str] = None,
    ) -> Portfolio:
        portfolio = self._db.get(Portfolio, portfolio_id)
        if portfolio is None:
            raise ValueError(f"Portfolio {portfolio_id} not found")
        if name is not None:                portfolio.name = name
        if base_currency is not None:       portfolio.base_currency = base_currency
        if inception_date is not None:      portfolio.inception_date = inception_date
        if benchmark is not None:           portfolio.benchmark = benchmark or None
        if management_fee_rate is not None: portfolio.management_fee_rate = management_fee_rate
        if performance_fee_rate is not None: portfolio.performance_fee_rate = performance_fee_rate
        if description is not None:         portfolio.description = description or None
        self._db.commit()
        self._db.refresh(portfolio)
        return portfolio

    def delete_portfolio(self, portfolio_id: str) -> None:
        portfolio = self._db.get(Portfolio, portfolio_id)
        if portfolio is None:
            raise ValueError(f"Portfolio {portfolio_id} not found")
        self._db.delete(portfolio)
        self._db.commit()

    def update_sub_account(
        self,
        sub_account_id: str,
        *,
        name: Optional[str] = None,
        initial_capital: Optional[Decimal] = None,
    ) -> SubAccount:
        sub = self._db.get(SubAccount, sub_account_id)
        if sub is None:
            raise ValueError(f"SubAccount {sub_account_id} not found")
        if name is not None:
            sub.name = name
        if initial_capital is not None:
            sub.initial_capital = Decimal(initial_capital)
        self._db.commit()
        self._db.refresh(sub)
        return sub

    def delete_sub_account(self, sub_account_id: str) -> None:
        sub = self._db.get(SubAccount, sub_account_id)
        if sub is None:
            raise ValueError(f"SubAccount {sub_account_id} not found")
        self._db.delete(sub)
        self._db.commit()

    def wipe_portfolio_data(self, portfolio_id: str) -> dict:
        """Remove all orders, deposits, and equity snapshots for a portfolio,
        but keep the portfolio + its sub-accounts intact."""
        from backend.models import Deposit, EquitySnapshot

        portfolio = self._db.get(Portfolio, portfolio_id)
        if portfolio is None:
            raise ValueError(f"Portfolio {portfolio_id} not found")

        sub_ids = [s.id for s in portfolio.sub_accounts]
        orders = 0
        deposits = 0
        if sub_ids:
            orders = (
                self._db.query(Order)
                .filter(Order.sub_account_id.in_(sub_ids))
                .delete(synchronize_session=False)
            )
            deposits = (
                self._db.query(Deposit)
                .filter(Deposit.sub_account_id.in_(sub_ids))
                .delete(synchronize_session=False)
            )
        snapshots = (
            self._db.query(EquitySnapshot)
            .filter(EquitySnapshot.portfolio_id == portfolio_id)
            .delete(synchronize_session=False)
        )
        self._db.commit()
        return {
            "orders_deleted": orders,
            "deposits_deleted": deposits,
            "snapshots_deleted": snapshots,
        }

    async def get_overview(self, portfolio_id: str) -> PortfolioOverview:
        portfolio = self._db.get(Portfolio, portfolio_id)
        if portfolio is None:
            raise ValueError(f"Portfolio {portfolio_id} not found")

        base = portfolio.base_currency.value
        sub_overviews: List[SubAccountOverview] = []
        total_balance = Decimal("0")
        total_market_value = Decimal("0")
        total_unrealized = Decimal("0")
        total_deposited = Decimal("0")
        open_trades = 0

        for sub in portfolio.sub_accounts:
            cash = Decimal(sub.initial_capital)

            deposits_in = Decimal("0")
            withdrawals_out = Decimal("0")
            for d in sub.deposits:
                amt = Decimal(d.amount)
                if d.type == DepositType.DEPOSIT:
                    deposits_in += amt
                else:
                    withdrawals_out += amt
            cash += deposits_in - withdrawals_out

            orders = (
                self._db.query(Order)
                .filter(Order.sub_account_id == sub.id)
                .order_by(Order.datetime)
                .all()
            )
            order_by_id = {o.id: o for o in orders}

            open_positions: List[OpenPosition] = []
            sub_market_value = Decimal("0")
            sub_unrealized = Decimal("0")

            for order in orders:
                if order.side == Side.BUY:
                    is_futures = order.direction is not None
                    if is_futures:
                        margin = Decimal(order.margin_used or 0)
                        cash -= margin + Decimal(order.fee)
                    else:
                        cash -= Decimal(order.total_value) + Decimal(order.fee)

                    if order.status != OrderStatus.CLOSED and Decimal(order.remaining_quantity) > 0:
                        # Use the provider-aware quote so an unknown token / API
                        # outage doesn't crash the dashboard. Fall back to entry
                        # price (zero unrealized) when no price is available.
                        try:
                            quote = await self._prices.get_quote(order.asset, base)
                        except Exception:
                            quote = None
                        if quote is not None and quote.price is not None:
                            current_price = Decimal(quote.price)
                            price_status = quote.status
                            price_source = quote.source
                        else:
                            current_price = Decimal(order.price)  # cost-basis fallback
                            price_status = "DISCONNECTED"
                            price_source = None
                        qty = Decimal(order.remaining_quantity)
                        total_qty = Decimal(order.quantity)
                        share = qty / total_qty if total_qty > 0 else Decimal("0")

                        if is_futures:
                            margin_remaining = Decimal(order.margin_used or 0) * share
                            funding_share = Decimal(order.funding_accumulated or 0) * share
                            unrealized = calc_unrealized_futures_pnl(
                                entry_price=Decimal(order.price),
                                current_price=current_price,
                                quantity=qty,
                                direction=order.direction,
                                funding_accumulated=funding_share,
                            )
                            # Equity contribution of an open futures position =
                            # locked margin you can recover + mark-to-market PnL.
                            market_value = margin_remaining + unrealized
                            open_positions.append(
                                OpenPosition(
                                    order_id=order.id,
                                    asset=order.asset,
                                    quantity=qty,
                                    entry_price=Decimal(order.price),
                                    current_price=current_price,
                                    market_value=market_value,
                                    unrealized_pnl=unrealized,
                                    leverage=order.leverage,
                                    direction=order.direction,
                                    margin_locked=margin_remaining,
                                    liquidation_price=Decimal(order.liquidation_price)
                                        if order.liquidation_price is not None else None,
                                    funding_accumulated=funding_share,
                                    price_status=price_status,
                                    price_source=price_source,
                                )
                            )
                        else:
                            market_value = calc_position_value(current_price, qty)
                            unrealized = calc_unrealized_pnl(
                                entry_price=Decimal(order.price),
                                current_price=current_price,
                                quantity=qty,
                            )
                            open_positions.append(
                                OpenPosition(
                                    order_id=order.id,
                                    asset=order.asset,
                                    quantity=qty,
                                    entry_price=Decimal(order.price),
                                    current_price=current_price,
                                    market_value=market_value,
                                    unrealized_pnl=unrealized,
                                    price_status=price_status,
                                    price_source=price_source,
                                )
                            )
                        sub_market_value += market_value
                        sub_unrealized += unrealized
                        open_trades += 1
                else:  # SELL — closes a buy lot (spot or futures)
                    linked = (
                        order_by_id.get(order.linked_buy_order_id)
                        if order.linked_buy_order_id else None
                    )
                    if linked is not None and linked.direction is not None:
                        sell_qty = Decimal(order.sell_quantity or order.quantity)
                        total_qty = Decimal(linked.quantity)
                        share = sell_qty / total_qty if total_qty > 0 else Decimal("0")
                        margin_share = Decimal(linked.margin_used or 0) * share
                        funding_share = Decimal(linked.funding_accumulated or 0) * share
                        raw_pnl = calc_futures_raw_pnl(
                            entry_price=Decimal(linked.price),
                            exit_price=Decimal(order.price),
                            quantity=sell_qty,
                            direction=linked.direction,
                        )
                        cash += margin_share + raw_pnl - Decimal(order.fee) - funding_share
                    else:
                        cash += Decimal(order.total_value) - Decimal(order.fee)

            sub_equity = cash + sub_market_value
            sub_overviews.append(
                SubAccountOverview(
                    id=sub.id,
                    name=sub.name,
                    type=sub.type,
                    initial_capital=Decimal(sub.initial_capital),
                    deposits_total=deposits_in,
                    withdrawals_total=withdrawals_out,
                    cash=cash,
                    market_value=sub_market_value,
                    equity=sub_equity,
                    unrealized_pnl=sub_unrealized,
                    open_positions=open_positions,
                )
            )
            total_balance += cash
            total_market_value += sub_market_value
            total_unrealized += sub_unrealized
            total_deposited += Decimal(sub.initial_capital) + deposits_in - withdrawals_out

        return PortfolioOverview(
            id=portfolio.id,
            name=portfolio.name,
            base_currency=portfolio.base_currency,
            total_balance=total_balance,
            total_market_value=total_market_value,
            total_equity=total_balance + total_market_value,
            total_unrealized_pnl=total_unrealized,
            total_deposited=total_deposited,
            open_trades=open_trades,
            sub_accounts=sub_overviews,
        )
