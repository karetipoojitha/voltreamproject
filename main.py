from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


dashboard_data = {
    "grid_power": 4.8,
    "solar_generation": 3.2,
    "net_consumption": 1.6
}

analytics_data = {
    "daily": [
        {"day": "Mon", "usage": 12},
        {"day": "Tue", "usage": 15},
        {"day": "Wed", "usage": 10},
        {"day": "Thu", "usage": 18},
        {"day": "Fri", "usage": 14},
        {"day": "Sat", "usage": 20},
        {"day": "Sun", "usage": 16},
    ],
    "weekly": [
        {"week": "Week 1", "usage": 110},
        {"week": "Week 2", "usage": 125},
        {"week": "Week 3", "usage": 118},
        {"week": "Week 4", "usage": 140},
    ],
    "monthly": [
        {"month": "Jan", "usage": 420},
        {"month": "Feb", "usage": 390},
        {"month": "Mar", "usage": 450},
        {"month": "Apr", "usage": 480},
    ]
}

devices = [
    {"id": 1, "name": "Air Conditioner", "status": True},
    {"id": 2, "name": "Ceiling Fan", "status": False},
    {"id": 3, "name": "Washing Machine", "status": True},
]

billing_data = {
    "current_bill": 2450,
    "projected_bill": 3200,
    "budget_alert": "Warning: You are nearing your monthly budget."
}


class DeviceUpdate(BaseModel):
    status: bool


@app.get("/")
def home():
    return {"message": "VoltStream Backend Running"}

@app.get("/dashboard")
def get_dashboard():
    return dashboard_data

@app.get("/analytics")
def get_analytics():
    return analytics_data

@app.get("/devices")
def get_devices():
    return devices

@app.patch("/devices/{device_id}")
def update_device(device_id: int, update: DeviceUpdate):
    for device in devices:
        if device["id"] == device_id:
            device["status"] = update.status
            return {
                "message": f"{device['name']} updated successfully",
                "device": device
            }

    return {"error": "Device not found"}

@app.get("/billing")
def get_billing():
    return billing_data