from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from config import VERTEX_AI_MODEL
from database import list_devices, update_device_status, save_chat_messages, find_device_by_name

router = APIRouter()

class AgentRequest(BaseModel):
    message: str


ON_WORDS  = ["turn on", "switch on", "enable", "start", "activate", "power on"]
OFF_WORDS = ["turn off", "switch off", "disable", "stop", "deactivate", "power off"]


def _parse_device_command(message: str):
    """
    Returns (device_id, device_name, state) or None if not a device command.
    state: True = ON, False = OFF
    """
    lowered = message.lower().strip()

    state = None
    for w in ON_WORDS:
        if w in lowered:
            state = True
            break
    if state is None:
        for w in OFF_WORDS:
            if w in lowered:
                state = False
                break
    if state is None:
        return None

    match = find_device_by_name(message)
    if match:
        device_id, device_name = match
        return device_id, device_name, state

    return None


def _handle_device_command(message: str) -> str | None:
    """Handle device command directly without ADK agent. Returns reply or None."""
    parsed = _parse_device_command(message)
    if parsed is None:
        return None

    device_id, device_name, state = parsed
    success = update_device_status(device_id, state)
    if not success:
        return f"Sorry, I couldn't find {device_name} in the system."

    state_word = "ON" if state else "OFF"
    return f"Done! {device_name} is now {state_word}."


async def _run_agent_llm(message: str) -> str:
    """Fall back to ADK agent for non-device queries."""
    try:
        from google.adk.agents import Agent
        from google.adk.tools import FunctionTool
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types
        from database import get_user_profile

        profile = get_user_profile()
        devices = list_devices()
        device_list = "\n".join(
            f"- {d['name']}: {'ON' if d['status'] else 'OFF'}" for d in devices
        )

        def get_all_device_status() -> dict:
            """Returns the current status of all smart home devices."""
            return {"devices": list_devices()}

        agent = Agent(
            name="voltstream_assistant",
            model=VERTEX_AI_MODEL,
            description="VoltStream smart home assistant.",
            instruction=f"""You are VoltStream AI assistant for {profile['name']}.
Current device status:
{device_list}

Answer questions about devices, energy usage, or home automation.
Be concise and friendly.
""",
            tools=[FunctionTool(get_all_device_status)],
        )

        session_service = InMemorySessionService()
        await session_service.create_session(
            app_name="voltstream",
            user_id="user",
            session_id="session-1",
        )
        runner = Runner(
            agent=agent,
            app_name="voltstream",
            session_service=session_service,
        )
        user_message = types.Content(role="user", parts=[types.Part(text=message)])

        final_reply = ""
        async for event in runner.run_async(
            user_id="user", session_id="session-1", new_message=user_message
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    final_reply = event.content.parts[0].text
                break

        return final_reply or "I could not process your request. Please try again."

    except Exception as e:
        return f"Assistant error: {str(e)}"


async def _run_agent(message: str) -> str:
    # 1. Try direct device command first — fast and reliable
    direct = _handle_device_command(message)
    if direct is not None:
        return direct

    # 2. Fall back to LLM agent for everything else
    return await _run_agent_llm(message)


@router.post("/agent")
async def agent_chat(req: AgentRequest) -> dict[str, str]:
    reply = ""
    try:
        reply = await _run_agent(req.message)
        return {"reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if req.message.strip():
            save_chat_messages(req.message.strip(), reply or "")
