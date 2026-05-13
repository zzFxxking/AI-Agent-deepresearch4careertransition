"""
Orchestrator - 研究任务协调者 (Lead Agent)

基于高级研究智能体设计优化：
- 查询类型分类（深度优先/广度优先/简单查询）
- 动态子智能体数量调整
- 智能终止（收益递减检测）
- 批判性信息验证

负责：
1. 任务拆解：将复杂研究任务分解为子任务
2. 查询类型判断：确定最优研究策略
3. 动态调度：根据复杂度调整子智能体数量
4. 任务分发：将子任务分配给 Workers
5. 结果汇总：收集并整合 Worker 结果
6. 质量控制：迭代优化直至达标或收益递减
7. 报告生成：生成最终研究报告
"""

import json
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Literal
from concurrent.futures import ThreadPoolExecutor, as_completed

from .tools import get_llm_client, extract_json, LLMResponse
from .prompts import (
    ORCHESTRATOR_SYSTEM_PROMPT,
    TASK_DECOMPOSITION_PROMPT,
    SYNTHESIS_PROMPT,
    QUALITY_CHECK_PROMPT,
    GAP_ANALYSIS_PROMPT,
    REPORT_REFINEMENT_PROMPT,
    DIMINISHING_RETURNS_CHECK_PROMPT,
    PARALLEL_TASK_COORDINATION_PROMPT,
)
from .config import AGENT_CONFIG
from .workers import CriticWorker


# ==================== 数据结构 ====================

@dataclass
class SubTask:
    """子任务数据结构 - 增强版"""
    id: str
    name: str
    description: str
    search_queries: list[str]
    priority: str = "medium"
    expected_output: str = ""
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[dict] = None
    # 新增字段
    research_objective: str = ""
    expected_sources: list[str] = field(default_factory=list)
    scope_boundaries: str = ""


@dataclass
class QueryTypeAnalysis:
    """查询类型分析结果"""
    query_type: Literal["depth_first", "breadth_first", "simple"]
    reasoning: str
    recommended_approach: str
    recommended_worker_count: int


@dataclass
class TaskPlan:
    """任务计划数据结构 - 增强版"""
    task_understanding: dict
    subtasks: list[SubTask]
    report_structure: dict
    # 新增字段
    query_type: QueryTypeAnalysis = None
    research_plan: dict = field(default_factory=dict)
    worker_count: dict = field(default_factory=dict)


@dataclass
class IterationRecord:
    """单次迭代记录"""
    iteration: int
    report: str
    quality_score: int
    quality_result: dict
    gap_analysis: Optional[dict] = None
    supplementary_results: list[dict] = field(default_factory=list)
    # 新增字段
    diminishing_returns_detected: bool = False
    score_improvement: int = 0
    critic_result: Optional[dict] = None  # Critic 审查结果（如果在本次迭代中执行）


@dataclass
class ResearchState:
    """研究状态数据结构"""
    original_task: str
    task_plan: Optional[TaskPlan] = None
    worker_results: list[dict] = field(default_factory=list)
    final_report: str = ""
    quality_score: int = 0
    status: str = "initialized"  # initialized, planning, researching, synthesizing, iterating, completed, failed
    error_msg: str = ""
    start_time: float = 0
    end_time: float = 0
    # 迭代优化相关
    iteration_count: int = 0
    iteration_history: list[IterationRecord] = field(default_factory=list)
    # 新增字段
    query_type: str = ""
    early_termination_reason: str = ""
    user_profile: Optional[dict] = None      # 【新增】用户画像
    structured_output: Dict = field(default_factory=dict)  # 【新增】结构化JSON数据
    critic_result: Optional[Dict] = None      # 【新增】Critic审查结果


# ==================== Orchestrator 类 ====================

class Orchestrator:
    """
    研究任务协调者 (Lead Agent)

    增强功能：
    - 查询类型分类和策略制定
    - 动态子智能体数量调整
    - 智能终止（收益递减检测）
    - 批判性信息验证
    - 用户画像透传和结构化输出
    """

    def __init__(
        self,
        worker_factory: Callable,
        max_workers: int = None,
        on_progress: Callable[[str, dict], None] = None,
        user_profile: Optional[dict] = None,
        memory=None,
        profile_id: str = "",
    ):
        """
        初始化 Orchestrator

        参数:
            worker_factory: Worker 工厂函数，用于创建 Worker 实例
            max_workers: 最大并行 Worker 数
            on_progress: 进度回调函数 (stage, data)
            user_profile: 用户画像字典
            memory: AgentMemory 实例（可选）
            profile_id: 用户画像ID（用于记忆关联）
        """
        self.llm = get_llm_client()
        self.worker_factory = worker_factory
        self.max_workers = max_workers or AGENT_CONFIG["max_workers"]
        self.on_progress = on_progress or (lambda stage, data: None)
        self.user_profile = user_profile or {}
        self.memory = memory
        self.profile_id = profile_id

    def _emit_progress(self, stage: str, data: dict = None):
        """发送进度事件"""
        self.on_progress(stage, data or {})

    def _format_user_profile(self) -> str:
        """格式化用户画像为文本"""
        if not self.user_profile:
            return "未提供用户画像"
        lines = []
        for key, value in self.user_profile.items():
            lines.append(f"- {key}: {value}")
        return "\n".join(lines)

    def _is_timed_out(self, start_time: float, total_timeout: int) -> bool:
        """检查是否超过总超时熔断时间"""
        return (time.time() - start_time) >= total_timeout

    def decompose_task(self, task: str) -> TaskPlan:
        """
        将研究任务拆解为子任务（增强版）

        新功能：
        - 查询类型判断
        - 动态子智能体数量建议
        - 详细研究计划

        参数:
            task: 原始研究任务描述

        返回:
            TaskPlan: 任务计划
        """
        self._emit_progress("decomposing", {"task": task})

        # 构建用户画像文本
        user_profile_text = self._format_user_profile()
        target_role = self.user_profile.get("target_role", "大模型应用开发工程师")
        time_budget = self.user_profile.get("time_budget", "3个月")
        company_tier = self.user_profile.get("company_tier", "大厂")
        current_level = self.user_profile.get("current_level", "有Python和PyTorch基础")
        focus_areas = self.user_profile.get("focus_areas", [])
        avoid_areas = self.user_profile.get("avoid_areas", [])

        # 获取历史记忆上下文
        memory_context = ""
        if self.memory and self.profile_id:
            memory_context = self.memory.get_memory_context(self.profile_id, max_records=3)

        prompt = TASK_DECOMPOSITION_PROMPT.format(
            task=task,
            user_profile=user_profile_text,
            target_role=target_role,
            time_budget=time_budget,
            company_tier=company_tier,
            current_level=current_level,
            focus_areas=", ".join(focus_areas) if focus_areas else "未指定",
            avoid_areas=", ".join(avoid_areas) if avoid_areas else "未指定",
            memory_context=memory_context or "无历史记录",
        )

        response = self.llm.chat(
            prompt=prompt,
            system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
            temperature=0.3,  # 任务拆解需要稳定性
        )

        if not response.success:
            raise Exception(f"任务拆解失败: {response.error_msg}")

        # 解析 JSON 结果
        result = extract_json(response.content)

        if not result:
            raise Exception("无法解析任务拆解结果")

        # 解析查询类型
        query_type_data = result.get("query_type", {})
        worker_count_data = result.get("worker_count", {})

        query_type = QueryTypeAnalysis(
            query_type=query_type_data.get("type", "breadth_first"),
            reasoning=query_type_data.get("reasoning", ""),
            recommended_approach=query_type_data.get("recommended_approach", ""),
            recommended_worker_count=worker_count_data.get("recommended", 3),
        )

        # 构建子任务列表（增强版）
        subtasks = []
        for st in result.get("subtasks", []):
            subtasks.append(SubTask(
                id=st.get("id", f"task_{len(subtasks)+1}"),
                name=st.get("name", "未命名任务"),
                description=st.get("description", ""),
                search_queries=st.get("search_queries", []),
                priority=st.get("priority", "medium"),
                expected_output=st.get("expected_output", ""),
                # 新增字段
                research_objective=st.get("research_objective", ""),
                expected_sources=st.get("expected_sources", []),
                scope_boundaries=st.get("scope_boundaries", ""),
            ))

        # 根据查询类型和建议调整子任务数量
        # 下限保护：至少保留 4 个 subtask（四个维度各至少1个）
        min_subtasks = 4
        if len(subtasks) < min_subtasks:
            # LLM 输出的 subtask 不足 4 个时，不做截断，信任 LLM 判断
            pass
        elif len(subtasks) > self.max_workers:
            # 仅在超过硬件上限时截断
            priority_order = {"high": 0, "medium": 1, "low": 2}
            subtasks.sort(key=lambda x: priority_order.get(x.priority, 1))
            subtasks = subtasks[:self.max_workers]

        task_plan = TaskPlan(
            task_understanding=result.get("task_understanding", {}),
            subtasks=subtasks,
            report_structure=result.get("report_structure", {}),
            query_type=query_type,
            research_plan=result.get("research_plan", {}),
            worker_count=worker_count_data,
        )

        self._emit_progress("decomposed", {
            "subtask_count": len(subtasks),
            "query_type": query_type.query_type,
            "recommended_workers": query_type.recommended_worker_count,
            "subtasks": [{"id": st.id, "name": st.name, "priority": st.priority} for st in subtasks],
        })

        return task_plan

    def dispatch_workers(self, task_plan: TaskPlan) -> list[dict]:
        """
        分发子任务给 Workers 并收集结果

        根据查询类型优化调度策略：
        - 深度优先：按视角分配
        - 广度优先：按子主题分配
        - 简单查询：单个 Worker

        参数:
            task_plan: 任务计划

        返回:
            list[dict]: Worker 结果列表
        """
        query_type = task_plan.query_type.query_type if task_plan.query_type else "breadth_first"

        # 确定实际并行数（LLM 动态决定，仅受硬件上限约束）
        actual_workers = min(
            len(task_plan.subtasks),
            self.max_workers,
        )
        self._emit_progress("dispatching", {
            "worker_count": len(task_plan.subtasks),
            "parallel_workers": actual_workers,
            "query_type": query_type,
        })

        results = []

        # 使用线程池并行执行（actual_workers 已在上面确定）
        with ThreadPoolExecutor(max_workers=actual_workers) as executor:
            # 提交所有任务
            future_to_task = {}
            for subtask in task_plan.subtasks:
                worker = self.worker_factory()
                future = executor.submit(worker.execute, subtask)
                future_to_task[future] = subtask

                self._emit_progress("worker_started", {
                    "task_id": subtask.id,
                    "task_name": subtask.name,
                    "priority": subtask.priority,
                })

            # 收集结果
            for future in as_completed(future_to_task):
                subtask = future_to_task[future]
                try:
                    result = future.result(timeout=AGENT_CONFIG["timeout_per_worker"])
                    subtask.status = "completed"
                    subtask.result = result
                    results.append(result)

                    self._emit_progress("worker_completed", {
                        "task_id": subtask.id,
                        "task_name": subtask.name,
                        "success": True,
                        "confidence_level": result.get("confidence_level", "unknown"),
                    })

                except Exception as e:
                    subtask.status = "failed"
                    results.append({
                        "task_id": subtask.id,
                        "task_name": subtask.name,
                        "error": str(e),
                        "success": False,
                    })

                    self._emit_progress("worker_failed", {
                        "task_id": subtask.id,
                        "task_name": subtask.name,
                        "error": str(e),
                    })

        return results

    def synthesize_results(
        self,
        original_task: str,
        task_plan: TaskPlan,
        worker_results: list[dict],
    ) -> str:
        """
        汇总 Worker 结果生成最终报告（增强版）

        新功能：
        - 基于查询类型的综合策略
        - 来源质量信息整合
        - 信息冲突识别

        参数:
            original_task: 原始研究任务
            task_plan: 任务计划
            worker_results: Worker 结果列表

        返回:
            str: 最终研究报告
        """
        self._emit_progress("synthesizing", {
            "result_count": len(worker_results),
        })

        # 格式化 Worker 结果
        results_text = self._format_worker_results(worker_results)

        # 格式化报告结构
        report_structure = json.dumps(
            task_plan.report_structure,
            ensure_ascii=False,
            indent=2,
        )

        # 格式化查询类型分析
        query_type_analysis = ""
        if task_plan.query_type:
            query_type_analysis = f"""
查询类型: {task_plan.query_type.query_type}
判断依据: {task_plan.query_type.reasoning}
研究方法: {task_plan.query_type.recommended_approach}
"""

        user_profile_text = self._format_user_profile()

        prompt = SYNTHESIS_PROMPT.format(
            original_task=original_task,
            user_profile=user_profile_text,
            query_type_analysis=query_type_analysis,
            report_structure=report_structure,
            worker_results=results_text,
            current_level=self.user_profile.get("current_level", ""),
            target_role=self.user_profile.get("target_role", ""),
            time_budget=self.user_profile.get("time_budget", ""),
        )

        response = self.llm.chat(
            prompt=prompt,
            system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
            temperature=0.5,
            max_tokens=16384,
        )

        if not response.success:
            raise Exception(f"报告生成失败: {response.error_msg}")

        self._emit_progress("synthesized", {
            "report_length": len(response.content),
        })

        return response.content

    def check_quality(self, report: str, original_task: str, query_type: str = "") -> dict:
        """
        对报告进行质量检查（增强版）

        新功能：
        - 基于查询类型的评估标准
        - 来源质量评估
        - 事实冲突检测

        参数:
            report: 研究报告
            original_task: 原始研究任务
            query_type: 查询类型

        返回:
            dict: 质量检查结果
        """
        self._emit_progress("quality_checking", {})

        prompt = QUALITY_CHECK_PROMPT.format(
            report=report,
            original_task=original_task,
            query_type=query_type or "未指定",
        )

        response = self.llm.chat(
            prompt=prompt,
            system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
            temperature=0.2,
        )

        if not response.success:
            return {"overall_score": 0, "error": response.error_msg}

        result = extract_json(response.content)
        if not result:
            result = {"overall_score": 70, "note": "质量检查结果解析失败"}

        self._emit_progress("quality_checked", {
            "score": result.get("overall_score", 0),
            "needs_revision": result.get("needs_revision", False),
            "revision_priority": result.get("revision_priority", "low"),
        })

        return result

    def check_diminishing_returns(
        self,
        original_task: str,
        current_score: int,
        iteration_history: list[IterationRecord],
        recent_supplementary_results: list[dict],
    ) -> dict:
        """
        检查是否达到收益递减点

        参数:
            original_task: 原始任务
            current_score: 当前质量分数
            iteration_history: 迭代历史
            recent_supplementary_results: 最近的补充研究结果

        返回:
            dict: 收益递减检查结果
        """
        # 构建迭代历史摘要
        history_summary = []
        for record in iteration_history:
            history_summary.append({
                "iteration": record.iteration,
                "score": record.quality_score,
                "improvement": record.score_improvement,
            })

        prompt = DIMINISHING_RETURNS_CHECK_PROMPT.format(
            original_task=original_task,
            current_score=current_score,
            iteration_history=json.dumps(history_summary, ensure_ascii=False),
            recent_supplementary_results=json.dumps(
                recent_supplementary_results[:3],  # 只取最近的结果
                ensure_ascii=False,
                indent=2,
            ) if recent_supplementary_results else "无",
        )

        response = self.llm.chat(
            prompt=prompt,
            system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
            temperature=0.2,
        )

        if not response.success:
            return {"diminishing_returns_detected": False}

        result = extract_json(response.content)
        return result or {"diminishing_returns_detected": False}

    def analyze_gaps(
        self,
        original_task: str,
        current_report: str,
        quality_result: dict,
        iteration: int,
        max_iterations: int,
        query_type: str = "",
    ) -> dict:
        """
        分析报告的差距和不足（增强版）

        参数:
            original_task: 原始研究任务
            current_report: 当前报告
            quality_result: 质量检查结果
            iteration: 当前迭代次数
            max_iterations: 最大迭代次数
            query_type: 查询类型

        返回:
            dict: 差距分析结果，包含补充任务
        """
        self._emit_progress("analyzing_gaps", {"iteration": iteration})

        prompt = GAP_ANALYSIS_PROMPT.format(
            original_task=original_task,
            query_type=query_type or "未指定",
            current_report=current_report,
            quality_result=json.dumps(quality_result, ensure_ascii=False, indent=2),
            iteration=iteration,
            max_iterations=max_iterations,
        )

        response = self.llm.chat(
            prompt=prompt,
            system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
            temperature=0.3,
        )

        if not response.success:
            return {"error": response.error_msg, "supplementary_tasks": []}

        result = extract_json(response.content)
        if not result:
            result = {
                "supplementary_tasks": [],
                "gap_analysis": {},
                "refinement_focus": [],
                "stop_iteration_recommendation": {"should_stop": False}
            }

        self._emit_progress("gaps_analyzed", {
            "iteration": iteration,
            "gap_count": len(result.get("gap_analysis", {}).get("completeness_gaps", {}).get("missing_aspects", [])),
            "task_count": len(result.get("supplementary_tasks", [])),
            "should_stop": result.get("stop_iteration_recommendation", {}).get("should_stop", False),
        })

        return result

    def dispatch_supplementary_workers(self, supplementary_tasks: list[dict]) -> list[dict]:
        """
        分发补充研究任务给 Workers

        参数:
            supplementary_tasks: 补充任务列表

        返回:
            list[dict]: 补充研究结果
        """
        if not supplementary_tasks:
            return []

        self._emit_progress("dispatching_supplementary", {
            "task_count": len(supplementary_tasks),
        })

        # 将补充任务转换为 SubTask 格式
        subtasks = []
        for st in supplementary_tasks:
            subtasks.append(SubTask(
                id=st.get("id", f"sup_task_{len(subtasks)+1}"),
                name=st.get("name", "补充研究任务"),
                description=st.get("description", ""),
                search_queries=st.get("search_queries", []),
                priority=st.get("priority", "high"),
                # 新增字段
                research_objective=st.get("research_objective", ""),
                expected_sources=st.get("expected_sources", []),
                scope_boundaries=st.get("scope_boundaries", ""),
            ))

        results = []

        with ThreadPoolExecutor(max_workers=min(len(subtasks), self.max_workers)) as executor:
            future_to_task = {}
            for subtask in subtasks:
                worker = self.worker_factory()
                future = executor.submit(worker.execute, subtask)
                future_to_task[future] = subtask

                self._emit_progress("supplementary_worker_started", {
                    "task_id": subtask.id,
                    "task_name": subtask.name,
                })

            for future in as_completed(future_to_task):
                subtask = future_to_task[future]
                try:
                    result = future.result(timeout=AGENT_CONFIG["timeout_per_worker"])
                    results.append(result)

                    self._emit_progress("supplementary_worker_completed", {
                        "task_id": subtask.id,
                        "task_name": subtask.name,
                        "success": True,
                    })
                except Exception as e:
                    results.append({
                        "task_id": subtask.id,
                        "task_name": subtask.name,
                        "error": str(e),
                        "success": False,
                    })

                    self._emit_progress("supplementary_worker_failed", {
                        "task_id": subtask.id,
                        "task_name": subtask.name,
                        "error": str(e),
                    })

        return results

    def refine_report(
        self,
        original_task: str,
        original_report: str,
        gap_analysis: dict,
        supplementary_results: list[dict],
        refinement_focus: list[str],
        verification_tasks: list[str] = None,
    ) -> str:
        """
        基于补充研究结果修订报告（增强版）

        参数:
            original_task: 原始研究任务
            original_report: 原始报告
            gap_analysis: 差距分析结果
            supplementary_results: 补充研究结果
            refinement_focus: 修订重点
            verification_tasks: 需要验证的事实

        返回:
            str: 修订后的报告
        """
        self._emit_progress("refining_report", {})

        # 格式化补充研究结果
        supplementary_text = self._format_worker_results(supplementary_results)

        prompt = REPORT_REFINEMENT_PROMPT.format(
            original_task=original_task,
            original_report=original_report,
            gap_analysis=json.dumps(gap_analysis, ensure_ascii=False, indent=2),
            supplementary_results=supplementary_text,
            refinement_focus="\n".join(f"- {f}" for f in refinement_focus),
            verification_tasks="\n".join(f"- {t}" for t in (verification_tasks or [])) or "无",
        )

        response = self.llm.chat(
            prompt=prompt,
            system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
            temperature=0.5,
            max_tokens=16384,
        )

        if not response.success:
            # 如果修订失败，返回原报告
            return original_report

        self._emit_progress("report_refined", {
            "new_length": len(response.content),
        })

        return response.content

    def _build_critic_supplementary_tasks(self, critic_result: dict, user_profile: dict) -> list[dict]:
        """将 Critic 审查发现的问题转换为补充搜索任务"""
        tasks = []
        overall = critic_result.get("overall_review", {})
        critical_issues = overall.get("critical_issues", [])
        score = overall.get("score", 0)

        if score >= 70 and not critical_issues:
            return tasks

        # 从八股覆盖不足生成搜索任务
        coverage = critic_result.get("interview_coverage", {})
        missing_topics = coverage.get("missing_topics", [])
        for topic in missing_topics[:3]:  # 最多处理3个缺失主题
            tasks.append({
                "id": f"critic_coverage_{len(tasks)+1}",
                "name": f"补充八股: {topic}",
                "description": f"Critic发现 {topic} 八股覆盖不足，搜索最新面经和高频考点",
                "search_queries": [f"{topic} 面试题 大模型 2025", f"{topic} 面经 {user_profile.get('company_tier', '大厂')}"],
                "priority": "high",
                "research_objective": f"补充 {topic} 的八股知识点和模拟面试题",
                "expected_sources": ["interview", "bocha"],
            })

        # 从项目质量问题生成搜索任务
        project_review = critic_result.get("project_review", {})
        toy_projects = project_review.get("toy_projects", [])
        match_issues = project_review.get("match_issues", [])
        if toy_projects or match_issues:
            # 用用户的 focus_areas 搜索更好的替代项目
            focus_areas = user_profile.get("focus_areas", [])
            alt_query = " ".join(focus_areas[:3]) if focus_areas else "大模型 开源项目"
            tasks.append({
                "id": f"critic_project_{len(tasks)+1}",
                "name": "替换低质量项目推荐",
                "description": f"Critic发现 {len(toy_projects)} 个toy项目，搜索更高质量的开源项目替代",
                "search_queries": [f"{alt_query} github stars:>100 2024 2025", f"{alt_query} 生产级 开源"],
                "priority": "high",
                "research_objective": "搜索高质量、生产级的替代开源项目",
                "expected_sources": ["github"],
            })

        # 从学习路径难度问题生成搜索任务
        path_review = critic_result.get("learning_path_review", {})
        difficulty_issues = path_review.get("difficulty_issues", [])
        if difficulty_issues:
            current = user_profile.get("current_level", "")
            target = user_profile.get("target_role", "")
            tasks.append({
                "id": f"critic_path_{len(tasks)+1}",
                "name": "调整学习路径难度",
                "description": f"Critic发现学习路径难度不匹配: {'; '.join(difficulty_issues[:2])}",
                "search_queries": [f"{current} 转 {target} 学习路线 循序渐进", f"{target} 入门 学习路径"],
                "priority": "medium",
                "research_objective": "搜索更适合当前水平的学习路径参考",
                "expected_sources": ["bocha", "interview"],
            })

        return tasks

    def run(self, task: str, user_profile: Optional[dict] = None) -> ResearchState:
        """
        执行完整的研究流程（增强版 - 带智能终止）

        参数:
            task: 研究任务描述
            user_profile: 用户画像字典（可选）

        返回:
            ResearchState: 研究状态（包含最终报告和结构化输出）

        迭代策略:
            - 最少迭代 min_iterations 次（默认2次）
            - 最多迭代 max_iterations 次（默认5次）
            - 达到质量阈值后，若已满足最少迭代次数则停止
            - 检测到收益递减时提前终止
        """
        # 更新用户画像
        if user_profile:
            self.user_profile = user_profile

        # 获取迭代配置
        min_iterations = AGENT_CONFIG.get("min_iterations", 2)
        max_iterations = AGENT_CONFIG.get("max_iterations", 5)
        quality_threshold = AGENT_CONFIG.get("quality_threshold", 80)
        enable_diminishing_returns_check = AGENT_CONFIG.get("enable_diminishing_returns_check", True)
        total_timeout = AGENT_CONFIG.get("total_task_timeout", 1200)

        state = ResearchState(
            original_task=task,
            user_profile=self.user_profile,
            start_time=time.time(),
            status="initialized",
        )

        try:
            # ========== 阶段1: 任务拆解（含查询类型判断） ==========
            state.status = "planning"
            state.task_plan = self.decompose_task(task)

            # 记录查询类型
            if state.task_plan.query_type:
                state.query_type = state.task_plan.query_type.query_type

            # 总超时熔断检查
            if self._is_timed_out(state.start_time, total_timeout):
                state.early_termination_reason = f"任务拆解后总耗时已超 {total_timeout}s 熔断阈值"
                state.status = "completed"
                state.end_time = time.time()
                self._emit_progress("timeout_terminated", {
                    "elapsed": state.end_time - state.start_time,
                    "threshold": total_timeout,
                    "phase": "after_decomposition",
                })
                return state

            # ========== 阶段2: 初始研究 ==========
            state.status = "researching"
            state.worker_results = self.dispatch_workers(state.task_plan)

            # ========== 阶段3: 生成初始报告 ==========
            state.status = "synthesizing"
            current_report = self.synthesize_results(
                task,
                state.task_plan,
                state.worker_results,
            )

            # ========== 阶段4: 迭代优化循环（带智能终止 + Critic门控） ==========
            state.status = "iterating"
            previous_score = 0
            critic_reviewed = False  # 确保 Critic 最多触发一次额外迭代

            for iteration in range(1, max_iterations + 1):
                # 总超时熔断检查（每次迭代前）
                if self._is_timed_out(state.start_time, total_timeout):
                    state.final_report = current_report
                    state.quality_score = state.iteration_history[-1].quality_score if state.iteration_history else 0
                    state.early_termination_reason = f"迭代 {iteration} 开始前总耗时已超 {total_timeout}s 熔断阈值"
                    state.status = "completed"
                    state.end_time = time.time()
                    self._emit_progress("timeout_terminated", {
                        "elapsed": state.end_time - state.start_time,
                        "threshold": total_timeout,
                        "iteration": iteration,
                        "current_score": state.quality_score,
                    })
                    return state

                self._emit_progress("iteration_start", {
                    "iteration": iteration,
                    "max_iterations": max_iterations,
                    "min_iterations": min_iterations,
                })

                # 4.1 质量检查
                quality_result = self.check_quality(
                    current_report,
                    task,
                    state.query_type,
                )
                current_score = quality_result.get("overall_score", 0)
                score_improvement = current_score - previous_score

                # 记录本次迭代
                iteration_record = IterationRecord(
                    iteration=iteration,
                    report=current_report,
                    quality_score=current_score,
                    quality_result=quality_result,
                    score_improvement=score_improvement,
                )
                state.iteration_history.append(iteration_record)
                state.iteration_count = iteration

                self._emit_progress("iteration_evaluated", {
                    "iteration": iteration,
                    "score": current_score,
                    "improvement": score_improvement,
                    "threshold": quality_threshold,
                    "passed": current_score >= quality_threshold,
                })

                # 4.2 判断是否可以结束迭代（质量 + Critic 双门控）
                if iteration >= min_iterations and current_score >= quality_threshold:
                    # 运行 Critic 审查，检查报告是否存在深层质量问题
                    if not critic_reviewed:
                        self._emit_progress("critic_reviewing", {
                            "iteration": iteration,
                            "phase": "in_loop",
                        })
                        critic = CriticWorker()
                        critic_result = critic.execute({
                            "report": current_report,
                            "user_profile": self.user_profile,
                        })
                        iteration_record.critic_result = critic_result
                        state.critic_result = critic_result
                        critic_reviewed = True

                        critic_score = critic_result.get("overall_review", {}).get("score", 0)
                        critical_issues = critic_result.get("overall_review", {}).get("critical_issues", [])

                        self._emit_progress("critic_reviewed", {
                            "iteration": iteration,
                            "critic_score": critic_score,
                            "critical_issues_count": len(critical_issues),
                        })

                        # Critic 通过 → 双门控均满足，结束迭代
                        if critic_score >= 70 and not critical_issues:
                            self._emit_progress("quality_passed", {
                                "iteration": iteration,
                                "score": current_score,
                                "critic_score": critic_score,
                                "message": f"质量+Critic双通过（{current_score}/{critic_score}），迭代结束",
                            })
                            break

                        # Critic 未通过 → 从审查结果生成补充任务，继续迭代修复
                        self._emit_progress("critic_failed_continue", {
                            "iteration": iteration,
                            "critic_score": critic_score,
                            "critical_issues": critical_issues[:3],
                            "message": "Critic发现质量问题，触发补充迭代修复",
                        })
                        critic_tasks = self._build_critic_supplementary_tasks(
                            critic_result, self.user_profile
                        )
                        if critic_tasks:
                            critic_results = self.dispatch_supplementary_workers(critic_tasks)
                            iteration_record.supplementary_results.extend(critic_results)
                            current_report = self.refine_report(
                                original_task=task,
                                original_report=current_report,
                                gap_analysis={"critic_findings": critic_result.get("overall_review", {})},
                                supplementary_results=critic_results,
                                refinement_focus=critical_issues[:5],
                            )
                        # 保存薄弱点到记忆
                        if self.memory and self.profile_id:
                            self.memory.extract_and_save_weak_points(self.profile_id, critic_result)
                        # 继续下一轮迭代（让质量检查重新评估修复后的报告）
                        previous_score = current_score
                        continue

                    # 已经做过 Critic 审查，直接结束
                    self._emit_progress("quality_passed", {
                        "iteration": iteration,
                        "score": current_score,
                        "message": f"质量检查通过（{current_score} >= {quality_threshold}），Critic已审查，迭代结束",
                    })
                    break

                # 4.3 检查收益递减（可选）
                if enable_diminishing_returns_check and iteration >= 2:
                    dr_result = self.check_diminishing_returns(
                        original_task=task,
                        current_score=current_score,
                        iteration_history=state.iteration_history,
                        recent_supplementary_results=iteration_record.supplementary_results,
                    )

                    if dr_result.get("diminishing_returns_detected", False):
                        iteration_record.diminishing_returns_detected = True
                        recommendation = dr_result.get("recommendation", {})

                        if recommendation.get("action") == "stop":
                            state.early_termination_reason = "收益递减检测触发提前终止"
                            self._emit_progress("diminishing_returns_stop", {
                                "iteration": iteration,
                                "score": current_score,
                                "reasoning": recommendation.get("reasoning", ""),
                            })
                            break

                # 4.4 如果还没到最大迭代次数，继续优化
                if iteration < max_iterations:
                    self._emit_progress("iteration_continue", {
                        "iteration": iteration,
                        "reason": "未达质量阈值" if current_score < quality_threshold else "未达最少迭代次数",
                    })

                    # 4.4.1 差距分析
                    gap_result = self.analyze_gaps(
                        original_task=task,
                        current_report=current_report,
                        quality_result=quality_result,
                        iteration=iteration,
                        max_iterations=max_iterations,
                        query_type=state.query_type,
                    )

                    iteration_record.gap_analysis = gap_result.get("gap_analysis", {})

                    # 检查是否建议停止迭代
                    stop_recommendation = gap_result.get("stop_iteration_recommendation", {})
                    if stop_recommendation.get("should_stop", False):
                        state.early_termination_reason = stop_recommendation.get("reasoning", "差距分析建议停止")
                        self._emit_progress("gap_analysis_stop", {
                            "iteration": iteration,
                            "reasoning": stop_recommendation.get("reasoning", ""),
                        })
                        break

                    # 4.4.2 执行补充研究
                    supplementary_tasks = gap_result.get("supplementary_tasks", [])
                    if supplementary_tasks:
                        supplementary_results = self.dispatch_supplementary_workers(supplementary_tasks)
                        iteration_record.supplementary_results = supplementary_results

                        # 4.4.3 修订报告
                        current_report = self.refine_report(
                            original_task=task,
                            original_report=current_report,
                            gap_analysis=gap_result.get("gap_analysis", {}),
                            supplementary_results=supplementary_results,
                            refinement_focus=gap_result.get("refinement_focus", []),
                            verification_tasks=gap_result.get("verification_tasks", []),
                        )
                    else:
                        # 没有补充任务，直接进入下一次评估
                        self._emit_progress("no_supplementary_tasks", {
                            "iteration": iteration,
                        })

                previous_score = current_score

                self._emit_progress("iteration_end", {
                    "iteration": iteration,
                })

            # ========== 阶段4.5: Critic 兜底审查（仅当循环中未运行时） ==========
            if not critic_reviewed:
                self._emit_progress("critic_reviewing", {"phase": "fallback"})
                critic = CriticWorker()
                critic_result = critic.execute({
                    "report": current_report,
                    "user_profile": self.user_profile,
                })
                state.critic_result = critic_result

                # 保存薄弱点到记忆
                if self.memory and self.profile_id and critic_result.get("success"):
                    weak_points = self.memory.extract_and_save_weak_points(
                        self.profile_id, critic_result
                    )
                    self._emit_progress("critic_reviewed", {
                        "overall_score": critic_result.get("overall_review", {}).get("score", 0),
                        "critical_issues_count": len(critic_result.get("overall_review", {}).get("critical_issues", [])),
                        "success": critic_result.get("success", False),
                        "weak_points_saved": len(weak_points),
                        "phase": "fallback",
                    })
                else:
                    self._emit_progress("critic_reviewed", {
                        "overall_score": critic_result.get("overall_review", {}).get("score", 0),
                        "critical_issues_count": len(critic_result.get("overall_review", {}).get("critical_issues", [])),
                        "success": critic_result.get("success", False),
                        "phase": "fallback",
                    })

            # ========== 阶段5: 完成 ==========
            state.final_report = current_report
            state.quality_score = state.iteration_history[-1].quality_score if state.iteration_history else 0
            state.status = "completed"
            state.end_time = time.time()

            self._emit_progress("completed", {
                "duration": state.end_time - state.start_time,
                "quality_score": state.quality_score,
                "iterations": state.iteration_count,
                "query_type": state.query_type,
                "early_termination": bool(state.early_termination_reason),
                "early_termination_reason": state.early_termination_reason,
            })

        except Exception as e:
            state.status = "failed"
            state.error_msg = str(e)
            state.end_time = time.time()

            self._emit_progress("failed", {
                "error": str(e),
            })

        return state

    def _format_worker_results(self, results: list[dict]) -> str:
        """格式化 Worker 结果为文本（增强版）"""
        parts = []
        for i, result in enumerate(results, 1):
            if result.get("success", True) and "error" not in result:
                # 提取 OODA 循环信息
                ooda_summary = ""
                ooda_cycles = result.get("ooda_cycles", [])
                if ooda_cycles:
                    ooda_summary = f"\n【OODA循环】执行了 {len(ooda_cycles)} 轮分析"

                # 提取来源质量信息
                source_quality = result.get("source_quality_assessment", {})
                source_summary = ""
                if source_quality:
                    high_quality = source_quality.get("high_quality_sources", [])
                    questionable = source_quality.get("questionable_sources", [])
                    if high_quality or questionable:
                        source_summary = f"\n【来源质量】优质来源: {len(high_quality)}个, 可疑来源: {len(questionable)}个"

                # 提取事实与推测区分
                speculative_info = result.get("speculative_vs_factual", {})
                spec_summary = ""
                if speculative_info:
                    verified = speculative_info.get("verified_facts", [])
                    speculative = speculative_info.get("speculative_claims", [])
                    if verified or speculative:
                        spec_summary = f"\n【事实验证】已验证: {len(verified)}项, 推测性: {len(speculative)}项"

                parts.append(f"""
--- Worker {i} 研究成果 ---
任务: {result.get('task_name', '未知')}
{ooda_summary}

【关键发现】
{self._format_findings(result.get('key_findings', []))}

【研究总结】
{result.get('summary', '无')}

【数据点】
{self._format_data_points(result.get('data_points', []))}

【洞察】
{chr(10).join('- ' + insight for insight in result.get('insights', []))}
{source_summary}
{spec_summary}

【置信度】{result.get('confidence_level', '未知')}
【置信度依据】{result.get('confidence_reasoning', '无')}

【研究局限性】{result.get('limitations', '无')}
【信息空白】{', '.join(result.get('information_gaps', [])) or '无'}
【终止原因】{result.get('termination_reason', '未知')}
""")
            else:
                parts.append(f"""
--- Worker {i} ---
任务: {result.get('task_name', '未知')}
状态: 失败
错误: {result.get('error', '未知错误')}
""")

        return "\n".join(parts)

    def _format_findings(self, findings: list[dict]) -> str:
        """格式化关键发现（增强版）"""
        if not findings:
            return "无"
        lines = []
        for f in findings:
            lines.append(f"- {f.get('finding', '')}")
            if f.get('data'):
                lines.append(f"  数据: {f.get('data')}")
            if f.get('source'):
                reliability = f.get('reliability', '未知')
                source_type = f.get('source_type', '')
                verified = "[已验证]" if f.get('is_verified') else "[待验证]"
                lines.append(f"  来源: {f.get('source')} [{reliability}可靠度] [{source_type}] {verified}")
            if f.get('reliability_reasoning'):
                lines.append(f"  可靠性依据: {f.get('reliability_reasoning')}")
        return "\n".join(lines)

    def _format_data_points(self, data_points: list[dict]) -> str:
        """格式化数据点（增强版）"""
        if not data_points:
            return "无"
        lines = []
        for dp in data_points:
            confidence = dp.get('confidence', '未知')
            confidence_icon = "[高]" if confidence == "high" else ("[中]" if confidence == "medium" else "[低]")
            lines.append(f"- {dp.get('metric', '')}: {dp.get('value', '')} (来源: {dp.get('source', '未知')}) {confidence_icon}")
        return "\n".join(lines)
