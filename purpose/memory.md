# Hermes Agent 自动进化机制分析

> **文档状态**：研究参考文档（2026-05-12 更新）
> **与当前项目的关系**：本分析中的"四层进化架构"和"提示词即控制器"思想直接影响了我方 `memory.py` 的设计：
> - **L2 情景记忆**（保存执行记录）→ 已实现为 SQLite `records` 表
> - **L3 语义记忆**（关键词匹配）→ 已通过 SQLite 索引 + `get_recent_records()` 简化实现
> - **技能进化 / Nudge / Meta-Agent** → 暂不实施（见 purpose.md 后续迭代规划）
>
> 本文档保留作为后续记忆/进化机制迭代的理论参考。

> 分析对象：[NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
> 分析日期：2026-05-11

---

## 1. 概述

Hermes Agent 的"自动进化机制"是一个**四层闭环学习系统**，通过系统提示引导、周期性 nudge、后台审查和策展人维护，实现技能和记忆的自我产生、自我改进。其核心设计哲学是：**Agent 不是被动等待用户说"记住这个"，而是被主动提示、主动审查、主动维护**。

---

## 2. 四层进化架构

### Layer 1: 系统提示引导（In-Session Evolution）

每一轮对话的系统提示中都会注入学习指令，教导 Agent 在使用工具的过程中主动保存技能和记忆。

**关键代码**：`agent/prompt_builder.py:179-186`

```python
SKILLS_GUIDANCE = (
    "After completing a complex task (5+ tool calls), fixing a tricky error, "
    "or discovering a non-trivial workflow, save the approach as a "
    "skill with skill_manage so you can reuse it next time.\n"
    "When using a skill and finding it outdated, incomplete, or wrong, "
    "patch it immediately with skill_manage(action='patch') -- don't wait to be asked. "
    "Skills that aren't maintained become liabilities."
)
```

**行为要求**：
- 完成复杂任务（5+ 工具调用）后**主动保存技能**
- 发现技能错误/过时/不完整时**立即 patch**，无需等待用户要求
- 技能索引提示会注入所有可用技能列表，并提示 "After difficult/iterative tasks, offer to save as a skill"

---

### Layer 2: 周期性 Nudge（Periodic Prompt）

Agent 内部维护两个计数器，在"不打扰用户主任务"的前提下周期性触发后台回顾。

**关键代码**：`run_agent.py:1888-1890, 1994-1998`

| 计数器 | 间隔默认值 | 触发条件 | 重置条件 |
|--------|-----------|----------|----------|
| `_turns_since_memory` | 10 轮用户对话 | 每 N 轮用户对话后 | Agent 调用 `memory` 工具时 |
| `_iters_since_skill` | 10 个工具调用迭代 | 每 N 个工具调用迭代后 | Agent 调用 `skill_manage` 工具时 |

**重要设计**：计数器在 Agent 初始化时**不会重置**，CLI 多轮对话中持续累积；Gateway 模式下会从会话历史中重构计数，确保 nudge 节奏不被打断。

---

### Layer 3: 后台回顾（Background Review）

当 nudge 触发后，系统**在用户任务完成后**（不影响主任务延迟）启动后台线程，创建一个"分身 Agent"审查刚才的对话并执行保存/更新。

**关键代码**：`run_agent.py:4117-4204`

实现要点：
- 创建 forked `AIAgent`，`max_iterations=16`，`quiet_mode=True`
- 只启用 `memory` 和 `skills` 两个工具集
- 共享父 Agent 的 `_memory_store`，直接写入磁盘
- 危险命令自动拒绝（防止死锁 TUI）
- 输出重定向到 `/dev/null`，用户无感知

**三种审查提示词**：

1. **`_MEMORY_REVIEW_PROMPT`** (`run_agent.py:3871-3880`)：聚焦用户画像（偏好、性格、期望）
2. **`_SKILL_REVIEW_PROMPT`** (`run_agent.py:3882-3976`)：技能进化的核心，要求 Agent "Be ACTIVE"
3. **`_COMBINED_REVIEW_PROMPT`** (`run_agent.py:3978-4007`)：同时审查记忆和技能

**技能审查的信号规则**（任一条即触发行动）：
- 用户纠正了风格/格式/语气/方法
- 出现非平凡的技术/修复/调试路径
- 加载的技能有错误/缺失/过时

**技能更新优先级**：
1. 更新当前加载的技能（如果相关）
2. 更新现有 umbrella 技能
3. 在现有 umbrella 下添加支持文件（references/templates/scripts）
4. 创建新技能（仅当没有现成 umbrella 时）

---

### Layer 4: 策展人（Curator）

策展人是**独立于主 Agent 的后台维护进程**，负责技能库的"新陈代谢"和长期结构性优化。

**关键代码**：`agent/curator.py`

#### 4.1 生命周期自动转换（纯代码，无需 LLM）

```python
# active -> stale: 超过 30 天未使用
# stale -> archived: 超过 90 天未使用
# stale -> active: 被再次使用后重新激活
```

#### 4.2 伞状合并（Umbrella Consolidation）

每 7 天（可配置）运行一次，fork 审查 Agent 执行合并：

> "The goal of the skill collection is a LIBRARY OF CLASS-LEVEL INSTRUCTIONS AND EXPERIENTIAL KNOWLEDGE."

**合并策略**：
- **合并到现有 umbrella**：patch 添加子章节
- **创建新 umbrella**：创建新的类级 SKILL.md
- **降级为支持文件**：session-specific 细节移到 `references/`、`templates/`、`scripts/`

**策展人不变式**：
- 只操作 Agent 创建的技能（通过 `created_by: agent` 标记）
- **从不自动删除**，只归档（可恢复）
- Pinned 技能跳过所有自动转换

---

## 3. 执行层工具

### 3.1 技能管理工具

**关键代码**：`tools/skill_manager_tool.py`

提供动作：`create`、`edit`、`patch`、`delete`、`write_file`、`remove_file`

- 所有技能存储在 `~/.hermes/skills/`
- Agent 创建的技能通过 `mark_agent_created()` 标记，进入策展人管理范围
- 支持安全扫描（`skills_guard.py`），默认关闭

### 3.2 记忆工具

**关键代码**：`tools/memory_tool.py`

提供动作：`add`、`replace`、`remove`

- 两个存储：`MEMORY.md`（Agent 个人笔记）和 `USER.md`（用户画像）
- 系统提示注入的是**会话开始时的冻结快照**，保持前缀缓存稳定
- 工具调用直接修改磁盘上的实时数据

### 3.3 技能使用追踪

**关键代码**：`tools/skill_usage.py`

记录在 `~/.hermes/skills/.usage.json`：

```python
bump_use(skill_name)      # 技能被使用时
bump_view(skill_name)     # 技能被查看时
bump_patch(skill_name)    # 技能被修补时
mark_agent_created(skill_name)  # 标记为 Agent 创建
```

数据驱动策展人的生命周期管理和合并决策。

---

## 4. 关键设计经验（供本项目参考）

1. **提示词即控制器**：将"何时保存技能/记忆"的规则直接写入系统提示，比硬编码触发器更灵活
2. **计数器 + 后台线程**：用轻量计数器跟踪使用频率，用户任务完成后再做重型回顾，避免影响主任务延迟
3. **冻结快照 + 实时写入**：系统提示用会话开始时的快照保持缓存稳定，工具直接写磁盘保证数据实时性
4. **分层技能结构**：鼓励"类级 umbrella 技能 + references/templates/scripts 支持文件"的结构，而非扁平的长列表
5. **策展人哲学**：自动化生命周期管理（active/stale/archived）+ 定期 LLM 驱动的结构性合并
6. **明确的不变式**：Agent 创建的技能 vs  bundled/hub 技能区分管理；归档代替删除；pinned 保护机制

---

## 5. 核心文件索引

| 文件路径 | 职责 |
|---------|------|
| `agent/prompt_builder.py:179-186` | SKILLS_GUIDANCE 系统提示 |
| `agent/prompt_builder.py:920+` | 技能索引注入系统提示 |
| `run_agent.py:1888-1890, 1994-1998` | Nudge 计数器初始化 |
| `run_agent.py:11638-11644` | 记忆 nudge 触发逻辑 |
| `run_agent.py:11918-11922` | 技能 nudge 触发逻辑 |
| `run_agent.py:15155-15181` | 后台回顾调度 |
| `run_agent.py:3871-4007` | 三种后台审查提示词 |
| `run_agent.py:4117-4204` | `_spawn_background_review` 实现 |
| `tools/skill_manager_tool.py` | 技能创建/编辑/删除工具 |
| `tools/memory_tool.py` | 记忆 add/replace/remove 工具 |
| `tools/skill_usage.py` | 技能使用追踪与生命周期状态 |
| `agent/curator.py` | 策展人：自动转换 + 伞状合并 |
| `agent/memory_manager.py` | 记忆提供者编排与上下文注入 |
| `agent/memory_provider.py` | 记忆提供者抽象基类 |
