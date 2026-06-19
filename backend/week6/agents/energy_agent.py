from google.adk.agents import Agent

from ..config import VERTEX_AI_MODEL

energy_agent = Agent(
    name="energy_agent",
    model=VERTEX_AI_MODEL,
    description="Handles energy analytics and optimization.",
    instruction="""
You analyze energy usage patterns, cost, and optimization strategies.
Be precise and technical.
"""
)
