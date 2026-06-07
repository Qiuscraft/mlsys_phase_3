import json
from typing import Any

from agents import RunHooks
from loguru import logger


def format_tool_payload(payload: Any) -> str:
    if payload is None:
        return "<none>"
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return payload
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


class ToolCallLogger(RunHooks):
    async def on_tool_start(self, context, agent, tool):
        tool_name = getattr(context, "tool_name", getattr(tool, "name", str(tool)))
        tool_arguments = getattr(context, "tool_arguments", None)

        logger.info(
            "Tool call started: {}\ninput:\n{}",
            tool_name,
            format_tool_payload(tool_arguments),
        )

    async def on_tool_end(self, context, agent, tool, result: str):
        tool_name = getattr(context, "tool_name", getattr(tool, "name", str(tool)))

        logger.info(
            "Tool call finished: {}\noutput:\n{}",
            tool_name,
            format_tool_payload(result),
        )
