"""
MCP Integration Tests - validate MCP module config, connection, and search.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_mcp_config():
    from deep_research.mcp.config import MCP_SERVER_CONFIGS, get_enabled_servers, is_mcp_available

    assert "github" in MCP_SERVER_CONFIGS, "Missing GitHub MCP config"
    github_cfg = MCP_SERVER_CONFIGS["github"]
    assert github_cfg["command"] == "npx"
    assert "search_repositories" in github_cfg["tools"]

    enabled = get_enabled_servers()
    print(f"[OK] MCP config loaded, enabled servers: {list(enabled.keys())}")

    mcp_available = is_mcp_available()
    print(f"[INFO] MCP runtime available: {mcp_available}")


def test_mcp_manager_init():
    from deep_research.mcp import MCPManager, get_mcp_manager

    mgr = get_mcp_manager()
    assert mgr is not None
    assert not mgr._server_configs

    mgr.configure({
        "github": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": os.getenv("GITHUB_API_KEY", "")},
            "enabled": True,
        }
    })

    assert "github" in mgr._server_configs
    print("[OK] MCP manager initialized")


def test_mcp_init_from_config():
    from deep_research.tools import init_mcp_from_config, get_mcp_manager

    init_mcp_from_config()

    mgr = get_mcp_manager()
    assert mgr is not None
    print(f"[OK] MCP init from config, enabled={mgr.enabled}")


def test_mcp_tool_def():
    from deep_research.mcp import MCPToolDef, MCPToolResult

    tool = MCPToolDef(
        name="search_repositories",
        description="Search GitHub repos",
        server="github",
        parameters={"query": "str", "perPage": "int"},
    )
    assert tool.name == "search_repositories"
    assert tool.server == "github"

    result = MCPToolResult(
        server="github", tool="search_repositories",
        success=True, data={"items": []},
    )
    assert result.success
    assert not result.error

    error_result = MCPToolResult(
        server="github", tool="search_repositories",
        success=False, error="Token not configured",
    )
    assert not error_result.success
    assert error_result.error == "Token not configured"

    print("[OK] MCP data structures test passed")


def test_mcp_search_integration():
    from deep_research.workers import SearchWorker

    worker = SearchWorker(max_queries=3, max_analysis_cycles=1)

    # _should_use_mcp: only for GitHub sources
    assert not worker._should_use_mcp(["NiuKe", "Zhihu"])

    # _try_mcp_search: should return None without real token (no crash)
    result = worker._try_mcp_search("RAG framework")
    assert result is None or hasattr(result, "success")
    print("[OK] MCP-SearchWorker integration test passed")


def test_mcp_disabled_graceful():
    from deep_research.mcp import MCPManager

    mgr = MCPManager()
    mgr.enabled = False

    result = mgr.call_tool("github", "search_repositories", {"query": "test"})
    assert not result.success
    assert "MCP" in result.error

    search_result = mgr.search("test", server="github")
    assert not search_result.success
    print("[OK] MCP disabled graceful degradation test passed")


if __name__ == "__main__":
    print("=" * 50)
    print("MCP Integration Tests")
    print("=" * 50)

    test_mcp_config()
    test_mcp_manager_init()
    test_mcp_init_from_config()
    test_mcp_tool_def()
    test_mcp_search_integration()
    test_mcp_disabled_graceful()

    print("\n" + "=" * 50)
    print("[OK] All MCP integration tests passed!")
    print("=" * 50)
    print()
    print("Note: To test real GitHub MCP connection:")
    print("  1. Install Node.js (>=18) and npx")
    print("  2. Set GITHUB_PERSONAL_ACCESS_TOKEN env var")
    print("  3. Run: pip install mcp")
    print("  4. Manual test:")
    print("     from deep_research.mcp import get_mcp_manager")
    print("     mgr = get_mcp_manager()")
    print("     mgr.configure({...})")
    print("     result = mgr.search('RAG framework stars:>100')")
