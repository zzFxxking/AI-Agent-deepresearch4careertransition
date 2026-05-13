"""
工具层 - 封装 LLM 调用、网络搜索等基础工具
"""

import json
import re
from typing import Generator, Optional
from dataclasses import dataclass, field
from openai import OpenAI

from .config import LLM_CONFIG, SEARCH_CONFIG
from .search_clients.base import SearchResult, SearchResponse  # 统一数据结构，从基类导出
from .search_clients.bocha import BochaSearchClient  # 从 tools.py 迁移到 search_clients/


# ==================== 数据结构（LLM 专用） ====================


@dataclass
class LLMResponse:
    """LLM 响应数据结构"""
    content: str
    model: str
    usage: dict = field(default_factory=dict)
    success: bool = True
    error_msg: str = ""


# ==================== LLM 工具 ====================

class LLMClient:
    """LLM 客户端封装"""

    def __init__(self):
        self.client = OpenAI(
            api_key=LLM_CONFIG["api_key"],
            base_url=LLM_CONFIG["base_url"],
        )
        self.default_model = LLM_CONFIG["model"]

    def chat(
        self,
        prompt: str,
        system_prompt: str = "",
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """
        同步调用 LLM

        参数:
            prompt: 用户提示
            system_prompt: 系统提示
            model: 模型名称，默认使用配置中的模型
            temperature: 温度参数
            max_tokens: 最大生成token数

        返回:
            LLMResponse: LLM 响应对象
        """
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = self.client.chat.completions.create(
                model=model or self.default_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            return LLMResponse(
                content=response.choices[0].message.content,
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                success=True,
            )
        except Exception as e:
            return LLMResponse(
                content="",
                model=model or self.default_model,
                success=False,
                error_msg=str(e),
            )

    def chat_stream(
        self,
        prompt: str,
        system_prompt: str = "",
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Generator[str, None, None]:
        """
        流式调用 LLM

        参数:
            prompt: 用户提示
            system_prompt: 系统提示
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大生成token数

        返回:
            Generator: 生成器，逐步返回文本
        """
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = self.client.chat.completions.create(
                model=model or self.default_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                stream_options={"include_usage": True},
            )

            for chunk in response:
                if chunk.choices and len(chunk.choices) > 0:
                    delta_content = chunk.choices[0].delta.content
                    if delta_content:
                        yield delta_content
        except Exception as e:
            yield f"\n[错误: {str(e)}]"


# ==================== 搜索工具 ====================

# Bocha 搜索客户端已迁移到 search_clients/bocha.py（继承 BaseSearchClient）
# SearchClient 保留为向后兼容别名
SearchClient = BochaSearchClient


# ==================== 辅助函数 ====================

def extract_xml(text: str, tag: str) -> str:
    """
    从文本中提取指定 XML 标签的内容

    参数:
        text: 包含 XML 的文本
        tag: 要提取的标签名

    返回:
        str: 标签内容，未找到则返回空字符串
    """
    match = re.search(f"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
    return match.group(1).strip() if match else ""


def extract_json(text: str) -> dict:
    """
    从文本中提取 JSON 对象

    参数:
        text: 包含 JSON 的文本

    返回:
        dict: 解析后的 JSON 对象，失败返回空字典
    """
    # 尝试找到 JSON 代码块
    json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试直接解析
    try:
        # 找到第一个 { 和最后一个 }
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
    except json.JSONDecodeError:
        pass

    return {}


def format_search_context(results: list[SearchResult], max_results: int = 5) -> str:
    """
    将搜索结果格式化为上下文字符串

    参数:
        results: 搜索结果列表
        max_results: 最大结果数

    返回:
        str: 格式化的上下文字符串
    """
    if not results:
        return "未找到相关搜索结果。"

    context_parts = []
    for i, result in enumerate(results[:max_results], 1):
        context_parts.append(f"[来源{i}] {result.to_context()}")

    return "\n---\n".join(context_parts)


# ==================== 搜索客户端注册表 ====================

_search_client_registry: dict[str, SearchClient] = {}


def register_search_client(name: str, client: SearchClient) -> None:
    """注册搜索客户端"""
    _search_client_registry[name] = client


def get_search_client(name: str = "default") -> SearchClient:
    """获取指定名称的搜索客户端"""
    if name in _search_client_registry:
        return _search_client_registry[name]
    # 默认返回通用搜索客户端
    return get_search_client_default()


def get_search_client_by_name(name: str) -> Optional[SearchClient]:
    """根据名称获取搜索客户端（不存在返回None）"""
    return _search_client_registry.get(name)


# ==================== MCP 工具注册表 ====================

def get_mcp_manager():
    """获取 MCP 管理器单例（惰性导入，避免循环依赖）"""
    from .mcp import get_mcp_manager as _get_mcp_mgr
    return _get_mcp_mgr()


def init_mcp_from_config():
    """从项目配置初始化 MCP 管理器。在应用启动时调用一次。"""
    from .config import MCP_CONFIG
    if not MCP_CONFIG.get("enabled", True):
        return

    mgr = get_mcp_manager()
    mgr.enabled = True

    from .mcp.config import MCP_SERVER_CONFIGS, is_mcp_available
    if not is_mcp_available():
        return

    # 同步 enabled 状态到 MCP Server 配置
    server_configs = {}
    for name, cfg in MCP_SERVER_CONFIGS.items():
        mcp_cfg = MCP_CONFIG.get(name, {})
        cfg_copy = dict(cfg)
        cfg_copy["enabled"] = mcp_cfg.get("enabled", True)
        # GitHub token 优先使用 MCP_CONFIG 中的
        if name == "github" and mcp_cfg.get("token"):
            cfg_copy["env"]["GITHUB_PERSONAL_ACCESS_TOKEN"] = mcp_cfg["token"]
        server_configs[name] = cfg_copy

    mgr.configure(server_configs)


# ==================== 全局实例 ====================

# 创建全局客户端实例（惰性加载）
_llm_client = None
_search_client = None


def get_llm_client() -> LLMClient:
    """获取 LLM 客户端单例"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


def get_search_client_default() -> SearchClient:
    """获取默认搜索客户端单例"""
    global _search_client
    if _search_client is None:
        _search_client = SearchClient(
            api_key=SEARCH_CONFIG["api_key"],
            base_url=SEARCH_CONFIG["base_url"],
            default_count=SEARCH_CONFIG["default_count"],
            summary=SEARCH_CONFIG["summary"],
        )
    return _search_client
