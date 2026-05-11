from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.services.import_service import ImportError as ImportErrorOut, ImportService

router = APIRouter(prefix="/api", tags=["import"])


class ImportErrorOutModel(BaseModel):
    row: int
    message: str


class ImportResultOut(BaseModel):
    rows_processed: int
    orders_created: int
    errors: List[ImportErrorOutModel]


class JsonImportRequest(BaseModel):
    rows: List[dict]


def _result_out(r) -> ImportResultOut:
    return ImportResultOut(
        rows_processed=r.rows_processed,
        orders_created=r.orders_created,
        errors=[ImportErrorOutModel(row=e.row, message=e.message) for e in r.errors],
    )


@router.get("/import/template", response_class=PlainTextResponse)
def get_csv_template() -> str:
    return ImportService.csv_template()


@router.post("/import/csv", response_model=ImportResultOut)
async def import_csv(
    portfolio_id: str = Query(...),
    dry_run: bool = Query(default=False),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="File must be UTF-8") from exc
    service = ImportService(db=db)
    try:
        result = service.import_csv(portfolio_id, text, dry_run=dry_run)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _result_out(result)


@router.post("/import/json", response_model=ImportResultOut)
def import_json(
    body: JsonImportRequest,
    portfolio_id: str = Query(...),
    dry_run: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    service = ImportService(db=db)
    try:
        result = service.import_json(portfolio_id, body.rows, dry_run=dry_run)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _result_out(result)


@router.get("/export/orders.csv", response_class=PlainTextResponse)
def export_orders_csv(
    portfolio_id: str = Query(...),
    db: Session = Depends(get_db),
):
    service = ImportService(db=db)
    try:
        text = service.export_csv(portfolio_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        content=text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="orders.csv"'},
    )
