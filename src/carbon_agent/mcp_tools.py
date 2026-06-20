"""Load the carbon-aware MCP server's tools as LangGraph-compatible tools."""

from __future__ import annotations

import os
from typing import cast

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from carbon_agent.resilience import call_with_resilience


async def load_carbon_tools() -> list[BaseTool]:
    """Fetch the four carbon tools from the MCP server over HTTP + JWT."""
    url = os.getenv("CARBON_MCP_URL", "http://localhost:8000/mcp")
    token = os.environ["CARBON_MCP_TOKEN"]  # read at call time, not import time
    client = MultiServerMCPClient(
        {
            "carbon": {
                "url": url,
                "transport": "http",
                "headers": {"Authorization": f"Bearer {token}"},
            }
        }
    )
    return cast(list[BaseTool], await call_with_resilience(client.get_tools))
