"""
CriticWorker 单元测试
使用 mock LLM 验证审查逻辑和返回结构
"""

import os
import sys
import json
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deep_research.workers import CriticWorker
from deep_research.tools import LLMResponse


# ========== Mock 数据 ==========

MOCK_REPORT = """
<!-- REPORT:main -->
# 主报告 - 执行摘要与学习路径

## 1. 执行摘要
测试摘要。

## 2. 学习路径

### 阶段1: 基础巩固期
- **持续时间**: 3周
- **核心任务**:
  - 巩固 Python 和 PyTorch 基础
  - 学习 Transformer 原理
- **验收标准**: 能手写 Attention 机制

### 阶段2: 项目实战期
- **持续时间**: 6周
- **核心任务**:
  - 深入研究 RAG 框架
  - 贡献开源项目
- **验收标准**: 完成一个端到端项目

### 阶段3: 面试冲刺期
- **持续时间**: 3周
- **核心任务**:
  - 背诵八股知识点
  - 模拟面试练习
- **验收标准**: 能流利回答高频面试题

<!-- END:main -->

<!-- REPORT:interview -->
# 八股知识点与模拟面试

## 知识点类别1: Transformer
### Q1: 什么是 Self-Attention？
**考察点**: 注意力机制
**参考答案要点**: 计算query/key/value点积
**来源**: 牛客网
**频率**: 高

## 模拟面试
### MQ1: 解释 Transformer 注意力机制
**考察点**: 注意力计算流程
**参考答案要点**: 从输入embedding到输出
**追问方向**: 为什么需要缩放
<!-- END:interview -->

<!-- REPORT:projects -->
# 项目推荐清单

## 项目1: miniMind
**GitHub**: https://github.com/jingyaogong/minimind
**Stars**: 200
**Forks**: 30
**技术栈**: Python, PyTorch
**匹配原因**: 适合入门大模型
**建议学习路径**: 从README开始
**关联面试题**:
- 如何实现一个简单的大模型？

## 项目2: RAGFlow
**GitHub**: https://github.com/infiniflow/ragflow
**Stars**: 3200
**Forks**: 450
**技术栈**: Python, FastAPI, React
**匹配原因**: 生产级RAG系统
**建议学习路径**: 先跑通docker部署
**关联面试题**:
- RAGFlow 的检索模块是如何设计的？
<!-- END:projects -->
"""

MOCK_CRITIC_JSON = {
    "project_review": {
        "toy_projects": [
            {
                "name": "miniMind",
                "reason": "纯教学demo，仅有200 stars，无实际应用场景",
                "replacement_suggestion": "建议替换为 LlamaIndex 或 LangChain"
            }
        ],
        "quality_projects": [
            {
                "name": "RAGFlow",
                "reason": "生产级RAG系统，3200 stars，有真实应用场景"
            }
        ],
        "match_issues": [],
        "score": 65,
        "comment": "混入了toy项目miniMind，需要替换"
    },
    "interview_coverage": {
        "covered_topics": ["Transformer"],
        "missing_topics": ["RAG", "Agent架构", "MCP协议", "RLHF"],
        "focus_areas_coverage": {
            "covered": ["RAG"],
            "missing": ["Agent框架", "MCP协议"]
        },
        "avoid_areas_violation": [],
        "coverage_score": 40,
        "comment": "八股覆盖度严重不足，仅覆盖Transformer"
    },
    "learning_path_review": {
        "difficulty_match": "appropriate",
        "difficulty_issues": [],
        "time_realistic": True,
        "time_issues": [],
        "phase_balance": "balanced",
        "score": 80,
        "comment": "学习路径难度与时间分配合理"
    },
    "overall_review": {
        "score": 62,
        "critical_issues": [
            "混入了toy项目miniMind",
            "八股覆盖度严重不足，缺少RAG/Agent/MCP/RLHF"
        ],
        "improvement_suggestions": [
            "将miniMind替换为生产级项目如LlamaIndex",
            "补充RAG、Agent架构、MCP协议相关八股"
        ],
        "revision_priority": "high",
        "comment": "报告质量不达标，需要大幅改进"
    }
}

MOCK_USER_PROFILE = {
    "target_role": "大模型应用开发工程师",
    "current_level": "有Python和PyTorch基础",
    "time_budget": "3个月",
    "company_tier": "大厂",
    "focus_areas": ["RAG", "Agent框架", "MCP协议"],
    "avoid_areas": ["前端开发", "嵌入式"],
}


def create_mock_llm_response(content: str, success: bool = True) -> LLMResponse:
    """构造 mock LLM 响应"""
    return LLMResponse(
        content=content,
        model="mock-model",
        success=success,
        error_msg="" if success else "mock error",
    )


def run_test_success():
    """测试：正常 LLM 返回有效 JSON"""
    print(f"\n{'='*60}")
    print("[测试] CriticWorker - 正常流程")
    print(f"{'='*60}")

    mock_llm = MagicMock()
    mock_llm.chat.return_value = create_mock_llm_response(
        content=f"```json\n{json.dumps(MOCK_CRITIC_JSON, ensure_ascii=False)}\n```"
    )

    with patch("deep_research.workers.get_llm_client", return_value=mock_llm):
        worker = CriticWorker()
        result = worker.execute({
            "report": MOCK_REPORT,
            "user_profile": MOCK_USER_PROFILE,
        })

    assert result["success"] is True, f"success 应为 True，实际: {result['success']}"

    # 验证项目审查
    project = result["project_review"]
    assert "toy_projects" in project
    assert len(project["toy_projects"]) == 1
    assert project["toy_projects"][0]["name"] == "miniMind"
    assert "replacement_suggestion" in project["toy_projects"][0]
    print(f"[OK] 项目审查: 识别出 {len(project['toy_projects'])} 个toy项目")

    # 验证八股覆盖度
    coverage = result["interview_coverage"]
    assert "missing_topics" in coverage
    assert len(coverage["missing_topics"]) >= 1
    assert "coverage_score" in coverage
    print(f"[OK] 八股覆盖度: 缺失 {len(coverage['missing_topics'])} 个知识点, 评分 {coverage['coverage_score']}")

    # 验证学习路径
    path = result["learning_path_review"]
    assert "difficulty_match" in path
    assert "time_realistic" in path
    print(f"[OK] 学习路径: 难度匹配={path['difficulty_match']}, 时间合理={path['time_realistic']}")

    # 验证整体审查
    overall = result["overall_review"]
    assert "score" in overall
    assert "critical_issues" in overall
    assert len(overall["critical_issues"]) >= 1
    assert "revision_priority" in overall
    print(f"[OK] 整体评分: {overall['score']}, 优先级: {overall['revision_priority']}")

    # 验证 prompt 构造
    call_args = mock_llm.chat.call_args
    prompt = call_args.kwargs.get("prompt") or call_args[1].get("prompt")
    assert "miniMind" not in prompt or "RAGFlow" in prompt, "prompt 应包含报告内容"
    assert "大模型应用开发工程师" in prompt, "prompt 应包含目标岗位"
    assert "RAG" in prompt and "Agent框架" in prompt, "prompt 应包含重点方向"
    print(f"[OK] Prompt 构造正确")

    print("[通过] CriticWorker - 正常流程")
    return True


def run_test_parse_failure():
    """测试：LLM 返回无效 JSON，验证 fallback"""
    print(f"\n{'='*60}")
    print("[测试] CriticWorker - JSON 解析失败 fallback")
    print(f"{'='*60}")

    mock_llm = MagicMock()
    mock_llm.chat.return_value = create_mock_llm_response(
        content="这不是有效的 JSON 格式"
    )

    with patch("deep_research.workers.get_llm_client", return_value=mock_llm):
        worker = CriticWorker()
        result = worker.execute({
            "report": MOCK_REPORT,
            "user_profile": MOCK_USER_PROFILE,
        })

    assert result["success"] is False, "解析失败时 success 应为 False"
    assert "error" in result
    assert result["overall_review"]["score"] == 0
    assert len(result["overall_review"]["critical_issues"]) >= 1
    print(f"[OK] Fallback 结构正确: success={result['success']}, score={result['overall_review']['score']}")
    print("[通过] CriticWorker - JSON 解析失败 fallback")
    return True


def run_test_llm_failure():
    """测试：LLM 调用失败，验证 fallback"""
    print(f"\n{'='*60}")
    print("[测试] CriticWorker - LLM 调用失败 fallback")
    print(f"{'='*60}")

    mock_llm = MagicMock()
    mock_llm.chat.return_value = create_mock_llm_response(
        content="",
        success=False,
    )

    with patch("deep_research.workers.get_llm_client", return_value=mock_llm):
        worker = CriticWorker()
        result = worker.execute({
            "report": MOCK_REPORT,
            "user_profile": MOCK_USER_PROFILE,
        })

    assert result["success"] is False, "LLM 失败时 success 应为 False"
    assert result["overall_review"]["revision_priority"] == "high"
    print(f"[OK] Fallback 结构正确: success={result['success']}, priority={result['overall_review']['revision_priority']}")
    print("[通过] CriticWorker - LLM 调用失败 fallback")
    return True


def run_test_orchestrator_integration():
    """测试：验证 Orchestrator 中正确引用了 CriticWorker"""
    print(f"\n{'='*60}")
    print("[测试] Orchestrator CriticWorker 集成检查")
    print(f"{'='*60}")

    from deep_research.orchestrator import Orchestrator, ResearchState
    from deep_research.workers import WorkerFactory

    # 检查 Orchestrator 导入了 CriticWorker
    import deep_research.orchestrator as orch_module
    assert hasattr(orch_module, "CriticWorker"), "orchestrator.py 应导入 CriticWorker"
    print("[OK] Orchestrator 已导入 CriticWorker")

    # 检查 WorkerFactory 有 create_critic_worker 方法
    assert hasattr(WorkerFactory, "create_critic_worker"), "WorkerFactory 应有 create_critic_worker"
    print("[OK] WorkerFactory 已添加 create_critic_worker")

    # 检查 ResearchState 有 critic_result 字段
    state = ResearchState(original_task="test")
    assert hasattr(state, "critic_result"), "ResearchState 应有 critic_result 字段"
    print("[OK] ResearchState 包含 critic_result 字段")

    print("[通过] Orchestrator CriticWorker 集成检查")
    return True


def main():
    results = []
    results.append(run_test_success())
    results.append(run_test_parse_failure())
    results.append(run_test_llm_failure())
    results.append(run_test_orchestrator_integration())

    print(f"\n{'='*60}")
    print(f"[汇总] 通过: {sum(results)}/{len(results)}")
    print(f"{'='*60}")

    if not all(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
