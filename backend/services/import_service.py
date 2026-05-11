import csv
import io
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from backend.models import (
    Direction,
    ExecutionVenue,
    MakerTaker,
    Order,
    OrderStatus,
    OrderType,
    Portfolio,
    Side,
    Strategy,
    SubAccount,
    SubAccountType,
    Tag,
)


# Phase 2 Step 10: extended CSV. Old templates without the new columns still
# parse — every new column is optional.
CSV_COLUMNS = [
    "datetime", "asset", "side", "quantity", "price",
    "fee", "sub_account", "leverage", "direction", "note",
    # Phase 2 enrichment
    "order_type", "venue", "exchange_order_id",
    "expected_price", "fee_currency", "maker_taker",
    "strategy", "tags",
]

CSV_TEMPLATE = (
    "datetime,asset,side,quantity,price,fee,sub_account,leverage,direction,note,"
    "order_type,venue,exchange_order_id,expected_price,fee_currency,maker_taker,"
    "strategy,tags\n"
    "2026-01-15 10:30:00,BTC,BUY,0.05,42500.00,2.13,Spot Main,,,DCA buy,"
    "LIMIT,BINANCE_SPOT,12345678,42600,USDT,MAKER,DCA Core,dca;weekly\n"
    "2026-01-20 14:00:00,BTC,SELL,0.03,44200.00,1.33,Spot Main,,,Take profit,"
    "MARKET,BINANCE_SPOT,12345679,,USDT,TAKER,DCA Core,take-profit\n"
    "2026-02-01 09:00:00,ETH,BUY,10,2250.00,2.25,Futures Hedge,5,LONG,Breakout entry,"
    "STOP_LIMIT,BINANCE_FUTURES,99887766,2240,USDT,MAKER,ETH Momentum,breakout;high-conviction\n"
)


@dataclass
class ImportError:
    row: int  # 1-indexed (matches editor row numbers; header is row 1)
    message: str


@dataclass
class ImportResult:
    rows_processed: int
    orders_created: int
    errors: List[ImportError] = field(default_factory=list)


@dataclass
class _Row:
    raw_index: int  # 1-indexed source row (header excluded)
    when: datetime
    asset: str
    side: Side
    quantity: Decimal
    price: Decimal
    fee: Decimal
    sub_account_name: str
    leverage: Optional[int]
    direction: Optional[Direction]
    note: Optional[str]
    # Phase 2 enrichment (all optional)
    order_type: Optional[OrderType] = None
    venue: Optional[ExecutionVenue] = None
    exchange_order_id: Optional[str] = None
    expected_price: Optional[Decimal] = None
    fee_currency: Optional[str] = None
    maker_taker: Optional[MakerTaker] = None
    strategy_name: Optional[str] = None
    tag_names: List[str] = field(default_factory=list)


_DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
)


def _parse_datetime(s: str) -> datetime:
    s = s.strip()
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return datetime.fromisoformat(s)


def _parse_decimal(s: str, field: str) -> Decimal:
    s = (s or "").strip()
    if not s:
        raise ValueError(f"{field} is required")
    try:
        return Decimal(s)
    except InvalidOperation:
        raise ValueError(f"{field} '{s}' is not a number")


def _parse_optional_decimal(s: Optional[str]) -> Decimal:
    if s is None or str(s).strip() == "":
        return Decimal("0")
    return Decimal(str(s))


def _parse_row(idx: int, raw: Dict[str, Optional[str]]) -> _Row:
    when_raw = raw.get("datetime") or ""
    when = _parse_datetime(when_raw) if when_raw else (_ for _ in ()).throw(ValueError("datetime is required"))

    side_raw = (raw.get("side") or "").strip().upper()
    if side_raw not in ("BUY", "SELL"):
        raise ValueError(f"side must be BUY or SELL, got '{side_raw}'")

    direction_raw = (raw.get("direction") or "").strip().upper()
    direction = Direction(direction_raw) if direction_raw else None

    leverage_raw = (raw.get("leverage") or "").strip()
    leverage = int(leverage_raw) if leverage_raw else None
    if leverage is not None and leverage < 1:
        raise ValueError(f"leverage must be >= 1, got {leverage}")

    # Phase 2 optional columns
    def _enum_or_none(s, cls):
        s = (s or "").strip().upper()
        return cls(s) if s else None

    order_type    = _enum_or_none(raw.get("order_type"), OrderType)
    venue         = _enum_or_none(raw.get("venue"), ExecutionVenue)
    maker_taker   = _enum_or_none(raw.get("maker_taker"), MakerTaker)
    exch_order_id = (raw.get("exchange_order_id") or "").strip() or None
    expected_raw  = (raw.get("expected_price") or "").strip()
    expected_price = Decimal(expected_raw) if expected_raw else None
    fee_currency  = (raw.get("fee_currency") or "").strip() or None
    strategy_name = (raw.get("strategy") or "").strip() or None
    tags_raw      = (raw.get("tags") or "").strip()
    tag_names = [t.strip() for t in tags_raw.split(";") if t.strip()] if tags_raw else []

    return _Row(
        raw_index=idx,
        when=when,
        asset=(raw.get("asset") or "").strip().upper() or (_ for _ in ()).throw(ValueError("asset is required")),
        side=Side(side_raw),
        quantity=_parse_decimal(raw.get("quantity") or "", "quantity"),
        price=_parse_decimal(raw.get("price") or "", "price"),
        fee=_parse_optional_decimal(raw.get("fee")),
        sub_account_name=(raw.get("sub_account") or "").strip() or (_ for _ in ()).throw(ValueError("sub_account is required")),
        leverage=leverage,
        direction=direction,
        note=(raw.get("note") or None),
        order_type=order_type,
        venue=venue,
        exchange_order_id=exch_order_id,
        expected_price=expected_price,
        fee_currency=fee_currency,
        maker_taker=maker_taker,
        strategy_name=strategy_name,
        tag_names=tag_names,
    )


class _FifoTracker:
    """Tracks open buys per (sub_account_id, asset, direction) for FIFO sell matching.

    Holds (Order, remaining_qty) pairs. Mutating remaining_qty here mirrors what
    will be persisted on the linked buy after the sell is committed.
    """

    def __init__(self, db: Session) -> None:
        self._queues: Dict[Tuple[str, str, Optional[str]], List[List]] = {}
        self._db = db

    def hydrate(self, sub: SubAccount) -> None:
        rows = (
            self._db.query(Order)
            .filter(Order.sub_account_id == sub.id)
            .filter(Order.side == Side.BUY)
            .filter(Order.status != OrderStatus.CLOSED)
            .filter(Order.remaining_quantity > 0)
            .order_by(Order.datetime)
            .all()
        )
        for o in rows:
            self.push(o)

    def push(self, order: Order) -> None:
        key = (
            order.sub_account_id,
            order.asset,
            order.direction.value if order.direction else None,
        )
        self._queues.setdefault(key, []).append([order, Decimal(order.remaining_quantity)])

    def consume(
        self,
        sub_id: str,
        asset: str,
        sell_qty: Decimal,
        direction: Optional[Direction],
    ) -> List[Tuple[Order, Decimal]]:
        # Try the explicit direction first; if empty, fall back to any direction.
        candidate_keys: List[Tuple[str, str, Optional[str]]] = []
        if direction is not None:
            candidate_keys.append((sub_id, asset, direction.value))
        else:
            candidate_keys.extend([
                (sub_id, asset, None),
                (sub_id, asset, "LONG"),
            ])

        out: List[Tuple[Order, Decimal]] = []
        remaining = Decimal(sell_qty)
        for key in candidate_keys:
            queue = self._queues.get(key, [])
            while remaining > 0 and queue:
                head = queue[0]
                buy_order, buy_remain = head
                take = min(buy_remain, remaining)
                out.append((buy_order, take))
                head[1] = buy_remain - take
                remaining -= take
                if head[1] == 0:
                    queue.pop(0)
            if remaining == 0:
                break
        if remaining > 0:
            raise ValueError(
                f"sell exceeds available open quantity for {asset} (short by {remaining})"
            )
        return out


class ImportService:
    def __init__(self, db: Session) -> None:
        self._db = db

    @staticmethod
    def csv_template() -> str:
        return CSV_TEMPLATE

    def import_csv(self, portfolio_id: str, content: str, dry_run: bool = False) -> ImportResult:
        reader = csv.DictReader(io.StringIO(content))
        rows = [r for r in reader]
        return self._process(portfolio_id, rows, dry_run=dry_run)

    def import_json(self, portfolio_id: str, rows: List[dict], dry_run: bool = False) -> ImportResult:
        return self._process(portfolio_id, rows, dry_run=dry_run)

    def _process(
        self,
        portfolio_id: str,
        rows: List[dict],
        dry_run: bool = False,
    ) -> ImportResult:
        portfolio = self._db.get(Portfolio, portfolio_id)
        if portfolio is None:
            raise ValueError(f"Portfolio {portfolio_id} not found")
        sub_by_name = {s.name: s for s in portfolio.sub_accounts}

        # Strategy + tag lookups (auto-create on demand for convenience)
        strategies_by_name = {s.name: s for s in self._db.query(Strategy).all()}
        tags_by_name = {t.name: t for t in self._db.query(Tag).all()}

        def _resolve_strategy(name):
            if not name:
                return None
            existing = strategies_by_name.get(name)
            if existing is not None:
                return existing
            new_strategy = Strategy(name=name)
            self._db.add(new_strategy)
            self._db.flush()
            strategies_by_name[name] = new_strategy
            return new_strategy

        def _resolve_tags(names):
            out = []
            for n in names:
                t = tags_by_name.get(n)
                if t is None:
                    t = Tag(name=n)
                    self._db.add(t)
                    self._db.flush()
                    tags_by_name[n] = t
                out.append(t)
            return out

        self._resolve_strategy = _resolve_strategy
        self._resolve_tags = _resolve_tags

        parsed: List[_Row] = []
        errors: List[ImportError] = []

        for i, raw in enumerate(rows):
            row_num = i + 2  # 1 = header line in editor
            try:
                parsed.append(_parse_row(row_num, raw))
            except Exception as exc:
                errors.append(ImportError(row=row_num, message=str(exc)))

        # Process chronologically — required for FIFO correctness
        parsed.sort(key=lambda r: r.when)

        # Hydrate FIFO trackers for all sub-accounts referenced
        fifo = _FifoTracker(self._db)
        for sub in portfolio.sub_accounts:
            fifo.hydrate(sub)

        created = 0
        for r in parsed:
            sub = sub_by_name.get(r.sub_account_name)
            if sub is None:
                errors.append(ImportError(
                    row=r.raw_index,
                    message=f"sub_account '{r.sub_account_name}' not found in portfolio",
                ))
                continue

            try:
                if r.side == Side.BUY:
                    order = self._build_buy(sub, r)
                    self._db.add(order)
                    self._db.flush()
                    fifo.push(order)
                    created += 1
                else:
                    matches = fifo.consume(sub.id, r.asset, r.quantity, r.direction)
                    for buy, sell_qty in matches:
                        sell_order = self._build_sell(sub, buy, sell_qty, r)
                        self._db.add(sell_order)
                        # Mirror state on the buy (the FIFO already deducted)
                        buy.remaining_quantity = Decimal(buy.remaining_quantity) - sell_qty
                        buy.status = (
                            OrderStatus.CLOSED if Decimal(buy.remaining_quantity) == 0
                            else OrderStatus.PARTIALLY_CLOSED
                        )
                        created += 1
                    self._db.flush()
            except Exception as exc:
                errors.append(ImportError(row=r.raw_index, message=str(exc)))

        if dry_run or errors:
            self._db.rollback()
            if errors and not dry_run:
                # Atomic-ish: any error rolls back the whole import.
                created = 0
        else:
            self._db.commit()

        return ImportResult(
            rows_processed=len(rows),
            orders_created=created,
            errors=errors,
        )

    def _build_buy(self, sub: SubAccount, r: _Row) -> Order:
        from backend.calculators.futures_calc import calc_liquidation_price, calc_margin_used
        from backend.services.asset_service import AssetService

        # Auto-register the asset (idempotent; default sources attached on first ensure).
        AssetService(self._db).ensure_asset(r.asset)

        leverage = direction = margin = liq = funding = None
        if sub.type == SubAccountType.FUTURES:
            if r.leverage is None:
                raise ValueError("futures BUY requires `leverage`")
            if r.direction is None:
                raise ValueError("futures BUY requires `direction` (LONG or SHORT)")
            leverage = r.leverage
            direction = r.direction
            margin = calc_margin_used(r.quantity, r.price, leverage)
            liq = calc_liquidation_price(r.price, leverage, direction)
            funding = Decimal("0")

        strat = self._resolve_strategy(r.strategy_name)
        slippage = (r.price - r.expected_price) if r.expected_price else None

        order = Order(
            sub_account_id=sub.id,
            datetime=r.when,
            asset=r.asset,
            side=Side.BUY,
            quantity=r.quantity,
            price=r.price,
            total_value=r.price * r.quantity,
            fee=r.fee,
            note=r.note,
            leverage=leverage,
            direction=direction,
            margin_used=margin,
            liquidation_price=liq,
            funding_accumulated=funding,
            status=OrderStatus.OPEN,
            remaining_quantity=r.quantity,
            # Phase 2
            strategy_id=strat.id if strat else None,
            order_type=r.order_type,
            execution_venue=r.venue,
            exchange_order_id=r.exchange_order_id,
            expected_price=r.expected_price,
            slippage=slippage,
            fee_currency=r.fee_currency,
            maker_taker=r.maker_taker,
        )
        if r.tag_names:
            order.tags = self._resolve_tags(r.tag_names)
        return order

    def _build_sell(
        self, sub: SubAccount, buy: Order, sell_qty: Decimal, r: _Row,
    ) -> Order:
        # When a single CSV sell row is FIFO-split across multiple open buys, the
        # row's fee is pro-rated across the resulting sell orders so the total
        # charged equals the user's input.
        row_qty = Decimal(r.quantity)
        fee_share = (Decimal(r.fee) * sell_qty / row_qty) if row_qty > 0 else Decimal(r.fee)

        strat = self._resolve_strategy(r.strategy_name) if r.strategy_name else None
        slippage = (r.price - r.expected_price) if r.expected_price else None

        sell = Order(
            sub_account_id=sub.id,
            datetime=r.when,
            asset=r.asset,
            side=Side.SELL,
            quantity=sell_qty,
            price=r.price,
            total_value=r.price * sell_qty,
            fee=fee_share,
            note=r.note,
            linked_buy_order_id=buy.id,
            sell_quantity=sell_qty,
            status=OrderStatus.CLOSED,
            remaining_quantity=Decimal("0"),
            # Phase 2 — sell inherits buy's strategy if not overridden
            strategy_id=(strat.id if strat else buy.strategy_id),
            order_type=r.order_type,
            execution_venue=r.venue,
            exchange_order_id=r.exchange_order_id,
            expected_price=r.expected_price,
            slippage=slippage,
            fee_currency=r.fee_currency,
            maker_taker=r.maker_taker,
        )
        if r.tag_names:
            sell.tags = self._resolve_tags(r.tag_names)
        return sell

    # ---------------- Export ----------------

    EXPORT_COLUMNS = CSV_COLUMNS + ["status", "remaining_quantity"]

    def export_csv(self, portfolio_id: str) -> str:
        portfolio = self._db.get(Portfolio, portfolio_id)
        if portfolio is None:
            raise ValueError(f"Portfolio {portfolio_id} not found")
        sub_by_id = {s.id: s for s in portfolio.sub_accounts}
        sub_ids = list(sub_by_id.keys())
        orders = (
            self._db.query(Order)
            .filter(Order.sub_account_id.in_(sub_ids))
            .order_by(Order.datetime)
            .all() if sub_ids else []
        )

        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(self.EXPORT_COLUMNS)
        for o in orders:
            writer.writerow([
                o.datetime.strftime("%Y-%m-%d %H:%M:%S"),
                o.asset,
                o.side.value,
                str(o.quantity),
                str(o.price),
                str(o.fee),
                sub_by_id[o.sub_account_id].name,
                str(o.leverage) if o.leverage is not None else "",
                o.direction.value if o.direction is not None else "",
                o.note or "",
                # Phase 2 columns
                o.order_type.value if o.order_type is not None else "",
                o.execution_venue.value if o.execution_venue is not None else "",
                o.exchange_order_id or "",
                str(o.expected_price) if o.expected_price is not None else "",
                o.fee_currency or "",
                o.maker_taker.value if o.maker_taker is not None else "",
                o.strategy.name if o.strategy is not None else "",
                ";".join(t.name for t in o.tags) if o.tags else "",
                # appended status fields
                o.status.value if o.status is not None else "",
                str(o.remaining_quantity) if o.remaining_quantity is not None else "",
            ])
        return out.getvalue()
