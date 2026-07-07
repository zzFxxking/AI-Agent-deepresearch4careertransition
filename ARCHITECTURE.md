# AI 求职助手 - 架构设计说明

> 面向面试官的深层技术讲解：架构决策、模块交互、关键流程、技术选型理由

---

## 1. 架构总览

### 1.1 设计模式：Orchestrator-Workers + 双门控质量控制 + 静态前端UI

```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend (frontend/)                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │ 首页     │ │ 需求输入 │ │ 生成进度 │ │ 报告查看 │  (静态HTML)│
│  │(Landing) │ │ (Form)   │ │ (SSE)    │ │(Workbench)│           │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘            │
│       └────────────┴─────┬──────┴────────────┘                  │
│                          │ HTTP REST + SSE                      │
└──────────────────────────┼──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│              FastAPI Backend (deep_research/api.py)              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    DeepResearchAgent                      │   │
│  │  ┌─────────────┐  ┌──────────┐  ┌───────────────────┐   │   │
│  │  │UserProfile   │  │ Agent    │  │ OutputFormatter    │   │   │
│  │  │Extractor    │  │ Memory   │  │ (三轨 Markdown+JSON)│  │   │
│  │  └──────┬──────┘  └────┬─────┘  └────────▲──────────┘   │   │
│  │         │              │                  │              │   │
│  │  ┌──────▼──────────────▼──────────────────┴──────┐       │   │
│  │  │                Orchestrator                    │       │   │
│  │  │  ┌──────────┐ ┌──────────┐ ┌───────────────┐  │       │   │
│  │  │  │Task      │ │Parallel  │ │Iteration+     │  │       │   │
│  │  │  │Decomp.   │→│Dispatch  │→│CriticGate     │  │       │   │
│  │  │  └──────────┘ └──────────┘ └───────────────┘  │       │   │
│  │  └──────┬────────────────────────────────────────┘       │   │
│  │         │                                                │   │
│  │  ┌──────▼──────────────────────────────────────────┐     │   │
│  │  │              Worker Pool                         │     │   │
│  │  │  ┌────────────┐ ┌────────┐ ┌──────────┐        │     │   │
│  │  │  │SearchWorker│ │Writer  │ │Critic    │        │     │   │
│  │  │  │(OODA循环)  │ │Worker  │ │Worker    │        │     │   │
│  │  │  └─────┬──────┘ └────────┘ └────┬─────┘        │     │   │
│  │  └────────┼───────────────────────┼───────────────┘     │   │
│  │           │                       │                      │   │
│  │  ┌────────▼───────────────────────▼───────────────┐     │   │
│  │  │            Search Clients Layer                 │     │   │
│  │  │  ┌─────────┐ ┌──────────┐ ┌──────────────┐    │     │   │
│  │  │  │ Bocha   │ │ GitHub   │ │ Interview    │    │     │   │
│  │  │  │ 通用搜索 │ │ API 搜索  │ │ site:限定    │    │     │   │
│  │  │  └─────────┘ └──────────┘ └──────────────┘    │     │   │
│  │  └────────────────────────────────────────────────┘     │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 为什么选择这个架构

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 编排模式 | Orchestrator-Workers（自适应 4-8 Worker）+ ReAct-Reflection 双模式 | 广度优先：LLM 根据画像动态拆解 4-8 个任务并行搜索；深度优先：Thought→Action→Observation 循环单点深挖 |
| Worker 工厂 | ThreadPoolExecutor | I/O 密集型任务（HTTP 搜索 + LLM 调用），Python GIL 不成瓶颈，线程实现最简单 |
| 记忆存储 | SQLite + WAL | 本地持久化，零运维成本；WAL 模式支持读写并发；threading.Lock 写保护 |
| Prompt 管理 | 字符串 Template | 避免引入 LangChain 等重型框架，自建模板已满足需求 |
| 搜索客户端 | 策略模式 + 统一接口 | 三种搜索源对外暴露一致的 `SearchResponse`，Worker 按 `expected_sources` 自动路由 |
| Critic 位置 | 迭代循环内第二门控 | 在质量评分通过后验证深层问题（toy 项目、八股覆盖），避免通用评分误导 |

---

## 2. 核心模块详解

### 2.1 Orchestrator (`orchestrator.py`)

**职责**：研究流程的中央控制器，管理从任务拆解到最终输出的完整生命周期。

**关键流程** (`run` 方法)：

```python
def run(task, user_profile):
    # 阶段1：任务拆解（含查询类型判断 + 记忆注入）
    task_plan = decompose_task(task)
    
    # 阶段2：并行 Worker 搜索
    worker_results = dispatch_workers(task_plan)
    
    # 阶段3：初始报告生成
    report = synthesize_results(task, task_plan, worker_results)
    
    # 阶段4：迭代优化循环（双门控）
    for iteration in range(max_iterations):
        quality = check_quality(report, task)
        
        if iteration >= min_iterations and quality >= threshold:
            # 门控1 通过 → 触发门控2（Critic）
            critic_result = CriticWorker.execute(report, user_profile)
            if critic_result.passed:
                break  # 双门控通过，结束迭代
            else:
                # Critic 未通过 → 生成补充任务，修复报告
                tasks = build_critic_supplementary_tasks(critic_result)
                supplementary = dispatch_supplementary_workers(tasks)
                report = refine_report(report, supplementary)
                continue  # 继续迭代
        
        # 收益递减检测
        if diminishing_returns_detected:
            break
        
        # 常规修正循环
        gaps = analyze_gaps(task, report, quality)
        if gaps.should_stop:
            break
        supplementary = dispatch_supplementary_workers(gaps.tasks)
        report = refine_report(report, supplementary)
    
    return ResearchState(report, quality, ...)
```

**关键设计点**：
- `_is_timed_out()` 在 3 个位置检查：任务拆解后 (L839)、每次迭代开始前 (L869)、补充 Worker 调度中，确保 20 分钟全局熔断生效
- `_build_critic_supplementary_tasks()` ：将 Critic 发现的 toy 项目、八股缺失等转化为具体搜索任务，实现审查→修正闭环
- 总超时熔断在 `orchestrator.py:174-176` 定义，在 L839、L869、L920-976 三处检查

### 2.2 SearchWorker (`workers.py`)

**职责**：执行单个搜索子任务，内置 OODA 循环和预算管理。

**OODA 循环**：

```
┌───────────────────────────────────────────────────────┐
│  Observe (观察)    Orient (定向)    Decide (决策)   Act (行动)
│      │                │               │              │
│  执行搜索查询    →  评估来源质量  →  判断是否继续  →  执行补充搜索
│  收集原始结果       识别信息空白     生成新查询词      或准备分析
│      │                │               │              │
│      └────────────────┴───────────────┴──────────────┘
│                    ↑ 循环直到预算耗尽或信息充足 ↓
└───────────────────────────────────────────────────────┘
```

**搜索客户端路由** (`_select_search_client`)：

```
expected_sources 包含 "github" → GitHubSearchClient
expected_sources 包含 "牛客网/力扣/面经" → InterviewSearchClient
其他 → BochaSearchClient (通用搜索兜底)
```

**关键改进**：
- `_identify_information_gaps()` 已从纯空格分词改为正则按中英文标点分词，解决中文文本信息空白识别失效问题
- `_assess_source_quality()` 统一引用 `AGENT_CONFIG["source_quality"]`，避免硬编码域名列表与 config 不同步

### 2.3 CriticWorker (`workers.py:617-722`)

**职责**：五维度审查面试准备报告质量，作为迭代循环的第二门控。

**审查维度**：

| 维度 | 检查内容 | 代码字段 |
|------|---------|---------|
| 项目质量 | toy 项目识别、Stars >= 50、真实应用场景 | `project_review` |
| 八股覆盖 | 知识点完整性、focus_areas 覆盖、前沿技术 | `interview_coverage` |
| 学习路径 | 难度匹配、时间合理性 | `learning_path_review` |
| 数量达标 | 八股 >= 30、项目 = 3、MQ = 3-4 | `quantity_review` |
| 背景适配 | 科班 vs 非科班的深度/风格匹配 | `background_fit_review` |

**双门控逻辑** (`orchestrator.py:917-978`)：

```
质量评分 >= threshold？
  ├─ 是 → 触发 CriticReview
  │       ├─ Critic 通过 → 双门控满足，结束迭代
  │       └─ Critic 未通过 → 生成补充任务修复 → 继续迭代
  └─ 否 → 常规差距分析 → 补充搜索 → 继续迭代
```

### 2.4 AgentMemory (`memory.py`)

**职责**：本地持久化用户画像、研究记录、薄弱点追踪。

**关键设计**：
- **SQLite + WAL 模式**：支持读写并发，FastAPI 多线程安全
- **自动迁移**：检测旧 JSON 格式 `agent_memory.json` 自动迁移到 SQLite 并备份
- **损坏容错**：数据库文件损坏时重建，JSON 解码失败时打印警告而非静默丢弃
- **线程安全**：`threading.Lock` 保护所有写操作（`save_profile`、`save_research_record`、`extract_and_save_weak_points`）

**数据模型**：

```sql
profiles (id, target_role, time_budget, raw_query, data JSON, created_at, updated_at)
records (id, profile_id FK, data JSON, created_at)
weak_points (profile_id Unique, points JSON, updated_at)
```

### 2.5 OutputFormatter (`output_formatter.py`)

**职责**：将 `ResearchState.final_report` 拆分为三轨输出并提取结构化 JSON。

**三轨拆分策略**：

```
final_report
  ├─ <!-- REPORT:main --> ... <!-- END:main --> → 主报告 Markdown
  ├─ <!-- REPORT:interview --> ... <!-- END:interview --> → 八股报告 Markdown
  └─ <!-- REPORT:projects --> ... <!-- END:projects --> → 项目报告 Markdown
```

**结构化提取策略**：正则匹配严格格式字段（`**字段名**：`），同时保留旧格式 fallback 解析，确保 LLM 输出格式偏差时不至于全空。

### 2.6 搜索客户端层 (`search_clients/`)

**统一接口**：

```python
class BaseSearchClient(ABC):
    def search(query, **kwargs) -> SearchResponse  # 统一返回
```

**三种实现**：

| 客户端 | 数据源 | 特色 |
|--------|--------|------|
| `BochaSearchClient` | Bocha Web Search API | 通用搜索兜底，技术概念解释 |
| `GitHubSearchClient` | GitHub REST API `/search/repositories` | `_parse_query` 从自然语言提取 stars/forks/language 过滤；SQL 注入过滤 |
| `InterviewSearchClient` | Bocha + `site:` 限定 | `SITE_MAPPING` 映射牛客/力扣/知乎等面经站点；`KEYWORD_TRIGGERS` 自动推断 |

---

## 3. 数据流详解

### 3.1 一次完整任务的完整数据流

```
1. UserProfileExtractor.extract(query, **fields)
   └→ UserProfile (target_role, time_budget, company_tier, current_level, focus_areas, avoid_areas)

2. AgentMemory.get_or_create_profile(profile)
   └→ profile_id → get_memory_context(profile_id)
   └→ 薄弱点 + 历史记录注入 Orchestrator.decompose_task()

3. Orchestrator.decompose_task(task)
   └→ LLM 调用 (TASK_DECOMPOSITION_PROMPT)
   └→ TaskPlan (query_type, subtasks[], report_structure, worker_count)

4. Orchestrator.dispatch_workers(task_plan)
   └→ ThreadPoolExecutor → search_worker_factory() → SearchWorker.execute(subtask)
   └→ [SearchWorker 内部: OODA 循环 → 搜索客户端路由 → LLM 分析]
   └→ worker_results[] (key_findings, source_quality_assessment, ooda_cycles)

5. Orchestrator.synthesize_results(task, task_plan, worker_results)
   └→ LLM 调用 (SYNTHESIS_PROMPT)
   └→ 初始报告 (三份 REPORT 标记包裹的 Markdown)

6. 迭代循环：
   6.1 Orchestrator.check_quality() → quality_score + suggestions
   6.2 CriticWorker.execute() → 五维度审查
   6.3 Orchestrator.analyze_gaps() → gap_analysis + supplementary_tasks
   6.4 Orchestrator.dispatch_supplementary_workers() → supplementary_results
   6.5 Orchestrator.refine_report() → 修订后报告

7. OutputFormatter.format(state)
   └→ _split_reports() → {main, interview, projects}
   └→ _build_structured_output() → 结构化 JSON
   └→ FormattedOutput (markdown×3 + json_data + metadata)

8. DeepResearchAgent._save_output()
   └→ research_output/{timestamp}_main.md
   └→ research_output/{timestamp}_interview.md
   └→ research_output/{timestamp}_projects.md
   └→ research_output/{timestamp}.json
   └→ research_output/{timestamp}_meta.json

9. AgentMemory.save_research_record()
   └→ SQLite INSERT (profile_id, data, created_at)
```

---

## 4. 关键决策记录

| 决策 | 选择 | 原因 |
|------|------|------|
| 架构方案 | 方案A（最小侵入式修改） | 时间窗口优先（3-5天 vs 7-10天），保留已验证的核心骨架 |
| Prompt 重构策略 | 全面替换为面试语境 | 原"研究报告"语境与求职场景差异大，渐进式修改会引入歧义 |
| Critic 执行时机 | 迭代循环内第二门控 | 仅在质量评分通过后运行，成本可控（平均 1 次/任务） |
| 八股组织维度 | 知识点类别（主） + 模型灵活切换 | 最通用，同时支持个性化 |
| 是否需要前端 | 不需要 | 项目目标是简历展示，非产品化；命令行 + FastAPI 演示足够 |
| InterviewSearchClient 实现 | Bocha + site: 限定 | 先快速实现，后续可升级为直接调用面经站点 API |
| AgentMemory 存储 | SQLite（替换原 JSON 文件） | JSON 并发不安全、查询弱；SQLite + WAL 满足多线程需求 |

---

## 5. 文件依赖关系

```
__init__.py
  └─ main.py
       ├─ orchestrator.py
       │    ├─ tools.py ────── search_clients/ (base → bocha, github, interview)
       │    ├─ prompts.py
       │    ├─ config.py
       │    └─ workers.py
       │         ├─ tools.py
       │         ├─ prompts.py
       │         └─ config.py
       ├─ user_profile.py
       ├─ output_formatter.py
       └─ memory.py
            └─ user_profile.py

api.py
  ├─ orchestrator.py
  ├─ workers.py
  ├─ config.py
  ├─ user_profile.py
  └─ output_formatter.py
```

**避免的循环依赖**：
- `InterviewSearchClient` → `BochaSearchClient`（同层导入，不涉及上层）
- `search_clients/__init__.py` 不做 `InterviewSearchClient` 的顶层导出，使用时直接 `from deep_research.search_clients.interview import`

---

## 6. 扩展点

当前架构预留的扩展点：

1. **新增搜索客户端**：继承 `BaseSearchClient`，在 `SearchWorker._select_search_client()` 中添加路由规则
2. **新增 Worker 类型**：继承 `BaseWorker`，在 `WorkerFactory` 中注册
3. **新增审查维度**：在 `CriticWorker.execute()` 和 `CRITIC_REVIEW_PROMPT` 中添加
4. **RAG 集成**：在 `memory.py` 旁新增 `vector_store.py`，在 iteration 循环前注入向量召回上下文
5. **MCP 协议接入** ✅ 已实现：`deep_research/mcp/` 模块（MCPManager + GitHub MCP Server 集成），
   支持 `mcp_first` 策略优先使用 MCP 搜索，不可用时自动降级传统 API。后续可扩展 Brave Search 等 Server。
6. **ReAct-Reflection 深度扩展** ✅ 已实现：`deep_research/react_agent.py` + `react_tools.py`，
   支持对已生成报告进行 Thought→Action→Observation 循环的深度追问与扩展，集成 Reflection 自反思机制。
