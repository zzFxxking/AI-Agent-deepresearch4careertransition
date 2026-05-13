"""
ReAct-Reflection Integration Tests - validate ReAct agent, tools, and CLI.
"""

import os
import sys
import json
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_tool_imports():
    from deep_research.react_tools import (
        ToolResult, BaseTool, SearchTool, ExtractTool,
        WriteTool, CritiqueTool, ALL_TOOLS, get_tool_by_name, get_tools_prompt,
    )

    assert len(ALL_TOOLS) == 4
    assert get_tool_by_name("search") is not None
    assert get_tool_by_name("extract") is not None
    assert get_tool_by_name("write") is not None
    assert get_tool_by_name("critique") is not None
    assert get_tool_by_name("nonexistent") is None

    prompt = get_tools_prompt()
    assert "search" in prompt
    assert "extract" in prompt
    assert "write" in prompt
    assert "critique" in prompt
    print("[OK] Tool imports and registry")


def test_tool_result_struct():
    from deep_research.react_tools import ToolResult

    r1 = ToolResult(success=True, content="test content")
    assert r1.success and r1.content == "test content" and not r1.error

    r2 = ToolResult(success=False, content="", error="failed")
    assert not r2.success and r2.error == "failed"
    print("[OK] ToolResult data structure")


def test_extract_tool():
    from deep_research.react_tools import ExtractTool

    tool = ExtractTool()
    assert tool.name == "extract"
    assert "topic" in tool.parameters

    # Empty source should fail
    result = tool.execute(topic="RLHF", source_text="")
    assert not result.success
    print("[OK] ExtractTool basic validation")


def test_write_tool():
    from deep_research.react_tools import WriteTool

    tool = WriteTool()
    assert tool.name == "write"
    assert "section" in tool.parameters
    assert "topic" in tool.parameters
    print("[OK] WriteTool basic validation")


def test_critique_tool():
    from deep_research.react_tools import CritiqueTool

    tool = CritiqueTool()
    assert tool.name == "critique"

    # Empty content should fail
    result = tool.execute(content="")
    assert not result.success
    print("[OK] CritiqueTool basic validation")


def test_react_agent_import():
    from deep_research.react_agent import (
        ReActReflectionAgent, ReActStep, ReActResult, REACT_SYSTEM_PROMPT,
    )

    assert REACT_SYSTEM_PROMPT
    assert "{tools}" in REACT_SYSTEM_PROMPT
    print("[OK] ReAct agent imports and prompt template")


def test_react_agent_init():
    from deep_research.react_agent import ReActReflectionAgent

    agent = ReActReflectionAgent(verbose=False)
    assert len(agent._tools) == 4
    assert "search" in agent._tools
    print("[OK] ReActReflectionAgent initialization")


def test_react_result_struct():
    from deep_research.react_agent import ReActStep, ReActResult

    step = ReActStep(
        step=1, thought="test", action="search",
        action_input={"query": "test"}, observation="result",
        tool_success=True, reflection="",
    )
    assert step.step == 1 and step.action == "search"

    result = ReActResult(
        task="test task", success=True,
        final_content="content", steps=[step],
        quality_score=80, duration=1.5,
    )
    assert result.success and result.quality_score == 80
    print("[OK] ReActStep/ReActResult data structures")


def test_react_agent_run_without_context():
    """Test agent handles missing context report gracefully."""
    from deep_research.react_agent import ReActReflectionAgent

    agent = ReActReflectionAgent(verbose=False)
    result = agent.run(
        task="扩展RLHF八股",
        context_report="",
        context_report_path="/nonexistent/path.md",
        max_steps=2,
    )
    assert not result.success
    assert "读取报告文件失败" in result.error
    print("[OK] ReAct agent handles missing file gracefully")


def test_search_tool_structure():
    from deep_research.react_tools import SearchTool

    tool = SearchTool()
    desc = tool.to_prompt_desc()
    assert "search" in desc
    assert "在线搜索" in desc
    print("[OK] Search tool prompt description")


if __name__ == "__main__":
    print("=" * 50)
    print("ReAct-Reflection Integration Tests")
    print("=" * 50)

    test_tool_imports()
    test_tool_result_struct()
    test_extract_tool()
    test_write_tool()
    test_critique_tool()
    test_react_agent_import()
    test_react_agent_init()
    test_react_result_struct()
    test_react_agent_run_without_context()
    test_search_tool_structure()

    print("\n" + "=" * 50)
    print("[OK] All ReAct-Reflection tests passed!")
    print("=" * 50)
