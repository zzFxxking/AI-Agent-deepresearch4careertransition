"""面经垂直搜索客户端

基于通用搜索（Bocha）封装，自动根据 expected_sources 追加 site: 限定词，
提升面经类搜索的精准度。
"""

from typing import List, Optional

from .base import BaseSearchClient, SearchResponse
from .bocha import BochaSearchClient
from ..config import SEARCH_CONFIG


class InterviewSearchClient(BaseSearchClient):
    """面经专用搜索客户端 —— site 限定增强"""

    SITE_MAPPING = {
        "牛客网": "site:nowcoder.com",
        "力扣": "site:leetcode.cn OR site:leetcode.com",
        "知乎": "site:zhihu.com",
        "脉脉": "site:maimai.cn",
        "csdn": "site:csdn.net",
        "博客园": "site:cnblogs.com",
        "简书": "site:jianshu.com",
        "segmentfault": "site:segmentfault.com",
    }

    # 面经关键词触发映射（当 expected_sources 未显式指定时使用）
    KEYWORD_TRIGGERS = {
        "面经": ["牛客网", "知乎", "力扣"],
        "面试": ["牛客网", "知乎", "力扣"],
        "八股": ["知乎", "牛客网", "csdn"],
        "经验": ["牛客网", "知乎"],
    }

    def __init__(self, base_client: Optional[BochaSearchClient] = None):
        if base_client is not None:
            self.base_client = base_client
        else:
            self.base_client = BochaSearchClient(
                api_key=SEARCH_CONFIG["api_key"],
                base_url=SEARCH_CONFIG["base_url"],
                default_count=SEARCH_CONFIG["default_count"],
                summary=SEARCH_CONFIG["summary"],
            )

    def search(
        self,
        query: str,
        count: int = None,
        freshness: str = None,
        expected_sources: Optional[List[str]] = None,
        **kwargs,
    ) -> SearchResponse:
        """
        执行面经搜索，自动追加 site 限定。

        参数:
            query: 原始搜索查询
            count / freshness: 透传给底层搜索客户端
            expected_sources: Orchestrator 下发的期望来源列表
        """
        enhanced_query = self._build_query(query, expected_sources)
        return self.base_client.search(enhanced_query, count=count, freshness=freshness)

    def _build_query(self, query: str, expected_sources: Optional[List[str]]) -> str:
        """根据 expected_sources 和查询内容构建带 site 限定的查询词。"""
        sites = []

        # 1. 显式映射 expected_sources
        if expected_sources:
            for src in expected_sources:
                if src in self.SITE_MAPPING:
                    sites.append(self.SITE_MAPPING[src])

        # 2. 若未命中任何 site，根据查询关键词自动推断
        if not sites:
            lower_q = query.lower()
            for keyword, default_sources in self.KEYWORD_TRIGGERS.items():
                if keyword in lower_q:
                    for ds in default_sources:
                        site_expr = self.SITE_MAPPING.get(ds)
                        if site_expr and site_expr not in sites:
                            sites.append(site_expr)
                    break

        if sites:
            # 去重并保持查询可读性
            unique_sites = []
            seen = set()
            for s in sites:
                if s not in seen:
                    seen.add(s)
                    unique_sites.append(s)
            site_clause = " OR ".join(unique_sites)
            return f"{query} ({site_clause})"

        return query
