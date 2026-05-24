from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import google.generativeai as genai
from dotenv import load_dotenv

from rag import ask_project_assistant, ask_question, build_db
from agent import router as agent_router
from database import (
    init_db,
    get_dashboard,
    list_devices,
    update_device_status,
    save_chat_messages,
    get_chat_history,
    clear_chat_history,
    get_billing_summary,
    list_billing_history,
    list_billing_transactions,
    get_analytics_daily,
    get_user_profile,
    update_user_profile,
)

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QuestionRequest(BaseModel):
    q: str
    mode: str = "advisor"
    assistant: str = "project"

class DeviceStatusUpdate(BaseModel):
    status: bool

app.include_router(agent_router, prefix="/api/v1", tags=["Agent"])

@app.on_event("startup")
def startup():
    init_db()
    build_db()

@app.get("/")
def home():
    return {"message": "VoltStream Backend Running"}

@app.get("/dashboard")
def dashboard():
    return get_dashboard()

@app.get("/devices")
def devices():
    return list_devices()

@app.patch("/devices/{device_id}")
def patch_device(device_id: int, body: DeviceStatusUpdate):
    if not update_device_status(device_id, body.status):
        raise HTTPException(status_code=404, detail="Device not found")
    return {"ok": True}

@app.get("/billing")
def billing():
    return get_billing_summary()

@app.get("/billing/history")
def billing_history():
    return list_billing_history()

@app.get("/billing/transactions")
def billing_transactions():
    return list_billing_transactions()

@app.get("/analytics")
def analytics():
    return {"daily": get_analytics_daily()}

@app.get("/api/v1/chat/history")
def chat_history(limit: int = 200):
    return {"messages": get_chat_history(limit)}

@app.delete("/api/v1/chat/history")
def delete_chat_history():
    clear_chat_history()
    return {"ok": True}

class ProfileUpdate(BaseModel):
    name: str
    budget_goal: float
    primary_goal: str
    household_size: int
    daily_schedule: str

@app.get("/api/v1/profile")
def get_profile():
    return get_user_profile()

@app.post("/api/v1/profile")
def post_profile(body: ProfileUpdate):
    return update_user_profile(body.dict())

import asyncio as _asyncio
from agent import _run_agent as _adk_run

# Keywords that indicate device control intent
_DEVICE_KEYWORDS = [
    "turn on", "turn off", "switch on", "switch off",
    "enable", "disable", "start", "stop",
    "toggle", "control", "set", "activate", "deactivate",
]

def _is_device_command(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in _DEVICE_KEYWORDS)


@app.post("/api/v1/qa")
def qa(payload: QuestionRequest):
    answer_text = ""
    source = "project"
    label = "Project AI Assistant"
    try:
        if payload.assistant == "rag":
            answer_text = ask_question(payload.q)
            source = "rag"
            label = "RAG AI"
        elif _is_device_command(payload.q):
            # Route device control commands through ADK agent
            answer_text = _asyncio.run(_adk_run(payload.q))
            source = "project"
            label = "Project AI Assistant"
        else:
            project_context = {
                "dashboard": get_dashboard(),
                "devices": list_devices(),
                "billing": get_billing_summary(),
                "analytics": get_analytics_daily(),
            }
            
            # Retrieve recent chat history to maintain conversational context
            history = get_chat_history(limit=20)
            history_text = ""
            if history:
                history_text = "Recent conversation history:\n"
                for msg in history:
                    role_label = "User" if msg["role"] == "user" else "Assistant"
                    history_text += f"{role_label}: {msg['content']}\n"
                history_text += "\n"

            profile = get_user_profile()
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            gemini = genai.GenerativeModel("gemini-2.5-flash")
            prompt = f"""You are VoltStream AI - a smart, friendly assistant with full knowledge of the user's VoltStream energy dashboard.
User profile (NEVER address the user by any name — not "User", not "Alex", not any name. Just reply directly):
- Monthly Energy Budget Goal: ${profile['budget_goal']}
- Primary Energy Goal: {profile['primary_goal']} (savings = save money, eco-friendly = minimize carbon/maximize solar, comfort = convenience)
- Household Size: {profile['household_size']} people
- Daily Schedule: {profile['daily_schedule']}

You can answer ANY question - general knowledge, coding, science, math, jokes, casual chat, or anything else.

You also have access to the user's live VoltStream data:
{project_context}

{history_text}
Guidelines:
- Greet the user warmly and naturally. Never use any name.
- For energy/device/billing questions: use the project data and their monthly budget to provide specific, tailored suggestions.
- If their primary goal is 'savings', prioritize tips to lower their bill. If 'eco-friendly', focus on using clean/solar energy. If 'comfort', balance convenience with automation.
- For general questions: answer helpfully like ChatGPT.
- For casual chat: be friendly, personal, and conversational.
- Keep answers concise but complete.
- Use bullet points when listing multiple items.
- For current events, politics, news, or recent changes (after 2023): say "My knowledge may be outdated on this. Please verify with a current source." and give what you know with a disclaimer
- Never address the user by any name (do not use "Alex", "User", or any other name).

User message: {payload.q}"""
            response = gemini.generate_content(prompt)
            answer_text = response.text
            source = "project"
            label = "Project AI Assistant"
        return {"answer": answer_text, "source": source, "label": label}
    except Exception as e:
        answer_text = f"Error: {str(e)}"
        return {"answer": answer_text, "source": "error", "label": "Error"}
    finally:
        if payload.q.strip():
            save_chat_messages(payload.q.strip(), answer_text or "")


# ─────────────────────────────────────────────
# Scheduled Device Commands
# ─────────────────────────────────────────────
import threading
import re as _re
from datetime import datetime, timedelta

class ScheduleRequest(BaseModel):
    command: str   # e.g. "turn off AC at 10pm"

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
        elif not period:
            # No am/pm — if hour <= 12 and current hour > hour, assume next occurrence
            pass  # keep as-is, handled by next-day logic below
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

@app.post("/api/v1/schedule")
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
