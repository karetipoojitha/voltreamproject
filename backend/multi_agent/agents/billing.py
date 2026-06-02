import logging
from typing import Any

from google.adk.agents import Agent

from ..prompts import BILLING_INSTRUCTION
from ..shared import MODEL, adk_tool, as_adk_tool, format_rupees

logger = logging.getLogger("voltstream.multi_agent")


@adk_tool
def get_billing_details() -> dict[str, Any]:
    """Retrieves full billing history and transaction data for analysis."""
    try:
        from database import get_billing_summary, list_billing_history, list_billing_transactions

        summary = get_billing_summary()
        history = list_billing_history()
        transactions = list_billing_transactions()
        avg_bill = round(sum(h["amount"] for h in history) / len(history), 2) if history else 0
        trend = "increasing" if history and history[-1]["amount"] > history[0]["amount"] else "decreasing"
        logger.info("[Billing] get_billing_details - current=%s, trend=%s", summary.get("current_bill"), trend)
        return {
            "currency": "INR",
            "current_bill": summary.get("current_bill", 0),
            "current_bill_display": format_rupees(summary.get("current_bill", 0)),
            "projected_bill": summary.get("projected_bill", 0),
            "projected_bill_display": format_rupees(summary.get("projected_bill", 0)),
            "budget_alert": summary.get("budget_alert", ""),
            "average_monthly_bill": avg_bill,
            "average_monthly_bill_display": format_rupees(avg_bill),
            "billing_trend": trend,
            "history": history,
            "recent_transactions": transactions[:3],
        }
    except Exception as e:
        logger.error("[Billing] Error: %s", e)
        return {"error": str(e)}


billing_agent = Agent(
    name="billing_agent",
    model=MODEL,
    description="Analyses billing data and provides cost-saving financial recommendations.",
    instruction=BILLING_INSTRUCTION,
    tools=[as_adk_tool(get_billing_details)],
)
