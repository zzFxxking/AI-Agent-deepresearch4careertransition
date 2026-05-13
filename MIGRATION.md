# AI 求职助手 - 改造前后对比

> 记录从「通用 Deep Research Agent」到「AI 求职助手」的完整改造过程。

---

## 1. 改造总览

| 维度 | 改造前 (v1.0) | 改造后 (v2.0) |
|------|-------------|-------------|
| **定位** | 通用深度研究 Agent（市场分析、学术综述、技术调研） | AI 大模型方向求职准备助手 |
| **输入** | 单一自然语言研究主题 | 自然语言 + 结构化字段（岗位/时间/公司层级等） |
| **输出** | 单份 Markdown 报告 + 引用来源 | 三份 Markdown 报告（学习路径/八股/项目）+ 结构化 JSON |
| **搜索** | Bocha 通用搜索 | Bocha + GitHub API + 面经 site:限定，按来源自动路由 |
| **质量控制** | 通用质量评分 (0-100) | 双门控（通用评分 + Critic 五维度审查） |
| **记忆** | 无 | SQLite 本地持久化（用户画像 + 历史记录 + 薄弱点追踪） |
| **输出格式** | Markdown 长文 + 学术引用 | 三轨 Markdown + JSON Schema 结构化输出 |
| **代码规模** | ~1500 行（核心 6 文件） | ~2500 行（核心 12 文件 + 4 文件搜索客户端包） |

---

## 2. 模块改造清单

### 2.1 保留并增强的模块

| 文件 | 改造前职责 | 改造后变更 |
|------|-----------|-----------|
| `orchestrator.py` | 任务拆解 → 分发 → 汇总 → 质量检查 → 迭代优化 | +用户画像透传 +Critic 双门控 +结构化输出字段 +3 处熔断检查点 |
| `workers.py` | SearchWorker(OODA), WriterWorker, AnalysisWorker, VisualizationWorker | -VisualizationWorker（删除） -AnalysisWorker（弱化） +CriticWorker（五维度审查） +中文分词修复 |
| `prompts.py` | 研究报告语境 | 全面替换为面试准备语境（四维拆解、背景适配、硬性数量约束） |
| `main.py` | DeepResearchAgent.research(task) | +user_profile 参数 +三轨文件保存 +ConsoleReporter 求职标签 |
| `tools.py` | LLM 调用 + Bocha 搜索 | +搜索客户端注册表 +Bocha 迁移到 search_clients/bocha.py |
| `config.py` | LLM + Agent 配置 | +GitHub API Key +求职场景配置 +来源质量精确域名 |
| `api.py` | 通用 ResearchRequest | +6 个用户画像可选字段 +structured_output 响应字段 +配置修改加锁保护 |

### 2.2 新增的模块

| 文件 | 职责 | 核心能力 |
|------|------|---------|
| `user_profile.py` | 用户画像解析 | Pydantic 模型验证、自然语言推断、中英文逗号兼容 |
| `memory.py` | Agent 记忆 | SQLite + WAL、自动 JSON 迁移、薄弱点提取、记忆上下文生成 |
| `output_formatter.py` | 输出格式化 | 三轨拆分、正则结构化提取、严格格式 + 旧格式 fallback 双路径 |
| `search_clients/base.py` | 搜索客户端基类 | SearchResult / SearchResponse 数据结构、搜索抽象接口 |
| `search_clients/bocha.py` | Bocha 通用搜索 | 从 tools.py 迁移并继承 BaseSearchClient |
| `search_clients/github.py` | GitHub 项目搜索 | REST API、stars/forks/language 解析、注入过滤 |
| `search_clients/interview.py` | 面经定向搜索 | Bocha + site: 限定、面经站点映射、关键词自动触发 |

### 2.3 删除的模块

| 模块 | 删除原因 |
|------|---------|
| `VisualizationWorker` | 生成图表 JSON 对学习路径无用 |
| 复杂学术引用格式 | 对面试准备场景过于冗长，简化为平台名标注 |

---

## 3. 解决的问题

### 3.1 核心痛点 → 解决方案

| 痛点 | 解决方案 | 对应模块 |
|------|---------|---------|
| 八股资料不成体系、内容过时 | 按知识点类别组织 >=30 道题，标明频率和时效性 | prompts.py + CriticWorker |
| 项目选择缺乏判断力，选了 toy 项目 | GitHub API stars/forks 过滤 + Critic toy 项目检测 | github.py + CriticWorker |
| 学习路径不清楚从何开始 | 根据 current_level 动态生成三阶段路径 | orchestractor.py + prompts.py |
| 每次从零开始，无个性化 | AgentMemory 持久化画像和薄弱点 | memory.py |
| 输出无法程序化处理 | 结构化 JSON（符合 spec.md Schema） | output_formatter.py |

### 3.2 测试中发现的 8 个 Bug 及修复

详见 [test_report.md](test_report.md)，摘要如下：

| Bug | 影响模块 | 修复 |
|-----|---------|------|
| `extract(None)` 崩溃 | user_profile.py | 入口添加 `if not query` 防御 |
| 中文逗号未分割 | user_profile.py | 分割前替换 `"，"` → `","` |
| `_load()` 静默忽略损坏 JSON | memory.py | 打印警告日志 |
| `_identify_information_gaps` 中文无效 | workers.py | 正则按中英文标点分词 |
| `_expand_queries` 非字符串崩溃 | workers.py | 添加 `str()` 类型转换 |
| `run_research_task` 无锁修改配置 | api.py | 引入 `threading.Lock()` |
| `_parse_query` 未过滤危险字符 | github.py | 正则移除 `"'`;--` 等注入字符 |
| `high_quality_domains` 匹配过宽 | config.py | `"nature"` → `"nature.com"` 精确匹配 |

---

## 4. 设计约定符合性

### 4.1 与 spec.md 的对应

| spec 需求 | 实现状态 |
|-----------|---------|
| 自然语言 + 结构化字段输入 | ✅ `user_profile.py` |
| 三轨 Markdown 输出 | ✅ `output_formatter.py` |
| 结构化 JSON 输出 | ✅ JSON Schema 兼容 |
| 学习路径（分阶段） | ✅ `TASK_DECOMPOSITION_PROMPT` |
| 八股清单（按知识点类别） | ✅ `SYNTHESIS_PROMPT` |
| 项目推荐（过滤 toy） | ✅ `GitHubSearchClient` + `CriticWorker` |
| 模拟面试 Q&A | ✅ MQ/EQ 格式 |
| AgentMemory 持久化 | ✅ SQLite + WAL |
| Critic Agent | ✅ 五维度审查 + 双门控 |
| Dockerfile / run.sh | ✅ 已交付 |
| 不扩展 API、不做前端 | ✅ api.py 仅微调 |

### 4.2 与 design.md 的对应

| design 约定 | 实现状态 |
|------------|---------|
| 方案A：最小侵入式修改 | ✅ 保留核心骨架 |
| 14 文件目录结构 | ✅ 全部实现 |
| 接口签名（UserProfile 等） | ✅ 与 design.md 4.1-4.7 一致 |
| LLM 使用策略 | ✅ 仅使用已有 API |
| 不引入 LangChain/向量数据库等 | ✅ 自建架构 |
| 搜索源方案 | ✅ Bocha + GitHub + 面经 |

---

## 5. 已知权衡与取舍

| 权衡点 | 选择 | 影响 | 后续改进方向 |
|--------|------|------|------------|
| InterviewSearchClient | Bocha + site: 限定 | 精准度依赖 Bocha 收录面经站点的质量 | 后续可升级为直接爬取或调用面经站点 API |
| AnalysisWorker | 保留类但不调度 | 代码中残留，可能被误调度 | 后续清理或改造成通用分析工具 |
| 输出格式化 | 正则解析 Markdown | LLM 格式偏差时需 fallback | 可升级为结构化 Prompt 约束 + Pydantic 二次校验 |
| 搜索预算固化为 config | 不根据实时 API 速率动态调整 | GitHub 无 Token 时可能 403 | 添加速率感知的动态退避策略 |
| 无 RAG 向量索引 | 每次实时搜索 | 重复查询无法复用 | 后续迭代加入向量存储 + 缓存 |

---

## 6. 版本历史

| 版本 | 日期 | 关键变更 |
|------|------|---------|
| v1.0 | 2025 | 通用 Deep Research Agent（Orchestrator-Workers, OODA, SSE） |
| v2.0 | 2026-05-12 | 改造为 AI 求职助手：垂直搜索、Critic Agent、AgentMemory、三轨输出 |
