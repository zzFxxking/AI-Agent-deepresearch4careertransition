# AI 求职助手 - Deep Research Agent

基于 **Orchestrator-Workers**（自适应 4-8 个 Worker）广度生成 + **ReAct-Reflection** 深度扩展双模式架构的 AI 求职准备系统，自动化为 AI/大模型方向求职者生成个性化的面试准备报告。

## 概述

AI 求职助手是一个多智能体协作系统，针对大模型应用开发 / 算法工程师等岗位，自动搜索、分析、整合网络信息，生成三份高质量面试准备报告：

- **学习路径报告**：从当前水平到目标岗位的阶段性路线图
- **八股面试报告**：按知识点类别组织的系统化面试题清单（>=30 道）
- **项目推荐报告**：高质量开源项目推荐（恰好 3 个，含模拟面试 Q&A）

### 架构一览

```
用户输入 (自然语言 + 结构化字段)
       │
       ▼
  ┌──────────────────┐
  │ UserProfileExtractor│  ← 用户画像解析
  └──────┬───────────┘
         │
  ┌──────▼───────────┐
  │   AgentMemory     │  ← SQLite 持久化记忆
  └──────┬───────────┘
         │
  ┌──────▼───────────┐
  │   Orchestrator    │  ← 任务拆解·并行调度·迭代优化
  └──────┬───────────┘
         │
  ┌──────▼──────────────────────────┐
  │  SearchWorker ×N (并行)          │
  │  ┌──────────┐ ┌──────────┐      │
  │  │ Bocha    │ │ GitHub   │ ...  │
  │  │ 通用搜索  │ │ 项目搜索  │      │
  │  └──────────┘ └──────────┘      │
  │  ┌──────────┐                   │
  │  │ Interview│                   │
  │  │ 面经搜索  │                   │
  │  └──────────┘                   │
  └──────┬──────────────────────────┘
         │
  ┌──────▼───────────┐
  │   CriticWorker    │  ← 审查质量·难度匹配·八股覆盖
  └──────┬───────────┘
         │
  ┌──────▼───────────┐
  │  OutputFormatter  │  ← 三轨输出 (Markdown + JSON)
  └──────┬───────────┘
         │
  ┌──────▼──────────────────────────┐
  │  *_main.md    *_interview.md    │
  │  *_projects.md   *.json         │
  └─────────────────────────────────┘
```

## 功能特性

### 核心求职能力
- **用户画像解析**：从自然语言中提取目标岗位、时间预算、当前水平，生成标准化画像
- **四维任务拆解**：学习路径、八股清单、项目推荐、模拟面试自动并行搜索
- **垂直搜索路由**：Bocha 通用搜索 / GitHub API 项目搜索 / 面经 site 限定搜索，按任务类型自动路由
- **Critic 审查**：五维度审查（项目质量、八股覆盖、难度匹配、背景适配、数量达标），双门控质量控制
- **Agent 记忆**：SQLite + WAL 本地持久化用户画像、历史记录、薄弱点追踪
- **三轨输出**：3 份 Markdown 报告 + 1 份结构化 JSON，供人工阅读和程序化消费

### 保留的高级特性
- **OODA 循环**：Worker 观察-定向-决策-行动循环，智能信息空白识别
- **动态调度**：根据查询复杂度自动调整 Worker 数量和搜索预算
- **迭代优化**：质量评分 → 差距分析 → 补充搜索 → 报告修订，最多 5 轮
- **收益递减检测**：连续提升不足时提前终止，避免无效迭代
- **总超时熔断**：20 分钟全局超时保护
- **SSE 流式输出**：FastAPI 服务支持 Server-Sent Events 实时进度推送

## 环境依赖

- Python 3.10+
- DeepSeek API Key（或 DashScope 通义千问 API Key）
- Bocha 搜索 API Key
- GitHub API Token（可选，用于提高 GitHub 搜索配额）

## 快速开始

### 1. 克隆项目

```bash
git clone <repo-url>
cd deep_research-学习助手
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example deep_research/.env
# 编辑 deep_research/.env，填入你的 API Keys
```

`.env` 最小配置：

```bash
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-your-deepseek-key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-v4-pro
BOCHA_API_KEY=sk-your-bocha-key
# GITHUB_API_KEY=ghp_your_github_token  # 可选
```

### 4. 一键运行

```bash
# 方式一：Shell 脚本
bash run.sh

# 方式二：Docker
docker build -t ai-job-helper .
docker run --rm -it --env-file deep_research/.env ai-job-helper

# 方式三：直接运行
python -m deep_research "我是数学专业研一，想找大模型应用开发实习" \
  --target-role "大模型应用开发工程师" \
  --time-budget "3个月" \
  --company-tier "大厂"
```

## 使用方法

### Python API

```python
from deep_research import DeepResearchAgent

agent = DeepResearchAgent(verbose=True)

result = agent.research(
    "我是数学专业研一学生，跨考计算机，会Python和PyTorch基础，"
    "想找大模型应用开发方向的暑期实习，有3个月准备时间",
    target_role="大模型应用开发工程师",
    time_budget="3个月",
    company_tier="大厂",
    current_level="有Python和PyTorch基础，没做过完整项目",
    focus_areas=["RAG", "Agent框架", "MCP协议"],
    avoid_areas=["前端开发", "嵌入式"],
)

# 获取三份 Markdown 报告
print(result.markdown)           # 主报告（学习路径）
print(result.markdown_interview) # 八股面试报告
print(result.markdown_projects)  # 项目推荐报告

# 获取结构化 JSON
import json
print(json.dumps(result.json_data, ensure_ascii=False, indent=2))
```

### 命令行

```bash
# 基础用法
python -m deep_research "你的求职需求描述"

# 完整参数
python -m deep_research "准备大模型应用开发面试" \
  --target-role "大模型应用开发工程师" \
  --time-budget "3个月" \
  --company-tier "大厂" \
  --current-level "有Python和PyTorch基础" \
  --focus-areas "RAG,Agent框架,MCP协议" \
  --avoid-areas "前端开发" \
  --workers 6 \
  --output ./my_reports

# 安静模式（仅输出报告文本）
python -m deep_research "转AI方向求职准备" --quiet
```

### FastAPI 服务

```bash
uvicorn deep_research.api:app --reload --port 8000
# 访问 http://localhost:8000/docs 查看 Swagger 文档
```

## 配置说明

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `LLM_PROVIDER` | LLM 供应商：`deepseek` / `dashscope` | `dashscope` |
| `DEEPSEEK_API_KEY` | DeepSeek API Key | - |
| `DEEPSEEK_BASE_URL` | DeepSeek API 地址 | `https://api.deepseek.com/v1` |
| `DEEPSEEK_MODEL` | DeepSeek 模型 | `deepseek-v4-pro` |
| `DASHSCOPE_API_KEY` | 阿里云 DashScope API Key | - |
| `BOCHA_API_KEY` | Bocha 搜索 API Key | - |
| `GITHUB_API_KEY` | GitHub Personal Access Token（可选） | - |

核心 Agent 参数在 [config.py](deep_research/config.py) 的 `AGENT_CONFIG` 中配置：

- `max_workers`：最大并行 Worker 数（默认 6）
- `max_iterations`：最大迭代次数（默认 5）
- `quality_threshold`：质量通过阈值（默认 80）
- `total_task_timeout`：总超时熔断（默认 1200s = 20 分钟）

## 项目结构

```
deep_research-学习助手/
├── README.md                   # 项目说明（当前文件）
├── spec.md                     # 需求规格说明书
├── design.md                   # 技术方案与架构设计
├── test_report.md              # 测试报告
├── acceptance_report.md        # 验收报告
├── ARCHITECTURE.md             # 架构深度讲解
├── DEMO.md                     # 完整使用案例演示
├── MIGRATION.md                # 改造前后对比
├── .env.example                # 环境变量模板
├── Dockerfile                  # Docker 构建文件
├── run.sh                      # 一键运行脚本
├── purpose/                    # 项目目标与演进路线
│   ├── purpose.md
│   ├── harness_engineering.md
│   └── memory.md
├── deep_research/              # 核心源代码包
│   ├── __init__.py             # 包初始化
│   ├── __main__.py             # CLI 入口
│   ├── config.py               # 全局配置中心
│   ├── main.py                 # DeepResearchAgent 主入口
│   ├── orchestrator.py         # Orchestrator 编排器
│   ├── workers.py              # Worker 执行器
│   ├── prompts.py              # Prompt 模板
│   ├── tools.py                # LLM/搜索工具层
│   ├── api.py                  # FastAPI 服务
│   ├── user_profile.py         # 用户画像解析
│   ├── memory.py               # AgentMemory 持久化
│   ├── output_formatter.py     # 三轨输出格式化
├── requirements.txt            # Python 依赖清单
│   └── search_clients/         # 垂直搜索客户端
│       ├── __init__.py
│       ├── base.py             # 抽象基类
│       ├── bocha.py            # Bocha 通用搜索
│       ├── github.py           # GitHub 项目搜索
│       └── interview.py        # 面经搜索
├── tests/                      # 单元测试
│   ├── __init__.py
│   ├── test_mvp.py
│   ├── test_run.py
│   ├── test_memory.py
│   ├── test_search_clients.py
│   ├── test_critic_worker.py
│   ├── test_split_reports.py
│   └── test_comprehensive.py
├── research_output/            # 示例输出
└── data/                       # 本地持久化数据
    └── agent_memory.db         # SQLite 记忆数据库
```

## 示例输出

运行后，`research_output/` 目录下生成 5 个文件：

```
research_output/
├── research_20260512_120000_main.md       # 主报告（学习路径 + 执行摘要）
├── research_20260512_120000_interview.md  # 八股面试报告（知识点清单 + 模拟问答）
├── research_20260512_120000_projects.md   # 项目推荐报告（项目详情 + MQ Q&A）
├── research_20260512_120000.json          # 结构化 JSON
└── research_20260512_120000_meta.json     # 元数据（质量分、迭代历史等）
```

## 适用场景

- **AI/大模型方向求职准备**：大模型应用开发、算法工程师等岗位
- **跨专业转型指导**：数学、金融等非科班背景转 AI 方向
- **面试模拟训练**：基于真实岗位和八股的模拟 Q&A
- **项目选择参考**：筛选高质量、非 toy 级别的开源项目

## 后续迭代方向

- 学习进度追踪仪表盘（需要前端 + 用户系统）
- 简历 PDF / GitHub 链接自动解析
- RAG 向量索引历史面经/项目库
- MCP 协议接入统一工具调用（✅ GitHub MCP Server 已集成，预留 Brave Search 扩展）
- 微信小程序/网页版前端

## 注意事项

1. 确保 API Key 配置正确（LLM + 搜索均需有效 Key）
2. GitHub 搜索建议配置 Token 以提高限额（无 Token 限 60 次/小时）
3. 单次生成耗时 2-5 分钟（复杂任务可能更长），有 20 分钟熔断保护
4. 用户数据全部本地存储（SQLite），不上传云端
