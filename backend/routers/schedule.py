import re as _re
import threading
from datetime import datetime, timedelta
from fastapi import APIRouter
from pydantic import BaseModel
from database import update_device_status, list_devices

router = APIRouter(prefix="/api/v1")

class ScheduleRequest(BaseModel):
    command: str

def _parse_schedule(command: str):
    """Extract device, action, and time from a scheduled command."""
    t = command.lower().strip()

    # Detect action
    if any(w in t for w in ["turn on", "switch on", "enable"]):
        action = True
    elif any(w in t for w in ["turn off", "switch off", "disable"]):
        action = False
    else:
        return None

    # Detect device
    device_map = {
        "ac": 1, "air conditioning": 1, "air con": 1,
        "fan": 2,
        "washing machine": 3, "washer": 3,
        "living room lights": 4, "lights": 4,
        "kitchen tv": 5, "tv": 5,
        "garage door": 6, "garage": 6,
    }
    device_id = None
    device_name = None
    for key, did in device_map.items():
        if key in t:
            device_id = did
            device_name = key.title()
            break
    if device_id is None:
        return None

    # Detect time — support "10pm", "10:30pm", "22:00", "in 5 minutes"
    time_match = _re.search(r'at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', t, _re.IGNORECASE)
    in_match   = _re.search(r'in\s+(\d+)\s*(minute|min|hour|hr)', t)

    now = datetime.now()
    target_time = None

    if time_match:
        hour   = int(time_match.group(1))
        minute = int(time_match.group(2)) if time_match.group(2) else 0
        period = time_match.group(3)
        if period and period.lower() == "pm" and hour != 12:
            hour += 12
        elif period and period.lower() == "am" and hour == 12:
            hour = 0
        target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target_time <= now:
            target_time += timedelta(days=1)
    elif in_match:
        amount = int(in_match.group(1))
        unit   = in_match.group(2)
        if "hour" in unit or "hr" in unit:
            target_time = now + timedelta(hours=amount)
        else:
            target_time = now + timedelta(minutes=amount)

    if target_time is None:
        return None

    delay_seconds = (target_time - now).total_seconds()
    return {
        "device_id": device_id,
        "device_name": device_name,
        "action": action,
        "target_time": target_time.strftime("%I:%M %p"),
        "delay_seconds": int(delay_seconds),
    }

def _execute_scheduled(device_id: int, state: bool):
    update_device_status(device_id, state)

@router.post("/schedule")
def schedule_command(req: ScheduleRequest):
    parsed = _parse_schedule(req.command)
    if not parsed:
        return {"ok": False, "message": "Could not parse the scheduled command. Try: 'turn off AC at 10pm' or 'turn on fan in 30 minutes'"}

    # Schedule the action
    timer = threading.Timer(
        parsed["delay_seconds"],
        _execute_scheduled,
        args=[parsed["device_id"], parsed["action"]]
    )
    timer.daemon = True
    timer.start()

    action_word = "ON" if parsed["action"] else "OFF"
    return {
        "ok": True,
        "message": f"Scheduled: {parsed['device_name']} will turn {action_word} at {parsed['target_time']}",
        "device_name": parsed["device_name"],
        "action": parsed["action"],
        "target_time": parsed["target_time"],
        "delay_seconds": parsed["delay_seconds"],
    }
