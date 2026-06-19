from google.adk.agents import Agent

from ..config import VERTEX_AI_MODEL

device_manager_agent = Agent(
    name="device_manager_agent",
    model=VERTEX_AI_MODEL,
    description="Manages device registry and metadata.",
    instruction="""
You manage device registration, status tracking, and metadata updates.
"""
)
