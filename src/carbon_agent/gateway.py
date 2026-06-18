"""FastAPI gateway in front of the carbon-scheduling agent."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph.state import CompiledStateGraph
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


async def _token_stream(
    agent: CompiledStateGraph, message: str, thread_id: str
) -> AsyncIterator[str]:
    """Yield the agent's reply as SSE lines, one per LLM token chunk."""
    cfg = {"configurable": {"thread_id": thread_id}}
    async for chunk, _meta in agent.astream(
        {"messages": [HumanMessage(message)]}, cfg, stream_mode="messages"
    ):
        # Only forward assistant tokens; tool/other messages aren't user-facing text.
        if isinstance(chunk, AIMessage) and chunk.content:
            yield f"data: {chunk.content}\n\n"
    yield "data: [DONE]\n\n"  # sentinel: lets the client close the stream early


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    thread_id = req.thread_id or str(uuid.uuid4())
    return StreamingResponse(
        _token_stream(app.state.agent, req.message, thread_id),
        media_type="text/event-stream",
        headers={"X-Thread-Id": thread_id},  # caller reads thread_id from the header
    )


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8001")))


if __name__ == "__main__":
    main()
