from fastapi import APIRouter
from pydantic import BaseModel
from database import get_user_profile, update_user_profile

router = APIRouter(prefix="/api/v1")

class ProfileUpdate(BaseModel):
    name: str
    budget_goal: float
    primary_goal: str
    household_size: int
    daily_schedule: str

@router.get("/profile")
def get_profile():
    return get_user_profile()

@router.post("/profile")
def post_profile(body: ProfileUpdate):
    return update_user_profile(body.dict())
