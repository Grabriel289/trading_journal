from datetime import date as date_cls, datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.models import EquitySnapshot
from backend.services.portfolio_service import PortfolioService
from backend.util.clock import utc_now


class SnapshotService:
    def __init__(self, db: Session, portfolio_service: PortfolioService) -> None:
        self._db = db
        self._portfolios = portfolio_service

    async def take_snapshot(
        self,
        portfolio_id: str,
        for_date: Optional[date_cls] = None,
    ) -> EquitySnapshot:
        overview = await self._portfolios.get_overview(portfolio_id)
        snap_date = for_date or utc_now().date()

        prior = (
            self._db.query(EquitySnapshot)
            .filter(EquitySnapshot.portfolio_id == portfolio_id)
            .filter(EquitySnapshot.date < snap_date)
            .order_by(EquitySnapshot.date)
            .all()
        )
        prior_peak = max((Decimal(p.total_equity) for p in prior), default=Decimal("0"))
        peak = max(prior_peak, overview.total_equity)
        drawdown = (
            ((peak - overview.total_equity) / peak * Decimal("100"))
            if peak > 0 else Decimal("0")
        )

        sub_account_data = [
            {
                "id": s.id,
                "name": s.name,
                "type": s.type.value,
                "equity": str(s.equity),
                "cash": str(s.cash),
                "market_value": str(s.market_value),
                "unrealized_pnl": str(s.unrealized_pnl),
            }
            for s in overview.sub_accounts
        ]

        existing = (
            self._db.query(EquitySnapshot)
            .filter(EquitySnapshot.portfolio_id == portfolio_id)
            .filter(EquitySnapshot.date == snap_date)
            .one_or_none()
        )
        if existing is not None:
            existing.total_equity = overview.total_equity
            existing.total_balance = overview.total_balance
            existing.total_deposited = overview.total_deposited
            existing.drawdown_pct = drawdown
            existing.sub_account_data = sub_account_data
            self._db.commit()
            self._db.refresh(existing)
            return existing

        snap = EquitySnapshot(
            portfolio_id=portfolio_id,
            date=snap_date,
            total_equity=overview.total_equity,
            total_balance=overview.total_balance,
            total_deposited=overview.total_deposited,
            drawdown_pct=drawdown,
            sub_account_data=sub_account_data,
        )
        self._db.add(snap)

        # Phase 2 Step 6: bump HWM if today's equity hit a new peak
        from backend.models import NAVRecord, Portfolio
        portfolio = self._db.get(Portfolio, portfolio_id)
        if portfolio is not None and (
            portfolio.high_water_mark is None
            or overview.total_equity > portfolio.high_water_mark
        ):
            portfolio.high_water_mark = overview.total_equity

        # Phase 2 Step 7: NAV record per snapshot
        nav_existing = (
            self._db.query(NAVRecord)
            .filter(NAVRecord.portfolio_id == portfolio_id, NAVRecord.date == snap_date)
            .one_or_none()
        )
        units = Decimal("1")  # single-investor default
        nav_per_unit = overview.total_equity / units if units > 0 else overview.total_equity
        # Exposure: gross = Σ|market_value|, net = Σ signed (short positions reduce net)
        gross_exposure = sum(
            (abs(Decimal(p.market_value)) for s in overview.sub_accounts for p in s.open_positions),
            Decimal("0"),
        )
        net_exposure = sum(
            (
                -Decimal(p.market_value) if (p.direction and p.direction.value == "SHORT")
                else Decimal(p.market_value)
                for s in overview.sub_accounts for p in s.open_positions
            ),
            Decimal("0"),
        )
        if nav_existing is None:
            self._db.add(NAVRecord(
                portfolio_id=portfolio_id, date=snap_date,
                total_nav=overview.total_equity,
                units_outstanding=units, nav_per_unit=nav_per_unit,
                gross_exposure=gross_exposure, net_exposure=net_exposure,
            ))
        else:
            nav_existing.total_nav = overview.total_equity
            nav_existing.nav_per_unit = nav_per_unit
            nav_existing.gross_exposure = gross_exposure
            nav_existing.net_exposure = net_exposure

        self._db.commit()
        self._db.refresh(snap)
        return snap

    def list_snapshots(
        self,
        portfolio_id: str,
        date_from: Optional[date_cls] = None,
        date_to: Optional[date_cls] = None,
    ) -> List[EquitySnapshot]:
        q = (
            self._db.query(EquitySnapshot)
            .filter(EquitySnapshot.portfolio_id == portfolio_id)
        )
        if date_from is not None:
            q = q.filter(EquitySnapshot.date >= date_from)
        if date_to is not None:
            q = q.filter(EquitySnapshot.date <= date_to)
        return list(q.order_by(EquitySnapshot.date).all())
