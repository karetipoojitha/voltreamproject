import logging
from typing import Any

from google.adk.agents import Agent

from ..prompts import ANALYST_INSTRUCTION
from ..shared import MODEL, adk_tool, as_adk_tool, format_rupees

logger = logging.getLogger("voltstream.multi_agent")


@adk_tool
def get_weekly_usage() -> dict[str, Any]:
    """Retrieves last week's daily energy usage data from VoltStream database."""
    try:
        from database import get_analytics_daily, get_billing_summary, get_dashboard

        daily = get_analytics_daily()
        dashboard = get_dashboard()
        billing = get_billing_summary()
        total_kwh = sum(d["usage"] for d in daily)
        avg_kwh = round(total_kwh / len(daily), 2) if daily else 0
        peak_day = max(daily, key=lambda d: d["usage"]) if daily else {}
        logger.info("[Analyst] get_weekly_usage - total=%s kWh, peak=%s", total_kwh, peak_day)
        return {
            "daily_usage": daily,
            "total_kwh": total_kwh,
            "average_daily_kwh": avg_kwh,
            "peak_day": peak_day,
            "currency": "INR",
            "grid_power_kw": dashboard.get("grid_power", 0),
            "solar_generation_kw": dashboard.get("solar_generation", 0),
            "current_bill": billing.get("current_bill", 0),
            "current_bill_display": format_rupees(billing.get("current_bill", 0)),
            "budget_alert": billing.get("budget_alert", ""),
        }
    except Exception as e:
        logger.error("[Analyst] Error: %s", e)
        return {"error": str(e)}


@adk_tool
def get_device_list() -> dict[str, Any]:
    """Retrieves all smart home devices and their current on/off status."""
    try:
        from database import list_devices

        devices = list_devices()
        active = [d for d in devices if d["status"]]
        logger.info("[Analyst] get_device_list - %s/%s ON", len(active), len(devices))
        return {
            "devices": devices,
            "active_count": len(active),
            "total_count": len(devices),
            "active_devices": [d["name"] for d in active],
        }
    except Exception as e:
        logger.error("[Analyst] Error: %s", e)
        return {"error": str(e)}


analyst_agent = Agent(
    name="analyst_agent",
    model=MODEL,
    description="Retrieves and analyses VoltStream energy usage and device data.",
    instruction=ANALYST_INSTRUCTION,
    tools=[as_adk_tool(get_weekly_usage), as_adk_tool(get_device_list)],
)
