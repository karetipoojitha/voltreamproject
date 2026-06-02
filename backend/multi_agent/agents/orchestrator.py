from google.adk.agents import Agent

from .advisor import advisor_agent
from .analyst import analyst_agent
from .billing import billing_agent
from ..prompts import ORCHESTRATOR_INSTRUCTION
from ..shared import MODEL


orchestrator_agent = Agent(
    name="orchestrator_agent",
    model=MODEL,
    description="Orchestrates the VoltStream multi-agent energy advisory system.",
    instruction=ORCHESTRATOR_INSTRUCTION,
    sub_agents=[analyst_agent, billing_agent, advisor_agent],
)
