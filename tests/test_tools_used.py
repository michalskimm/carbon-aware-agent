from langchain_core.messages import AIMessage, ToolMessage

from carbon_agent.gateway import _executed_tools


def test_reports_successful_tool():
    msgs = [
        AIMessage(content=""),
        ToolMessage(content="80 gCO2", name="greenest_window", tool_call_id="1"),
    ]
    assert _executed_tools(msgs) == ["greenest_window"]


def test_excludes_errored_tool():
    err = ToolMessage(content="boom", name="forecast", tool_call_id="2", status="error")
    assert _executed_tools([err]) == []


def test_no_tools_is_empty():
    assert _executed_tools([AIMessage(content="declined")]) == []
