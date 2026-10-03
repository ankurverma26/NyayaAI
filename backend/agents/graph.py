"""LangGraph workflow:  router -> planner -> retriever -> evidence_verifier
                         -> (no evidence? query_expander -> retriever, once) -> reasoner -> END
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from backend.agents.llm import LLMClient, get_llm_client
from backend.agents.nodes import make_nodes
from backend.agents.state import AgentState, new_state

MAX_RETRIES = 1


def route_after_verification(state: dict) -> str:
    """'answer' when evidence was verified (or retries are used up), else 'retry'."""
    if state.get("verified_evidence") or state.get("retry_count", 0) >= MAX_RETRIES:
        return "answer"
    return "retry"


class SequentialGraph:
    """Same flow without LangGraph (used for tests, or if langgraph is not installed)."""
    engine = "sequential"

    def __init__(self, nodes: dict[str, Callable[[dict], dict]]) -> None:
        self.nodes = nodes

    def invoke(self, state: dict) -> dict:
        state = dict(state)
        order = ["router", "planner", "retriever", "evidence_verifier"]
        for name in order:
            state.update(self.nodes[name](state))
        while route_after_verification(state) == "retry":
            for name in ("query_expander", "retriever", "evidence_verifier"):
                state.update(self.nodes[name](state))
        state.update(self.nodes["reasoner"](state))
        return state


def build_graph(retriever: Any, llm: Optional[LLMClient] = None, engine: str = "auto"):
    """Compile the workflow. engine: 'auto' (LangGraph if installed) | 'langgraph' | 'sequential'."""
    nodes = make_nodes(retriever, llm or get_llm_client())
    if engine == "sequential":
        return SequentialGraph(nodes)
    try:
        from langgraph.graph import END, StateGraph
    except ImportError:
        if engine == "langgraph":
            raise
        return SequentialGraph(nodes)

    g = StateGraph(AgentState)
    for name, fn in nodes.items():
        g.add_node(name, fn)
    g.set_entry_point("router")
    g.add_edge("router", "planner")
    g.add_edge("planner", "retriever")
    g.add_edge("retriever", "evidence_verifier")
    g.add_conditional_edges("evidence_verifier", route_after_verification,
                            {"retry": "query_expander", "answer": "reasoner"})
    g.add_edge("query_expander", "retriever")
    g.add_edge("reasoner", END)
    compiled = g.compile()
    compiled.engine = "langgraph"  # type: ignore[attr-defined]
    return compiled


def run_agent(retriever: Any, query: str = "", llm: Optional[LLMClient] = None, engine: str = "auto", **context: Any) -> dict:
    """Run one research request and return the final state (answer, evidence, trace)."""
    graph = build_graph(retriever, llm, engine)
    state = new_state(query=query, **context)
    result = graph.invoke(state)
    result["workflow_engine"] = getattr(graph, "engine", "langgraph")
    return result
