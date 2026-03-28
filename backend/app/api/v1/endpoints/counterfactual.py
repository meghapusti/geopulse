"""
Counterfactual 'what if' endpoint.
User sends a hypothetical tension level for a region → model returns
how market predictions would shift vs current actual tension.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.schemas import CounterfactualRequest, CounterfactualResponse
from app.signals.predictors.lgbm_predictor import LGBMPredictor

router = APIRouter()
_predictor = LGBMPredictor()


@router.post("", response_model=CounterfactualResponse)
async def counterfactual(
    req: CounterfactualRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await _predictor.predict_counterfactual(
        region_code=req.region_code,
        tension_override=req.tension_override,
        horizon_hours=req.horizon_hours,
        db=db,
    )
    return result
