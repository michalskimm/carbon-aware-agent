"""Load the carbon-aware MCP server's tools as LangGraph-comatible tools."""

from __future__ import annotations

import os

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

MCP_URL = os.getenv("CARBON_MCP_URL", "http://localhost:8000/mcp")
MCP_TOKEN = os.environ["CARBON_MCP_TOKEN"]


async def load_carbon_tools() -> list[BaseTool]:
    """Fetch the four carbon tools from the MCP server over streamable HTTP + JWT."""
    client = MultiServerMCPClient(
        {
            "carbon": {
                "url": MCP_URL,
                "transport": "http",
                "headers": {"Authorization": f"Bearer {MCP_TOKEN}"},
            }
        }
    )
    return await client.get_tools()
