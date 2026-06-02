from google.adk.agents import Agent

from ..prompts import ADVISOR_INSTRUCTION
from ..shared import MODEL


advisor_agent = Agent(
    name="advisor_agent",
    model=MODEL,
    description="Gives personalised energy-saving recommendations based on usage analysis.",
    instruction=ADVISOR_INSTRUCTION,
    tools=[],
)
