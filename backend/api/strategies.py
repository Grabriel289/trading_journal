from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from backend.api.dependencies import get_strategy_service
from backend.services.strategy_service import StrategyService

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


class StrategyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: Optional[str] = None
    color: Optional[str] = Field(default=None, max_length=7)


class StrategyEditRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = None
    color: Optional[str] = Field(default=None, max_length=7)
    is_active: Optional[bool] = None


class StrategyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    is_active: bool
    created_at: datetime


@router.get("", response_model=List[StrategyOut])
def list_strategies(
    active_only: bool = Query(default=True),
    service: StrategyService = Depends(get_strategy_service),
):
    return service.list_all(active_only=active_only)


@router.post("", response_model=StrategyOut, status_code=201)
def create_strategy(
    body: StrategyCreate,
    service: StrategyService = Depends(get_strategy_service),
):
    try:
        return service.create(name=body.name, description=body.description, color=body.color)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{strategy_id}", response_model=StrategyOut)
def update_strategy(
    strategy_id: str,
    body: StrategyEditRequest,
    service: StrategyService = Depends(get_strategy_service),
):
    try:
        return service.update(
            strategy_id,
            name=body.name,
            description=body.description,
            color=body.color,
            is_active=body.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{strategy_id}", status_code=204)
def delete_strategy(
    strategy_id: str,
    service: StrategyService = Depends(get_strategy_service),
):
    try:
        service.delete(strategy_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
