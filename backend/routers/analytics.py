from fastapi import APIRouter
from database import get_analytics_daily

router = APIRouter()

@router.get("/analytics")
def get_analytics():
    return {"daily": get_analytics_daily()}
