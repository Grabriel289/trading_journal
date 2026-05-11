from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.models import Deposit, DepositType, SubAccount
from backend.util.clock import utc_now


@dataclass
class DepositInput:
    sub_account_id: str
    amount: Decimal
    type: DepositType
    note: Optional[str] = None
    when: Optional[datetime] = None


class DepositService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, data: DepositInput) -> Deposit:
        sub = self._db.get(SubAccount, data.sub_account_id)
        if sub is None:
            raise ValueError(f"SubAccount {data.sub_account_id} not found")
        if Decimal(data.amount) <= 0:
            raise ValueError("Amount must be positive")

        deposit = Deposit(
            sub_account_id=sub.id,
            datetime=data.when or utc_now(),
            amount=Decimal(data.amount),
            type=data.type,
            note=data.note,
        )
        self._db.add(deposit)
        self._db.commit()
        self._db.refresh(deposit)
        return deposit

    def list(
        self,
        sub_account_id: Optional[str] = None,
        type: Optional[DepositType] = None,
    ) -> List[Deposit]:
        q = self._db.query(Deposit)
        if sub_account_id:
            q = q.filter(Deposit.sub_account_id == sub_account_id)
        if type:
            q = q.filter(Deposit.type == type)
        return list(q.order_by(Deposit.datetime.desc()).all())

    def delete(self, deposit_id: str) -> None:
        deposit = self._db.get(Deposit, deposit_id)
        if deposit is None:
            raise ValueError(f"Deposit {deposit_id} not found")
        self._db.delete(deposit)
        self._db.commit()
