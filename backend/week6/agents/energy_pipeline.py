from google.adk.agents import Agent

from ..config import VERTEX_AI_MODEL

energy_pipeline = Agent(
    name="energy_pipeline",
    model=VERTEX_AI_MODEL,
    description="Energy forecasting pipeline.",
    instruction="""
You handle forecasting, trend prediction, and pipeline orchestration for energy data.
"""
)
