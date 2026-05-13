"""垂直搜索客户端 —— 按来源类型自动路由"""

from .base import BaseSearchClient, SearchResult, SearchResponse
from .bocha import BochaSearchClient
from .github import GitHubSearchClient
# InterviewSearchClient 通过 lazy import 避免与 tools.py 的循环依赖
# 使用时请直接: from deep_research.search_clients.interview import InterviewSearchClient

__all__ = [
    "BaseSearchClient",
    "SearchResult",
    "SearchResponse",
    "BochaSearchClient",
    "GitHubSearchClient",
]
