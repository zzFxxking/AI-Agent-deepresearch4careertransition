"""GitHub 垂直搜索客户端

直接调用 GitHub Search API，支持 stars / forks / language 过滤。
结果自动转换为 SearchResult 格式，方便 Worker 统一处理。
"""

import re
import os
import requests
from typing import Optional, Tuple

from .base import BaseSearchClient, SearchResult, SearchResponse


class GitHubSearchClient(BaseSearchClient):
    """GitHub 仓库搜索客户端"""

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_API_KEY", "")
        self.base_url = "https://api.github.com/search/repositories"
        self.per_page = 10

    def search(
        self,
        query: str,
        count: int = None,
        freshness: str = None,
        **kwargs,
    ) -> SearchResponse:
        """
        执行 GitHub 仓库搜索。

        参数:
            query: 搜索关键词，可内嵌过滤条件如 stars>100、language:python
            count: 返回结果数量（默认 10）
            freshness: 被 SearchClient 接口保留，GitHub API 中忽略

        返回:
            SearchResponse: 标准搜索结果格式
        """
        github_query, min_stars, min_forks, language = self._parse_query(query)

        # 空查询保护
        if not github_query.strip():
            github_query = "LLM"  # fallback，避免 GitHub API 400

        q_parts = [github_query]
        if min_stars is not None:
            q_parts.append(f"stars:>={min_stars}")
        if min_forks is not None:
            q_parts.append(f"forks:>={min_forks}")
        if language:
            q_parts.append(f"language:{language}")

        params = {
            "q": " ".join(q_parts),
            "sort": "stars",
            "order": "desc",
            "per_page": count or self.per_page,
        }

        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            resp = requests.get(
                self.base_url,
                params=params,
                headers=headers,
                timeout=30,
            )

            if resp.status_code == 403:
                # 速率限制或权限不足 —— 降级返回错误，Worker 层面会继续使用默认搜索兜底
                return SearchResponse(
                    query=query,
                    success=False,
                    error_msg="GitHub API 速率限制或权限不足（请配置 GITHUB_API_KEY）",
                )
            if resp.status_code != 200:
                return SearchResponse(
                    query=query,
                    success=False,
                    error_msg=f"GitHub API 错误: HTTP {resp.status_code}",
                )

            data = resp.json()
            items = data.get("items", [])
            results = []
            for item in items:
                desc = item.get("description") or "暂无描述"
                stars = item.get("stargazers_count", 0)
                forks = item.get("forks_count", 0)
                lang = item.get("language") or "未知"
                updated = item.get("updated_at", "")[:10] if item.get("updated_at") else ""
                snippet = (
                    f"{desc} | stars:{stars} | forks:{forks} | lang:{lang}"
                )
                results.append(
                    SearchResult(
                        title=item.get("full_name", ""),
                        url=item.get("html_url", ""),
                        snippet=snippet,
                        site_name="GitHub",
                        date=updated,
                    )
                )

            return SearchResponse(
                query=query,
                results=results,
                total_matches=data.get("total_count", len(results)),
                success=True,
            )

        except requests.Timeout:
            return SearchResponse(
                query=query, success=False, error_msg="GitHub 搜索请求超时"
            )
        except Exception as e:
            return SearchResponse(
                query=query, success=False, error_msg=f"GitHub 搜索异常: {e}"
            )

    def _parse_query(self, query: str) -> Tuple[str, Optional[int], Optional[int], Optional[str]]:
        """从自然语言查询中提取 GitHub 过滤条件。

        支持的写法:
            - stars>100, stars:>100, stars>=100, stars > 100
            - forks>10, forks:>10, forks>=10
            - language:python, python 语言
        """
        min_stars: Optional[int] = None
        min_forks: Optional[int] = None
        language: Optional[str] = None

        # stars —— 支持 stars>100, stars:>100, stars >= 100
        stars_match = re.search(
            r"stars\s*[:>]?\s*[>=]?\s*(\d+)", query, re.IGNORECASE
        )
        if stars_match:
            min_stars = int(stars_match.group(1))
            query = re.sub(
                r"stars\s*[:>]?\s*[>=]?\s*\d+", "", query, flags=re.IGNORECASE
            )

        # forks
        forks_match = re.search(
            r"forks\s*[:>]?\s*[>=]?\s*(\d+)", query, re.IGNORECASE
        )
        if forks_match:
            min_forks = int(forks_match.group(1))
            query = re.sub(
                r"forks\s*[:>]?\s*[>=]?\s*\d+", "", query, flags=re.IGNORECASE
            )

        # language:xxx
        lang_match = re.search(
            r"language\s*[:\s]\s*(\w+)", query, re.IGNORECASE
        )
        if lang_match:
            language = lang_match.group(1)
            query = re.sub(
                r"language\s*[:\s]\s*\w+", "", query, flags=re.IGNORECASE
            )

        # 清理后只保留有效关键词，并移除可能导致注入或语法问题的特殊字符
        cleaned = " ".join(query.split())
        # 移除 SQL/Shell 注入风险字符：分号、反引号、单双引号、注释符等
        cleaned = re.sub(r"['\"`;]|--", "", cleaned)
        return cleaned, min_stars, min_forks, language
