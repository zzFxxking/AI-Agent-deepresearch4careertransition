"""Bocha 通用搜索客户端

从 tools.py 迁移出的 Bocha API 封装，继承 BaseSearchClient 统一接口。
"""

import time
import requests
from typing import Optional

from .base import BaseSearchClient, SearchResult, SearchResponse


class BochaSearchClient(BaseSearchClient):
    """Bocha 网络搜索客户端 —— 通用搜索兜底"""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.bocha.cn/v1/web-search",
        default_count: int = 10,
        summary: bool = True,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.default_count = default_count
        self.summary = summary

    def search(
        self,
        query: str,
        count: int = None,
        freshness: str = None,
        **kwargs,
    ) -> SearchResponse:
        """执行 Bocha 网络搜索"""
        try:
            payload = {
                "query": query,
                "summary": self.summary,
                "count": count or self.default_count,
            }
            if freshness:
                payload["freshness"] = freshness

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=30,
            )

            data = response.json()

            if data.get("code") != 200:
                return SearchResponse(
                    query=query,
                    success=False,
                    error_msg=data.get("msg", "搜索失败"),
                )

            web_pages = data.get("data", {}).get("webPages", {})
            results = []

            for item in web_pages.get("value", []):
                results.append(
                    SearchResult(
                        title=item.get("name", ""),
                        url=item.get("url", ""),
                        snippet=item.get("snippet", ""),
                        site_name=item.get("siteName", ""),
                        date=item.get("dateLastCrawled", "")[:10]
                        if item.get("dateLastCrawled")
                        else "",
                    )
                )

            return SearchResponse(
                query=query,
                results=results,
                total_matches=web_pages.get("totalEstimatedMatches", len(results)),
                success=True,
            )

        except requests.Timeout:
            return SearchResponse(
                query=query, success=False, error_msg="搜索请求超时"
            )
        except Exception as e:
            return SearchResponse(
                query=query, success=False, error_msg=str(e)
            )

    def multi_search(
        self,
        queries: list[str],
        count: int = None,
    ) -> list[SearchResponse]:
        """批量执行搜索（顺序执行）"""
        results = []
        for query in queries:
            result = self.search(query, count)
            results.append(result)
            time.sleep(0.5)
        return results
