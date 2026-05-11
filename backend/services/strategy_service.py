from typing import List, Optional

from sqlalchemy.orm import Session

from backend.models import Strategy


class StrategyService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(
        self,
        name: str,
        description: Optional[str] = None,
        color: Optional[str] = None,
    ) -> Strategy:
        existing = self._db.query(Strategy).filter(Strategy.name == name).one_or_none()
        if existing is not None:
            raise ValueError(f"Strategy '{name}' already exists")
        strategy = Strategy(name=name, description=description, color=color)
        self._db.add(strategy)
        self._db.commit()
        self._db.refresh(strategy)
        return strategy

    def list_all(self, active_only: bool = True) -> List[Strategy]:
        q = self._db.query(Strategy)
        if active_only:
            q = q.filter(Strategy.is_active.is_(True))
        return list(q.order_by(Strategy.name).all())

    def get(self, strategy_id: str) -> Optional[Strategy]:
        return self._db.get(Strategy, strategy_id)

    def update(
        self,
        strategy_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Strategy:
        strategy = self._db.get(Strategy, strategy_id)
        if strategy is None:
            raise ValueError(f"Strategy {strategy_id} not found")
        if name is not None:        strategy.name = name
        if description is not None: strategy.description = description or None
        if color is not None:       strategy.color = color or None
        if is_active is not None:   strategy.is_active = is_active
        self._db.commit()
        self._db.refresh(strategy)
        return strategy

    def delete(self, strategy_id: str) -> None:
        """Strategies aren't cascaded — orders keep their dangling strategy_id
        which the UI will render as "(deleted strategy)" or just blank. If you
        want to recover the name, deactivate instead of delete."""
        strategy = self._db.get(Strategy, strategy_id)
        if strategy is None:
            raise ValueError(f"Strategy {strategy_id} not found")
        # Null-out the FK on any orders pointing at this strategy so we don't
        # leave dangling references.
        from backend.models import Order
        (
            self._db.query(Order)
            .filter(Order.strategy_id == strategy_id)
            .update({Order.strategy_id: None}, synchronize_session=False)
        )
        self._db.delete(strategy)
        self._db.commit()
