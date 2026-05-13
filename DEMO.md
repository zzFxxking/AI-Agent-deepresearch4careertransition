# AI 求职助手 - 完整演示案例

> 一个完整的端到端使用案例，展示从输入到三轨输出的全部过程。

---

## 案例背景

**用户画像**：
- 身份：数学专业研一，跨考计算机
- 目标岗位：大模型应用开发工程师
- 目标公司：大厂
- 准备时间：3 个月
- 当前水平：有 Python 和 PyTorch 基础，没做过完整项目
- 重点方向：RAG、Agent 框架、MCP 协议
- 排除方向：前端开发、嵌入式

---

## 步骤 1：命令行运行

```bash
python -m deep_research \
  "我是数学专业研一学生，跨考计算机，会Python和PyTorch基础，想找大模型应用开发方向的暑期实习，有3个月准备时间" \
  --target-role "大模型应用开发工程师" \
  --time-budget "3个月" \
  --company-tier "大厂" \
  --current-level "有Python和PyTorch基础，没做过完整项目" \
  --focus-areas "RAG,Agent框架,MCP协议"
```

## 步骤 2：控制台输出（进度）

```
============================================================
[实验] AI求职助手 - Deep Research Agent
============================================================

[任务] 求职目标: 我是数学专业研一学生...
[岗位] 目标岗位: 大模型应用开发工程师
[时间] 准备周期: 3个月
[层级] 目标公司: 大厂
[时间] 开始时间: 2026-05-12 10:30:00
------------------------------------------------------------

[搜索] 正在分析任务...
[清单] 任务拆解完成，共 4 个子任务（根据用户画像自适应：学习路径1个，八股1个，项目1个，扩展1个）
   - 学习路径规划
   - 八股清单-核心知识点
   - 开源项目推荐
   - 扩展问题生成

[启动] 共 4 个子任务，并行 4 个 Workers...
   [开始] 学习路径规划
   [开始] 八股清单-核心知识点
   [开始] 开源项目推荐
   [开始] 扩展问题生成
   [完成] 学习路径规划 [15.3s]
   [完成] 八股清单-核心知识点 [22.1s]
   [完成] 开源项目推荐 [18.7s]
   [完成] 扩展问题生成 [19.2s]

[编写] 正在生成研究报告...
[报告] 报告生成完成 (12853 字符)

━━━ 第 1/5 次迭代 ━━━
[检查] 正在进行质量检查...
[评分] 质量评分: 82分 (阈值:80) [通过]
   [审查] Critic审查中...
   [审查] Critic评分: 78，发现问题: 2个
   [问题] 八股覆盖不足: 缺少「向量数据库/Embedding」知识点
   [问题] 项目推荐质量: miniMind - 判定为toy项目(纯教学demo)
   [补充] 分发 2 个补充研究任务...
      [补充] 补充八股: 向量数据库
      [补充] 替换低质量项目推荐
      [完成] 补充八股: 向量数据库 [12.4s]
      [完成] 替换低质量项目推荐 [8.9s]
   [优化] 正在修订报告...
   [报告] 报告修订完成 (14892 字符)

━━━ 第 2/5 次迭代 ━━━
[检查] 正在进行质量检查...
[评分] 质量评分: 88分 (阈值:80) [通过]
   [审查] Critic评分: 85，严重问题: 0个
[通过] 质量+Critic双通过（88/85），迭代结束

============================================================
[通过] 面试准备报告已生成
[目录] 输出目录: ./research_output
[文件] 主报告 + 八股面试 + 项目推荐（各含 Markdown + JSON）
============================================================
```

## 步骤 3：输出文件

`research_output/` 目录下生成 5 个文件：

```
research_output/
├── research_20260512_103000_main.md      ← 主报告（学习路径）
├── research_20260512_103000_interview.md ← 八股面试报告
├── research_20260512_103000_projects.md  ← 项目推荐报告
├── research_20260512_103000.json         ← 结构化 JSON
└── research_20260512_103000_meta.json    ← 元数据
```

## 步骤 4：输出内容预览

### 主报告 `_main.md`（节选）

```markdown
# 主报告 - 执行摘要与学习路径

## 1. 背景分析与目标定位

- **背景类型判断**: 数学背景转AI（跨考计算机）
- **目标岗位分析**: 大模型应用开发工程师，核心考察 RAG系统设计、

Agent框架实现、MCP协议理解、工程落地能力
- **学习策略**: 聚焦概念理解和工程应用，适当补充数学基础

## 2. 阶段性学习路径

### 阶段1: 基础巩固期（第1-4周）
- **持续时间**: 4周
- **核心任务**:
  - Python 项目工程化实践（完成 1 个中等规模 CLI 工具）
  - Transformer 架构系统学习（论文精读 + 手写 Attention）
  - PyTorch 实战：用 HuggingFace 微调一个 GPT-2 模型
- **验收标准**: 能独立完成模型微调全流程；能口头画出 Transformer 结构
- **关联八股/项目**: 掌握 Transformer / Attention 八股；为项目1打基础

### 阶段2: 项目实战期（第5-8周）
- **持续时间**: 4周
- **核心任务**:
  - 克隆并运行 RAGFlow，理解 RAG 系统架构
  - 动手实现一个简易 Agent（ReAct 循环 + 工具调用）
  - 学习 MCP 协议并实现一个 MCP Server
- **验收标准**: 能独立搭建 RAG 系统；能解释 Agent 设计决策

### 阶段3: 面试冲刺期（第9-12周）
- **持续时间**: 4周
- **核心任务**:
  - 系统性刷八股清单（40 道 + EQ）
  - 针对 3 个推荐项目模拟面试
  - 复盘项目中的技术决策和 trade-off
- **验收标准**: 能应对大厂一面/二面技术问答

## 3. 八股清单使用指南
入门阶段先过一遍基础题，进阶题在项目实战中同步学习...
```

### 八股面试报告 `_interview.md`（节选）

```markdown
# 八股知识点清单

## Transformer / Attention机制

### Q1: Self-Attention 的计算公式是什么？Q、K、V 分别是什么？
**考察点**: Attention 机制核心原理
**参考答案要点**: Q=W_q·X, K=W_k·X, V=W_v·X;
Attention(Q,K,V)=softmax(QK^T/√d_k)V;
除以√d_k 是为了防止点积过大导致 softmax 梯度消失
**难度标签**: 基础
**频率**: 高

### Q2: 为什么 Transformer 使用多头注意力而不是单头？
**考察点**: 多头的设计动机
**参考答案要点**: 单头只能关注一种关系模式；
多头允许模型在不同子空间学习不同的注意力模式；
类比：CNN 多卷积核
**难度标签**: 进阶
**频率**: 高

## RAG / 检索增强生成

### Q1: 简述 RAG 的完整流程
**考察点**: RAG 系统架构理解
**参考答案要点**: 文档加载→文本分割→Embedding→向量入库；
用户查询→查询 Embedding→相似度检索→召回 Top-K→拼接 Prompt→LLM 生成
**难度标签**: 基础
**频率**: 高

## 扩展问题区

### EQ1: 在 RAGFlow 项目中，如何评估检索质量？
**关联项目**: RAGFlow
**问题背景**: 基于该项目实际使用的检索评估方案
**考察点**: 检索质量评估指标
**参考答案要点**: Recall@K, MRR, NDCG；
人工标注 Ground Truth；A/B 测试不同 chunk_size 和 embedding 模型
**难度标签**: 进阶

...

## 模拟面试

### MQ1: 你做的 RAG 项目中，检索准确率不高怎么办？
**考察点**: 系统性问题排查能力
**参考答案要点**: ①检查 Embedding 模型是否匹配领域；
②调整 chunk_size 和 overlap；③加入 reranker；④混合检索（BM25 + 向量）
**追问方向**: 如何评估 reranker 效果；混合检索的权重如何确定
```

### 项目推荐报告 `_projects.md`（节选）

```markdown
# 项目推荐清单

## 项目1: RAGFlow
**GitHub**: https://github.com/infiniflow/ragflow
**Stars**: 32000
**Forks**: 3200
**技术栈**: Python, FastAPI, React, Elasticsearch
**难度分级**: 进阶
**匹配原因**: RAG 方向最佳入门项目，有你重点关注的 RAG 技术栈架构；
代码质量高且文档完善；大厂面试高频项目

### 模拟面试 Q&A

#### MQ1: RAGFlow 中的文档解析 pipeline 是如何设计的？
**考察点**: 系统设计和工程实践
**参考答案框架**: 支持 PDF/Word/图片等多格式；
使用 DeepDoc 模型做版面分析；智能分块策略
**追问方向**: 如何保证分块不丢失上下文语义

#### MQ2: 如果让你优化 RAGFlow 的检索延迟，你会从哪些方面入手？
**考察点**: 性能优化能力
**参考答案框架**: Embedding 缓存、索引分片、近似检索、异步处理
**追问方向**: FAISS vs Elasticsearch 选型

## 项目2: LangGraph
...

## 项目3: MCP-CLI
...
```

### 结构化 JSON `_meta.json`（节选）

```json
{
  "original_task": "我是数学专业研一学生...",
  "status": "completed",
  "quality_score": 88,
  "duration": 186.5,
  "iteration_count": 2,
  "task_plan": {
    "subtask_count": 4,
    "worker_mode": "adaptive (4-8)",
    "report_structure": {
      "title": "大模型应用开发工程师 面试准备报告",
      "sections": ["学习路径", "八股清单", "项目推荐"],
      "key_deliverables": [
        "阶段性学习路线",
        ">=30道八股题",
        "恰好3个高质量开源项目"
      ]
    }
  },
  "iteration_history": [
    {
      "iteration": 1,
      "quality_score": 82,
      "report_length": 12853,
      "gap_count": 2,
      "supplementary_task_count": 2
    },
    {
      "iteration": 2,
      "quality_score": 88,
      "report_length": 14892,
      "gap_count": 0,
      "supplementary_task_count": 0
    }
  ]
}
```

---

## 步骤 5：Python API 方式

等价于以上的 Python 代码：

```python
from deep_research import DeepResearchAgent

agent = DeepResearchAgent(verbose=True, save_output=True)

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

# 获取输出
print(f"质量评分: {result.metadata['quality_score']}")
print(f"迭代次数: {result.metadata['iterations']}")
print(f"主报告长度: {len(result.markdown)} 字符")
print(f"八股报告长度: {len(result.markdown_interview)} 字符")
print(f"项目报告长度: {len(result.markdown_projects)} 字符")
print(f"JSON 包含字段: {list(result.json_data.keys())}")

# 查看结构化数据
projects = result.json_data.get("project_recommendations", [])
for p in projects:
    print(f"项目: {p['name']} (Stars: {p['stars']}, 模拟面试: {len(p['mock_qa'])}道)")

categories = result.json_data.get("interview_questions", {}).get("categories", [])
for cat in categories:
    print(f"八股类别: {cat['name']} ({len(cat['questions'])} 道题)")

phases = result.json_data.get("learning_path", {}).get("phases", [])
for phase in phases:
    print(f"学习阶段: {phase['name']} ({phase['duration']}, {len(phase['tasks'])} 个任务)")
```

---

## 步骤 6：FastAPI 方式

```bash
# Terminal 1: 启动服务
uvicorn deep_research.api:app --reload --port 8000

# Terminal 2: 提交任务
curl -X POST "http://localhost:8000/research" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "我是数学专业研一，想找大模型应用开发实习",
    "target_role": "大模型应用开发工程师",
    "time_budget": "3个月",
    "company_tier": "大厂",
    "focus_areas": ["RAG", "Agent框架"]
  }'

# 返回: {"task_id": "a1b2c3d4", "status": "pending", ...}

# 查询状态
curl "http://localhost:8000/research/a1b2c3d4"

# 获取结果（完成后）
curl "http://localhost:8000/research/a1b2c3d4/result"
# 返回包含 structured_output 字段的完整 JSON
```

---

## 典型运行时间

| 场景 | 耗时 | 说明 |
|------|------|------|
| 快速生成 | 60-90s | 简单画像，1 次迭代通过 |
| 标准生成 | 120-180s | 含 Critic 修正，2 次迭代 |
| 深度生成 | 180-300s | 多轮补充搜索，3-4 次迭代 |

---

## 步骤 7：ReAct-Reflection 深度扩展（新增）

当用户对已生成的报告有更深入的需求时，可使用 ReAct-Reflection 模式进行单点深度追问。

### CLI 方式

```bash
# 深度八股扩展：将 RLHF 八股扩展到 15 道题
python -m deep_research react \
  --mode interview \
  --task "将RLHF相关八股扩展到15道，每题深入数学推导和源码分析" \
  --context-report research_output/research_20260512_202503_interview.md \
  --max-steps 8

# 单项目深度分析：分析 RAGFlow 适配性
python -m deep_research react \
  --mode project \
  --task "深入分析RAGFlow是否适合我的背景，给出具体学习路线" \
  --context-report research_output/research_20260512_202503_projects.md \
  --max-steps 6

# 追问模式：回答具体技术问题
python -m deep_research react \
  --mode qa \
  --task "Transformer KV Cache 的实现原理与优化方案" \
  --context-report research_output/research_20260512_202503_main.md \
  --max-steps 5
```

### Python API 方式

```python
from deep_research.react_agent import ReActReflectionAgent

agent = ReActReflectionAgent(verbose=True)

result = agent.run(
    task="将RLHF八股扩展到15道，每题深入数学推导",
    context_report_path="research_output/xxx_interview.md",
    max_steps=8,
)

print(result.final_content)
print(f"推理链: {len(result.steps)} 步")
print(f"质量评分: {result.quality_score}")
for step in result.steps:
    print(f"  Step {step.step}: {step.action} → {step.tool_success}")
```
