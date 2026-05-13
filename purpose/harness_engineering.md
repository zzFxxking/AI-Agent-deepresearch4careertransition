# Deep Research Agent - Harness Engineering 改造指南

> **文档状态**：设计参考文档（2026-05-12 更新）
> **与当前项目的关系**：本文档中部分概念已在 AI 求职助手改造中落地，但以不同于文档描述的方式实现：
> - **Critic Agent** → 已实现为 `workers.py:617-722` 的 `CriticWorker`（五维度审查 + 迭代内门控），而非独立 `critic.py`
> - **AgentMemory** → 已实现为 `memory.py`（SQLite + WAL + threading.Lock），而非 JSON + episodes.jsonl
> - **约束引擎** → `config.py` 中的 `AGENT_CONFIG` 字典承载了大部分配置约束
> - **TelemetryCollector / MetaAgent / Checkpoint** → 暂不实施（见 purpose.md 后续迭代规划）
> - **MCP** → 已实现为 `deep_research/mcp/` 模块（MCPManager + GitHub MCP Server 集成）
> - **AGENTS.md / constraints.py / harness_cli.py** → 未创建，当前非优先
>
> 本文档保留作为后续迭代（Meta-Agent、Telemetry、Checkpoint）的设计参考。

---

## 1. 核心理念

Harness Engineering（驾驭工程）的核心思想是：**人类设计环境、约束和规则，AI Agent 在边界内自主执行和演进**。

对于本项目（Deep Research Agent）而言，这意味着：

- **你不是在写 Agent 的每一行逻辑**，而是在定义 Agent 能够理解并遵守的" harness"（驾驭框架）
- **Agent 能够读懂自己的架构**（通过 AGENTS.md），知道每个组件的职责和边界
- **Agent 能够审查自己的输出**（通过 Critic Agent），发现事实错误和逻辑漏洞
- **Agent 能够从运行中学习**（通过 Meta-Agent），自动优化 Prompt 和配置
- **Agent 能够诊断自己的健康状态**（通过遥测系统），识别瓶颈和异常

## 2. 为什么本项目需要 Harness Engineering

当前 Deep Research Agent 已经具备良好的基础：
- Orchestrator-Workers 架构
- OODA 循环
- 迭代优化与质量检查
- 来源质量评估

但仍存在以下瓶颈：
1. **知识孤岛**：项目的架构知识只存在于开发者的头脑中，AI Agent 无法自主理解和修改代码
2. **缺乏审查**：Worker 之间互不审查，报告质量仅依赖 LLM 的自我评估
3. **无法进化**：每次运行都是独立事件，系统不会从历史中学习
4. **可观测性弱**：进度输出是给人看的控制台日志，不是给 Agent 分析的结构化数据
5. **配置黑盒**：配置散落在 Python 字典中，Agent 无法理解配置的含义和影响

Harness Engineering 改造将解决以上所有问题。

---

## 3. 改造架构总览

改造后的系统将新增以下核心组件：

```
┌─────────────────────────────────────────────────────────────┐
│                     Deep Research Agent                      │
│                      (Harness Engineering)                   │
├─────────────────────────────────────────────────────────────┤
│  Human Layer (人类掌舵)                                      │
│  ├─ AGENTS.md        ← 机器可读的架构说明书                  │
│  ├─ constraints.py   ← 显性化行为约束                        │
│  └─ config.py (Schema版) ← 自描述配置                        │
├─────────────────────────────────────────────────────────────┤
│  Agent Layer (智能体执行)                                     │
│  ├─ Orchestrator     ← 研究主管 (已有)                       │
│  ├─ SearchWorker     ← 搜索研究员 (已有)                     │
│  ├─ WriterWorker     ← 报告撰写员 (已有)                     │
│  ├─ CriticAgent      ← 质量审查员 (新增)                     │
│  └─ MetaAgent        ← 系统进化引擎 (新增)                   │
├─────────────────────────────────────────────────────────────┤
│  Observability Layer (可观测性)                              │
│  └─ TelemetryCollector ← 结构化遥测系统 (新增)               │
├─────────────────────────────────────────────────────────────┤
│  Interface Layer (接口)                                      │
│  ├─ api.py           ← FastAPI 服务 (新增 Harness 端点)      │
│  └─ harness_cli.py   ← Harness 管理 CLI (新增)               │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. 第一阶段：基础设施（P0）

### 4.1 AGENTS.md — 机器可读的架构说明书

**文件位置**：`deep_research/AGENTS.md`

**目的**：让 AI Agent（包括外部的 Claude、Codex 等）能够快速理解项目结构、组件职责、修改规则。

**核心原则**：
- 使用 `@section` 标记，便于 Agent 快速定位
- 每个组件定义 `invariants`（不变式），Agent 执行时不可违反
- 明确 `capabilities`（能力边界），Agent 知道能做什么
- 列出 `dependencies`（依赖关系），Agent 知道修改一处会影响哪里

**完整模板**：

```markdown
# Deep Research Agent - AGENTS.md

## @meta
version: 1.0.0
last_updated: 2026-05-11
agent_count: 5
architecture: orchestrator-workers
language: zh-CN

## @orchestrator
id: orchestrator
name: 研究主管
file: deep_research/orchestrator.py
class: Orchestrator
responsibilities:
  - task_decomposition: 将复杂研究任务拆解为并行子任务
  - worker_dispatch: 动态调度 Workers 执行任务
  - result_synthesis: 汇总 Worker 结果生成最终报告
  - quality_control: 迭代优化直至达标或收益递减
  - iteration_optimization: 检测收益递减并智能终止
invariants:
  - "max_workers <= 10"
  - "min_iterations >= 1"
  - "quality_threshold between 0 and 100"
  - "worker_count <= max_workers"
dependencies:
  - tools.LLMClient
  - tools.SearchClient
  - prompts.ORCHESTRATOR_SYSTEM_PROMPT
  - prompts.TASK_DECOMPOSITION_PROMPT
  - prompts.SYNTHESIS_PROMPT
  - prompts.QUALITY_CHECK_PROMPT
  - prompts.GAP_ANALYSIS_PROMPT
  - config.AGENT_CONFIG
  - config.LLM_CONFIG
inputs:
  - task: str (用户研究任务描述)
outputs:
  - ResearchState (包含最终报告、质量分数、迭代历史)

## @worker:search
id: search_worker
name: 搜索研究员
file: deep_research/workers.py
class: SearchWorker
extends: BaseWorker
responsibilities:
  - ooda_cycle_execution: 执行 OODA 循环进行迭代式搜索
  - source_quality_assessment: 批判性评估来源质量
  - research_budget_management: 管理搜索预算避免过度消耗
  - information_gap_identification: 识别信息空白并决定终止时机
invariants:
  - "budget.queries_used <= budget.max_queries"
  - "len(ooda_cycles) <= max_analysis_cycles"
  - "must distinguish facts from speculation"
  - "must flag low-quality sources"
capabilities:
  - web_search: 通过 SearchClient 执行网络搜索
  - source_quality_scoring: 基于域名和内容评估来源可靠性
  - query_expansion: 使用 LLM 扩展搜索查询词
  - budget_tracking: 跟踪并遵守研究预算
inputs:
  - subtask: SubTask (包含任务描述、搜索词、预期输出)
outputs:
  - dict (包含关键发现、来源质量评估、OODA 循环记录)

## @worker:writer
id: writer_worker
name: 报告撰写员
file: deep_research/workers.py
class: WriterWorker
extends: BaseWorker
responsibilities:
  - section_writing: 将研究数据转化为专业报告章节
  - citation_management: 管理引用和来源标注
  - style_consistency: 保持专业写作风格
inputs:
  - task: dict (包含 section_title, research_data, source_quality)
outputs:
  - dict (包含 section_title, content)

## @critic
id: critic_agent
name: 质量审查员
file: deep_research/critic.py
class: CriticAgent
responsibilities:
  - cross_worker_review: Worker 间交叉审查，发现矛盾信息
  - factual_consistency_check: 检查报告与 Worker 原始发现的一致性
  - source_credibility_audit: 审计来源可信度
  - bias_detection: 检测偏见和确认偏误
  - completeness_review: 审查报告完整性
invariants:
  - "must be independent from Orchestrator and Workers"
  - "must use separate prompt templates"
  - "must output structured review reports"
dependencies:
  - tools.LLMClient
  - prompts.CRITIC_REVIEW_PROMPT
inputs:
  - report: str
  - worker_results: List[dict]
  - task_plan: TaskPlan
outputs:
  - ReviewReport (包含 overall_score, findings, passed)

## @meta_agent
id: meta_agent
name: 系统进化引擎
file: deep_research/meta_agent.py
class: MetaAgent
responsibilities:
  - execution_analysis: 分析单次执行，提取学习信号
  - pattern_learning: 从批量执行中学习最优模式
  - prompt_optimization: 基于性能数据优化 Prompt
  - config_tuning: 自动调整配置参数
  - self_reflection: 周期性回顾和系统级反思
triggers:
  - periodic: 每 N 次研究任务后自动触发
  - quality_drop: 连续 M 次质量分数低于阈值
  - manual: 通过 API 或 CLI 手动触发
dependencies:
  - tools.LLMClient
  - telemetry.TelemetryCollector
  - config.AGENT_CONFIG_SCHEMA
inputs:
  - states: List[ResearchState]
outputs:
  - MetaLearningRecord (包含 changes_made, expected_improvement)

## @tools
id: tools
file: deep_research/tools.py
components:
  - LLMClient: LLM 调用封装 (OpenAI 兼容接口)
  - SearchClient: 网络搜索封装 (Bocha API)
  - extract_json: 从文本中提取 JSON
  - extract_xml: 从 XML 标签中提取内容
  - format_search_context: 格式化搜索结果为上下文

## @config
id: config
file: deep_research/config.py
schema: AgentConfigSchema
sections:
  - LLM_CONFIG: LLM API 配置
  - SEARCH_CONFIG: 搜索 API 配置
  - AGENT_CONFIG: Agent 行为配置
  - LOG_CONFIG: 日志配置
  - OUTPUT_CONFIG: 输出配置

## @constraints
id: constraints
file: deep_research/constraints.py
engine: ConstraintEngine
rule_categories:
  - orchestrator: Orchestrator 行为约束
  - search_worker: SearchWorker 行为约束
  - writer_worker: WriterWorker 行为约束
  - global: 全局约束

## @telemetry
id: telemetry
file: deep_research/telemetry.py
class: TelemetryCollector
event_types:
  - TASK_DECOMPOSED
  - WORKERS_DISPATCHED
  - WORKER_STARTED / WORKER_COMPLETED / WORKER_FAILED
  - SYNTHESIS_COMPLETED
  - QUALITY_CHECKED
  - CRITIC_REVIEW
  - ITERATION_COMPLETED
  - CONFIG_VIOLATION
  - CONSTRAINT_VIOLATION

## @rules
- rule_id: R001
  scope: orchestrator
  name: quality_threshold_termination
  condition: "iteration >= min_iterations AND score >= quality_threshold"
  action: "terminate_iteration"
  priority: high

- rule_id: R002
  scope: search_worker
  name: budget_exhaustion_termination
  condition: "budget.queries_used >= budget.max_queries"
  action: "terminate_research"
  priority: critical

- rule_id: R003
  scope: search_worker
  name: low_quality_source_flagging
  condition: "source_domain in low_quality_indicators OR source_reliability == low"
  action: "flag_questionable_and_log"
  priority: high

- rule_id: R004
  scope: global
  name: api_key_presence
  condition: "not api_key"
  action: "raise_configuration_error"
  priority: critical

- rule_id: R005
  scope: orchestrator
  name: diminishing_returns_detection
  condition: "score_improvement < 5 for 3 consecutive iterations"
  action: "recommend_early_termination"
  priority: medium
```

**使用方式**：
当 AI Agent（如 Claude、Codex）需要修改项目时，首先读取 `AGENTS.md`，即可了解：
- 项目的整体架构
- 每个组件的职责和边界
- 修改某处会影响哪些其他组件
- 必须遵守的不变式约束

### 4.2 constraints.py — 约束即代码

**文件位置**：`deep_research/constraints.py`

**目的**：将散落在 `config.py` 中的隐式约束显性化为可执行、可验证、可被 Agent 理解的代码对象。

**核心设计**：

```python
"""
约束定义 - Harness Engineering 核心文件

所有 Agent 行为约束的显式定义。
约束可以被：
1. Agent 自身读取并遵守
2. Meta-Agent 分析并优化
3. Critic Agent 验证
"""

from dataclasses import dataclass
from typing import List, Callable, Any
from enum import Enum


class ConstraintSeverity(Enum):
    CRITICAL = "critical"    # 违反会导致系统错误
    WARNING = "warning"      # 违反会降低质量
    INFO = "info"            # 违反仅作提示


@dataclass
class Constraint:
    """约束定义"""
    id: str
    name: str
    description: str
    scope: str              # "orchestrator" | "search_worker" | "writer_worker" | "global"
    severity: ConstraintSeverity
    check: Callable[[Any], bool]  # 验证函数
    error_message: str
    auto_fix: Callable[[Any], Any] = None  # 自动修复函数（可选）


# ========== Orchestrator 约束 ==========

ORCHESTRATOR_CONSTRAINTS = [
    Constraint(
        id="C-ORCH-001",
        name="max_workers_limit",
        description="并行 Worker 数不得超过配置上限",
        scope="orchestrator",
        severity=ConstraintSeverity.CRITICAL,
        check=lambda ctx: ctx.get("worker_count", 0) <= ctx.get("max_workers", 6),
        error_message="Worker 数量超过上限，请减少并行任务",
    ),
    Constraint(
        id="C-ORCH-002",
        name="min_iteration_enforcement",
        description="即使质量达标也必须执行最少迭代次数",
        scope="orchestrator",
        severity=ConstraintSeverity.WARNING,
        check=lambda ctx: ctx.get("iteration", 0) >= ctx.get("min_iterations", 2),
        error_message="未达到最少迭代次数",
    ),
    Constraint(
        id="C-ORCH-003",
        name="quality_threshold_range",
        description="质量阈值必须在 0-100 范围内",
        scope="orchestrator",
        severity=ConstraintSeverity.CRITICAL,
        check=lambda ctx: 0 <= ctx.get("quality_threshold", 80) <= 100,
        error_message="质量阈值无效",
    ),
    Constraint(
        id="C-ORCH-004",
        name="diminishing_returns_early_stop",
        description="检测到收益递减时允许提前终止",
        scope="orchestrator",
        severity=ConstraintSeverity.INFO,
        check=lambda ctx: True,  # 仅作提示，不强制
        error_message="检测到收益递减",
    ),
]

# ========== SearchWorker 约束 ==========

SEARCH_WORKER_CONSTRAINTS = [
    Constraint(
        id="C-SRCH-001",
        name="budget_compliance",
        description="搜索次数不得超过研究预算",
        scope="search_worker",
        severity=ConstraintSeverity.CRITICAL,
        check=lambda ctx: ctx.get("queries_used", 0) <= ctx.get("max_queries", 5),
        error_message="搜索预算已耗尽",
    ),
    Constraint(
        id="C-SRCH-002",
        name="source_quality_flagging",
        description="低质量来源必须被标记",
        scope="search_worker",
        severity=ConstraintSeverity.WARNING,
        check=lambda ctx: all(
            s.get("reliability") != "low" or s.get("flagged", False)
            for s in ctx.get("sources", [])
        ),
        error_message="发现未标记的低质量来源",
    ),
    Constraint(
        id="C-SRCH-003",
        name="fact_speculation_separation",
        description="必须明确区分事实和推测",
        scope="search_worker",
        severity=ConstraintSeverity.WARNING,
        check=lambda ctx: len(ctx.get("speculative_claims", [])) == 0 or
                         ctx.get("speculative_disclaimer", False),
        error_message="推测性内容缺少免责声明",
    ),
    Constraint(
        id="C-SRCH-004",
        name="ooda_cycle_limit",
        description="OODA 循环次数不得超过上限",
        scope="search_worker",
        severity=ConstraintSeverity.CRITICAL,
        check=lambda ctx: ctx.get("ooda_cycle_count", 0) <= ctx.get("max_analysis_cycles", 3),
        error_message="OODA 循环次数超限",
    ),
]

# ========== 全局约束 ==========

GLOBAL_CONSTRAINTS = [
    Constraint(
        id="C-GLB-001",
        name="api_key_presence",
        description="API Key 必须配置",
        scope="global",
        severity=ConstraintSeverity.CRITICAL,
        check=lambda ctx: bool(ctx.get("api_key")),
        error_message="API Key 未配置",
    ),
    Constraint(
        id="C-GLB-002",
        name="output_dir_writable",
        description="输出目录必须可写",
        scope="global",
        severity=ConstraintSeverity.CRITICAL,
        check=lambda ctx: ctx.get("output_dir_writable", True),
        error_message="输出目录不可写",
    ),
]


class ConstraintEngine:
    """约束引擎 - 验证 Agent 行为是否符合约束"""

    def __init__(self):
        self.constraints: List[Constraint] = []
        self.violations: List[dict] = []

    def register(self, constraints: List[Constraint]):
        """注册约束"""
        self.constraints.extend(constraints)

    def validate(self, context: dict, scope: str = None) -> List[dict]:
        """验证给定上下文是否满足所有约束

        Args:
            context: 验证上下文，包含需要检查的变量
            scope: 可选，只验证指定范围的约束

        Returns:
            List[dict]: 违规列表
        """
        violations = []
        for c in self.constraints:
            if scope and c.scope != scope and c.scope != "global":
                continue
            try:
                if not c.check(context):
                    violations.append({
                        "constraint_id": c.id,
                        "name": c.name,
                        "severity": c.severity.value,
                        "message": c.error_message,
                        "scope": c.scope,
                    })
            except Exception as e:
                violations.append({
                    "constraint_id": c.id,
                    "name": c.name,
                    "severity": "error",
                    "message": f"约束检查异常: {e}",
                    "scope": c.scope,
                })
        self.violations.extend(violations)
        return violations

    def get_agent_readable_rules(self) -> str:
        """生成 Agent 可读的规则文本"""
        lines = ["# 系统约束规则\n"]
        for c in self.constraints:
            lines.append(f"## {c.id}: {c.name}")
            lines.append(f"- 范围: {c.scope}")
            lines.append(f"- 严重级别: {c.severity.value}")
            lines.append(f"- 描述: {c.description}")
            lines.append(f"- 违反提示: {c.error_message}")
            lines.append("")
        return "\n".join(lines)

    def get_violations_summary(self) -> dict:
        """获取违规摘要"""
        critical = [v for v in self.violations if v["severity"] == "critical"]
        warnings = [v for v in self.violations if v["severity"] == "warning"]
        return {
            "total": len(self.violations),
            "critical": len(critical),
            "warnings": len(warnings),
            "details": self.violations,
        }
```

**与现有代码集成**：

在 `orchestrator.py` 的 `Orchestrator` 类中：

```python
from .constraints import ConstraintEngine, ORCHESTRATOR_CONSTRAINTS, GLOBAL_CONSTRAINTS

class Orchestrator:
    def __init__(self, ...):
        # ... 现有初始化代码 ...
        self.constraint_engine = ConstraintEngine()
        self.constraint_engine.register(ORCHESTRATOR_CONSTRAINTS)
        self.constraint_engine.register(GLOBAL_CONSTRAINTS)

    def run(self, task: str) -> ResearchState:
        # 启动时验证全局约束
        global_violations = self.constraint_engine.validate({
            "api_key": LLM_CONFIG.get("api_key"),
            "output_dir_writable": os.access(OUTPUT_CONFIG["output_dir"], os.W_OK),
        }, scope="global")

        if any(v["severity"] == "critical" for v in global_violations):
            raise ConfigurationError(f"全局约束违反: {global_violations}")

        # ... 阶段1: 任务拆解 ...
        state.task_plan = self.decompose_task(task)

        # 验证 Orchestrator 约束
        orch_violations = self.constraint_engine.validate({
            "worker_count": len(state.task_plan.subtasks),
            "max_workers": self.max_workers,
            "quality_threshold": AGENT_CONFIG["quality_threshold"],
        }, scope="orchestrator")

        if orch_violations:
            self._emit_progress("constraint_violations", {
                "violations": orch_violations,
            })

        # ... 后续阶段 ...
```

在 `workers.py` 的 `SearchWorker` 中：

```python
from .constraints import ConstraintEngine, SEARCH_WORKER_CONSTRAINTS

class SearchWorker(BaseWorker):
    def __init__(self, ...):
        # ... 现有初始化 ...
        self.constraint_engine = ConstraintEngine()
        self.constraint_engine.register(SEARCH_WORKER_CONSTRAINTS)

    def execute(self, subtask) -> dict:
        # ... OODA 循环中 ...
        # 每次循环后验证约束
        violations = self.constraint_engine.validate({
            "queries_used": self.budget.queries_used,
            "max_queries": self.budget.max_queries,
            "ooda_cycle_count": len(self.ooda_cycles),
            "max_analysis_cycles": self.budget.max_analysis_cycles,
            "sources": [...],  # 当前来源列表
            "speculative_claims": [...],  # 推测性声明
        }, scope="search_worker")

        if violations:
            # 将违规信息加入结果
            result["constraint_violations"] = violations
```

---

## 5. 第二阶段：Agent 间审查机制（P0）

### 5.1 critic.py — 独立审查 Agent

**文件位置**：`deep_research/critic.py`

**目的**：实现独立的 Critic Agent，对 Worker 输出和最终报告进行交叉审查。这是 Harness Engineering 中"Agent 审查 Agent"的核心实践。

**设计原则**：
1. **独立性**：Critic Agent 完全独立于 Orchestrator 和 Workers
2. **多维度**：从事实一致性、来源可信度、偏见、完整性四个维度审查
3. **结构化**：输出结构化的 ReviewReport，便于下游处理
4. **可学习**：审查历史可被 Meta-Agent 学习

**核心代码**：

```python
"""
Critic Agent - 质量审查与交叉验证

Harness Engineering 核心组件：
- Worker 间互审
- 事实一致性检查
- 来源可信度审计
- 偏见检测
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum

from .tools import get_llm_client, extract_json
from .config import AGENT_CONFIG


class ReviewType(Enum):
    CROSS_WORKER = "cross_worker"      # Worker 间交叉审查
    FACTUAL = "factual"                # 事实一致性审查
    SOURCE = "source"                  # 来源可信度审查
    BIAS = "bias"                      # 偏见检测
    COMPLETENESS = "completeness"      # 完整性审查


@dataclass
class ReviewFinding:
    """审查发现"""
    review_type: ReviewType
    severity: str  # critical / warning / info
    target: str    # 被审查对象
    issue: str
    evidence: str
    recommendation: str
    confidence: str  # high / medium / low


@dataclass
class ReviewReport:
    """审查报告"""
    overall_score: int
    findings: List[ReviewFinding] = field(default_factory=list)
    passed: bool = False
    summary: str = ""


class CriticAgent:
    """
    Critic Agent - 独立质量审查员

    设计原则：
    1. 独立于 Orchestrator 和 Workers
    2. 使用独立的 Prompt 和评估标准
    3. 输出结构化审查报告
    4. 审查结果可被 Meta-Agent 学习
    """

    def __init__(self):
        self.llm = get_llm_client()
        self.review_history: List[ReviewReport] = []

    def cross_worker_review(self, worker_results: List[dict]) -> ReviewReport:
        """
        Worker 间交叉审查

        检查：
        - 不同 Worker 的发现是否一致
        - 是否存在矛盾信息
        - 信息覆盖是否完整
        """
        # 提取所有关键发现
        all_findings = []
        for r in worker_results:
            if not r.get("success", True):
                continue
            for f in r.get("key_findings", []):
                all_findings.append({
                    "task": r.get("task_name"),
                    "finding": f.get("finding"),
                    "source": f.get("source"),
                    "reliability": f.get("reliability"),
                })

        prompt = f"""请对以下多个 Worker 的研究结果进行交叉审查：

<Worker 研究结果>
{self._format_findings_for_review(all_findings)}
</Worker 研究结果>

请检查：
1. **事实一致性**: 不同 Worker 报告的事实是否一致？是否有矛盾？
2. **信息覆盖**: 是否有重要方面未被任何 Worker 覆盖？
3. **来源冲突**: 不同 Worker 引用的来源是否有冲突？
4. **质量差异**: 哪些 Worker 的输出质量明显更高/更低？

以 JSON 格式输出审查结果：
```json
{{
    "overall_score": 85,
    "findings": [
        {{
            "review_type": "cross_worker",
            "severity": "warning",
            "target": "Worker 名称",
            "issue": "问题描述",
            "evidence": "证据",
            "recommendation": "改进建议",
            "confidence": "high"
        }}
    ],
    "passed": true/false,
    "summary": "审查总结"
}}
```"""

        response = self.llm.chat(prompt=prompt, temperature=0.2)
        result = extract_json(response.content) if response.success else {}

        return self._parse_review_report(result, ReviewType.CROSS_WORKER)

    def factual_consistency_check(self, report: str, worker_results: List[dict]) -> ReviewReport:
        """
        检查最终报告与 Worker 原始发现的事实一致性

        防止：
        - 报告编造 Worker 未提供的信息
        - 报告歪曲 Worker 的发现
        - 报告遗漏 Worker 的关键发现
        """
        # 提取 Worker 的所有关键事实
        worker_facts = []
        for r in worker_results:
            if not r.get("success", True):
                continue
            for f in r.get("key_findings", []):
                worker_facts.append({
                    "task": r.get("task_name"),
                    "fact": f.get("finding"),
                    "source": f.get("source"),
                    "is_verified": f.get("is_verified", False),
                })

        prompt = f"""请检查最终报告与 Worker 原始发现的事实一致性。

<Worker 关键事实>
{self._format_facts_for_check(worker_facts)}
</Worker 关键事实>

<最终报告>
{report[:5000]}  # 截取前5000字避免过长
</最终报告>

请检查：
1. **编造检测**: 报告中是否有 Worker 未提供的信息？
2. **歪曲检测**: 报告是否歪曲了 Worker 的发现？
3. **遗漏检测**: Worker 的关键发现是否被报告遗漏？
4. **验证状态**: 报告中标记为"已验证"的信息是否真的被验证过？

以 JSON 格式输出审查结果：
```json
{{
    "overall_score": 85,
    "findings": [
        {{
            "review_type": "factual",
            "severity": "critical",
            "target": "报告章节",
            "issue": "报告声称 X，但 Worker 未提供此信息",
            "evidence": "Worker 原始输出...",
            "recommendation": "补充 Worker 验证或删除此声明",
            "confidence": "high"
        }}
    ],
    "passed": true/false,
    "summary": "审查总结"
}}
```"""

        response = self.llm.chat(prompt=prompt, temperature=0.2)
        result = extract_json(response.content) if response.success else {}

        return self._parse_review_report(result, ReviewType.FACTUAL)

    def source_credibility_audit(self, report: str, worker_results: List[dict]) -> ReviewReport:
        """
        来源可信度审计

        检查：
        - 报告中引用的来源是否真实存在
        - 来源质量评估是否合理
        - 是否存在单一来源依赖
        """
        # 提取所有来源
        all_sources = []
        for r in worker_results:
            assessment = r.get("source_quality_assessment", {})
            all_sources.extend(assessment.get("high_quality_sources", []))
            all_sources.extend(assessment.get("questionable_sources", []))

        prompt = f"""请审计研究报告的来源可信度。

<Worker 来源评估>
{self._format_sources_for_audit(all_sources)}
</Worker 来源评估>

<最终报告>
{report[:3000]}
</最终报告>

请检查：
1. **来源真实性**: 报告中引用的来源是否在 Worker 输出中真实存在？
2. **质量评估合理性**: 来源的质量评估是否合理？
3. **单一来源依赖**: 是否有重要论点仅依赖单一来源？
4. **来源多样性**: 来源类型是否足够多样？

以 JSON 格式输出审查结果。"""

        response = self.llm.chat(prompt=prompt, temperature=0.2)
        result = extract_json(response.content) if response.success else {}

        return self._parse_review_report(result, ReviewType.SOURCE)

    def detect_bias(self, report: str, task_plan: dict) -> ReviewReport:
        """
        偏见检测

        检查：
        - 是否过度依赖特定类型的来源
        - 是否存在确认偏误
        - 是否忽略了反面证据
        """
        prompt = f"""请检测研究报告中的潜在偏见。

<原始任务>
{task_plan.get("task_understanding", {}).get("core_objective", "")}
</原始任务>

<报告>
{report[:4000]}
</报告>

请检查：
1. **来源偏见**: 是否过度依赖特定立场或类型的来源？
2. **确认偏误**: 是否只收集支持某一观点的证据，忽略反面证据？
3. **平衡性**: 对于争议性话题，是否呈现了多方观点？
4. **语言偏见**: 是否使用了带有倾向性的语言？

以 JSON 格式输出审查结果。"""

        response = self.llm.chat(prompt=prompt, temperature=0.2)
        result = extract_json(response.content) if response.success else {}

        return self._parse_review_report(result, ReviewType.BIAS)

    def review_report(self, report: str, worker_results: List[dict], task_plan: dict) -> ReviewReport:
        """
        执行完整审查流程

        返回综合审查报告
        """
        reviews = [
            self.cross_worker_review(worker_results),
            self.factual_consistency_check(report, worker_results),
            self.source_credibility_audit(report, worker_results),
            self.detect_bias(report, task_plan),
        ]

        # 合并审查结果
        all_findings = []
        for r in reviews:
            all_findings.extend(r.findings)

        # 计算综合分数（取最低分，因为任何一个维度的严重问题都不可接受）
        scores = [r.overall_score for r in reviews]
        overall_score = min(scores) if scores else 0

        # 如果有 critical 发现，则未通过
        passed = not any(f.severity == "critical" for f in all_findings)

        review_report = ReviewReport(
            overall_score=overall_score,
            findings=all_findings,
            passed=passed,
            summary=self._generate_summary(all_findings),
        )

        self.review_history.append(review_report)
        return review_report

    # ========== 辅助方法 ==========

    def _parse_review_report(self, result: dict, review_type: ReviewType) -> ReviewReport:
        """解析 LLM 输出的审查结果"""
        findings = []
        for f in result.get("findings", []):
            findings.append(ReviewFinding(
                review_type=review_type,
                severity=f.get("severity", "info"),
                target=f.get("target", ""),
                issue=f.get("issue", ""),
                evidence=f.get("evidence", ""),
                recommendation=f.get("recommendation", ""),
                confidence=f.get("confidence", "medium"),
            ))

        return ReviewReport(
            overall_score=result.get("overall_score", 0),
            findings=findings,
            passed=result.get("passed", True),
            summary=result.get("summary", ""),
        )

    def _generate_summary(self, findings: List[ReviewFinding]) -> str:
        """生成审查总结"""
        critical = [f for f in findings if f.severity == "critical"]
        warnings = [f for f in findings if f.severity == "warning"]
        return f"发现 {len(critical)} 个严重问题, {len(warnings)} 个警告, 共 {len(findings)} 项发现"

    def _format_findings_for_review(self, findings: List[dict]) -> str:
        """格式化发现用于审查"""
        lines = []
        for i, f in enumerate(findings, 1):
            lines.append(f"{i}. [{f['task']}] {f['finding']}")
            lines.append(f"   来源: {f['source']} | 可靠性: {f['reliability']}")
        return "\n".join(lines)

    def _format_facts_for_check(self, facts: List[dict]) -> str:
        """格式化事实用于检查"""
        lines = []
        for i, f in enumerate(facts, 1):
            verified = "[已验证]" if f['is_verified'] else "[待验证]"
            lines.append(f"{i}. [{f['task']}] {verified} {f['fact']}")
            lines.append(f"   来源: {f['source']}")
        return "\n".join(lines)

    def _format_sources_for_audit(self, sources: List[str]) -> str:
        """格式化来源用于审计"""
        return "\n".join(f"- {s}" for s in sources)
```

**与 Orchestrator 集成**：

修改 `orchestrator.py` 的 `ResearchState`：

```python
@dataclass
class ResearchState:
    # ... 现有字段 ...
    # 新增：Critic 审查相关
    critic_reviews: List[ReviewReport] = field(default_factory=list)
    review_score: int = 0
```

在 `Orchestrator.run()` 的迭代循环中，质量检查之后加入 Critic 审查：

```python
from .critic import CriticAgent

# ... 在阶段4的迭代循环中 ...

# 4.1 质量检查（已有）
quality_result = self.check_quality(current_report, task, state.query_type)
current_score = quality_result.get("overall_score", 0)

# 新增: 4.1.5 Critic 审查
critic = CriticAgent()
review_report = critic.review_report(
    current_report,
    state.worker_results,
    state.task_plan,
)
state.critic_reviews.append(review_report)
state.review_score = review_report.overall_score

self._emit_progress("critic_reviewed", {
    "iteration": iteration,
    "review_score": review_report.overall_score,
    "passed": review_report.passed,
    "finding_count": len(review_report.findings),
})

# 审查未通过时，使用审查发现生成补充任务
if not review_report.passed and iteration < max_iterations:
    critic_tasks = self._convert_findings_to_tasks(review_report.findings)
    if critic_tasks:
        supplementary_results = self.dispatch_supplementary_workers(critic_tasks)
        iteration_record.supplementary_results.extend(supplementary_results)
        current_report = self.refine_report(
            original_task=task,
            original_report=current_report,
            gap_analysis={"critic_findings": [f.__dict__ for f in review_report.findings]},
            supplementary_results=supplementary_results,
            refinement_focus=[f.recommendation for f in review_report.findings if f.severity == "critical"],
        )

# 综合质量分数和审查分数作为迭代终止条件
combined_score = min(current_score, review_report.overall_score)

# 判断是否可以结束迭代（使用 combined_score）
if iteration >= min_iterations and combined_score >= quality_threshold and review_report.passed:
    self._emit_progress("quality_passed", {
        "iteration": iteration,
        "score": current_score,
        "review_score": review_report.overall_score,
        "message": f"质量和审查均通过，迭代结束",
    })
    break
```

**需要的 Prompt 模板**（添加到 `prompts.py`）：

```python
# Critic Agent Prompts
CRITIC_SYSTEM_PROMPT = """你是一位严格的质量审查员，专注于发现研究报告中的事实错误、逻辑漏洞和偏见。

你的审查原则：
1. 事实至上：任何未经 Worker 原始输出支持的信息都必须标记
2. 来源审计：检查来源是否真实、质量评估是否合理
3. 偏见检测：识别确认偏误和片面论证
4. 平衡性：确保争议性话题呈现多方观点

你必须：
- 具体指出问题所在，不要泛泛而谈
- 提供改进建议
- 区分 critical（严重）和 warning（警告）级别"""
```

---

## 6. 第三阶段：Meta-Agent 自我改进（P1）

### 6.1 meta_agent.py — 系统进化引擎

**文件位置**：`deep_research/meta_agent.py`

**目的**：实现 Meta-Agent，持续分析系统运行数据，优化 Prompt、配置和策略。这是 Harness Engineering 中"系统自我进化"的核心。

**设计灵感**：受 Hermes Agent 四层进化架构（In-Session Evolution、Periodic Nudge、Background Review、Curator）启发。

**核心代码**：

```python
"""
Meta Agent - 系统自我进化引擎

基于 Harness Engineering 和 Hermes Agent 进化机制：
- 执行分析：从单次运行中提取学习信号
- 批量学习：从历史数据中学习模式
- Prompt 优化：基于效果自动改进
- 配置调优：动态调整参数
"""

import json
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from pathlib import Path

from .tools import get_llm_client, extract_json
from .config import AGENT_CONFIG, OUTPUT_CONFIG


@dataclass
class ExecutionPattern:
    """执行模式 - 从多次运行中学习到的模式"""
    pattern_id: str
    query_type: str
    task_complexity: str
    optimal_worker_count: int
    optimal_iterations: int
    common_gaps: List[str]
    effective_strategies: List[str]
    created_at: float
    usage_count: int = 0


@dataclass
class PromptPerformance:
    """Prompt 性能记录"""
    prompt_name: str
    success_rate: float
    avg_quality_score: float
    common_failures: List[str]
    suggested_improvements: List[str]


@dataclass
class MetaLearningRecord:
    """元学习记录"""
    timestamp: float
    trigger: str  # "periodic" | "quality_drop" | "manual"
    changes_made: List[dict]
    expected_improvement: str
    validation_result: Optional[dict] = None


class MetaAgent:
    """
    Meta Agent - 系统进化引擎

    触发条件：
    1. 周期性：每 N 次研究任务后自动回顾
    2. 质量下降：连续 M 次质量分数低于阈值
    3. 手动触发：通过 API 或 CLI 调用

    改进范围：
    1. Prompt 模板优化
    2. 配置参数调优
    3. 执行策略学习
    4. 约束规则更新
    """

    def __init__(self):
        self.llm = get_llm_client()
        self.patterns: List[ExecutionPattern] = []
        self.learning_history: List[MetaLearningRecord] = []
        self.execution_count = 0
        self.meta_data_path = Path(OUTPUT_CONFIG["output_dir"]) / "meta_learning.json"
        self._load_patterns()

    def _load_patterns(self):
        """加载已学习的模式"""
        if self.meta_data_path.exists():
            try:
                with open(self.meta_data_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.patterns = [
                        ExecutionPattern(**p) for p in data.get("patterns", [])
                    ]
                    self.learning_history = [
                        MetaLearningRecord(**r) for r in data.get("history", [])
                    ]
                    self.execution_count = data.get("execution_count", 0)
            except Exception:
                pass

    def _save_patterns(self):
        """保存学习到的模式"""
        self.meta_data_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.meta_data_path, "w", encoding="utf-8") as f:
            json.dump({
                "patterns": [
                    {
                        "pattern_id": p.pattern_id,
                        "query_type": p.query_type,
                        "task_complexity": p.task_complexity,
                        "optimal_worker_count": p.optimal_worker_count,
                        "optimal_iterations": p.optimal_iterations,
                        "common_gaps": p.common_gaps,
                        "effective_strategies": p.effective_strategies,
                        "created_at": p.created_at,
                        "usage_count": p.usage_count,
                    }
                    for p in self.patterns
                ],
                "history": [
                    {
                        "timestamp": r.timestamp,
                        "trigger": r.trigger,
                        "changes_made": r.changes_made,
                        "expected_improvement": r.expected_improvement,
                        "validation_result": r.validation_result,
                    }
                    for r in self.learning_history
                ],
                "execution_count": self.execution_count,
            }, f, ensure_ascii=False, indent=2)

    def analyze_execution(self, state: "ResearchState") -> dict:
        """
        分析单次执行，提取学习信号

        学习信号：
        - 迭代次数 vs 质量分数的关系
        - Worker 数量 vs 任务复杂度的关系
        - 常见差距模式
        - 质量瓶颈
        """
        self.execution_count += 1

        # 计算效率指标
        efficiency = state.quality_score / max(state.iteration_count, 1)

        # 质量曲线
        quality_curve = [
            {
                "iteration": r.iteration,
                "score": r.quality_score,
                "improvement": r.score_improvement,
            }
            for r in state.iteration_history
        ]

        # Worker 利用率
        successful_workers = sum(
            1 for r in state.worker_results if r.get("success", True)
        )
        worker_utilization = successful_workers / max(len(state.worker_results), 1)

        # 提取常见差距模式
        gap_patterns = []
        for record in state.iteration_history:
            if record.gap_analysis:
                gaps = record.gap_analysis.get("completeness_gaps", {})
                gap_patterns.extend(gaps.get("missing_aspects", []))

        # Critic 审查结果分析
        critic_scores = [r.overall_score for r in state.critic_reviews]
        avg_critic_score = sum(critic_scores) / len(critic_scores) if critic_scores else 0

        signals = {
            "task": state.original_task[:100],
            "query_type": state.query_type,
            "efficiency": efficiency,
            "quality_curve": quality_curve,
            "final_score": state.quality_score,
            "iteration_count": state.iteration_count,
            "worker_count": len(state.worker_results),
            "worker_utilization": worker_utilization,
            "gap_patterns": list(set(gap_patterns)),
            "critic_score": avg_critic_score,
            "early_terminated": bool(state.early_termination_reason),
            "duration": state.end_time - state.start_time,
        }

        return signals

    def learn_from_batch(self, states: List["ResearchState"]) -> MetaLearningRecord:
        """
        从批量执行中学习模式

        输出：
        - 最优 Worker 数量配置
        - 最优迭代策略
        - Prompt 改进建议
        - 配置调优建议
        """
        # 聚合分析
        analysis = self._aggregate_analysis(states)

        # 生成改进建议
        current_config = {
            k: v for k, v in AGENT_CONFIG.items()
            if isinstance(v, (int, float, bool, str, list))
        }

        prompt = f"""请基于以下系统运行数据，生成改进建议：

<运行数据分析>
{json.dumps(analysis, ensure_ascii=False, indent=2)}
</运行数据分析>

<当前配置>
{json.dumps(current_config, ensure_ascii=False, indent=2)}
</当前配置>

请分析：
1. 哪些配置参数明显不合理？
2. 哪些 Prompt 模板需要改进？
3. 有哪些可沉淀的执行模式？
4. 系统的主要瓶颈在哪里？

以 JSON 格式输出：
```json
{{
    "config_tuning": [
        {{
            "parameter": "参数名",
            "current_value": "当前值",
            "suggested_value": "建议值",
            "reasoning": "理由",
            "confidence": "high/medium/low"
        }}
    ],
    "prompt_improvements": [
        {{
            "prompt_name": "Prompt名称",
            "issue": "发现的问题",
            "suggested_change": "建议修改",
            "expected_impact": "预期效果"
        }}
    ],
    "new_patterns": [
        {{
            "query_type": "查询类型",
            "complexity": "复杂度",
            "optimal_workers": 建议Worker数,
            "optimal_iterations": 建议迭代数,
            "key_strategies": ["策略1", "策略2"]
        }}
    ],
    "bottlenecks": ["瓶颈1", "瓶颈2"],
    "priority_actions": ["优先行动1", "优先行动2"]
}}
```"""

        response = self.llm.chat(prompt=prompt, temperature=0.3)
        suggestions = extract_json(response.content) if response.success else {}

        # 应用高置信度的配置调优（仅记录，不自动应用）
        changes = []
        for tuning in suggestions.get("config_tuning", []):
            if tuning.get("confidence") == "high":
                changes.append({
                    "type": "config",
                    "parameter": tuning.get("parameter"),
                    "from": tuning.get("current_value"),
                    "to": tuning.get("suggested_value"),
                    "reasoning": tuning.get("reasoning"),
                })

        # 记录新模式
        for pattern in suggestions.get("new_patterns", []):
            # 检查是否已存在类似模式
            existing = [p for p in self.patterns
                       if p.query_type == pattern.get("query_type")
                       and p.task_complexity == pattern.get("complexity")]

            if existing:
                # 更新已有模式
                existing[0].optimal_worker_count = pattern.get("optimal_workers", existing[0].optimal_worker_count)
                existing[0].optimal_iterations = pattern.get("optimal_iterations", existing[0].optimal_iterations)
                existing[0].effective_strategies = pattern.get("key_strategies", existing[0].effective_strategies)
                existing[0].usage_count += 1
            else:
                self.patterns.append(ExecutionPattern(
                    pattern_id=f"pattern_{int(time.time())}_{len(self.patterns)}",
                    query_type=pattern.get("query_type", "unknown"),
                    task_complexity=pattern.get("complexity", "medium"),
                    optimal_worker_count=pattern.get("optimal_workers", 3),
                    optimal_iterations=pattern.get("optimal_iterations", 3),
                    common_gaps=[],
                    effective_strategies=pattern.get("key_strategies", []),
                    created_at=time.time(),
                ))

        record = MetaLearningRecord(
            timestamp=time.time(),
            trigger="periodic",
            changes_made=changes,
            expected_improvement=json.dumps(suggestions.get("priority_actions", []), ensure_ascii=False),
        )
        self.learning_history.append(record)
        self._save_patterns()

        return record

    def get_adaptive_config(self, task: str, query_type: str) -> dict:
        """
        根据学习到的模式，为特定任务生成自适应配置

        例如：对于"简单查询"，自动减少 Worker 数量和迭代次数
        """
        # 查找匹配的模式
        matching = [p for p in self.patterns if p.query_type == query_type]

        if matching:
            # 使用使用次数最多的模式
            best = max(matching, key=lambda p: p.usage_count)
            return {
                "max_workers": best.optimal_worker_count,
                "max_iterations": best.optimal_iterations,
                "learned": True,
                "pattern_id": best.pattern_id,
            }

        return {"learned": False}

    def should_trigger_learning(self, recent_states: List["ResearchState"]) -> bool:
        """判断是否应该触发学习"""
        # 周期性触发：每 10 次执行
        if self.execution_count % 10 == 0 and self.execution_count > 0:
            return True

        # 质量下降触发：连续 3 次低于 70 分
        if len(recent_states) >= 3:
            recent_scores = [s.quality_score for s in recent_states[-3:]]
            if all(score < 70 for score in recent_scores):
                return True

        return False

    def _aggregate_analysis(self, states: List["ResearchState"]) -> dict:
        """聚合多个执行状态的分析"""
        if not states:
            return {}

        scores = [s.quality_score for s in states]
        iterations = [s.iteration_count for s in states]
        durations = [s.end_time - s.start_time for s in states]

        # 按查询类型分组
        by_query_type = {}
        for s in states:
            qt = s.query_type or "unknown"
            if qt not in by_query_type:
                by_query_type[qt] = []
            by_query_type[qt].append(s)

        query_type_stats = {}
        for qt, qt_states in by_query_type.items():
            qt_scores = [s.quality_score for s in qt_states]
            query_type_stats[qt] = {
                "count": len(qt_states),
                "avg_score": sum(qt_scores) / len(qt_scores),
                "avg_iterations": sum(s.iteration_count for s in qt_states) / len(qt_states),
                "avg_duration": sum(s.end_time - s.start_time for s in qt_states) / len(qt_states),
            }

        return {
            "total_executions": len(states),
            "avg_score": sum(scores) / len(scores),
            "min_score": min(scores),
            "max_score": max(scores),
            "avg_iterations": sum(iterations) / len(iterations),
            "avg_duration": sum(durations) / len(durations),
            "early_termination_rate": sum(1 for s in states if s.early_termination_reason) / len(states),
            "query_type_stats": query_type_stats,
            "common_gaps": self._extract_common_gaps(states),
        }

    def _extract_common_gaps(self, states: List["ResearchState"]) -> List[str]:
        """提取常见的信息差距模式"""
        gap_counter = {}
        for s in states:
            for record in s.iteration_history:
                if record.gap_analysis:
                    gaps = record.gap_analysis.get("completeness_gaps", {})
                    for gap in gaps.get("missing_aspects", []):
                        gap_counter[gap] = gap_counter.get(gap, 0) + 1

        # 返回出现频率最高的前 10 个差距
        sorted_gaps = sorted(gap_counter.items(), key=lambda x: x[1], reverse=True)
        return [gap for gap, count in sorted_gaps[:10]]
```

**与主系统集成**：

在 `main.py` 的 `DeepResearchAgent.research()` 中：

```python
from .meta_agent import MetaAgent

class DeepResearchAgent:
    def __init__(self, ...):
        # ... 现有初始化 ...
        self.meta_agent = MetaAgent()
        self.recent_states: List[ResearchState] = []

    def research(self, task: str, ...) -> str:
        # ... 执行研究 ...
        state = orchestrator.run(task)

        # 新增: 分析本次执行
        signals = self.meta_agent.analyze_execution(state)
        self.recent_states.append(state)

        # 检查是否需要触发学习
        if self.meta_agent.should_trigger_learning(self.recent_states):
            learning_record = self.meta_agent.learn_from_batch(self.recent_states)
            if self.verbose:
                print(f"[Meta-Agent] 学习触发，生成了 {len(learning_record.changes_made)} 条改进建议")

        # ... 保存输出 ...
```

在 `api.py` 中增加端点：

```python
@app.post("/harness/learn", tags=["Harness"])
async def trigger_learning():
    """手动触发 Meta-Agent 学习"""
    from .meta_agent import MetaAgent
    from .main import DeepResearchAgent

    meta = MetaAgent()
    # 这里可以从文件加载历史状态
    # 简化实现：返回学习建议
    return {
        "message": "学习触发成功",
        "patterns_learned": len(meta.patterns),
        "learning_history": len(meta.learning_history),
    }

@app.get("/harness/patterns", tags=["Harness"])
async def get_learned_patterns():
    """获取已学习的模式"""
    from .meta_agent import MetaAgent
    meta = MetaAgent()
    return {
        "patterns": [
            {
                "query_type": p.query_type,
                "complexity": p.task_complexity,
                "optimal_workers": p.optimal_worker_count,
                "optimal_iterations": p.optimal_iterations,
                "strategies": p.effective_strategies,
                "usage_count": p.usage_count,
            }
            for p in meta.patterns
        ]
    }
```

---

## 7. 第四阶段：可观测性增强（P1）

### 7.1 telemetry.py — 结构化遥测系统

**文件位置**：`deep_research/telemetry.py`

**目的**：将当前分散的控制台输出转化为结构化的、可被 Agent 自我诊断的遥测系统。

**核心代码**：

```python
"""
Telemetry - 结构化可观测性系统

Harness Engineering 核心组件：
- 结构化事件日志
- 性能指标收集
- Agent 自我诊断接口
- 健康检查
"""

import json
import time
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Callable
from enum import Enum
from pathlib import Path
from datetime import datetime


class EventType(Enum):
    # Orchestrator 事件
    TASK_DECOMPOSED = "task_decomposed"
    WORKERS_DISPATCHED = "workers_dispatched"
    SYNTHESIS_COMPLETED = "synthesis_completed"
    QUALITY_CHECKED = "quality_checked"
    ITERATION_COMPLETED = "iteration_completed"

    # Worker 事件
    WORKER_STARTED = "worker_started"
    WORKER_COMPLETED = "worker_completed"
    WORKER_FAILED = "worker_failed"
    OODA_CYCLE = "ooda_cycle"

    # Critic 事件
    CRITIC_REVIEW = "critic_review"

    # 系统事件
    CONFIG_VIOLATION = "config_violation"
    CONSTRAINT_VIOLATION = "constraint_violation"
    ERROR = "error"


@dataclass
class TelemetryEvent:
    """遥测事件"""
    event_type: str
    timestamp: float
    task_id: Optional[str]
    stage: str
    data: dict
    agent: str  # 产生事件的 Agent
    duration_ms: Optional[int] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class PerformanceMetrics:
    """性能指标"""
    task_id: str
    total_duration_ms: int
    iteration_count: int
    worker_count: int
    quality_score: int
    review_score: int
    token_usage: dict = field(default_factory=dict)
    search_queries_count: int = 0
    constraint_violations: int = 0


class TelemetryCollector:
    """
    遥测收集器

    设计原则：
    1. 所有事件结构化，便于机器分析
    2. 支持实时流式输出和批量分析
    3. 提供 Agent 自我诊断接口
    4. 与现有进度回调兼容
    """

    def __init__(self, output_dir: str = "./telemetry"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.events: List[TelemetryEvent] = []
        self.metrics: List[PerformanceMetrics] = []
        self.subscribers: List[Callable] = []
        self._current_task: Optional[str] = None
        self._stage_start_times: Dict[str, float] = {}

    def start_task(self, task_id: str, task_description: str):
        """开始记录任务"""
        self._current_task = task_id
        self._stage_start_times = {}
        self.emit(EventType.TASK_DECOMPOSED, "initialized", {
            "task_description": task_description,
        })

    def start_stage(self, stage: str):
        """记录阶段开始"""
        self._stage_start_times[stage] = time.time()

    def end_stage(self, stage: str, data: dict = None):
        """记录阶段结束"""
        start_time = self._stage_start_times.get(stage)
        duration_ms = int((time.time() - start_time) * 1000) if start_time else None

        self.emit(EventType.WORKERS_DISPATCHED, stage, data or {}, duration_ms)

    def emit(self, event_type: EventType, stage: str, data: dict, duration_ms: int = None):
        """发送事件"""
        event = TelemetryEvent(
            event_type=event_type.value,
            timestamp=time.time(),
            task_id=self._current_task,
            stage=stage,
            data=data,
            agent=self._infer_agent(stage),
            duration_ms=duration_ms,
        )
        self.events.append(event)

        # 通知订阅者
        for sub in self.subscribers:
            try:
                sub(event)
            except Exception:
                pass

    def record_metrics(self, metrics: PerformanceMetrics):
        """记录性能指标"""
        self.metrics.append(metrics)
        self._save_metrics()

    def subscribe(self, callback: Callable):
        """订阅事件"""
        self.subscribers.append(callback)

    # ========== Agent 自我诊断接口 ==========

    def diagnose(self, task_id: Optional[str] = None) -> dict:
        """
        Agent 自我诊断

        分析遥测数据，识别问题模式：
        - 哪些阶段耗时最长？
        - 哪些 Worker 最容易失败？
        - 质量瓶颈在哪里？
        - 约束违反频率？
        """
        events = [e for e in self.events if not task_id or e.task_id == task_id]

        # 阶段耗时分析
        stage_durations = {}
        for e in events:
            if e.duration_ms:
                stage_durations[e.stage] = stage_durations.get(e.stage, []) + [e.duration_ms]

        avg_durations = {
            stage: sum(durations) / len(durations)
            for stage, durations in stage_durations.items()
        }

        # 错误分析
        errors = [e for e in events if e.event_type == EventType.ERROR.value]

        # Worker 失败分析
        worker_failures = [
            e for e in events
            if e.event_type == EventType.WORKER_FAILED.value
        ]

        # 约束违反
        violations = [
            e for e in events
            if e.event_type == EventType.CONSTRAINT_VIOLATION.value
        ]

        return {
            "task_id": task_id or "all",
            "total_events": len(events),
            "bottleneck_stage": max(avg_durations, key=avg_durations.get) if avg_durations else None,
            "avg_stage_durations": avg_durations,
            "error_count": len(errors),
            "worker_failure_count": len(worker_failures),
            "constraint_violation_count": len(violations),
            "common_errors": self._cluster_errors(errors),
            "recommendations": self._generate_recommendations(
                avg_durations, errors, violations
            ),
        }

    def get_health_status(self) -> dict:
        """系统健康状态"""
        recent_metrics = self.metrics[-10:] if len(self.metrics) >= 10 else self.metrics

        if not recent_metrics:
            return {"status": "unknown", "reason": "无历史数据"}

        avg_quality = sum(m.quality_score for m in recent_metrics) / len(recent_metrics)
        avg_duration = sum(m.total_duration_ms for m in recent_metrics) / len(recent_metrics)
        failure_rate = sum(1 for m in recent_metrics if m.quality_score < 60) / len(recent_metrics)

        status = "healthy"
        if failure_rate > 0.3:
            status = "degraded"
        if avg_quality < 50:
            status = "critical"

        return {
            "status": status,
            "avg_quality_score": round(avg_quality, 1),
            "avg_duration_ms": int(avg_duration),
            "failure_rate": round(failure_rate, 2),
            "tasks_analyzed": len(recent_metrics),
            "last_updated": datetime.now().isoformat(),
        }

    def export_for_meta_agent(self) -> dict:
        """导出给 Meta-Agent 分析的数据"""
        return {
            "events": [asdict(e) for e in self.events],
            "metrics": [asdict(m) for m in self.metrics],
            "summary": self.diagnose(),
            "health": self.get_health_status(),
        }

    def export_events(self, task_id: Optional[str] = None) -> List[dict]:
        """导出事件列表"""
        events = [e for e in self.events if not task_id or e.task_id == task_id]
        return [asdict(e) for e in events]

    # ========== 内部方法 ==========

    def _infer_agent(self, stage: str) -> str:
        """从阶段名推断 Agent"""
        if "worker" in stage.lower() and "critic" not in stage.lower():
            return "search_worker"
        elif "critic" in stage.lower():
            return "critic_agent"
        elif "iteration" in stage.lower() or "quality" in stage.lower():
            return "orchestrator"
        return "system"

    def _cluster_errors(self, errors: List[TelemetryEvent]) -> List[dict]:
        """聚类错误（简化实现）"""
        error_messages = {}
        for e in errors:
            msg = e.data.get("error", "未知错误")
            # 按错误类型聚类
            error_type = msg.split(":")[0] if ":" in msg else msg[:50]
            error_messages[error_type] = error_messages.get(error_type, 0) + 1

        return [
            {"error_type": k, "count": v}
            for k, v in sorted(error_messages.items(), key=lambda x: x[1], reverse=True)
        ]

    def _generate_recommendations(self, durations, errors, violations) -> List[str]:
        """生成改进建议"""
        recommendations = []

        # 耗时瓶颈建议
        if durations:
            bottleneck = max(durations, key=durations.get)
            if durations[bottleneck] > 30000:  # 30秒
                recommendations.append(
                    f"阶段 '{bottleneck}' 平均耗时 {durations[bottleneck]:.0f}ms，建议优化"
                )

        # 错误建议
        if len(errors) > 3:
            recommendations.append(
                f"最近检测到 {len(errors)} 个错误，建议检查 Worker 稳定性"
            )

        # 约束违反建议
        if len(violations) > 0:
            recommendations.append(
                f"检测到 {len(violations)} 次约束违反，建议审查约束配置"
            )

        return recommendations

    def _save_metrics(self):
        """保存指标到文件"""
        metrics_path = self.output_dir / "metrics.jsonl"
        with open(metrics_path, "a", encoding="utf-8") as f:
            for m in self.metrics:
                f.write(json.dumps(asdict(m), ensure_ascii=False) + "\n")
```

**与现有系统集成**：

修改 `main.py`，将 `ConsoleReporter` 与 `TelemetryCollector` 结合：

```python
from .telemetry import TelemetryCollector, PerformanceMetrics, EventType

class DeepResearchAgent:
    def __init__(self, ...):
        # ... 现有初始化 ...
        self.telemetry = TelemetryCollector()

    def research(self, task: str, ...) -> str:
        # 生成任务 ID
        task_id = f"task_{int(time.time())}"
        self.telemetry.start_task(task_id, task)

        # ... 创建 Orchestrator ...
        orchestrator = Orchestrator(
            worker_factory=search_worker_factory,
            max_workers=max_workers or AGENT_CONFIG["max_workers"],
            on_progress=lambda stage, data: self._on_progress(stage, data, task_id),
        )

        # 执行研究
        state = orchestrator.run(task)

        # 记录性能指标
        self.telemetry.record_metrics(PerformanceMetrics(
            task_id=task_id,
            total_duration_ms=int((state.end_time - state.start_time) * 1000),
            iteration_count=state.iteration_count,
            worker_count=len(state.worker_results),
            quality_score=state.quality_score,
            review_score=state.review_score if hasattr(state, 'review_score') else 0,
            search_queries_count=sum(
                r.get("research_budget_used", "0").split("/")[0]
                for r in state.worker_results
            ),
            constraint_violations=sum(
                len(r.get("constraint_violations", []))
                for r in state.worker_results
            ),
        ))

        # 保存遥测数据
        self._save_telemetry(task_id)

        return state.final_report

    def _on_progress(self, stage: str, data: dict, task_id: str):
        """进度回调：同时更新遥测和控制台"""
        # 更新遥测
        event_type = self._map_stage_to_event(stage)
        self.telemetry.emit(event_type, stage, data)

        # 更新控制台
        self.reporter.report(stage, data)

    def _map_stage_to_event(self, stage: str) -> EventType:
        """将进度阶段映射为遥测事件类型"""
        mapping = {
            "decomposing": EventType.TASK_DECOMPOSED,
            "worker_started": EventType.WORKER_STARTED,
            "worker_completed": EventType.WORKER_COMPLETED,
            "worker_failed": EventType.WORKER_FAILED,
            "synthesizing": EventType.SYNTHESIS_COMPLETED,
            "quality_checked": EventType.QUALITY_CHECKED,
            "critic_reviewed": EventType.CRITIC_REVIEW,
        }
        return mapping.get(stage, EventType.ITERATION_COMPLETED)

    def _save_telemetry(self, task_id: str):
        """保存遥测数据到文件"""
        telemetry_path = Path(OUTPUT_CONFIG["output_dir"]) / f"telemetry_{task_id}.json"
        telemetry_path.parent.mkdir(parents=True, exist_ok=True)
        with open(telemetry_path, "w", encoding="utf-8") as f:
            json.dump({
                "task_id": task_id,
                "events": self.telemetry.export_events(task_id),
                "diagnosis": self.telemetry.diagnose(task_id),
            }, f, ensure_ascii=False, indent=2)
```

---

## 8. 第五阶段：配置重构（P1）

### 8.1 config.py 重构 — 带 Schema 的自描述配置

**文件位置**：`deep_research/config.py`（修改）

**目的**：将配置从扁平字典重构为带 Schema 的分层结构，使 Agent 能理解和安全修改配置。

**关键修改**：

```python
"""
配置文件 - Deep Research Agent 全局配置 (Harness Engineering 版)

改造要点：
- 所有配置项带类型、约束、说明
- Agent 可读取并理解配置语义
- 支持运行时动态调整
- 保留向后兼容的 AGENT_CONFIG 字典
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

_env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=_env_path)
load_dotenv()


@dataclass
class ConfigField:
    """配置字段定义 - 包含元信息供 Agent 理解"""
    value: Any
    type: str
    description: str
    constraints: Dict[str, Any] = field(default_factory=dict)
    mutable: bool = True  # 是否允许运行时修改
    impact: str = ""  # 修改此配置的影响说明


@dataclass
class AgentConfigSchema:
    """Agent 配置 Schema - 自描述配置结构"""

    # ========== Orchestrator 配置 ==========
    max_workers: ConfigField = field(default_factory=lambda: ConfigField(
        value=6,
        type="int",
        description="最大并行 Worker 数",
        constraints={"min": 1, "max": 10},
        mutable=True,
        impact="增加可提升并行度，但会增加 API 调用成本和复杂度",
    ))

    max_search_depth: ConfigField = field(default_factory=lambda: ConfigField(
        value=3,
        type="int",
        description="最大搜索深度（迭代次数）",
        constraints={"min": 1, "max": 5},
        mutable=True,
        impact="增加可提升研究深度，但会显著增加耗时",
    ))

    timeout_per_worker: ConfigField = field(default_factory=lambda: ConfigField(
        value=120,
        type="int",
        description="单个 Worker 超时时间（秒）",
        constraints={"min": 30, "max": 300},
        mutable=True,
        impact="过短会导致 Worker 频繁超时，过长会阻塞整体流程",
    ))

    # ========== 迭代优化配置 ==========
    min_iterations: ConfigField = field(default_factory=lambda: ConfigField(
        value=2,
        type="int",
        description="最少迭代次数",
        constraints={"min": 1, "max": 5},
        mutable=True,
        impact="确保最低质量检查轮次",
    ))

    max_iterations: ConfigField = field(default_factory=lambda: ConfigField(
        value=5,
        type="int",
        description="最大迭代次数",
        constraints={"min": 2, "max": 10},
        mutable=True,
        impact="防止无限循环的上限",
    ))

    quality_threshold: ConfigField = field(default_factory=lambda: ConfigField(
        value=80,
        type="int",
        description="质量通过阈值（0-100）",
        constraints={"min": 0, "max": 100},
        mutable=True,
        impact="提高阈值可提升报告质量，但会增加迭代次数和耗时",
    ))

    # ========== 智能终止配置 ==========
    enable_diminishing_returns_check: ConfigField = field(default_factory=lambda: ConfigField(
        value=True,
        type="bool",
        description="是否启用收益递减检测",
        constraints={},
        mutable=True,
        impact="启用可避免无效迭代，节省资源",
    ))

    diminishing_returns_threshold: ConfigField = field(default_factory=lambda: ConfigField(
        value=3,
        type="int",
        description="连续 N 次提升小于 5 分则触发收益递减",
        constraints={"min": 2, "max": 5},
        mutable=True,
        impact="越小越敏感，越早终止",
    ))

    # ========== Worker 配置 ==========
    worker_max_ooda_cycles: ConfigField = field(default_factory=lambda: ConfigField(
        value=3,
        type="int",
        description="每个 Worker 最大 OODA 循环次数",
        constraints={"min": 1, "max": 5},
        mutable=True,
        impact="增加可提升 Worker 研究深度",
    ))

    # ========== 来源质量配置 ==========
    high_quality_domains: ConfigField = field(default_factory=lambda: ConfigField(
        value=[".gov", ".edu", ".org", "reuters", "bloomberg", "nature", "arxiv"],
        type="list[str]",
        description="高质量域名列表",
        constraints={},
        mutable=True,
        impact="影响来源质量评估的严格程度",
    ))

    low_quality_indicators: ConfigField = field(default_factory=lambda: ConfigField(
        value=["forum", "reddit", "quora", "blog", "medium.com"],
        type="list[str]",
        description="低质量来源指标",
        constraints={},
        mutable=True,
        impact="影响来源质量评估的敏感度",
    ))

    def to_dict(self) -> dict:
        """转换为普通字典（兼容现有代码）"""
        result = {}
        for key in self.__dataclass_fields__:
            config_field = getattr(self, key)
            result[key] = config_field.value
        return result

    def to_agent_readable(self) -> str:
        """生成 Agent 可读的配置说明"""
        lines = ["# Agent 配置说明\n"]
        for key in self.__dataclass_fields__:
            cf = getattr(self, key)
            lines.append(f"## {key}")
            lines.append(f"- 类型: {cf.type}")
            lines.append(f"- 当前值: {cf.value}")
            lines.append(f"- 说明: {cf.description}")
            if cf.constraints:
                lines.append(f"- 约束: {cf.constraints}")
            lines.append(f"- 可修改: {'是' if cf.mutable else '否'}")
            lines.append(f"- 影响: {cf.impact}")
            lines.append("")
        return "\n".join(lines)

    def update(self, key: str, value: Any) -> bool:
        """安全更新配置"""
        if key not in self.__dataclass_fields__:
            return False

        cf = getattr(self, key)
        if not cf.mutable:
            return False

        # 验证约束
        constraints = cf.constraints
        if "min" in constraints and value < constraints["min"]:
            return False
        if "max" in constraints and value > constraints["max"]:
            return False

        cf.value = value
        return True

    def get_field_info(self, key: str) -> Optional[dict]:
        """获取字段元信息"""
        if key not in self.__dataclass_fields__:
            return None
        cf = getattr(self, key)
        return {
            "type": cf.type,
            "value": cf.value,
            "description": cf.description,
            "constraints": cf.constraints,
            "mutable": cf.mutable,
            "impact": cf.impact,
        }


# ========== 全局配置实例 ==========

# LLM 配置（保持简单字典，因为通常不运行时修改）
LLM_CONFIG = {
    "api_key": os.getenv("DASHSCOPE_API_KEY"),
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "model": "qwen-plus",
    "model_smart": "qwen-max",
    "model_fast": "qwen-turbo",
    "max_tokens": 8192,
    "temperature": 0.7,
}

# 搜索配置
SEARCH_CONFIG = {
    "api_key": os.getenv("BOCHA_API_KEY"),
    "base_url": "https://api.bocha.cn/v1/web-search",
    "default_count": 10,
    "summary": True,
}

# Agent 配置（新的 Schema 版本）
AGENT_CONFIG_SCHEMA = AgentConfigSchema()

# 兼容旧代码：导出扁平字典
AGENT_CONFIG = AGENT_CONFIG_SCHEMA.to_dict()

# 日志配置
LOG_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    "show_worker_details": True,
    "show_search_results": False,
    "show_ooda_cycles": True,
    "show_source_quality": True,
}

# 输出配置
OUTPUT_CONFIG = {
    "save_intermediate": True,
    "output_dir": "./research_output",
    "formats": ["markdown", "json"],
    "include_ooda_logs": True,
    "include_source_assessment": True,
}
```

**使用方式**：

```python
# Agent 读取配置说明
from deep_research.config import AGENT_CONFIG_SCHEMA
print(AGENT_CONFIG_SCHEMA.to_agent_readable())

# Agent 安全更新配置
success = AGENT_CONFIG_SCHEMA.update("max_workers", 8)
if success:
    # 同步到兼容字典
    AGENT_CONFIG["max_workers"] = 8

# Meta-Agent 获取字段信息
info = AGENT_CONFIG_SCHEMA.get_field_info("quality_threshold")
# {'type': 'int', 'value': 80, 'description': '质量通过阈值（0-100）',
#  'constraints': {'min': 0, 'max': 100}, 'mutable': True,
#  'impact': '提高阈值可提升报告质量，但会增加迭代次数和耗时'}
```

---

## 9. 第六阶段：整合与自动化（P2）

### 9.1 harness_cli.py — Harness 管理 CLI

**文件位置**：`deep_research/harness_cli.py`

**核心功能**：

```python
"""
Harness CLI - Harness Engineering 管理工具

提供命令行接口管理 Harness 组件：
- 查看 AGENTS.md 解析结果
- 验证约束
- 运行自我诊断
- 触发 Meta-Agent 学习
- 查看系统健康状态
- 导出遥测数据
"""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Deep Research Agent - Harness Engineering CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m deep_research.harness agents           # 查看 AGENTS.md
  python -m deep_research.harness validate         # 验证约束
  python -m deep_research.harness diagnose         # 自我诊断
  python -m deep_research.harness learn            # 触发学习
  python -m deep_research.harness health           # 健康状态
  python -m deep_research.harness export-telemetry # 导出遥测
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # agents 命令
    agents_parser = subparsers.add_parser("agents", help="查看 AGENTS.md 解析结果")

    # validate 命令
    validate_parser = subparsers.add_parser("validate", help="验证约束")

    # diagnose 命令
    diagnose_parser = subparsers.add_parser("diagnose", help="运行自我诊断")
    diagnose_parser.add_argument("--task-id", help="指定任务 ID")

    # learn 命令
    learn_parser = subparsers.add_parser("learn", help="触发 Meta-Agent 学习")

    # health 命令
    health_parser = subparsers.add_parser("health", help="查看系统健康状态")

    # export-telemetry 命令
    export_parser = subparsers.add_parser("export-telemetry", help="导出遥测数据")
    export_parser.add_argument("--output", "-o", default="./telemetry_export.json")
    export_parser.add_argument("--task-id", help="指定任务 ID")

    args = parser.parse_args()

    if args.command == "agents":
        _show_agents()
    elif args.command == "validate":
        _validate_constraints()
    elif args.command == "diagnose":
        _diagnose(args.task_id)
    elif args.command == "learn":
        _trigger_learning()
    elif args.command == "health":
        _show_health()
    elif args.command == "export-telemetry":
        _export_telemetry(args.output, args.task_id)
    else:
        parser.print_help()


def _show_agents():
    """显示 AGENTS.md 解析结果"""
    agents_md_path = Path(__file__).parent / "AGENTS.md"
    if not agents_md_path.exists():
        print("错误: AGENTS.md 不存在")
        return

    # 简单解析并显示
    content = agents_md_path.read_text(encoding="utf-8")
    print(content)


def _validate_constraints():
    """验证约束"""
    from .constraints import ConstraintEngine, ORCHESTRATOR_CONSTRAINTS, SEARCH_WORKER_CONSTRAINTS, GLOBAL_CONSTRAINTS

    engine = ConstraintEngine()
    engine.register(ORCHESTRATOR_CONSTRAINTS)
    engine.register(SEARCH_WORKER_CONSTRAINTS)
    engine.register(GLOBAL_CONSTRAINTS)

    # 使用当前配置验证
    from .config import AGENT_CONFIG, LLM_CONFIG
    violations = engine.validate({
        "worker_count": AGENT_CONFIG["max_workers"],
        "max_workers": AGENT_CONFIG["max_workers"],
        "quality_threshold": AGENT_CONFIG["quality_threshold"],
        "api_key": LLM_CONFIG.get("api_key"),
    })

    if violations:
        print(f"发现 {len(violations)} 个约束违反:")
        for v in violations:
            print(f"  [{v['severity']}] {v['constraint_id']}: {v['message']}")
    else:
        print("所有约束验证通过")


def _diagnose(task_id: Optional[str] = None):
    """运行自我诊断"""
    from .telemetry import TelemetryCollector

    telemetry = TelemetryCollector()
    diagnosis = telemetry.diagnose(task_id)

    print(json.dumps(diagnosis, ensure_ascii=False, indent=2))


def _trigger_learning():
    """触发 Meta-Agent 学习"""
    from .meta_agent import MetaAgent

    meta = MetaAgent()
    print(f"已学习模式数量: {len(meta.patterns)}")
    print(f"学习历史记录: {len(meta.learning_history)}")

    # 显示最近的学习记录
    if meta.learning_history:
        latest = meta.learning_history[-1]
        print(f"\n最近一次学习 ({latest.timestamp}):")
        print(f"  触发条件: {latest.trigger}")
        print(f"  改进建议: {latest.expected_improvement}")


def _show_health():
    """显示系统健康状态"""
    from .telemetry import TelemetryCollector

    telemetry = TelemetryCollector()
    health = telemetry.get_health_status()

    status_icon = {
        "healthy": "✅",
        "degraded": "⚠️",
        "critical": "❌",
        "unknown": "❓",
    }.get(health["status"], "❓")

    print(f"{status_icon} 系统状态: {health['status']}")
    print(f"   平均质量分数: {health.get('avg_quality_score', 'N/A')}")
    print(f"   平均耗时: {health.get('avg_duration_ms', 'N/A')}ms")
    print(f"   失败率: {health.get('failure_rate', 'N/A')}")
    print(f"   分析任务数: {health.get('tasks_analyzed', 'N/A')}")


def _export_telemetry(output_path: str, task_id: Optional[str] = None):
    """导出遥测数据"""
    from .telemetry import TelemetryCollector

    telemetry = TelemetryCollector()
    data = telemetry.export_for_meta_agent()

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"遥测数据已导出到: {output}")


if __name__ == "__main__":
    main()
```

### 9.2 api.py 新增 Harness 端点

**需要添加到 `api.py` 的端点**：

```python
# ========== Harness Engineering 端点 ==========

@app.get("/harness/agents", tags=["Harness"])
async def get_agents_info():
    """获取 AGENTS.md 解析结果"""
    agents_md_path = Path(__file__).parent / "AGENTS.md"
    if not agents_md_path.exists():
        raise HTTPException(status_code=404, detail="AGENTS.md 不存在")

    content = agents_md_path.read_text(encoding="utf-8")
    return {
        "agents_md_exists": True,
        "content": content,
    }


@app.get("/harness/constraints", tags=["Harness"])
async def get_constraints_status():
    """获取当前约束状态"""
    from .constraints import ConstraintEngine, ORCHESTRATOR_CONSTRAINTS, SEARCH_WORKER_CONSTRAINTS

    engine = ConstraintEngine()
    engine.register(ORCHESTRATOR_CONSTRAINTS)
    engine.register(SEARCH_WORKER_CONSTRAINTS)

    return {
        "total_constraints": len(engine.constraints),
        "constraints": [
            {"id": c.id, "name": c.name, "scope": c.scope, "severity": c.severity.value}
            for c in engine.constraints
        ],
    }


@app.get("/harness/health", tags=["Harness"])
async def get_harness_health():
    """获取系统健康状态（增强版）"""
    from .telemetry import TelemetryCollector

    telemetry = TelemetryCollector()
    health = telemetry.get_health_status()

    return {
        **health,
        "service": "Deep Research Agent",
        "version": "1.0.0",
    }


@app.post("/harness/diagnose", tags=["Harness"])
async def run_diagnosis():
    """触发自我诊断"""
    from .telemetry import TelemetryCollector

    telemetry = TelemetryCollector()
    diagnosis = telemetry.diagnose()

    return diagnosis


@app.post("/harness/learn", tags=["Harness"])
async def trigger_meta_learning():
    """触发 Meta-Agent 学习"""
    from .meta_agent import MetaAgent

    meta = MetaAgent()
    return {
        "patterns_count": len(meta.patterns),
        "learning_history_count": len(meta.learning_history),
        "execution_count": meta.execution_count,
    }


@app.get("/harness/telemetry", tags=["Harness"])
async def get_telemetry_data(task_id: Optional[str] = None):
    """获取遥测数据"""
    from .telemetry import TelemetryCollector

    telemetry = TelemetryCollector()
    return {
        "events": telemetry.export_events(task_id),
        "diagnosis": telemetry.diagnose(task_id),
        "health": telemetry.get_health_status(),
    }
```

---

## 10. 实施路线图

### 阶段一（P0 - 立即实施）

1. **创建 `AGENTS.md`**
   - 耗时：30 分钟
   - 影响：AI Agent 能够自主理解项目架构
   - 验证：让 Claude 读取 AGENTS.md 后回答项目结构问题

2. **创建 `constraints.py`**
   - 耗时：1 小时
   - 影响：运行时约束验证，防止越界行为
   - 验证：修改配置超出范围时触发约束违反

3. **创建 `critic.py`**
   - 耗时：2 小时
   - 影响：研究报告质量显著提升
   - 验证：运行研究任务，检查是否生成 critic 审查报告

4. **修改 `orchestrator.py` 集成 Critic**
   - 耗时：1 小时
   - 影响：迭代循环中加入审查环节
   - 验证：研究完成后检查 ResearchState.critic_reviews

### 阶段二（P1 - 一周内实施）

5. **创建 `telemetry.py`**
   - 耗时：2 小时
   - 影响：结构化可观测性
   - 验证：运行任务后检查 telemetry 输出文件

6. **创建 `meta_agent.py`**
   - 耗时：2 小时
   - 影响：系统自我进化能力
   - 验证：运行 10 次任务后触发学习，检查生成的模式

7. **重构 `config.py`**
   - 耗时：1 小时
   - 影响：配置自描述，Agent 可理解
   - 验证：调用 to_agent_readable() 输出配置说明

### 阶段三（P2 - 两周内实施）

8. **创建 `harness_cli.py`**
   - 耗时：1 小时
   - 影响：命令行管理 Harness 组件
   - 验证：运行各子命令检查输出

9. **修改 `api.py` 增加 Harness 端点**
   - 耗时：30 分钟
   - 影响：通过 API 管理 Harness
   - 验证：调用各端点检查响应

10. **修改 `main.py` 集成遥测和 Meta-Agent**
    - 耗时：1 小时
    - 影响：完整的 Harness Engineering 闭环
    - 验证：运行完整研究流程，检查所有组件协同工作

---

## 11. 预期效果

| 指标 | 改造前 | 改造后（预期） |
|------|--------|----------------|
| Agent 理解项目能力 | 无 | 通过 AGENTS.md 完全理解 |
| 事实一致性错误 | 中等 | 减少 60%+（Critic Agent）|
| 系统自我进化 | 无 | 自动优化 Prompt 和配置 |
| 瓶颈识别 | 人工分析 | 自动诊断（遥测系统）|
| 配置错误捕获 | 运行时异常 | 运行时约束验证 |
| 平均质量分数 | 基线 | 提升 10-15 分（50 次后）|
| 迭代次数 | 固定 | 减少 20-30%（Meta-Agent）|

---

## 12. 验证清单

### 单元验证

```python
# 1. 验证 AGENTS.md 可被解析
# 读取 AGENTS.md 并验证包含所有必要 section

# 2. 验证约束引擎
from deep_research.constraints import ConstraintEngine
engine = ConstraintEngine()
# 注册约束并验证

# 3. 验证 Critic Agent
from deep_research.critic import CriticAgent
critic = CriticAgent()
report = critic.cross_worker_review([...])
assert report.overall_score >= 0

# 4. 验证遥测
from deep_research.telemetry import TelemetryCollector
tel = TelemetryCollector()
diagnosis = tel.diagnose()
assert "bottleneck_stage" in diagnosis
```

### 集成验证

```bash
# 1. 运行完整研究任务，检查遥测输出
python -m deep_research "测试研究主题" --telemetry

# 2. 检查 Critic 审查结果是否生成
cat research_output/research_*_critic.json

# 3. 触发 Meta-Agent 学习
curl -X POST http://localhost:8000/harness/learn

# 4. 检查系统健康
curl http://localhost:8000/harness/health

# 5. 运行 Harness CLI
python -m deep_research.harness health
python -m deep_research.harness diagnose
```

### 长期验证

- 运行 100 次研究任务，对比改造前后的平均质量分数
- 检查 Meta-Agent 学习到的模式是否合理
- 验证 Critic 发现的错误是否确实被修复
- 确认遥测数据完整性和准确性

---

## 13. 注意事项

1. **向后兼容**：所有改造必须保持与现有代码的向后兼容。AGENT_CONFIG 字典仍然可用。
2. **渐进实施**：建议按阶段实施，每完成一个阶段就进行验证。
3. **Prompt 管理**：Critic 和 Meta-Agent 的 Prompt 需要单独管理，避免与现有 Prompt 混淆。
4. **性能影响**：Critic Agent 会增加一次 LLM 调用，Meta-Agent 的批量学习需要积累足够数据。
5. **数据隐私**：遥测数据可能包含敏感信息，注意存储和传输安全。

---

*文档版本: 1.0.0*
*最后更新: 2026-05-11*
*适用项目: Deep Research Agent (Orchestrator-Workers 架构)*
