from collections.abc import Callable
from typing import Any, TypeVar

from google.adk.tools import FunctionTool

from config import VERTEX_AI_MODEL

MODEL = VERTEX_AI_MODEL
ToolFunc = TypeVar("ToolFunc", bound=Callable[..., Any])


def format_rupees(value: Any) -> str:
    amount = float(value or 0)
    if amount.is_integer():
        return f"Rs. {int(amount)}"
    return f"Rs. {amount:.2f}"


def adk_tool(func: ToolFunc) -> ToolFunc:
    setattr(func, "_adk_tool", FunctionTool(func))
    return func


def as_adk_tool(func: Callable[..., Any]) -> FunctionTool:
    return getattr(func, "_adk_tool")
