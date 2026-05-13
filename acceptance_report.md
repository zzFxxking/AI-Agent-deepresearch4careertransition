# AI求职助手改造项目 —— 代码验收报告（第三轮审计）

> **审计日期**: 2026-05-12
> **审计员**: 独立代码审计员（第三轮）
> **依据文档**: `spec.md` v1.0, `design.md` v1.0, `acceptance_report.md` (第二轮)
> **审计范围**: `deep_research/` 包全部源代码、`tests/`、配置文件、全部文档交付物

---

## 1. 总体结论

**核心功能实现度：约 97%**

第二轮审计中的 6 个缺失交付物已全部补齐，代码核心功能实现度高。本轮发现 3 个轻微问题（均为 P2 级别的文档/配置偏差），不影响核心功能运行。项目已进入可交付状态。

---

## 2. 第二轮审计修复核实

上一轮 acceptance_report.md 列出的 P1/P2 修复项及缺失交付物验证结果：

| 修复项 | 第二轮状态 | 第三轮核实 |
|--------|-----------|---------|
| P1-1: spec.md 熔断时间同步为 20 分钟 | ✅ 已修复 | ✅ `spec.md:253` |
| P1-2: README.md 重写为 AI 求职助手场景 | ❌ 缺失 | ✅ **现已更新**（求职场景快速开始、新模块结构、三轨输出） |
| P1-3: 补充部署文件（.env.example, Dockerfile, run.sh） | ❌ 缺失 | ✅ **现已全部补齐** |
| P1-4: purpose/ 文档更新 | ✅ 已修复 | ✅ 三个文件均已更新 |
| P2-1: workers.py 域名列表同步 config | ✅ 已修复 | ✅ `workers.py:398-400` 统一引用 `AGENT_CONFIG` |
| P2-2: ARCHITECTURE.md | ❌ 缺失 | ✅ **现已创建**（架构总览、核心模块详解、关键技术决策） |
| P2-3: DEMO.md | ❌ 缺失 | ✅ **现已创建**（完整端到端案例：命令行 → 控制台输出 → 输出文件预览） |
| P2-4: MIGRATION.md | ❌ 缺失 | ✅ **现已创建**（改造总览、模块清单、数据流对比、面试展示要点） |
| P2-5: Bocha 迁移到 search_clients/ | ✅ 已修复 | ✅ `search_clients/bocha.py` 继承 `BaseSearchClient` |

8 个 bug 修复（跨两轮审计）持续有效：

| Bug | 代码位置 | 核实 |
|-----|---------|------|
| `extract(None)` 崩溃 | `user_profile.py:35-37` | ✅ |
| 中文逗号未分割 | `user_profile.py:61-63` | ✅ |
| `_load()` 静默忽略损坏 JSON | `memory.py:36-42` | ✅ |
| `_identify_information_gaps` 中文无效 | `workers.py:435-437` | ✅ |
| `_expand_queries` 接受非字符串 | `workers.py:453` | ✅ |
| `run_research_task` 无锁修改全局配置 | `api.py:207,264-295` | ✅ |
| GitHub `_parse_query` 未过滤危险字符 | `github.py:171` | ✅ |
| `high_quality_domains` 匹配过宽 | `config.py:104-107` | ✅ |

---

## 3. 需求逐项验收（完整复核）

### 3.1 保留功能（spec 3.2）

| 需求项 | 状态 | 代码位置 |
|--------|------|---------|
| Orchestrator-Workers 核心架构 | ✅ | `orchestrator.py:120-1120`, `workers.py:81-818` |
| ReAct-Reflection 深度扩展框架 | ✅ | `react_agent.py`, `react_tools.py` |
| MCP 协议集成 | ✅ | `mcp/__init__.py`, `mcp/config.py` |
| 任务拆解（自适应 4-8 Worker） | ✅ | `orchestrator.py:178-291`, `prompts.py:46-204` |
| 并行 Worker 调度（ThreadPoolExecutor） | ✅ | `orchestrator.py:328-371` |
| 迭代优化与收益递减检测 | ✅ | `orchestrator.py:867-1060`, `prompts.py:996-1054` |
| SSE 流式进度输出 | ✅ | `api.py:440-502` |
| FastAPI 服务层保留 | ✅ | `api.py:212-534` |

### 3.2 新增功能（spec 3.3）

| 需求项 | 状态 | 代码位置 |
|--------|------|---------|
| GitHubSearchClient | ✅ | `search_clients/github.py:15-172` |
| InterviewSearchClient | ⚠️ 部分实现 | `search_clients/interview.py:13-98`；基于 Bocha + `site:` 限定（design.md 6.2 明确方案） |
| BochaSearchClient 保留 | ✅ | `search_clients/bocha.py:13-109`；继承 `BaseSearchClient` |
| AgentMemory 持久化 | ✅ | `memory.py:17-287`；SQLite + WAL + threading.Lock |
| Critic Agent | ✅ | `workers.py:607-712`；五维度审查 + 迭代循环内门控 |
| 结构化 JSON 输出 | ✅ | `output_formatter.py:14-575`；三轨 Markdown + JSON Schema |
| 面试模拟问答 | ✅ | `prompts.py:207-389` Synthesis Prompt 含 MQ/EQ 格式 |

### 3.3 删除/替换模块（spec 3.4）

| 需求项 | 状态 | 说明 |
|--------|------|------|
| 删除 VisualizationWorker | ✅ | `workers.py` 中无此类 |
| 弱化 AnalysisWorker | ✅ | 类仍存在于 `workers.py:717-780`，Orchestrator 未调度，WorkerFactory 保留创建方法（符合"弱化不删除"） |
| 简化来源标注 | ✅ | Prompt 中明确"平台名即可" |
| 垂直搜索替代通用搜索 | ✅ | SearchWorker 按 `expected_sources` 自动路由三客户端 |

### 3.4 输入输出（spec 4）

| 需求项 | 状态 |
|--------|------|
| 自然语言 + 结构化字段输入 | ✅ `user_profile.py:30-73`, `main.py:261-268` |
| 三轨 Markdown 输出 | ✅ `main.py:414-436` |
| 结构化 JSON 输出 | ✅ `output_formatter.py:79-105` |
| JSON Schema 与 spec 一致 | ⚠️ `project_recommendations` 扩展字段（difficulty_level/quality_gate/implementation_steps/key_modules）较 spec 丰富，向下兼容 |

### 3.5 非功能性需求（spec 5）

| 需求项 | 状态 | 说明 |
|--------|------|------|
| 仅使用已有 LLM API | ✅ | DeepSeek/DashScope 切换 |
| 搜索源：Bocha + GitHub + 面经 | ✅ | |
| 耗时 2-5 分钟（20 分钟熔断） | ✅ | `config.py:61` `total_task_timeout: 1200` |
| 熔断机制 | ✅ | 3 处 `_is_timed_out()` 检查点 |
| 线程池大小控制 | ✅ | `config.py:58` |
| 本地持久化 | ✅ | SQLite `./data/agent_memory.db` |
| CLI 交互 | ✅ | `main.py:476-595` |
| FastAPI 保留不扩展 | ✅ | 新增字段向后兼容 |
| Dockerfile / run.sh | ✅ **新补齐** | `Dockerfile` (37 行), `run.sh` (96 行) |
| .env.example | ✅ **新补齐** | 含 LLM/Bocha/GitHub 模板 |
| 类型注解 + Pydantic | ✅ | |
| 关键决策点注释 | ✅ | |

### 3.6 交付物（spec 6）

| 交付物 | 状态 | 说明 |
|--------|------|------|
| 完整源代码 | ✅ | `deep_research/` 包 12 个核心文件 + `search_clients/` 5 个文件 |
| `requirements.txt` | ✅ | |
| `.env.example` | ✅ **新补齐** | 含 DeepSeek/DashScope/Bocha/GitHub 配置模板 |
| `Dockerfile` | ✅ **新补齐** | Python 3.12-slim 基础镜像，含构建和运行说明 |
| `run.sh` | ✅ **新补齐** | 一键运行脚本（环境检查 → 依赖安装 → 目录创建 → 启动） |
| `README.md` | ✅ **已更新** | 全面重写为 AI 求职助手场景：架构一览、求职特性、完整使用示例、配置说明 |
| `ARCHITECTURE.md` | ✅ **新补齐** | 架构总览、核心模块详解（Orchestrator/SearchWorker/CriticWorker/OutputFormatter）、关键流程、面试展示要点 |
| `DEMO.md` | ✅ **新补齐** | 完整端到端案例：命令行输入 → 控制台输出 → 5 个输出文件 → 内容预览 |
| `MIGRATION.md` | ✅ **新补齐** | 改造总览、13 个模块的改造前后对比、数据流变化、面试展示要点 |
| `purpose/` 文档 | ✅ 已更新 | 3 个文件均已更新为求职助手改造后状态 |
| `tests/` 目录 | ✅ | 7 个测试文件（共 1873 行代码） |
| 示例输出 | ✅ | `research_output/` 下有 `.md` 和 `.json` 示例 |

---

## 4. 本轮新发现的偏差与风险

### 4.1 README.md 项目结构树缩进错误（P2 — 轻微格式问题）

**问题**：`README.md:241-243` 中 `requirements.txt` 出现在 `deep_research/` 目录的缩进层级下，与搜索客户端包同级：
```
│   ├── output_formatter.py     # 三轨输出格式化
├── requirements.txt            # Python 依赖清单
│   └── search_clients/         # 垂直搜索客户端
```
正确结构应为 `requirements.txt` 在根目录，`search_clients/` 在 `deep_research/` 下：
```
│   ├── output_formatter.py
│   └── search_clients/
├── requirements.txt
```

**影响**：可能导致读者对项目结构产生困惑。不影响代码功能。

**代码位置**：`README.md:241-243`

### 4.2 purpose.md 版本号与 __init__.py 不一致（P2 — 轻微文档偏差）

**问题**：`purpose/purpose.md:5` 标注当前版本为 `v1.0`，但 `deep_research/__init__.py:27` 标注 `__version__ = "2.0.0"`。

**影响**：读者可能对项目版本状态产生混淆。

**代码位置**：`purpose/purpose.md:5`, `deep_research/__init__.py:27`

### 4.3 OutputFormatter LLM 输出格式脆弱性（P2 — 持续低风险）

**问题**：`output_formatter.py` 大量使用正则表达式解析 LLM 生成的 Markdown（`_split_reports`、`_extract_learning_path`、`_extract_question_categories`、`_extract_mock_qa`、`_build_structured_projects` 等）。如果 LLM 生成的报告格式偏离 Prompt 约定的标记规范，结构化提取会失败，输出为空数组/默认值。

**现有缓解措施**：
- Prompt 中明确规定了 `<!-- REPORT:name -->...<!-- END:name -->` 标记格式
- 每个提取方法都有 fallback 逻辑（如旧格式兼容）
- `extract_json()` 有容错逻辑

**代码位置**：`output_formatter.py:55-72` (split), `output_formatter.py:219-273` (learning_path), `output_formatter.py:275-330` (categories), `output_formatter.py:120-217` (projects)

---

## 5. 持续存在的已知风险（中低风险）

### 5.1 中风险

| 风险 | 说明 | 应对 |
|------|------|------|
| InterviewSearchClient 精准度依赖 Bocha | 面经搜索通过 Bocha + `site:` 限定词实现（design.md 6.2 明确方案）。若 Bocha 对面经站点收录不全，搜索结果质量可能下降 | 已知权衡，降级方案为后续接入爬虫 |

### 5.2 低风险

| 风险 | 说明 |
|------|------|
| AnalysisWorker 工厂方法仍可调用 | `WorkerFactory.create_analysis_worker()` 仍存在（workers.py:805），若被误调用会生成不适配求职场景的通用分析。当前 Orchestrator 不调度，但存在意外调用可能 |
| `search_clients/__init__.py` InterviewSearchClient 非直接导出 | InterviewSearchClient 通过 lazy import 避免循环依赖（`__init__.py:6-7`），需手动导入。不影响核心流程但增大了使用方的认知成本 |
| 正则解析依赖 Prompt 格式稳定性 | OutputFormatter 的 6 个正则提取方法全部依赖 LLM 严格遵循 Prompt 格式。单次生成格式偏差就会导致结构化输出部分缺失 |

---

## 6. 设计约定符合性（design.md）

### 6.1 目录结构

| design.md 约定 | 实际 | 偏差 |
|---------------|------|------|
| `search_clients/` 包（含 base/bocha/github/interview + `__init__.py`） | ✅ 5 个文件完整 | |
| `tests/` 目录（含 `__init__.py` + 4 个测试文件） | ✅ 7 个测试文件，超出 design 要求 | |
| `user_profile.py` | ✅ | |
| `memory.py` | ✅ SQLite + WAL + threading.Lock，超出 JSON 方案 |
| `output_formatter.py` | ✅ | |
| `Dockerfile` / `run.sh` | ✅ 已补齐 | |
| `.env.example` | ✅ 已补齐 | |

### 6.2 接口签名

| 接口 | 状态 |
|------|------|
| UserProfile (user_profile.py) | ✅ 与 design.md 4.1 完全一致 |
| AgentMemory (memory.py) | ✅ SQLite + WAL + threading.Lock，超出 design.md JSON 要求 |
| GitHubSearchClient (github.py) | ✅ 继承 BaseSearchClient |
| InterviewSearchClient (interview.py) | ✅ 继承 BaseSearchClient |
| CriticWorker (workers.py) | ✅ 五维度审查，含 fallback 容错 |
| OutputFormatter (output_formatter.py) | ✅ 三轨输出 |
| Orchestrator.run() | ✅ 含 user_profile + Critic 双门控 + 3 处熔断检查点 |
| DeepResearchAgent.research() | ✅ 含 user_profile + **profile_fields |
| api.py ResearchRequest | ✅ 6 个画像字段 + structured_output |

### 6.3 LLM 使用策略（design.md 6.3）

| 场景 | design 要求 | 实际实现 |
|------|-----------|---------|
| 任务拆解/报告综合/差距分析 | model_smart | ✅ `orchestrator.py:224` temperature=0.3（任务拆解） + synthesize_results temperature=0.5 |
| Worker 搜索分析/Critic 审查 | 默认 model | ✅ `workers.py:503` SearchWorker temperature=0.3, `workers.py:661` CriticWorker temperature=0.3 |
| 用户画像提取/查询扩展 | model_fast | ⚠️ `user_profile.py` 使用规则推断而非 LLM（`_infer_*` 方法），`workers.py:451` query expansion 使用默认 llm。合理实现，规则推断降低了成本和延迟 |

---

## 7. 新增潜在风险与边界场景（本轮新增）

### 7.1 高风险

无新增高风险项。

### 7.2 中风险

| 风险 | 说明 |
|------|------|
| （无新增中风险项） | 第二轮审计的中风险项（InterviewSearchClient Bocha 依赖）持续存在 |

### 7.3 低风险

| 风险 | 说明 |
|------|------|
| README 项目树缩进错误 | 见 4.1 |
| purpose.md 版本号不一致 | 见 4.2 |
| OutputFormatter 正则脆弱性 | 见 4.3 |
| `project_recommendations` JSON 扩展字段 | 新增字段（difficulty_level/quality_gate/implementation_steps/key_modules/full_description）可能被依赖 spec Schema 的消费者视为额外字段。实际为向下兼容扩展 |
| FastAPI 标题仍为通用版本 | `api.py:222` 标题仍为 `"Deep Research Agent API"`，未更新为求职助手描述。功能无影响 |

---

## 8. 验收结果汇总（第三轮更新）

| 类别 | 已完整实现 | 部分实现/偏差 | 未实现 |
|------|-----------|--------------|--------|
| 核心求职功能 | 7 项 | 1 项（InterviewSearchClient 精准度） | 0 项 |
| 输入输出格式 | 3 项 | 1 项（JSON 扩展字段） | 0 项 |
| 非功能需求 | 11 项 | 0 项 | 0 项 |
| 交付物 | 12 项 | 0 项 | 0 项 |
| **合计** | **33 项** | **2 项** | **0 项** |

### 与第二轮对比

| 指标 | 第二轮 | 第三轮 | 变化 |
|------|--------|--------|------|
| 已完整实现 | 26 项 | 33 项 | +7（6 个文档交付物 + 1 个 .env.example） |
| 部分实现/偏差 | 1 项 | 2 项 | +1（JSON Schema 扩展字段，向下兼容） |
| 未实现 | 6 项 | 0 项 | **全部补齐** |

---

## 9. 整改建议（第三轮更新）

### P0 — 阻塞性
（无——历轮 P0 均已修复）

### P1 — 重要偏差
（无——第二轮 P1 全部修复，本轮无新 P1）

### P2 — 完善项

1. **修复 README.md 项目结构树缩进**：`README.md:241-243` 将 `requirements.txt` 提升到根目录缩进级别，`search_clients/` 保持在 `deep_research/` 下。

2. **统一版本号**：将 `purpose/purpose.md:5` 的 `v1.0` 更新为 `v2.0`（与 `__init__.py:27` 的 `__version__ = "2.0.0"` 保持一致）。

3. **（可选）更新 FastAPI 标题**：`api.py:222` 将 `"Deep Research Agent API"` 更新为 AI 求职助手相关描述（如 `"AI 求职助手 API"`）。

4. **（可选）分析 OutputFormatter 强健性**：考虑在 LLM 输出解析失败时，增加结构化的日志/告警，便于排查输出格式问题。目前已有 fallback 静默处理，但不易发现格式偏差。

---

> **审计结论**（2026-05-12 第三轮）：第二轮审计的 6 个缺失交付物已全部补齐（README 重写、Dockerfile、run.sh、.env.example、ARCHITECTURE.md、DEMO.md、MIGRATION.md），所有 8 个代码 Bug 修复持续有效。项目核心求职功能完整，代码质量良好，1873 行测试覆盖核心模块。本轮新发现 3 个 P2 级别问题（README 缩进、版本号不一致、OutputFormatter 脆弱性），均为文档/配置层面的轻微偏差。**项目已进入可交付状态**，建议修复上述 P2 项后正式交付。
