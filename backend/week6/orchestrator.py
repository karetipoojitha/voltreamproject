from google.adk.agents import Agent

from .agents.energy_agent import energy_agent
from .agents.device_control import device_control_agent
from .agents.device_manager import device_manager_agent
from .agents.bulk_agent import bulk_agent
from .agents.energy_pipeline import energy_pipeline
from .config import VERTEX_AI_MODEL
from .prompt import ORCHESTRATOR_PROMPT

orchestrator = Agent(
    name="voltstream_orchestrator",
    model=VERTEX_AI_MODEL,
    description="VoltStream root orchestrator.",
    instruction=ORCHESTRATOR_PROMPT,
    sub_agents=[
        device_control_agent,
        device_manager_agent,
        bulk_agent,
        energy_agent,
        energy_pipeline,
    ],
)
