import os
from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import APIRouter, HTTPException
from google.adk.tools import FunctionTool
from pydantic import BaseModel
from database import list_devices, update_device_status, save_chat_messages

router = APIRouter()
ToolFunc = TypeVar("ToolFunc", bound=Callable[..., Any])


def adk_tool(func: ToolFunc) -> ToolFunc:
    setattr(func, "_adk_tool", FunctionTool(func))
    return func


def _as_adk_tool(func: Callable[..., Any]) -> FunctionTool:
    return getattr(func, "_adk_tool")


class AgentRequest(BaseModel):
    message: str


@adk_tool
def get_device_status(device_id: int) -> dict:
    """Returns the current on/off status of a device by its ID.

    Args:
        device_id: The integer ID of the device to check.

    Returns:
        A dict with id, name, and status fields, or an error dict.
    """
    try:
        devices = list_devices()
        for device in devices:
            if device["id"] == device_id:
                return {"id": device["id"], "name": device["name"], "status": device["status"]}
        names = [f"id={d['id']} name='{d['name']}'" for d in devices]
        return {"error": f"Device with id {device_id} not found. Available: {names}"}
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}


@adk_tool
def toggle_device(device_id: int, state: bool) -> dict:
    """Turns a smart home device on or off.

    Args:
        device_id: The integer ID of the device to control.
        state: True to turn the device ON, False to turn it OFF.

    Returns:
        A dict with id, name, and updated status, or an error dict.
    """
    try:
        success = update_device_status(device_id, state)
        if not success:
            devices = list_devices()
            names = [f"id={d['id']} name='{d['name']}'" for d in devices]
            return {"error": f"Device with id {device_id} not found. Available: {names}"}
        # fetch updated record
        devices = list_devices()
        for d in devices:
            if d["id"] == device_id:
                return {"id": d["id"], "name": d["name"], "status": d["status"]}
        return {"error": "Device updated but could not retrieve record."}
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}


def _build_agent() -> Any:
    from google.adk.agents import Agent
    from database import get_user_profile
    profile = get_user_profile()
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    return Agent(
        name="voltstream_device_agent",
        model=model,
        description="Controls VoltStream smart home devices via natural language.",
        instruction=f"""You are a personal smart home assistant for VoltStream.
You help the user, {profile['name']}, control their home devices using natural language.

Personal context for {profile['name']}:
- Budget Goal: ${profile['budget_goal']}
- Primary Goal: {profile['primary_goal']}
- Daily Schedule: {profile['daily_schedule']}

Available devices:
- id=1  Air Conditioning  (also: AC, air con, air conditioning)
- id=2  Fan
- id=3  Washing Machine  (also: washer)
- id=4  Living Room Lights  (also: lights)
- id=5  Kitchen TV  (also: TV, television)
- id=6  Garage Door  (also: garage)

Rules:
1. To turn on/off a device, call toggle_device with the correct device_id and state (True=on, False=off).
2. To check device status, call get_device_status.
3. Resolve names case-insensitively. AC/air con = id=1, lights = id=4, TV = id=5, garage = id=6.
4. After toggling, confirm the action and new state. Address {profile['name']} by name if natural.
5. If device not found, list available devices.
6. Be concise, friendly, and helpful.
""",
        tools=[_as_adk_tool(get_device_status), _as_adk_tool(toggle_device)],
    )


_session_service: Any | None = None


def _get_session_service() -> Any:
    global _session_service
    if _session_service is None:
        from google.adk.sessions import InMemorySessionService
        _session_service = InMemorySessionService()
    return _session_service


async def _run_agent(message: str) -> str:
    from google.adk.runners import Runner
    from google.genai import types

    agent = _build_agent()
    session_service = _get_session_service()
    existing = await session_service.get_session(
        app_name="voltstream",
        user_id="user",
        session_id="session-1",
    )
    if not existing:
        await session_service.create_session(
            app_name="voltstream",
            user_id="user",
            session_id="session-1",
        )
    runner = Runner(agent=agent, app_name="voltstream", session_service=session_service)
    user_message = types.Content(role="user", parts=[types.Part(text=message)])

    final_reply = ""
    async for event in runner.run_async(user_id="user", session_id="session-1", new_message=user_message):
        if event.is_final_response():
            if event.content and event.content.parts:
                final_reply = event.content.parts[0].text
            break

    return final_reply or "I could not process your request. Please try again."


@router.post("/agent")
async def agent_chat(req: AgentRequest) -> dict[str, str]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured")
    reply = ""
    try:
        reply = await _run_agent(req.message)
        return {"reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if req.message.strip():
            save_chat_messages(req.message.strip(), reply or "")
