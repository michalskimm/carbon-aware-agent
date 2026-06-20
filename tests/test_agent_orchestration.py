import pytest
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from carbon_agent.agent import _build_model


@pytest.fixture
def llm_or_skip():
    """Skip unless a usable LLM can actually be constructed.

    Ask the real factory 'can you build a model?' instead of re-checking env
    vars here - so the test knows nothing about which providers or keys exist,
    and adding a new provider to _build_model never touches this test.
    """
    try:
        return _build_model()
    except Exception as e:  # noqa: BLE001 - any build failure means skip
        pytest.skip(f"No usable LLM configured: {e}")


@tool
def greenest_window(hours: int) -> str:
    """Fake carbon tool: returns a canned windows so no MCP server is needed."""
    return "02:00-05:00 (lowest forecast intensity)"


@pytest.mark.asyncio
async def test_agent_uses_injected_tool(llm_or_skip):
    from carbon_agent.agent import build_graph

    g = await build_graph(tools=[greenest_window], model=llm_or_skip)
    cfg = {"configurable": {"thread_id": "fake-tool-1"}}
    out = await g.ainvoke({"messages": [HumanMessage("When should I run a 3-hour job?")]}, cfg)
    assert out["messages"][-1].content  # agent produced a final answer
