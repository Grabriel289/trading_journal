from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.dependencies import get_deposit_service
from backend.api.schemas import DepositCreate, DepositOut
from backend.models.enums import DepositType
from backend.services.deposit_service import DepositInput, DepositService

router = APIRouter(prefix="/api/deposits", tags=["deposits"])


@router.post("", response_model=DepositOut)
def create_deposit(
    body: DepositCreate,
    service: DepositService = Depends(get_deposit_service),
):
    try:
        deposit = service.create(
            DepositInput(
                sub_account_id=body.sub_account_id,
                amount=body.amount,
                type=body.type,
                note=body.note,
                when=body.when,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return deposit


@router.get("", response_model=List[DepositOut])
def list_deposits(
    sub_account_id: Optional[str] = Query(default=None),
    type: Optional[DepositType] = Query(default=None),
    service: DepositService = Depends(get_deposit_service),
):
    return service.list(sub_account_id=sub_account_id, type=type)


@router.delete("/{deposit_id}", status_code=204)
def delete_deposit(
    deposit_id: str,
    service: DepositService = Depends(get_deposit_service),
):
    try:
        service.delete(deposit_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
