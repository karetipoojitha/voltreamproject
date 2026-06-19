import re

from google import genai as vertex_genai
from fastapi import APIRouter
from pydantic import BaseModel

from config import VERTEX_AI_MODEL
from multi_agent import run_multi_agent
from agent import _run_agent as _adk_run, _handle_device_command
from rag import ask_question

from database import (
    get_dashboard,
    list_devices,
    get_billing_summary,
    get_analytics_daily,
    get_user_profile,
    get_chat_history,
    clear_chat_history,
    save_chat_messages,
    update_device_status,
)

router = APIRouter(prefix="/api/v1")


# ─────────────────────────────
# REQUEST MODELS
# ─────────────────────────────
class QuestionRequest(BaseModel):
    q: str
    mode: str = "advisor"
    assistant: str = "project"


class MultiAgentRequest(BaseModel):
    message: str


# ─────────────────────────────
# DEVICE KEYWORDS
# ─────────────────────────────
_DEVICE_KEYWORDS = [
    "turn on", "turn off", "switch on", "switch off",
    "enable", "disable", "start", "stop",
    "toggle", "control", "set", "activate", "deactivate",
]

_BILL_KEYWORDS = ["bill", "billing", "cost", "charge", "payment"]
_DEVICE_GROUP_KEYWORDS = [
    "devices",
    "all devices",
    "all the devices",
    "every device",
    "appliances",
    "all appliances",
]

_RAG_KEYWORDS = [
    "passive solar",
    "photovoltaic",
    "photoelectric",
    "solar collector",
    "solar technology",
    "solar history",
    "history of solar",
    "history of solar energy",
    "history of solar technology",
    "solar cell",
    "pv system",
    "thin-film",
    "solar furnace",
    "solar-powered",
    "net metering",
    "battery storage",
    "nrel",
    "archimedes",
    "einstein",
]


def _is_device_command(text: str) -> bool:
    return any(k in text.lower() for k in _DEVICE_KEYWORDS)


def _wants_bill(text: str) -> bool:
    lowered = text.lower()
    return any(k in lowered for k in _BILL_KEYWORDS)


def _device_action_state(text: str) -> bool | None:
    lowered = text.lower()
    if any(k in lowered for k in ("turn on", "switch on", "enable", "start", "activate")):
        return True
    if any(k in lowered for k in ("turn off", "switch off", "disable", "stop", "deactivate")):
        return False
    return None


def _is_bulk_device_control(text: str) -> bool:
    lowered = text.lower()
    return _device_action_state(lowered) is not None and any(k in lowered for k in _DEVICE_GROUP_KEYWORDS)


def _format_bill_summary() -> str:
    billing = get_billing_summary()
    current_bill = billing.get("current_bill", 0)
    projected_bill = billing.get("projected_bill", 0)
    if float(current_bill).is_integer():
        current_bill = int(current_bill)
    if float(projected_bill).is_integer():
        projected_bill = int(projected_bill)

    return (
        f"Current Bill: Rs. {current_bill}\n"
        f"Projected Bill: Rs. {projected_bill}\n"
        f"Budget Alert: {billing.get('budget_alert', '')}"
    )


def _set_all_devices(state: bool) -> str:
    devices = list_devices()
    for device in devices:
        update_device_status(device["id"], state)

    updated_devices = list_devices()
    state_word = "ON" if state else "OFF"
    names = ", ".join(device["name"] for device in updated_devices)
    return f"All devices set to {state_word}: {names}"


def _combined_device_bill_reply(message: str) -> str:
    state = _device_action_state(message)
    device_reply = _set_all_devices(bool(state))
    return f"Device Control:\n{device_reply}\n\nWeekly Bill:\n{_format_bill_summary()}"


def _is_rag_question(text: str) -> bool:
    lowered = text.lower()
    if any(k in lowered for k in _RAG_KEYWORDS):
        return True

    if re.search(r"\b(1[7-9]\d{2}|20\d{2})\b", lowered) and any(
        term in lowered for term in ("explain", "about", "what happened", "timeline", "history", "milestone")
    ):
        return True

    solar_terms = ("solar", "sunlight", "sun's heat", "sun rays")
    knowledge_terms = (
        "history", "timeline", "milestone", "invent", "invented",
        "discover", "discovered", "what is", "explain", "how did",
    )
    return any(term in lowered for term in solar_terms) and any(term in lowered for term in knowledge_terms)


# ─────────────────────────────
# CHAT HISTORY
# ─────────────────────────────
@router.get("/chat/history")
def chat_history(limit: int = 200):
    return {"messages": get_chat_history(limit)}


@router.delete("/chat/history")
def delete_chat_history():
    clear_chat_history()
    return {"ok": True}


# ─────────────────────────────
# QA ENDPOINT
# ─────────────────────────────
@router.post("/qa")
async def qa(payload: QuestionRequest):
    answer_text = ""
    source = "project"
    label = "VoltStream AI"

    try:
        # ── RAG ──
        if payload.assistant == "rag" or _is_rag_question(payload.q):
            answer_text = ask_question(payload.q)
            source = "rag"
            label = "RAG AI"

        # ── DEVICE COMMAND ──
        elif _is_bulk_device_control(payload.q) and _wants_bill(payload.q):
            answer_text = _combined_device_bill_reply(payload.q)

        elif _is_device_command(payload.q):
            q = payload.q.lower()

            all_devices = any(x in q for x in _DEVICE_GROUP_KEYWORDS)
            turn_on = bool(_device_action_state(q))

            if all_devices:
                devices = list_devices()

                for d in devices:
                    update_device_status(d["id"], turn_on)

                state = "ON" if turn_on else "OFF"
                names = ", ".join(d["name"] for d in devices)

                answer_text = f"All devices set to {state}: {names}"

            else:
                answer_text = await _adk_run(payload.q)

        # ── NORMAL AI ──
        else:
            profile = get_user_profile()

            context = {
                "dashboard": get_dashboard(),
                "devices": list_devices(),
                "billing": get_billing_summary(),
                "analytics": get_analytics_daily(),
            }

            history = get_chat_history(limit=10)
            history_text = "\n".join(
                f"{m['role']}: {m['content']}" for m in history
            )

            vertex_client = vertex_genai.Client()

            model_name = VERTEX_AI_MODEL

            prompt = f"""
You are VoltStream AI assistant.

User profile:
Budget: {profile['budget_goal']}
Goal: {profile['primary_goal']}
Household: {profile['household_size']}
Schedule: {profile['daily_schedule']}

Project data:
{context}

Chat history:
{history_text}

User: {payload.q}
"""

            response = vertex_client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            answer_text = response.text

        return {
            "answer": answer_text,
            "source": source,
            "label": label
        }

    except Exception as e:
        error_msg = str(e)
        if "403" in error_msg or "disabled" in error_msg.lower() or "PERMISSION_DENIED" in error_msg:
            # Fallback mock response when API is disabled
            fallback_answer = (
                "Hello! I am operating in offline mock mode because Vertex AI is disabled. "
                "You asked: '" + payload.q + "'. "
                "I can help you manage your devices, view analytics, and lower your energy bill once Vertex AI is enabled."
            )
            return {
                "answer": fallback_answer,
                "source": "project",
                "label": "VoltStream AI (Mock Mode)"
            }
        
        return {
            "answer": f"Error: {error_msg}",
            "source": "error",
            "label": "Error"
        }

    finally:
        if payload.q.strip():
            save_chat_messages(payload.q, answer_text)


# ─────────────────────────────
# MULTI AGENT ENDPOINT
# ─────────────────────────────
@router.post("/multi-agent")
async def multi_agent_chat(req: MultiAgentRequest):
    try:
        if _is_rag_question(req.message):
            return {
                "reply": ask_question(req.message),
                "trace": [{
                    "agent": "RAG",
                    "step": "RETRIEVE",
                    "msg": "Answered from the energy PDF knowledge base.",
                    "time": "",
                }],
            }

        if _is_bulk_device_control(req.message) and _wants_bill(req.message):
            return {
                "reply": _combined_device_bill_reply(req.message),
                "trace": [
                    {
                        "agent": "DeviceControl",
                        "step": "EXECUTE",
                        "msg": "Updated all device states from the request.",
                        "time": "",
                    },
                    {
                        "agent": "Billing",
                        "step": "FETCH",
                        "msg": "Returned current weekly bill details.",
                        "time": "",
                    },
                ],
            }

        elif _is_device_command(req.message):
            q = req.message.lower()

            all_devices = any(x in q for x in _DEVICE_GROUP_KEYWORDS)
            turn_on = bool(_device_action_state(q))

            if all_devices:
                devices = list_devices()

                for d in devices:
                    update_device_status(d["id"], turn_on)

                state = "ON" if turn_on else "OFF"
                names = ", ".join(d["name"] for d in devices)

                return {
                    "reply": f"All devices set to {state}: {names}",
                    "trace": [{
                        "agent": "DeviceControl",
                        "step": "EXECUTE",
                        "msg": f"Set all devices to {state}",
                        "time": "",
                    }]
                }

            else:
                reply = _handle_device_command(req.message)
                if reply:
                    return {
                        "reply": reply,
                        "trace": [{
                            "agent": "DeviceControl",
                            "step": "EXECUTE",
                            "msg": f"Executed device command: {req.message}",
                            "time": "",
                        }]
                    }

        result = await run_multi_agent(req.message)
        return result
    except Exception as e:
        error_msg = str(e)
        if "403" in error_msg or "disabled" in error_msg.lower() or "PERMISSION_DENIED" in error_msg:
            return {
                "reply": "Mock Mode (Vertex AI Disabled): I'm currently running in mock mode because the Vertex AI API is disabled. Please enable it in the Google Cloud Console to restore full functionality.",
                "trace": [{"agent": "MockAgent", "step": "EXECUTE", "msg": "API disabled. Returned mock response.", "time": ""}]
            }
        raise
