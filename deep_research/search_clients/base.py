"""搜索客户端抽象基类 —— 统一 SearchResult / SearchResponse 数据结构"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, List
from dataclasses import dataclass, field


@dataclass
class SearchResult:
    """搜索结果数据结构"""
    title: str
    url: str
    snippet: str
    site_name: str = ""
    date: str = ""
    metadata: Dict = field(default_factory=dict)  # 扩展字段（stars/forks/来源平台等）

    def to_context(self) -> str:
        """转换为上下文字符串"""
        return f"【{self.title}】\n来源: {self.site_name or self.url}\n日期: {self.date or '未知'}\n内容: {self.snippet}\n"


@dataclass
class SearchResponse:
    """搜索响应数据结构"""
    query: str
    results: List[SearchResult] = field(default_factory=list)
    total_matches: int = 0
    success: bool = True
    error_msg: str = ""


class BaseSearchClient(ABC):
    """搜索客户端抽象基类 —— 所有垂直搜索客户端统一接口"""

    @abstractmethod
    def search(self, query: str, **kwargs) -> SearchResponse:
        """执行搜索，返回统一格式的搜索结果"""
        ...
