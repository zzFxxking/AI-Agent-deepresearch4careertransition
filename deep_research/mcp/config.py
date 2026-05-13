"""
MCP Server 配置 — 定义可用的 MCP Server 连接参数。

每个 Server 的配置结构:
    {
        "command": "npx" | "python" | "node",
        "args": [命令行参数列表],
        "env": {环境变量字典},
        "enabled": true/false,
        "description": "描述",
        "tools": ["工具列表及说明"],
    }
"""

import os

# ==================== GitHub MCP Server ====================

GITHUB_MCP_CONFIG = {
    "command": "npx",
    "args": [
        "-y",
        "@modelcontextprotocol/server-github",
    ],
    "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": os.getenv(
            "GITHUB_PERSONAL_ACCESS_TOKEN",
            os.getenv("GITHUB_API_KEY", ""),
        ),
    },
    "enabled": os.getenv("MCP_GITHUB_ENABLED", "true").lower() == "true",
    "description": "GitHub MCP Server — 仓库搜索、文件读取、Issue 管理",
    "tools": [
        "search_repositories",       # 搜索 GitHub 仓库
        "get_file_contents",         # 读取仓库文件内容
        "search_issues",             # 搜索 Issues
        "list_issues",               # 列出 Issues
        "search_code",               # 代码搜索
    ],
}


# ==================== Brave Search MCP Server（预留） ====================

BRAVE_MCP_CONFIG = {
    "command": "npx",
    "args": [
        "-y",
        "@modelcontextprotocol/server-brave-search",
    ],
    "env": {
        "BRAVE_API_KEY": os.getenv("BRAVE_API_KEY", ""),
    },
    "enabled": os.getenv("MCP_BRAVE_ENABLED", "false").lower() == "true",
    "description": "Brave Search MCP Server — 英文技术资料搜索（预留）",
    "tools": [
        "brave_web_search",
        "brave_local_search",
        "brave_news_search",
    ],
}


# ==================== MCP Server 注册表 ====================

MCP_SERVER_CONFIGS: dict[str, dict] = {
    "github": GITHUB_MCP_CONFIG,
    # "brave": BRAVE_MCP_CONFIG,  # 待后续启用
}


def get_enabled_servers() -> dict[str, dict]:
    """获取所有已启用的 MCP Server 配置。"""
    return {
        name: cfg
        for name, cfg in MCP_SERVER_CONFIGS.items()
        if cfg.get("enabled", True)
    }


def is_mcp_available() -> bool:
    """检查 MCP 运行时依赖是否可用。"""
    import shutil
    # 检查 npx（GitHub MCP 需要）
    has_npx = shutil.which("npx") is not None or shutil.which("node") is not None
    # 检查 mcp Python 包
    try:
        import mcp  # noqa: F401
        has_mcp_pkg = True
    except ImportError:
        has_mcp_pkg = False
    return has_npx and has_mcp_pkg
