import os
import asyncio as _asyncio
import google.generativeai as genai
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from rag import ask_question
from agent import _run_agent as _adk_run
from multi_agent import run_multi_agent as _run_multi_agent
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

class QuestionRequest(BaseModel):
    q: str
    mode: str = "advisor"
    assistant: str = "project"

class MultiAgentRequest(BaseModel):
    message: str

_DEVICE_KEYWORDS = [
    "turn on", "turn off", "switch on", "switch off",
    "enable", "disable", "start", "stop",
    "toggle", "control", "set", "activate", "deactivate",
]

def _is_device_command(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in _DEVICE_KEYWORDS)

@router.get("/chat/history")
def chat_history(limit: int = 200):
    return {"messages": get_chat_history(limit)}

@router.delete("/chat/history")
def delete_chat_history():
    clear_chat_history()
    return {"ok": True}

@router.post("/qa")
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
            q_low = payload.q.lower()
            # Handle bulk "all devices" commands directly
            all_words = ["all devices", "all my devices", "all the devices", "every device", "all"]
            is_bulk = any(w in q_low for w in all_words)
            if is_bulk:
                want_on = any(w in q_low for w in ["turn on", "switch on", "enable"])
                new_state = want_on
                devices = list_devices()
                for d in devices:
                    update_device_status(d["id"], new_state)
                state_word = "ON" if new_state else "OFF"
                device_list = ", ".join(d["name"] for d in devices)
                answer_text = f"Done! All devices are now {state_word}. ({device_list})"
            else:
                # Route single device commands through ADK agent
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

@router.post("/multi-agent")
async def multi_agent_chat(req: MultiAgentRequest):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured")
    try:
        result = await _run_multi_agent(req.message)
        if isinstance(result, dict):
            return result
        return {"reply": result, "trace": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
