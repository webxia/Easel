"""Real LangGraph stage execution with a separate durable SQLite checkpointer.

Graph state contains only references. Domain task completion and OperationService
dispatch gates are re-read even when LangGraph resumes a previously saved node.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from .errors import ProductionError

if TYPE_CHECKING:
    from .worker import RunLease, Worker


class GraphState(TypedDict, total=False):
    run_id: str
    task_id: str | None
    task_kind: str | None


class PersistentGraph:
    def __init__(self, worker: Worker):
        self.worker = worker

    @staticmethod
    def require_dependencies():
        try:
            import langgraph.graph  # noqa: F401
            import langgraph.checkpoint.sqlite.aio  # noqa: F401
        except ImportError as error:
            raise ProductionError("capability_unavailable", "V2 持久执行依赖未安装，请安装 Easel production 依赖", status_code=503) from error

    def build(self, lease: RunLease, checkpointer):
        from langgraph.graph import END, START, StateGraph

        async def resolve(_state):
            task = self.worker._next(lease)
            return {"run_id": lease.run_id, "task_id": task["id"] if task else None,
                    "task_kind": task["kind"] if task else None}

        def node(kind):
            async def execute(state):
                if state.get("run_id") != lease.run_id:
                    raise ProductionError("checkpoint_mismatch", "检查点不属于当前运行")
                if state.get("task_id"):
                    await self.worker.dispatch(lease, state["task_id"], kind or state["task_kind"])
                return {}
            return execute

        builder = StateGraph(GraphState)
        builder.add_node("resolve", resolve)
        names = {kind: "stage_"+kind for kind in self.worker.handlers}
        for kind, name in names.items():
            builder.add_node(name, node(kind))
            builder.add_edge(name, "resolve")
        builder.add_node("missing_capability", node(None))
        builder.add_edge("missing_capability", "resolve")
        builder.add_edge(START, "resolve")
        builder.add_conditional_edges("resolve", lambda state: END if not state.get("task_id") else names.get(state["task_kind"], "missing_capability"))
        return builder.compile(checkpointer=checkpointer)

    async def run(self, lease: RunLease):
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        from langsmith import tracing_context

        self.worker.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        async with AsyncSqliteSaver.from_conn_string(str(self.worker.checkpoint_path)) as saver:
            graph = self.build(lease, saver)
            config = {"configurable": {"thread_id": lease.run_id}, "recursion_limit": 256}
            # Never inherit cloud tracing merely because the host has tracing env vars.
            with tracing_context(enabled=False):
                checkpoint = await graph.aget_state(config)
                # Resume unfinished graph nodes; a completed checkpoint with unfinished
                # business work starts at resolve and reconciles from domain truth.
                await graph.ainvoke(None if checkpoint.next else {"run_id": lease.run_id}, config, durability="sync")
