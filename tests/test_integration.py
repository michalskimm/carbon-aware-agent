import os

import pytest

requires_mcp = pytest.mark.skipif(
    not os.getenv("CARBON_MCP_URL"),
    reason="needs a running MCP server + CARBON_MCP_URL",
)


@requires_mcp
@pytest.mark.asyncio
async def test_agent_end_to_end():
    from langchain_core.messages import HumanMessage

    from carbon_agent.agent import build_graph

    g = await build_graph()
    cfg = {"configurable": {"thread_id": "it-1"}}
    out = await g.ainvoke({"messages": [HumanMessage("test")]}, cfg)
    assert out["messages"][-1].content  # got a non-empty reply
