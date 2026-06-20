import pytest
from langgraph.types import Command

from carbon_agent.agent import build_schedule_graph


@pytest.mark.asyncio
async def test_commit_pauses_then_resumes_on_approval():
    g = build_schedule_graph()
    cfg = {"configurable": {"thread_id": "test-approve"}}
    out = await g.ainvoke({"window": "", "committed": False}, cfg)
    assert out["__interrupt__"][0].value["action"] == "commit_schedule"  # paused
    out = await g.ainvoke(Command(resume="approve"), cfg)
    assert out["committed"] is True  # resumed, approved


@pytest.mark.asyncio
async def test_commit_rejected():
    g = build_schedule_graph()
    cfg = {"configurable": {"thread_id": "test-reject"}}
    await g.ainvoke({"window": "", "committed": False}, cfg)
    out = await g.ainvoke(Command(resume="reject"), cfg)
    assert out["committed"] is False  # edge case
