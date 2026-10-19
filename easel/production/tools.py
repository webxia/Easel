"""Typed, scoped tools; model output cannot extend this registry."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from pydantic import BaseModel

from .context import TaskContext


@dataclass(frozen=True)
class MediaToolResult:
    """Only trusted local tools can return actual media, never model arguments."""
    evidence: dict
    media: tuple[dict, ...]
    required: frozenset[str]


@dataclass(frozen=True)
class ScopedTool:
    name: str
    description: str
    arguments: type[BaseModel]
    execute: Callable[[BaseModel, TaskContext], Awaitable[dict[str, Any] | MediaToolResult]]
    handle_fields: tuple[str, ...] = ()

    def definition(self) -> dict:
        schema = self.arguments.model_json_schema()
        schema["additionalProperties"] = False
        return {"type": "function", "function": {
            "name": self.name, "description": self.description, "parameters": schema,
        }}

    async def invoke(self, data: dict, context: TaskContext) -> dict:
        if set(data) - set(self.arguments.model_fields):
            raise ValueError("Unknown tool argument")
        parsed = self.arguments.model_validate(data)
        for name in self.handle_fields:
            value = getattr(parsed, name)
            handles = value if isinstance(value, list) else [value]
            if any(handle not in context.allowed_handles for handle in handles):
                raise ValueError("Tool handle outside current work scope")
        result = await self.execute(parsed, context)
        if isinstance(result, MediaToolResult):
            if not result.evidence or not result.media:
                raise ValueError("Tool returned no usable media evidence")
            return result
        if not isinstance(result, dict) or not result:
            raise ValueError("Tool returned no usable evidence")
        return result


ALLOWED_TOOLS = frozenset({
    "search_materials", "inspect_media", "read_project", "propose_generation",
    "submit_edit", "get_operation", "get_render", "search_public_facts",
})


def tool_registry(tools: tuple[ScopedTool, ...]) -> dict[str, ScopedTool]:
    result = {tool.name: tool for tool in tools}
    if len(result) != len(tools) or set(result) - ALLOWED_TOOLS:
        raise ValueError("Unsupported or duplicate production tool")
    return result
