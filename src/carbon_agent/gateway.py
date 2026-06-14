"""FastAPI gateway in front of the carbon-scheduling agent."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from carbon_agent.agent import build_agent


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build the agent once at startup; store on app.state for handlers."""
    app.state.agent = await build_agent()
    yield
    # No async teardown: InMemorySaver holds no connections to close.


app = FastAPI(title="carbon-aware-agent", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    thread_id: str


@app.get("/")
async def root() -> dict:
    """Service index — points humans and probes at health and the API docs."""
    return {"service": "carbon-aware-agent", "health": "/health", "docs": "/docs"}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/chat")
async def chat(req: ChatRequest) -> ChatResponse:
    thread_id = req.thread_id or str(uuid.uuid4())
    cfg = {"configurable": {"thread_id": thread_id}}
    agent = app.state.agent
    out = await agent.ainvoke({"messages": [HumanMessage(req.message)]}, cfg)
    return ChatResponse(reply=out["messages"][-1].content, thread_id=thread_id)


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8001")))


if __name__ == "__main__":
    main()
