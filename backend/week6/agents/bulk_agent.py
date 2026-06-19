from google.adk.agents import Agent

from ..config import VERTEX_AI_MODEL

bulk_agent = Agent(
    name="bulk_agent",
    model=VERTEX_AI_MODEL,
    description="Handles bulk operations.",
    instruction="""
You perform batch operations on devices or energy data.
Optimize for efficiency.
""")
