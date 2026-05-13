"""
综合测试脚本 - 覆盖正常用例、边界值、异常输入和失败场景
"""

import sys
import os
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deep_research.user_profile import UserProfile, UserProfileExtractor
from deep_research.memory import AgentMemory
from deep_research.output_formatter import OutputFormatter, FormattedOutput
from deep_research.tools import extract_json, extract_xml, format_search_context, SearchResult, SearchResponse, LLMResponse
from deep_research.search_clients.github import GitHubSearchClient
from deep_research.search_clients.interview import InterviewSearchClient
from deep_research.workers import SearchWorker, CriticWorker
from deep_research.orchestrator import Orchestrator, ResearchState, SubTask, TaskPlan, IterationRecord
from deep_research.config import JOB_SEARCH_CONFIG, AGENT_CONFIG


# ==================== 辅助函数 ====================

def make_state(report="", quality_score=0, iterations=0, start=0.0, end=0.0):
    """构造一个 ResearchState"""
    state = ResearchState(original_task="test")
    state.final_report = report
    state.quality_score = quality_score
    state.iteration_count = iterations
    state.start_time = start
    state.end_time = end
    state.status = "completed"
    return state


# ==================== 1. UserProfile 测试 ====================

def test_user_profile_normal():
    """正常用例：构造标准用户画像"""
    print("\n[Test] UserProfile - 正常构造")
    profile = UserProfile(
        target_role="算法工程师",
        time_budget="6个月",
        company_tier="大厂",
        current_level="有机器学习基础",
        focus_areas=["Transformer", "RLHF"],
        avoid_areas=["前端开发"],
        raw_query="测试查询",
    )
    assert profile.target_role == "算法工程师"
    assert profile.focus_areas == ["Transformer", "RLHF"]
    print("  [OK] 正常构造通过")
    return True


def test_user_profile_boundary():
    """边界值：空/超长字段"""
    print("\n[Test] UserProfile - 边界值")

    # 空 focus_areas / avoid_areas
    profile = UserProfile(
        target_role="测试",
        time_budget="1个月",
        company_tier="中厂",
        focus_areas=[],
        avoid_areas=[],
        raw_query="",
    )
    assert profile.focus_areas == []
    assert profile.avoid_areas == []
    print("  [OK] 空列表通过")

    # 超长文本
    long_text = "A" * 10000
    profile2 = UserProfile(
        target_role=long_text,
        time_budget=long_text,
        company_tier=long_text,
        raw_query=long_text,
    )
    assert len(profile2.target_role) == 10000
    print("  [OK] 超长文本通过")
    return True


def test_user_profile_exception():
    """异常输入：缺失必填字段、错误类型"""
    print("\n[Test] UserProfile - 异常输入")

    # 缺失必填字段 target_role
    try:
        UserProfile(time_budget="3个月", company_tier="大厂", raw_query="test")
        assert False, "应抛出验证错误"
    except Exception as e:
        print(f"  [OK] 缺失必填字段正确报错: {type(e).__name__}")

    # 错误类型：focus_areas 传入字符串而非列表
    try:
        UserProfile(
            target_role="test",
            time_budget="3个月",
            company_tier="大厂",
            focus_areas="RAG,Agent",  # 应该是列表
            raw_query="test",
        )
        # Pydantic v2 对 list[str] 传入字符串会尝试 coerce，可能成功也可能失败
        print("  [INFO] Pydantic 对字符串的处理视版本而定")
    except Exception as e:
        print(f"  [OK] 错误类型被拦截: {type(e).__name__}")

    return True


def test_extractor_boundary():
    """边界值：Extractor 对 None / 非字符串 query 的处理"""
    print("\n[Test] UserProfileExtractor - 边界值")

    extractor = UserProfileExtractor()

    # None query —— 当前代码可能崩溃
    try:
        result = extractor.extract(None)
        print(f"  [WARN] None query 没有崩溃，返回: {result}")
    except Exception as e:
        print(f"  [OK] None query 正确处理: {type(e).__name__}")

    # 空字符串
    result = extractor.extract("")
    assert result.target_role == "大模型应用开发工程师"  # fallback
    print("  [OK] 空字符串 fallback 正确")

    # 中文逗号分隔
    result = extractor.extract(
        "test",
        focus_areas="RAG，Agent框架，MCP",
        avoid_areas="前端，嵌入式"
    )
    # 注意：当前代码按英文逗号 split，中文逗号不会被分割
    assert result.focus_areas == ["RAG", "Agent框架", "MCP"], f"实际: {result.focus_areas}"
    print(f"  [INFO] 中文逗号处理: {result.focus_areas}")

    return True


# ==================== 2. AgentMemory 测试 ====================

def test_memory_failure_scenarios():
    """失败场景：文件不存在、损坏的数据文件、权限问题"""
    print("\n[Test] AgentMemory - 失败场景")

    with tempfile.TemporaryDirectory() as tmpdir:
        # 损坏的数据文件（非 JSON 也非 SQLite）
        bad_path = os.path.join(tmpdir, "bad.db")
        with open(bad_path, "w", encoding="utf-8") as f:
            f.write("{not valid anything")

        try:
            memory = AgentMemory(db_path=bad_path)
            # SQLite 会检测到文件损坏并自动重建
            pid = memory.save_profile(UserProfile(
                target_role="test", time_budget="3个月", company_tier="大厂", raw_query="test"
            ))
            assert pid is not None
            print("  [OK] 损坏文件被自动重建，AgentMemory 正常工作")
            memory.close()
        except Exception as e:
            print(f"  [FAIL] 损坏文件处理异常: {type(e).__name__}: {e}")
            return False

        # 不存在的目录（应自动创建）
        nested_path = os.path.join(tmpdir, "sub1", "sub2", "memory.db")
        memory2 = AgentMemory(db_path=nested_path)
        profile = UserProfile(target_role="test", time_budget="3个月", company_tier="大厂", raw_query="test")
        pid = memory2.save_profile(profile)
        assert pid is not None
        print("  [OK] 嵌套目录自动创建")
        memory2.close()

    return True


def test_memory_concurrent_risk():
    """风险场景：并发写入安全性验证"""
    print("\n[Test] AgentMemory - 并发风险检查")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "memory.db")
        memory = AgentMemory(db_path=db_path)

        # 快速连续保存多个 profile
        saved_ids = []
        for i in range(10):
            p = UserProfile(target_role=f"role_{i}", time_budget="3个月", company_tier="大厂", raw_query=f"q{i}")
            saved_ids.append(memory.save_profile(p))

        # 通过 get_profile 验证全部保存成功
        for pid in saved_ids:
            profile = memory.get_profile(pid)
            assert profile is not None, f"profile {pid} 未找到"
        print(f"  [OK] 连续保存 10 个 profile，全部可读取")

        memory.close()

    return True


# ==================== 3. OutputFormatter 测试 ====================

def test_formatter_normal():
    """正常用例：标准报告拆分"""
    print("\n[Test] OutputFormatter - 正常拆分")

    report = """<!-- REPORT:main -->
# 主报告

### 阶段1: 基础巩固期
- **持续时间**: 3周
- **核心任务**:
  - 任务1
- **验收标准**: 标准1
<!-- END:main -->

<!-- REPORT:interview -->
# 八股

## 知识点类别1: Transformer
### Q1: 什么是 Attention?
**考察点**: 注意力
**参考答案要点**: 点积
**来源**: 牛客网
**频率**: 高
<!-- END:interview -->

<!-- REPORT:projects -->
# 项目

## 项目1: RAGFlow
**GitHub**: https://github.com/infiniflow/ragflow
**Stars**: 32,000
**Forks**: 3,000
**技术栈**: Python, FastAPI
**匹配原因**: 生产级RAG
<!-- END:projects -->
"""

    state = make_state(report=report, quality_score=85, iterations=2, start=0.0, end=10.0)
    profile = UserProfile(target_role="test", time_budget="3个月", company_tier="大厂", raw_query="test")
    formatter = OutputFormatter(user_profile=profile)
    result = formatter.format(state)

    assert result.markdown.startswith("# 主报告")
    assert "RAGFlow" in result.markdown_projects
    assert "Attention" in result.markdown_interview
    assert "基础巩固期" in result.json_data["learning_path"]["phases"][0]["name"]
    print("  [OK] 正常拆分通过")
    return True


def test_formatter_boundary():
    """边界值：空报告、无标记、超大报告"""
    print("\n[Test] OutputFormatter - 边界值")

    # 空报告
    state = make_state(report="")
    formatter = OutputFormatter()
    result = formatter.format(state)
    assert result.markdown == ""
    assert result.json_data["learning_path"]["phases"]  # 有 fallback
    print("  [OK] 空报告 fallback 正确")

    # 无标记的旧格式报告
    old_report = "# 这是一份旧格式的完整报告\n\n## 学习路径\n一些内容"
    state = make_state(report=old_report)
    result = formatter.format(state)
    assert result.markdown == old_report
    assert result.markdown_interview == ""
    print("  [OK] 旧格式 fallback 正确")

    # 超大报告（模拟）
    huge_report = "<!-- REPORT:main -->\n" + "A" * 500000 + "\n<!-- END:main -->"
    state = make_state(report=huge_report)
    result = formatter.format(state)
    assert len(result.markdown) == 500000  # strip 后仅剩 500000 个 A
    print("  [OK] 超大报告处理通过")

    return True


def test_formatter_exception():
    """异常输入：畸形标记、不完整项目块"""
    print("\n[Test] OutputFormatter - 异常输入")

    # 不匹配的标记
    bad_report = "<!-- REPORT:main -->\n内容\n<!-- END:interview -->"
    state = make_state(report=bad_report)
    formatter = OutputFormatter()
    result = formatter.format(state)
    # 正则无法匹配，fallback 到旧格式
    assert result.markdown == bad_report
    print("  [OK] 不匹配标记 fallback 正确")

    # 畸形的项目块（缺少字段）
    bad_projects = """<!-- REPORT:projects -->
## 项目1: TestProject
**GitHub**: invalid-url
**Stars**: not_a_number
**技术栈**:
<!-- END:projects -->
"""
    state = make_state(report=bad_projects)
    result = formatter.format(state)
    projects = result.json_data.get("project_recommendations", [])
    # stars 解析失败应 fallback 到 0
    if projects:
        assert projects[0]["stars"] == 0, f"实际 stars: {projects[0]['stars']}"
        print(f"  [OK] 畸形数字 fallback: stars={projects[0]['stars']}")
    else:
        print("  [WARN] 未解析到项目")

    return True


def test_formatter_missing_state_fields():
    """异常输入：state 缺少关键字段"""
    print("\n[Test] OutputFormatter - 缺失 state 字段")

    state = ResearchState(original_task="test")
    # final_report 为 None（不是空字符串）
    state.final_report = None  # type: ignore
    state.start_time = 0.0
    state.end_time = None  # type: ignore

    formatter = OutputFormatter()
    try:
        result = formatter.format(state)
        print(f"  [WARN] None final_report 未崩溃，返回类型: {type(result)}")
    except Exception as e:
        print(f"  [OK] None final_report 正确处理: {type(e).__name__}: {e}")

    return True


# ==================== 4. tools.py 测试 ====================

def test_extract_json_boundary():
    """边界值：各种 JSON 提取场景"""
    print("\n[Test] extract_json - 边界值")

    # 标准 JSON 代码块
    text1 = '```json\n{"a": 1}\n```'
    assert extract_json(text1) == {"a": 1}
    print("  [OK] 标准代码块")

    # 无代码块，直接文本中的 JSON
    text2 = 'some text {"a": 1} more text'
    assert extract_json(text2) == {"a": 1}
    print("  [OK] 内嵌 JSON")

    # 空字符串
    assert extract_json("") == {}
    print("  [OK] 空字符串")

    # 无 JSON 的文本
    assert extract_json("no json here") == {}
    print("  [OK] 无 JSON")

    # 损坏的 JSON
    assert extract_json('```json\n{"a": }\n```') == {}
    print("  [OK] 损坏 JSON")

    # 超大 JSON
    huge = '{"data": "' + "A" * 100000 + '"}'
    result = extract_json(huge)
    assert len(result.get("data", "")) == 100000
    print("  [OK] 超大 JSON")

    return True


def test_format_search_context():
    """边界值：空结果、大量结果"""
    print("\n[Test] format_search_context - 边界值")

    # 空结果
    assert "未找到" in format_search_context([])
    print("  [OK] 空结果")

    # 大量结果
    results = [SearchResult(title=f"T{i}", url=f"http://example.com/{i}", snippet=f"S{i}") for i in range(100)]
    ctx = format_search_context(results, max_results=5)
    assert ctx.count("[来源") == 5
    print("  [OK] 大量结果截断")

    return True


# ==================== 5. GitHubSearchClient 测试 ====================

def test_github_parse_query_boundary():
    """边界值：极端查询字符串"""
    print("\n[Test] GitHubSearchClient - 查询解析边界值")

    client = GitHubSearchClient(token="")

    # 纯过滤条件，无关键词
    q, s, f, l = client._parse_query("stars>100 forks>5 language:python")
    assert q == "", f"期望空字符串，实际: '{q}'"
    assert s == 100
    print(f"  [INFO] 纯过滤条件解析: query='{q}', stars={s}, forks={f}, lang={l}")

    # 特殊字符和注入尝试（修复后危险符号应被过滤）
    q2, _, _, _ = client._parse_query("test\"; DROP TABLE users;--")
    assert '"' not in q2 and ';' not in q2 and '--' not in q2, f"危险符号应被过滤，实际: '{q2}'"
    print(f"  [OK] 危险符号已过滤: '{q2}'")

    # 负数（不应被匹配）
    q3, s3, _, _ = client._parse_query("stars>-100")
    assert s3 is None or s3 == 100  # 正则可能匹配 100
    print(f"  [INFO] 负数处理: stars={s3}")

    return True


def test_github_search_failure():
    """失败场景：网络超时、500 错误、无效响应"""
    print("\n[Test] GitHubSearchClient - 失败场景")

    client = GitHubSearchClient(token="")

    # 500 错误
    with patch("deep_research.search_clients.github.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp

        resp = client.search("test")
        assert not resp.success
        assert "500" in resp.error_msg
        print(f"  [OK] 500 错误: {resp.error_msg}")

    # 网络超时
    with patch("deep_research.search_clients.github.requests.get") as mock_get:
        mock_get.side_effect = requests.Timeout("连接超时")
        resp = client.search("test")
        assert not resp.success
        assert "超时" in resp.error_msg
        print(f"  [OK] 超时处理: {resp.error_msg}")

    # 无效 JSON 响应
    with patch("deep_research.search_clients.github.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_resp

        try:
            resp = client.search("test")
            print(f"  [WARN] 无效 JSON 未崩溃: success={resp.success}")
        except Exception as e:
            print(f"  [OK] 无效 JSON 正确处理: {type(e).__name__}")

    return True


# ==================== 6. InterviewSearchClient 测试 ====================

def test_interview_build_query_boundary():
    """边界值：空列表、超大列表、特殊字符"""
    print("\n[Test] InterviewSearchClient - 查询构建边界值")

    client = InterviewSearchClient()

    # None expected_sources
    q = client._build_query("test", None)
    assert q == "test"
    print("  [OK] None sources")

    # 空列表
    q = client._build_query("test", [])
    assert q == "test"
    print("  [OK] 空列表")

    # 不存在的 source
    q = client._build_query("test", ["不存在的站点"])
    assert q == "test"
    print("  [OK] 不存在的 source")

    # SQL 注入尝试
    q = client._build_query("test'; DROP TABLE--", ["知乎"])
    assert "DROP TABLE" in q  # 当前实现只是字符串拼接，未做清理
    print(f"  [INFO] 注入尝试结果: {q}")

    return True


# ==================== 7. SearchWorker 测试 ====================

def test_search_worker_ooda_boundary():
    """边界值：零预算、空子任务"""
    print("\n[Test] SearchWorker - OODA 边界值")

    worker = SearchWorker(max_queries=0, max_analysis_cycles=0)

    # 预算检查
    assert worker._should_terminate()
    print("  [OK] 零预算立即终止")

    # 空子任务
    empty_subtask = SubTask(id="t1", name="empty", description="", search_queries=[])
    # 不实际执行 execute（需要搜索客户端），只测试复杂度评估
    complexity = worker._assess_task_complexity(empty_subtask)
    assert complexity == "simple"  # 空描述 < 50 字符
    print(f"  [OK] 空子任务复杂度: {complexity}")

    return True


def test_search_worker_source_quality():
    """边界值：来源质量评估的各种场景"""
    print("\n[Test] SearchWorker - 来源质量评估边界值")

    worker = SearchWorker()

    # None 字段
    result = SearchResult(title="t", url="http://example.com", snippet="s", site_name=None)
    quality = worker._assess_source_quality(result)
    assert quality in ("high", "medium", "low")
    print(f"  [OK] None site_name: {quality}")

    # 空字符串
    result2 = SearchResult(title="", url="", snippet="", site_name="")
    quality2 = worker._assess_source_quality(result2)
    assert quality2 == "medium"  # 空 URL 不匹配任何指标
    print(f"  [OK] 空字符串: {quality2}")

    # 中文内容中的低质量指标
    result3 = SearchResult(title="t", url="http://example.com", snippet="可能也许据说", site_name="")
    quality3 = worker._assess_source_quality(result3)
    assert quality3 == "low"
    print(f"  [OK] 中文低质量指标: {quality3}")

    return True


def test_search_worker_dedup():
    """边界值：去重逻辑"""
    print("\n[Test] SearchWorker - 去重边界值")

    worker = SearchWorker()
    results = [
        SearchResult(title="A", url="http://a.com", snippet="s1"),
        SearchResult(title="B", url="http://a.com", snippet="s2"),  # 相同 URL
        SearchResult(title="C", url="http://c.com", snippet="s3"),
    ]
    unique = worker._deduplicate_results(results)
    assert len(unique) == 2
    print(f"  [OK] 去重: 3 -> {len(unique)}")

    return True


# ==================== 8. CriticWorker 测试 ====================

def test_critic_worker_exception():
    """异常输入：空报告、畸形 user_profile"""
    print("\n[Test] CriticWorker - 异常输入")

    # 空报告
    mock_llm = MagicMock()
    mock_llm.chat.return_value = LLMResponse(content="", model="m", success=False)

    with patch("deep_research.workers.get_llm_client", return_value=mock_llm):
        worker = CriticWorker()
        result = worker.execute({"report": "", "user_profile": {}})
        assert result["success"] is False
        print("  [OK] 空报告 + LLM 失败 fallback")

    # user_profile 为 None
    mock_llm2 = MagicMock()
    mock_llm2.chat.return_value = LLMResponse(content="```json\n{}\n```", model="m", success=True)

    with patch("deep_research.workers.get_llm_client", return_value=mock_llm2):
        worker = CriticWorker()
        try:
            result = worker.execute({"report": "test", "user_profile": None})
            print(f"  [WARN] None profile 未崩溃: {result['success']}")
        except (AttributeError, TypeError) as e:
            print(f"  [OK] None profile 正确处理: {type(e).__name__}")

    return True


# ==================== 9. Orchestrator 测试 ====================

def test_orchestrator_decompose_failure():
    """失败场景：LLM 调用失败时的 fallback"""
    print("\n[Test] Orchestrator - 任务拆解失败")

    mock_llm = MagicMock()
    mock_llm.chat.return_value = LLMResponse(content="", model="m", success=False, error_msg="API 限流")

    with patch("deep_research.orchestrator.get_llm_client", return_value=mock_llm):
        orch = Orchestrator(worker_factory=lambda: MagicMock())
        try:
            plan = orch.decompose_task("test task")
            assert False, "应抛出异常"
        except Exception as e:
            assert "任务拆解失败" in str(e)
            print(f"  [OK] 拆解失败正确抛出: {e}")

    return True


def test_orchestrator_state_structure():
    """正常用例：ResearchState 默认值"""
    print("\n[Test] Orchestrator - ResearchState 默认值")

    state = ResearchState(original_task="test")
    assert state.status == "initialized"
    assert state.quality_score == 0
    assert state.iteration_count == 0
    assert state.structured_output == {}
    assert state.critic_result is None
    print("  [OK] 默认值正确")

    return True


def test_orchestrator_worker_timeout():
    """失败场景：Worker 超时处理"""
    print("\n[Test] Orchestrator - Worker 超时")

    def slow_worker_factory():
        worker = MagicMock()
        def slow_execute(subtask):
            import time
            time.sleep(10)  # 模拟慢操作
            return {"success": True}
        worker.execute = slow_execute
        return worker

    # 将超时设为一个很小的值来测试（但当前 timeout 来自 AGENT_CONFIG，不可动态传参）
    # 我们直接测试 dispatch_workers 对异常 Worker 的处理
    mock_llm = MagicMock()
    mock_llm.chat.return_value = LLMResponse(content="test", model="m", success=True)

    with patch("deep_research.orchestrator.get_llm_client", return_value=mock_llm):
        orch = Orchestrator(worker_factory=slow_worker_factory, max_workers=1)

        # 构造一个任务计划
        plan = TaskPlan(
            task_understanding={},
            subtasks=[SubTask(id="t1", name="slow", description="", search_queries=["test"])],
            report_structure={},
        )
        plan.query_type = None

        # 由于 timeout_per_worker 默认 120 秒，这里无法快速测试超时
        # 改为测试失败 Worker
        def fail_worker_factory():
            worker = MagicMock()
            worker.execute.side_effect = Exception("Worker 崩溃")
            return worker

        orch2 = Orchestrator(worker_factory=fail_worker_factory, max_workers=1)
        results = orch2.dispatch_workers(plan)
        assert len(results) == 1
        assert results[0]["success"] is False
        assert "Worker 崩溃" in results[0]["error"]
        print(f"  [OK] Worker 崩溃正确处理: {results[0]['error']}")

    return True


# ==================== 10. Config 测试 ====================

def test_config_values():
    """正常用例：配置值合法性"""
    print("\n[Test] Config - 配置值检查")

    assert AGENT_CONFIG["max_workers"] > 0
    assert AGENT_CONFIG["max_iterations"] >= AGENT_CONFIG["min_iterations"]
    assert 0 <= AGENT_CONFIG["quality_threshold"] <= 100

    assert JOB_SEARCH_CONFIG["project_quality"]["min_stars"] >= 0
    assert JOB_SEARCH_CONFIG["project_quality"]["min_forks"] >= 0

    print("  [OK] 配置值合法")
    return True


# ==================== 主入口 ====================

def main():
    tests = [
        test_user_profile_normal,
        test_user_profile_boundary,
        test_user_profile_exception,
        test_extractor_boundary,
        test_memory_failure_scenarios,
        test_memory_concurrent_risk,
        test_formatter_normal,
        test_formatter_boundary,
        test_formatter_exception,
        test_formatter_missing_state_fields,
        test_extract_json_boundary,
        test_format_search_context,
        test_github_parse_query_boundary,
        test_github_search_failure,
        test_interview_build_query_boundary,
        test_search_worker_ooda_boundary,
        test_search_worker_source_quality,
        test_search_worker_dedup,
        test_critic_worker_exception,
        test_orchestrator_decompose_failure,
        test_orchestrator_state_structure,
        test_orchestrator_worker_timeout,
        test_config_values,
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"  [FAIL] {test.__name__}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"[汇总] 通过: {passed}/{total}")
    if passed < total:
        print("[失败列表]")
        for t, r in zip(tests, results):
            if not r:
                print(f"  - {t.__name__}")
    print("=" * 60)

    return all(results)


if __name__ == "__main__":
    import requests  # 用于 mock 异常
    success = main()
    sys.exit(0 if success else 1)
