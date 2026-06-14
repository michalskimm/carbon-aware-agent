"""The carbon-scheduling agent: a LangGraph agent over the MCP carbon tools."""

from __future__ import annotations

import os

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.runnables import Runnable
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from carbon_agent.mcp_tools import load_carbon_tools

SYSTEM_PROMPT = (
    "You are a carbon-aware scheduling assistant. When a user wants to run a workload, "
    "use the greenest_window tool to find the lowest-carbon time, and explain the choice "
    "in one or two sentences. Use the other tools for current intensity, forecast, or mix."
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
    from langchain_anthropic import ChatAnthropic

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
    checkpointer = InMemorySaver()  # swap for a durable store in prod (see Defend-it)
    return create_agent(model, tools, system_prompt=SYSTEM_PROMPT, checkpointer=checkpointer)


async def build_graph() -> Runnable:
    """Hand-built equivalent of build_agent: an explicit ReAct StateGraph.

    Same behavior as the prebuilt create_agent, but the loop is spelled out so
    the nodes, the routing condition, and the state model are all visible and
    owned. MessagesState supplies the `messages` key with an add_messages
    reducer, so each node returning {"messages": [...]} appends rather than
    overwrites — that append semantics is the whole reason the loop accumulates
    context instead of clobbering it.
    """
    tools = await load_carbon_tools()
    model = _build_model().bind_tools(tools)  # bind_tools: the model can now emit tool calls

    def call_model(state: MessagesState) -> dict:
        """The agent node: prepend the system prompt, call the LLM once."""
        messages = [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]]
        return {"messages": [model.invoke(messages)]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))  # executes tool calls, appends ToolMessages
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)  # tool calls? -> "tools", else -> END
    graph.add_edge("tools", "agent")  # results flow back; the loop closes here
    return graph.compile(checkpointer=InMemorySaver())
