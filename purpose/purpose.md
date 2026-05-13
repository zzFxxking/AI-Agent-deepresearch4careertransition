# AI求职助手 — 项目现状与后续路线

> **项目定位**：面向 AI/大模型求职者的个性化学习路径与面试准备助手
> **当前版本**：v1.0（2026-05-12）
> **改造基线**：从 Deep Research Agent（通用研究）→ AI 求职助手（垂直求职场景）

---

## 1. 已完成的改造

### 1.1 核心架构（复用）

| 模块 | 状态 | 位置 |
|------|------|------|
| Orchestrator-Workers 架构（自适应 4-8 Worker） | ✅ 直接复用 | `orchestrator.py` |
| ReAct-Reflection 深度扩展 | ✅ 新增 | `react_agent.py` + `react_tools.py` |
| 任务拆解与优先级排序 | ✅ 直接复用 | `orchestrator.py:178-287` |
| 并行 Worker 调度（ThreadPoolExecutor） | ✅ 直接复用 | `orchestrator.py:328-371` |
| 迭代优化与收益递减检测 | ✅ 直接复用 | `orchestrator.py:867-1060` |
| SSE 流式进度输出 | ✅ 直接复用 | `api.py:440-502` |
| FastAPI 服务层 | ✅ 保留不扩展 | `api.py:212-534` |

### 1.2 新增功能

| 模块 | 状态 | 位置 |
|------|------|------|
| **GitHubSearchClient** — GitHub API 垂直搜索 | ✅ | `search_clients/github.py` |
| **InterviewSearchClient** — 面经站点定向搜索 | ✅ | `search_clients/interview.py` |
| **BochaSearchClient** — 通用搜索兜底 | ✅ | `tools.py:141-250` |
| **AgentMemory** — SQLite + WAL 持久化 | ✅ | `memory.py` |
| **CriticWorker** — 五维度审查 + 迭代内门控 | ✅ | `workers.py:617-722` |
| **结构化 JSON 输出** — 三轨 Markdown + JSON | ✅ | `output_formatter.py` |
| **面试模拟问答** — MQ/EQ 格式 Q&A | ✅ | `prompts.py:207-389` |
| **用户画像解析** — Pydantic + 规则推断 | ✅ | `user_profile.py` |
| **总超时熔断** — 3 处检查点 + 20 分钟上限 | ✅ | `orchestrator.py:174-176` |

### 1.3 删除/弱化

| 模块 | 状态 |
|------|------|
| VisualizationWorker | ✅ 已删除 |
| AnalysisWorker | ✅ 弱化（类保留，Orchestrator 未调度） |
| 复杂学术引用 | ✅ 简化为平台名标注 |

---

## 2. 待完成的交付物

以下为 spec.md 要求的交付物，计划项目收尾时统一完成：

- [ ] `README.md` — 更新为求职助手场景
- [ ] `.env.example` — 环境变量模板
- [ ] `Dockerfile` / `run.sh` — 一键部署
- [ ] `ARCHITECTURE.md` — 架构说明（面试讲解用）
- [ ] `DEMO.md` — 完整生成案例
- [ ] `MIGRATION.md` — 改造前后对比
- [ ] `search_clients/bocha.py` — Bocha 从 tools.py 迁移并继承 BaseSearchClient

---

## 3. 暂不做（后续迭代）

以下为 spec.md 明确排除或低优先级的功能：

| 功能 | 原因 |
|------|------|
| 学习进度追踪仪表盘 | 需前端 + 用户系统 |
| API 层扩展 / 前端界面 | 项目定位为简历展示，非产品化 |
| MCP 协议接入 | ✅ 已实现 | `deep_research/mcp/` 模块，已接入 GitHub MCP Server |
| RAG 向量索引 | 后续迭代（当前 SQLite + 关键词匹配够用） |
| Meta-Agent 自我进化 | 后续迭代（需积累足够运行数据） |
| Checkpoint 中断恢复 | 后续迭代（当前任务粒度不需中断恢复） |
| TelemetryCollector | 后续迭代（当前控制台日志够用） |
| 账号系统 / 多用户 | 非产品化目标 |

---

## 4. 当前代码质量

- **核心实现度**：约 92%（按第二轮审计）
- **测试覆盖**：`tests/` 下 7 个测试文件，pytest 全部通过
- **线程安全**：AgentMemory SQLite + WAL + threading.Lock
- **熔断保护**：单 Worker 200s + 总任务 1200s（20 分钟）
- **类型注解**：Pydantic 模型 + 关键决策点注释

---

## 5. 关键决策记录

| 决策 | 选择 | 原因 |
|------|------|------|
| 记忆存储 | SQLite + WAL | 线程安全、零依赖、已有生态 |
| Critic 位置 | 迭代循环内第二门控 | 质量门控 + Critic 独立审查，双重保障 |
| 面经搜索 | Bocha + site 限定 | 无需对接各站点独立 API |
| Bocha 客户端位置 | tools.py（未迁移） | 避免循环依赖，后续迁移到 search_clients/ |
| 熔断时间 | 20 分钟 | 多轮迭代 + Critic 审查 + LLM 调用耗时 |

---

*更新日期：2026-05-12（第二轮审计 — P1-4 修复）*
