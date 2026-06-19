import logging
from datetime import datetime
from typing import TypedDict

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from .agents import analyst_agent, billing_agent, orchestrator_agent
from .prompts import billing_status_prompt, device_status_prompt

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("voltstream.multi_agent")


class AgentTraceEvent(TypedDict):
    agent: str
    step: str
    msg: str
    time: str


class MultiAgentResult(TypedDict):
    reply: str
    trace: list[AgentTraceEvent]


def _trace_time() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _short_trace(text: str) -> str:
    return text[:120] + ("..." if len(text) > 120 else "")


def _is_combined_bill_device_request(message: str) -> bool:
    text = message.lower()
    bill_terms = ("bill", "billing", "cost", "charge", "payment")
    device_terms = ("device", "devices", "divice", "divices", "appliance", "appliances")
    return any(term in text for term in bill_terms) and any(term in text for term in device_terms)


def _fallback_billing_reply() -> str:
    from database import get_billing_summary

    summary = get_billing_summary()
    current_bill = summary.get("current_bill", 0)
    projected_bill = summary.get("projected_bill", 0)
    if float(current_bill).is_integer():
        current_bill = int(current_bill)
    if float(projected_bill).is_integer():
        projected_bill = int(projected_bill)

    return (
        f"Current Bill: Rs. {current_bill}\n"
        f"Projected Bill: Rs. {projected_bill}\n"
        f"Budget Alert: {summary.get('budget_alert', '')}"
    )


async def run_multi_agent(message: str) -> MultiAgentResult:
    """Run the multi-agent pipeline and return reply + agent trace."""
    trace: list[AgentTraceEvent] = []
    trace.append({"agent": "Orchestrator", "step": "PLAN", "msg": f"Received: {message}", "time": _trace_time()})
    logger.info("[Orchestrator] Received: %s", message)

    session_id = f"multi-{int(datetime.now().timestamp())}"
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name="voltstream_multi",
        user_id="user",
        session_id=session_id,
    )

    async def run_specialist(agent: Agent, agent_name: str, specialist_prompt: str) -> str:
        runner = Runner(
            agent=agent,
            app_name="voltstream_multi",
            session_service=session_service,
        )
        user_message = types.Content(role="user", parts=[types.Part(text=specialist_prompt)])
        reply = ""
        async for event in runner.run_async(
            user_id="user",
            session_id=session_id,
            new_message=user_message,
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    reply = event.content.parts[0].text or ""
                break

        if not reply and agent_name == "Billing":
            reply = _fallback_billing_reply()
        if not reply and agent_name == "Analyst":
            from database import list_devices
            devices = list_devices()
            reply = "\n".join(f"- {d['name']}: {'ON' if d['status'] else 'OFF'}" for d in devices)

        trace.append({
            "agent": agent_name,
            "step": "EXECUTE",
            "msg": _short_trace(reply or f"{agent_name} completed without text output"),
            "time": _trace_time(),
        })
        logger.info("[%s] %s", agent_name, reply[:80])
        return reply

    if _is_combined_bill_device_request(message):
        trace.append({
            "agent": "Orchestrator",
            "step": "ROUTE",
            "msg": "Using Billing for bill details and Analyst for device list",
            "time": _trace_time(),
        })
        billing_reply = await run_specialist(
            billing_agent,
            "Billing",
            billing_status_prompt(message),
        )
        analyst_reply = await run_specialist(
            analyst_agent,
            "Analyst",
            device_status_prompt(message),
        )
        final_reply = f"Weekly Bill:\n{billing_reply}\n\nDevices:\n{analyst_reply}"

        trace.append({
            "agent": "Orchestrator",
            "step": "RESPOND",
            "msg": "Billing and device-list response delivered to user",
            "time": _trace_time(),
        })
        logger.info("[Orchestrator] Final billing + device-list response ready")
        return {
            "reply": final_reply or "I could not generate a response. Please try again.",
            "trace": trace,
        }

    runner = Runner(
        agent=orchestrator_agent,
        app_name="voltstream_multi",
        session_service=session_service,
    )

    user_message = types.Content(role="user", parts=[types.Part(text=message)])

    final_reply = ""
    async for event in runner.run_async(
        user_id="user",
        session_id=session_id,
        new_message=user_message,
    ):
        if hasattr(event, "author") and event.author:
            agent_name = str(event.author).replace("_agent", "").title()
            if event.content and event.content.parts:
                text = event.content.parts[0].text or ""
                if text and len(text) > 10:
                    trace.append({
                        "agent": agent_name,
                        "step": "EXECUTE" if agent_name != "Orchestrator" else "OBSERVE",
                        "msg": _short_trace(text),
                        "time": _trace_time(),
                    })
                    logger.info("[%s] %s", agent_name, text[:80])

        if event.is_final_response():
            if event.content and event.content.parts:
                final_reply = event.content.parts[0].text
            break

    trace.append({"agent": "Orchestrator", "step": "RESPOND", "msg": "Final response delivered to user", "time": _trace_time()})
    logger.info("[Orchestrator] Final response ready")

    if not final_reply:
        final_reply = "Mock Mode: Vertex AI returned no final response. Check the trace/logs for auth, model, or routing errors."

    return {
        "reply": final_reply,
        "trace": trace,
    }
