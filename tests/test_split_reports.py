"""
快速验证报告拆分逻辑
无需调用 LLM，纯本地测试
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deep_research.output_formatter import OutputFormatter, FormattedOutput
from deep_research.user_profile import UserProfile
from deep_research.orchestrator import ResearchState

# ========== 测试 1：带标记的三份报告拆分 ==========

test_report_marked = """
<!-- REPORT:main -->
# 主报告 - 执行摘要与学习路径

你是数学专业研一学生，目标是找大厂大模型应用开发实习。

## 1. 执行摘要
3-5句话概括用户背景、目标岗位和报告核心内容。

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

## 3. 参考来源
牛客网、知乎、GitHub
<!-- END:main -->

<!-- REPORT:interview -->
# 八股知识点与模拟面试

## 知识点类别1: Transformer
### Q1: 什么是 Self-Attention？
**考察点**: 对注意力机制的理解
**参考答案要点**: 计算query/key/value点积；加权求和；并行计算优势
**来源**: 牛客网
**频率**: 高

### Q2: Multi-Head Attention 的作用是什么？
**考察点**: 多头注意力机制
**参考答案要点**: 多个子空间并行计算；增强表达能力；不同头关注不同特征
**来源**: 力扣
**频率**: 高

## 知识点类别2: RAG
### Q1: RAG 的核心流程是什么？
**考察点**: RAG 架构理解
**参考答案要点**: 检索相关文档；拼接prompt；生成回答
**来源**: 知乎
**频率**: 高

### Q2: 向量检索的常用索引有哪些？
**考察点**: 向量数据库
**参考答案要点**: HNSW、IVF、Flat； trade-off between speed and accuracy
**来源**: 牛客网
**频率**: 中

## 模拟面试
### MQ1: 解释 Transformer 的注意力机制
**考察点**: 对注意力计算流程的理解
**参考答案要点**: 从输入embedding到输出；Scaled Dot-Product；Multi-Head
**追问方向**: 为什么需要缩放；与RNN相比的优势

### MQ2: RAG 系统如何评估检索质量？
**考察点**: RAG 评估指标
**参考答案要点**: Recall@K、MRR、NDCG；人工评估
**追问方向**: 如何优化检索效果；重排序策略
<!-- END:interview -->

<!-- REPORT:projects -->
# 项目推荐清单

## 项目1: RAGFlow
**GitHub**: https://github.com/infiniflow/ragflow
**Stars**: 3200
**Forks**: 450
**技术栈**: Python, FastAPI, React
**匹配原因**: 生产级RAG系统，适合学习企业级RAG架构
**建议学习路径**: 先跑通docker部署，再深入检索模块
**关联面试题**:
- RAGFlow 的检索模块是如何设计的？
- 如何为 RAGFlow 添加新的文档解析器？

## 项目2: LlamaIndex
**GitHub**: https://github.com/run-llama/llama_index
**Stars**: 35000
**Forks**: 5000
**技术栈**: Python
**匹配原因**: 最流行的RAG框架，生态丰富
**建议学习路径**: 从基础索引开始，逐步学习高级检索策略
**关联面试题**:
- LlamaIndex 的索引类型有哪些？
- 如何实现自定义检索器？
<!-- END:projects -->
"""

# ========== 测试 2：旧格式（无标记）fallback ==========

test_report_legacy = """
# 大模型应用开发工程师 面试准备报告

## 1. 执行摘要
测试摘要内容。

## 2. 学习路径
基础巩固期 -> 项目实战期 -> 面试冲刺期

## 3. 八股清单
Transformer、RAG、Agent...

## 4. 项目推荐
https://github.com/infiniflow/ragflow
https://github.com/run-llama/llama_index

## 5. 模拟面试
Q1: 什么是注意力机制？
"""


def create_mock_state(report: str) -> ResearchState:
    """构造一个带 final_report 的 mock ResearchState"""
    state = ResearchState(
        original_task="测试任务",
        start_time=0,
        end_time=100.5,
        status="completed",
        quality_score=92,
        iteration_count=2,
        final_report=report,
    )
    return state


def run_test(name: str, report: str, expected_main_has: str = None,
             expected_interview_has: str = None, expected_projects_has: str = None):
    print(f"\n{'='*60}")
    print(f"[测试] {name}")
    print(f"{'='*60}")

    profile = UserProfile(
        target_role="大模型应用开发工程师",
        time_budget="3个月",
        company_tier="大厂",
        current_level="研一",
        focus_areas=["RAG", "Agent"],
        avoid_areas=[],
        raw_query="测试",
    )
    formatter = OutputFormatter(user_profile=profile)
    state = create_mock_state(report)
    result = formatter.format(state)

    print(f"[结果] task_id: {result.json_data.get('task_id')}")
    print(f"[结果] quality_score: {result.metadata.get('quality_score')}")
    print(f"[结果] main 长度: {len(result.markdown)} 字符")
    print(f"[结果] interview 长度: {len(result.markdown_interview)} 字符")
    print(f"[结果] projects 长度: {len(result.markdown_projects)} 字符")

    # 断言检查
    ok = True
    if expected_main_has and expected_main_has not in result.markdown:
        print(f"[失败] 主报告未包含: {expected_main_has}")
        ok = False
    if expected_interview_has and expected_interview_has not in result.markdown_interview:
        print(f"[失败] 八股报告未包含: {expected_interview_has}")
        ok = False
    if expected_projects_has and expected_projects_has not in result.markdown_projects:
        print(f"[失败] 项目报告未包含: {expected_projects_has}")
        ok = False

    # 结构化数据检查
    learning_path = result.json_data.get("learning_path", {})
    categories = result.json_data.get("interview_questions", {}).get("categories", [])
    projects = result.json_data.get("project_recommendations", [])
    print(f"[结构化] 学习路径阶段数: {len(learning_path.get('phases', []))}")
    print(f"[结构化] 八股分类数: {len(categories)}")
    print(f"[结构化] 项目推荐数: {len(projects)}")

    for i, cat in enumerate(categories[:3]):
        print(f"  - 分类 {i+1}: {cat.get('name')} (问题数: {len(cat.get('questions', []))})")

    for i, proj in enumerate(projects[:3]):
        print(f"  - 项目 {i+1}: {proj.get('name')} (stars: {proj.get('stars')}, "
              f"技术栈: {proj.get('tech_stack')}, 关联面试题: {len(proj.get('interview_questions', []))})")

    if ok:
        print(f"[通过] {name}")
    else:
        print(f"[失败] {name}")
    return ok


def main():
    results = []

    results.append(run_test(
        "三份标记格式报告",
        test_report_marked,
        expected_main_has="基础巩固期",
        expected_interview_has="Transformer",
        expected_projects_has="RAGFlow",
    ))

    results.append(run_test(
        "旧格式报告 fallback",
        test_report_legacy,
        expected_main_has="面试准备报告",
    ))

    print(f"\n{'='*60}")
    print(f"[汇总] 通过: {sum(results)}/{len(results)}")
    print(f"{'='*60}")

    if not all(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
