"""
MCP (Model Context Protocol) Manager — 统一管理外部 MCP Server 连接与工具调用。

支持:
- GitHub MCP Server: 精准查询仓库详情、README、Issues
- 后续扩展: Brave Search、Filesystem 等 MCP Server
- 同步/异步双模式调用
- 搜索结果自动转换为项目统一的 SearchResult 格式
"""

import asyncio
import json
import os
import threading
from dataclasses import dataclass, field
from typing import Optional, Callable

from ..search_clients.base import SearchResult, SearchResponse


# ==================== 数据结构 ====================

@dataclass
class MCPToolDef:
    """MCP 工具定义"""
    name: str
    description: str
    server: str
    parameters: dict = field(default_factory=dict)


@dataclass
class MCPToolResult:
    """MCP 工具调用结果"""
    server: str
    tool: str
    success: bool
    data: dict = field(default_factory=dict)
    error: str = ""


# ==================== MCP 管理器 ====================

class MCPManager:
    """
    MCP 连接管理器 — 管理多个 MCP Server 的生命周期与工具调用。

    使用方式:
        manager = MCPManager()
        manager.configure({"github": {...}})
        results = manager.search("RAG framework stars:>100", server="github")
    """

    def __init__(self):
        self._server_configs: dict[str, dict] = {}
        self._tools_cache: dict[str, list[MCPToolDef]] = {}
        self._enabled = True

    # ---------- 配置 ----------

    def configure(self, server_configs: dict[str, dict]) -> None:
        """配置 MCP Server 连接参数。

        server_configs 格式:
            {
                "github": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_xxx"},
                    "enabled": true,
                }
            }
        """
        self._server_configs = server_configs

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

    def is_server_available(self, name: str) -> bool:
        """检查 MCP Server 是否可用（已配置 + 依赖存在）"""
        cfg = self._server_configs.get(name, {})
        if not cfg.get("enabled", True):
            return False
        command = cfg.get("command", "")
        # 检查 npx 是否可用（GitHub MCP 依赖 Node.js）
        if command == "npx":
            import shutil
            return shutil.which("npx") is not None or shutil.which("node") is not None
        return True

    # ---------- 核心: 异步工具调用 ----------

    async def _connect_and_call(
        self,
        server_name: str,
        tool_name: str,
        tool_args: dict,
    ) -> MCPToolResult:
        """连接到 MCP Server，调用指定工具，返回结果。"""
        cfg = self._server_configs.get(server_name)
        if not cfg:
            return MCPToolResult(
                server=server_name, tool=tool_name,
                success=False, error=f"MCP Server '{server_name}' 未配置",
            )

        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            env = os.environ.copy()
            if cfg.get("env"):
                env.update(cfg["env"])

            server_params = StdioServerParameters(
                command=cfg["command"],
                args=cfg.get("args", []),
                env=env,
            )

            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    result = await session.call_tool(tool_name, tool_args)

                    # 解析返回内容
                    data = {}
                    if result.content:
                        for item in result.content:
                            if hasattr(item, "text") and item.text:
                                try:
                                    parsed = json.loads(item.text)
                                    if isinstance(parsed, dict):
                                        data.update(parsed)
                                    else:
                                        data["text"] = item.text
                                except json.JSONDecodeError:
                                    data["text"] = item.text

                    return MCPToolResult(
                        server=server_name, tool=tool_name,
                        success=True, data=data,
                    )

        except ImportError:
            return MCPToolResult(
                server=server_name, tool=tool_name,
                success=False, error="mcp 包未安装，请执行: pip install mcp",
            )
        except Exception as e:
            return MCPToolResult(
                server=server_name, tool=tool_name,
                success=False, error=str(e),
            )

    # ---------- 同步桥接 ----------

    def _run_async(self, coro):
        """在同步上下文中运行异步协程（线程安全）。"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        # 当前有事件循环在运行 → 在新线程中执行
        result_container = []
        error_container = []

        def _runner():
            try:
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                result_container.append(new_loop.run_until_complete(coro))
                new_loop.close()
            except Exception as e:
                error_container.append(e)

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        thread.join(timeout=60)

        if error_container:
            raise error_container[0]
        return result_container[0] if result_container else None

    def call_tool(self, server: str, tool: str, args: dict) -> MCPToolResult:
        """同步调用 MCP 工具。"""
        if not self._enabled:
            return MCPToolResult(
                server=server, tool=tool,
                success=False, error="MCP 未启用",
            )
        return self._run_async(self._connect_and_call(server, tool, args))

    # ---------- 搜索集成 ----------

    def search(
        self,
        query: str,
        server: str = "github",
        max_results: int = 10,
    ) -> SearchResponse:
        """
        通过 MCP Server 执行搜索，返回统一 SearchResponse 格式。

        参数:
            query: 搜索查询词
            server: MCP Server 名称（默认 github）
            max_results: 最大结果数

        返回:
            SearchResponse: 统一搜索响应
        """
        if not self._enabled or not self.is_server_available(server):
            return SearchResponse(
                query=query,
                success=False,
                error_msg=f"MCP Server '{server}' 不可用",
            )

        if server == "github":
            return self._search_github(query, max_results)
        else:
            return SearchResponse(
                query=query,
                success=False,
                error_msg=f"不支持的 MCP Server: '{server}'",
            )

    def _search_github(self, query: str, max_results: int) -> SearchResponse:
        """使用 GitHub MCP Server 搜索仓库。"""
        result = self.call_tool("github", "search_repositories", {
            "query": query,
            "perPage": max_results,
        })

        if not result.success:
            return SearchResponse(
                query=query,
                success=False,
                error_msg=result.error,
            )

        search_results = []
        items = result.data.get("items", [])
        if not items and "text" in result.data:
            # 尝试从文本中解析
            try:
                parsed = json.loads(result.data["text"])
                items = parsed.get("items", [])
            except (json.JSONDecodeError, TypeError):
                pass

        for item in items[:max_results]:
            search_results.append(SearchResult(
                title=item.get("full_name", item.get("name", "")),
                url=item.get("html_url", ""),
                snippet=item.get("description", ""),
                site_name="GitHub",
                date=item.get("updated_at", ""),
                metadata={
                    "stars": item.get("stargazers_count", 0),
                    "forks": item.get("forks_count", 0),
                    "language": item.get("language", ""),
                    "topics": item.get("topics", []),
                    "source": "mcp_github",
                },
            ))

        return SearchResponse(
            query=query,
            results=search_results,
            total_matches=len(search_results),
            success=True,
        )

    # ---------- 项目专属查询 ----------

    def get_repo_details(self, owner: str, repo: str) -> MCPToolResult:
        """获取指定仓库的详细信息（README、stats 等）。"""
        # 获取仓库基本信息
        result = self.call_tool("github", "get_file_contents", {
            "owner": owner,
            "repo": repo,
            "path": "README.md",
        })
        return result

    def search_issues(self, owner: str, repo: str, query: str = "") -> MCPToolResult:
        """搜索仓库 Issues。"""
        full_query = f"repo:{owner}/{repo}"
        if query:
            full_query += f" {query}"
        return self.call_tool("github", "search_issues", {
            "query": full_query,
        })


# ==================== 全局单例 ====================

_mcp_manager: Optional[MCPManager] = None


def get_mcp_manager() -> MCPManager:
    """获取 MCP 管理器单例"""
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = MCPManager()
    return _mcp_manager
