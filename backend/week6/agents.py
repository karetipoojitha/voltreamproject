from google.adk.agents import Agent

try:
    from .config import VERTEX_AI_MODEL
except ImportError:
    from config import VERTEX_AI_MODEL


energy_agent = Agent(
    name="energy_agent",
    model=VERTEX_AI_MODEL,
    description="Handles energy analytics and optimization.",
    instruction="""
You analyze energy usage patterns, cost, and optimization strategies.
Be precise and technical.
""",
)


device_control_agent = Agent(
    name="device_control_agent",
    model=VERTEX_AI_MODEL,
    description="Controls IoT devices.",
    instruction="""
You control smart devices (ON/OFF, scheduling, state changes).
Return structured commands.
""",
)


device_manager_agent = Agent(
    name="device_manager_agent",
    model=VERTEX_AI_MODEL,
    description="Manages device registry and metadata.",
    instruction="""
You manage device registration, status tracking, and metadata updates.
""",
)


bulk_agent = Agent(
    name="bulk_agent",
    model=VERTEX_AI_MODEL,
    description="Handles bulk operations.",
    instruction="""
You perform batch operations on devices or energy data.
Optimize for efficiency.
""",
)


energy_pipeline = Agent(
    name="energy_pipeline",
    model=VERTEX_AI_MODEL,
    description="Energy forecasting pipeline.",
    instruction="""
You handle forecasting, trend prediction, and pipeline orchestration for energy data.
""",
)


__all__ = [
    "energy_agent",
    "device_control_agent",
    "device_manager_agent",
    "bulk_agent",
    "energy_pipeline",
]
