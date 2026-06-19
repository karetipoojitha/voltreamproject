from google.adk.agents import Agent

from ..config import VERTEX_AI_MODEL

device_control_agent = Agent(
    name="device_control_agent",
    model=VERTEX_AI_MODEL,
    description="Controls IoT devices.",
    instruction="""
You control smart devices (ON/OFF, scheduling, state changes).
Return structured commands.
"""
)
