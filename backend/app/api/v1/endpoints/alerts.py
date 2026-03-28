"""Alerts endpoint."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import Alert
from app.schemas.schemas import AlertOut, AlertSubscribeRequest

router = APIRouter()


@router.get("", response_model=list[AlertOut])
async def get_alerts(
    severity: str | None = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Alert).order_by(Alert.created_at.desc()).limit(limit)
    if severity:
        stmt = stmt.where(Alert.severity == severity)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/subscribe")
async def subscribe(req: AlertSubscribeRequest):
    # TODO: store subscription in DB and wire to Resend
    return {"status": "subscribed", "email": req.email}
