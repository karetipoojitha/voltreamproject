from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import list_devices, update_device_status

router = APIRouter()

class DeviceStatusUpdate(BaseModel):
    status: bool

@router.get("/devices")
def get_devices():
    return list_devices()

@router.patch("/devices/{device_id}")
def patch_device(device_id: int, body: DeviceStatusUpdate):
    if not update_device_status(device_id, body.status):
        raise HTTPException(status_code=404, detail="Device not found")
    return {"ok": True}
