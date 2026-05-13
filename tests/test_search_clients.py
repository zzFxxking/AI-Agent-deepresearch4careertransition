"""
垂直搜索客户端单元测试
覆盖 GitHubSearchClient、InterviewSearchClient 和 SearchWorker 路由逻辑
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import Mock, patch, MagicMock

from deep_research.search_clients.github import GitHubSearchClient
from deep_research.search_clients.interview import InterviewSearchClient
from deep_research.workers import SearchWorker
from deep_research.tools import SearchResult, SearchResponse


# ==================== GitHubSearchClient 测试 ====================

def test_github_parse_query():
    """测试 GitHub 查询解析器"""
    print("\n" + "=" * 60)
    print("[测试] GitHubSearchClient - 查询解析")
    print("=" * 60)

    client = GitHubSearchClient(token="")

    cases = [
        ("LLM Agent stars>100", ("LLM Agent", 100, None, None)),
        ("RAG 框架 stars:>50 forks>10", ("RAG 框架", 50, 10, None)),
        ("python project language:python", ("python project", None, None, "python")),
        ("stars>=200 language:rust", ("", 200, None, "rust")),
        ("miniMind 教学项目", ("miniMind 教学项目", None, None, None)),
    ]

    for query, expected in cases:
        result = client._parse_query(query)
        assert result == expected, f"解析失败: {query} -> {result}, 期望 {expected}"
        print(f"[OK] '{query}' -> {result}")

    print("[通过] GitHubSearchClient - 查询解析")
    return True


def test_github_search_mock():
    """测试 GitHub 搜索客户端（mock HTTP）"""
    print("\n" + "=" * 60)
    print("[测试] GitHubSearchClient - 搜索执行（mock）")
    print("=" * 60)

    client = GitHubSearchClient(token="fake_token")

    mock_data = {
        "total_count": 2,
        "items": [
            {
                "full_name": "infiniflow/ragflow",
                "html_url": "https://github.com/infiniflow/ragflow",
                "description": "基于深度文档理解的 RAG 引擎",
                "stargazers_count": 32500,
                "forks_count": 3000,
                "language": "Python",
                "updated_at": "2026-05-10T12:00:00Z",
            },
            {
                "full_name": "test/repo",
                "html_url": "https://github.com/test/repo",
                "description": None,
                "stargazers_count": 10,
                "forks_count": 2,
                "language": None,
                "updated_at": "",
            },
        ]
    }

    with patch("deep_research.search_clients.github.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_data
        mock_get.return_value = mock_resp

        resp = client.search("RAG 开源项目 stars>100", count=5)

        assert resp.success, f"搜索应成功: {resp.error_msg}"
        assert len(resp.results) == 2, f"应返回2条结果，实际 {len(resp.results)}"
        assert resp.total_matches == 2

        # 验证结果字段转换
        first = resp.results[0]
        assert first.title == "infiniflow/ragflow"
        assert first.site_name == "GitHub"
        assert "32500" in first.snippet
        assert "Python" in first.snippet
        assert first.date == "2026-05-10"

        # 验证无描述的项目也能正常处理
        second = resp.results[1]
        assert "暂无描述" in second.snippet
        assert "未知" in second.snippet

        # 验证请求参数
        call_args = mock_get.call_args
        params = call_args.kwargs.get("params") or call_args[1].get("params")
        assert "RAG 开源项目" in params["q"]
        assert "stars:>=100" in params["q"]
        assert params["per_page"] == 5

        print(f"[OK] GitHub 搜索成功，返回 {len(resp.results)} 条结果")
        print(f"   - {first.title}: {first.snippet[:50]}...")

    print("[通过] GitHubSearchClient - 搜索执行（mock）")
    return True


def test_github_rate_limit():
    """测试 GitHub 速率限制处理"""
    print("\n" + "=" * 60)
    print("[测试] GitHubSearchClient - 速率限制处理")
    print("=" * 60)

    client = GitHubSearchClient(token="")

    with patch("deep_research.search_clients.github.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_get.return_value = mock_resp

        resp = client.search("test")
        assert not resp.success
        assert "速率限制" in resp.error_msg
        print(f"[OK] 403 正确降级: {resp.error_msg}")

    print("[通过] GitHubSearchClient - 速率限制处理")
    return True


# ==================== InterviewSearchClient 测试 ====================

def test_interview_build_query():
    """测试面经查询构建"""
    print("\n" + "=" * 60)
    print("[测试] InterviewSearchClient - 查询构建")
    print("=" * 60)

    client = InterviewSearchClient()

    # 1. 显式 expected_sources
    q1 = client._build_query("大模型面试八股", ["牛客网", "知乎"])
    assert "site:nowcoder.com" in q1, f"应包含牛客网 site: {q1}"
    assert "site:zhihu.com" in q1, f"应包含知乎 site: {q1}"
    print(f"[OK] 显式来源: {q1}")

    # 2. 关键词自动触发
    q2 = client._build_query("Transformer 面经", None)
    assert "site:" in q2, f"关键词触发应生成 site: {q2}"
    print(f"[OK] 关键词触发: {q2}")

    # 3. 无触发条件时原样返回
    q3 = client._build_query("通用技术文章", None)
    assert q3 == "通用技术文章", f"无触发应原样返回: {q3}"
    print(f"[OK] 无触发原样返回: {q3}")

    # 4. 去重测试
    q4 = client._build_query("面试", ["牛客网", "牛客网"])
    # 不应出现重复的 site:nowcoder.com
    assert q4.count("site:nowcoder.com") == 1, f"应去重: {q4}"
    print(f"[OK] 去重: {q4}")

    print("[通过] InterviewSearchClient - 查询构建")
    return True


def test_interview_search_proxy():
    """测试面经客户端透传到底层搜索"""
    print("\n" + "=" * 60)
    print("[测试] InterviewSearchClient - 透传调用")
    print("=" * 60)

    mock_base = Mock()
    mock_base.search.return_value = SearchResponse(
        query="test", results=[SearchResult(title="t", url="u", snippet="s")]
    )
    client = InterviewSearchClient(base_client=mock_base)

    resp = client.search("大模型八股", count=5, freshness="week", expected_sources=["知乎"])

    assert resp.success
    assert len(resp.results) == 1
    # 验证底层被调用，且查询词被增强
    call_args = mock_base.search.call_args
    enhanced_query = call_args[0][0]
    assert "大模型八股" in enhanced_query
    assert "site:zhihu.com" in enhanced_query
    assert call_args.kwargs.get("count") == 5
    assert call_args.kwargs.get("freshness") == "week"
    print(f"[OK] 透传成功，增强查询: {enhanced_query}")

    print("[通过] InterviewSearchClient - 透传调用")
    return True


# ==================== SearchWorker 路由测试 ====================

def test_search_worker_routing():
    """测试 SearchWorker 根据 expected_sources 自动路由"""
    print("\n" + "=" * 60)
    print("[测试] SearchWorker - 客户端路由")
    print("=" * 60)

    worker = SearchWorker()

    # 1. GitHub 路由
    client = worker._select_search_client(["GitHub", "技术博客"])
    from deep_research.search_clients.github import GitHubSearchClient
    assert isinstance(client, GitHubSearchClient), f"应路由到 GitHubSearchClient，实际 {type(client)}"
    print("[OK] GitHub 来源正确路由到 GitHubSearchClient")

    # 2. 面经路由
    client = worker._select_search_client(["牛客网", "力扣"])
    from deep_research.search_clients.interview import InterviewSearchClient
    assert isinstance(client, InterviewSearchClient), f"应路由到 InterviewSearchClient，实际 {type(client)}"
    print("[OK] 面经来源正确路由到 InterviewSearchClient")

    # 3. 八股关键词路由
    client = worker._select_search_client(["知乎", "技术博客"])  # 虽然没面经站点，但八股在 keywords 里
    # 注意：这里 "知乎" 是 interview_markers 之一，所以会路由到 InterviewSearchClient
    assert isinstance(client, InterviewSearchClient), f"知乎应触发面经路由，实际 {type(client)}"
    print("[OK] 知乎关键词正确路由到 InterviewSearchClient")

    # 4. 默认路由
    client = worker._select_search_client(["技术博客"])
    from deep_research.tools import SearchClient
    assert isinstance(client, SearchClient), f"通用来源应路由到默认 SearchClient，实际 {type(client)}"
    print("[OK] 通用来源正确路由到默认 SearchClient")

    # 5. 空来源路由
    client = worker._select_search_client([])
    assert isinstance(client, SearchClient), f"空来源应回退到默认 SearchClient，实际 {type(client)}"
    print("[OK] 空来源正确回退到默认 SearchClient")

    print("[通过] SearchWorker - 客户端路由")
    return True


# ==================== 主入口 ====================

def main():
    results = []
    results.append(test_github_parse_query())
    results.append(test_github_search_mock())
    results.append(test_github_rate_limit())
    results.append(test_interview_build_query())
    results.append(test_interview_search_proxy())
    results.append(test_search_worker_routing())

    print("\n" + "=" * 60)
    print(f"[汇总] 通过: {sum(results)}/{len(results)}")
    print("=" * 60)

    if not all(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
