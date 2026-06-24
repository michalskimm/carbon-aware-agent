"""The carbon-scheduling agent: a LangGraph agent over the MCP carbon tools."""

from __future__ import annotations

import os
from typing import TypedDict

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.runnables import Runnable
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import interrupt

from carbon_agent.mcp_tools import load_carbon_tools

SYSTEM_PROMPT = (
    "You are a carbon-aware scheduling assistant for the UK electricity grid. "
    "Use greenest_window for workload scheduling recommendations, current_intensity "
    "for current carbon intensity, forecast for future intensity forecasts, and "
    "generation_mix for generation mix information. "
    "For scheduling requests, use greenest_window when the user has provided a duration; "
    "if no duration is provided, ask for one. Only assume a duration when explicitly "
    "instructed to, and state the assumption before calling any scheduling tool. "
    "The forecast horizon is 48 hours and durations are whole hours. Do not call "
    "scheduling tools for requests exceeding 48 hours or requiring sub-hour precision; "
    "instead explain the limitation and suggest a supported alternative. "
    "Never calculate, infer, extrapolate, or estimate carbon-intensity values yourself; "
    "report only values returned by tools. "
    "You may briefly explain concepts directly about grid carbon intensity, generation "
    "mix, and carbon-aware scheduling (e.g. what a unit means). Do not discuss broader "
    "energy policy, environmental impacts of specific technologies, or unrelated topics; "
    "for those, briefly decline and restate what you can help with. Keep responses concise."
)


# Default provider when LLM_PROVIDER is unset, and default model per provider
# (overridable via LLM_MODEL). The full config surface lives in these two
# declarations — update model names here, in one place.
_DEFAULT_PROVIDER = "openai"
_DEFAULT_MODELS = {
    "openai": "gpt-4.1",
    "anthropic": "claude-sonnet-4-6",
}


def _build_model() -> BaseChatModel:
    """Construct the chat model from env. Provider-agnostic by design.

    LLM_PROVIDER selects the backend (default: openai); LLM_MODEL overrides the
    model string. Imports are lazy so only the chosen provider's SDK need be
    installed — anthropic is an optional extra (uv sync --extra anthropic).
    Config is read here, not at import time, so the module imports cleanly.
    """
    provider = os.getenv("LLM_PROVIDER", _DEFAULT_PROVIDER).lower()
    if provider not in _DEFAULT_MODELS:
        raise ValueError(
            f"Unknown LLM_PROVIDER: {provider!r}. Expected one of {sorted(_DEFAULT_MODELS)}."
        )
    model = os.getenv("LLM_MODEL", _DEFAULT_MODELS[provider])
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model, temperature=0)
    from langchain_anthropic import ChatAnthropic  # type: ignore[reportMissingImports]

    # model= is the Pydantic alias for model_name; Pylance's stub flags it (and
    # "missing" timeout/stop) but the runtime ctor is **kwargs-validated. Stub gap.
    return ChatAnthropic(model=model, temperature=0)  # type: ignore[call-arg]


async def build_agent() -> Runnable:
    """Construct the agent with MCP tools and an in-memory checkpointer.

    Returns a CompiledStateGraph (a Runnable); typed as Runnable to depend on
    the stable public invoke contract rather than langgraph's internal generic.
    """
    tools = await load_carbon_tools()
    model = _build_model()
    checkpointer = InMemorySaver()  # swap for a durable store in prod
    return create_agent(model, tools, system_prompt=SYSTEM_PROMPT, checkpointer=checkpointer)


async def build_graph(tools: list | None = None, model: BaseChatModel | None = None) -> Runnable:
    """Hand-built equivalent of build_agent: an explicit ReAct StateGraph.

    Same behavior as the prebuilt create_agent, but the loop is spelled out so
    the nodes, the routing condition, and the state model are all visible and
    owned. MessagesState supplies the `messages` key with an add_messages
    reducer, so each node returning {"messages": [...]} appends rather than
    overwrites — that append semantics is the whole reason the loop accumulates
    context instead of clobbering it.
    """
    if tools is None:
        tools = await load_carbon_tools()
    if model is None:
        model = _build_model()
    model_with_tools = model.bind_tools(tools)  # bind_tools: the model can now emit tool calls

    def call_model(state: MessagesState) -> dict:
        """The agent node: prepend the system prompt, call the LLM once."""
        messages = [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]]
        return {"messages": [model_with_tools.invoke(messages)]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))  # executes tool calls, appends ToolMessages
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)  # tool calls? -> "tools", else -> END
    graph.add_edge("tools", "agent")  # results flow back; the loop closes here
    return graph.compile(checkpointer=InMemorySaver())


class ScheduleState(TypedDict):
    """State for the schedule-commit flow."""

    window: str  # the proposed greenest window (set upstream)
    committed: bool  # whether the human approved the commit


def propose(state: ScheduleState) -> dict:
    """Stand-in for the agent deciding on a window (real version calls the tools)."""
    return {"window": state.get("windows", "02:00-05:00 (lowest forecast intensity)")}


def commit_schedule(state: ScheduleState) -> dict:
    """Gate the irreversible action behind human approval."""
    decision = interrupt(
        {
            "action": "commit_schedule",
            "window": state["window"],
            "prompt": "Approve running the job in this window?",
        }
    )
    # decision is whatever the caller passed to Command(resume=...)
    if decision == "approve":
        return {"committed": True}
    return {"committed": False}


def build_schedule_graph() -> Runnable:
    """A minimal commit-gated graph: propose -> (interrupt) commit."""
    g = StateGraph(ScheduleState)
    g.add_node("propose", propose)
    g.add_node("commit", commit_schedule)
    g.add_edge(START, "propose")
    g.add_edge("propose", "commit")
    g.add_edge("commit", END)
    return g.compile(checkpointer=InMemorySaver())
