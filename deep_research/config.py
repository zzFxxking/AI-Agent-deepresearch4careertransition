"""
配置文件 - Deep Research Agent 的全局配置

基于高级研究智能体设计优化：
- Lead Agent: 查询类型分类、动态子智能体调度
- SubAgent: OODA循环、研究预算、来源质量评估
"""

import os
from dotenv import load_dotenv

# 加载环境变量（支持从模块所在目录加载）
_env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=_env_path)
load_dotenv()  # 同时尝试当前工作目录

# ==================== LLM 配置 ====================
# 通过 LLM_PROVIDER 环境变量切换供应商: "dashscope" | "deepseek"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "dashscope").lower().strip()

if LLM_PROVIDER == "deepseek":
    LLM_CONFIG = {
        "provider": "deepseek",
        "api_key": os.getenv("DEEPSEEK_API_KEY", os.getenv("DASHSCOPE_API_KEY", "")),
        "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"),
        "model_smart": os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"),
        "model_fast": os.getenv("DEEPSEEK_MODEL_FAST", "deepseek-v4-flash"),
        "max_tokens": int(os.getenv("DEEPSEEK_MAX_TOKENS", "8192")),
        "temperature": float(os.getenv("DEEPSEEK_TEMPERATURE", "0.7")),
    }
else:
    LLM_CONFIG = {
        "provider": "dashscope",
        "api_key": os.getenv("DASHSCOPE_API_KEY"),
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",  # 默认模型
        "model_smart": "qwen-max",  # 用于复杂推理的模型
        "model_fast": "qwen-turbo",  # 用于简单任务的快速模型
        "max_tokens": 8192,
        "temperature": 0.7,
    }

# ==================== 搜索 API 配置 ====================
SEARCH_CONFIG = {
    "api_key": os.getenv("BOCHA_API_KEY"),
    "base_url": "https://api.bocha.cn/v1/web-search",
    "default_count": 10,  # 默认返回结果数
    "summary": True,  # 是否返回摘要
}

# GitHub API Token（可选，用于提高搜索配额）
GITHUB_API_KEY = os.getenv("GITHUB_API_KEY", "")

# ==================== Agent 配置 ====================
AGENT_CONFIG = {
    # ========== Orchestrator (Lead Agent) 配置 ==========
    "max_workers": 8,  # 最大并行 Worker 数（硬件上限，LLM 动态决定实际数量 4-8）
    "max_search_depth": 3,  # 最大搜索深度（迭代次数）
    "timeout_per_worker": 200,  # 单个 Worker 超时时间（秒）
    "total_task_timeout": 1200,  # 整体任务熔断超时（秒），默认 20 分钟

    # ========== 查询类型与子智能体数量配置 ==========
    # 子智能体数量指南（根据查询复杂度自动调整）
    "worker_count_guidelines": {
        "simple": {"min": 1, "max": 2},      # 简单/直接查询
        "standard": {"min": 2, "max": 3},     # 标准复杂度查询
        "medium": {"min": 3, "max": 5},       # 中等复杂度查询
        "high": {"min": 5, "max": 10},        # 高复杂度查询
    },

    # ========== 研究任务配置 ==========
    "min_sources_per_topic": 3,  # 每个主题最少信息源数
    "max_sources_per_topic": 10,  # 每个主题最多信息源数

    # ========== 报告配置 ==========
    "report_language": "zh-CN",  # 报告语言
    "include_sources": True,  # 是否包含来源引用
    "include_summary": True,  # 是否包含执行摘要

    # ========== 迭代优化配置 ==========
    "min_iterations": 2,  # 最少迭代次数（即使质量通过也至少迭代2次）
    "max_iterations": 5,  # 最大迭代次数
    "quality_threshold": 80,  # 质量通过阈值（0-100）

    # ========== 智能终止配置 ==========
    "enable_diminishing_returns_check": True,  # 启用收益递减检测
    "diminishing_returns_threshold": 3,  # 连续 N 次提升小于 5 分则触发
    "early_termination_min_score": 75,  # 提前终止的最低分数要求

    # ========== SubAgent (Worker) 配置 ==========
    # OODA 循环配置
    "worker_max_ooda_cycles": 3,  # 每个 Worker 最大 OODA 循环次数

    # 研究预算配置（根据任务复杂度自动调整）
    "research_budget": {
        "simple": {"max_queries": 3, "max_cycles": 1},
        "medium": {"max_queries": 5, "max_cycles": 2},
        "complex": {"max_queries": 8, "max_cycles": 3},
    },

    # 来源质量评估配置
    "source_quality": {
        "high_quality_domains": [
            ".gov", ".edu", ".org",
            "reuters.com", "bloomberg.com", "wsj.com", "nytimes.com",
            "nature.com", "nature.org", "science.org", "arxiv.org",
            "statista.com", "mckinsey.com", "gartner.com", "idc.com",
        ],
        "low_quality_indicators": [
            "forum", "reddit", "quora", "yahoo answers",
            "wiki", "blog", "medium.com",
        ],
        "speculative_language": [
            "可能", "也许", "据说", "传闻", "预计",
            "may", "might", "possibly", "reportedly",
        ],
    },
}

# ==================== 日志配置 ====================
LOG_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    "show_worker_details": True,  # 是否显示 Worker 详细信息
    "show_search_results": False,  # 是否显示搜索结果详情
    "show_ooda_cycles": True,  # 是否显示 OODA 循环详情
    "show_source_quality": True,  # 是否显示来源质量评估
}

# ==================== MCP 配置 ====================
MCP_CONFIG = {
    "enabled": os.getenv("MCP_ENABLED", "true").lower() == "true",
    # GitHub MCP Server — 仓库搜索、文件读取、Issue 查询
    "github": {
        "enabled": os.getenv("MCP_GITHUB_ENABLED", "true").lower() == "true",
        "token": os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN", os.getenv("GITHUB_API_KEY", "")),
    },
    # Brave Search MCP Server（预留扩展）
    "brave": {
        "enabled": os.getenv("MCP_BRAVE_ENABLED", "false").lower() == "true",
        "api_key": os.getenv("BRAVE_API_KEY", ""),
    },
    # 搜索策略: "mcp_first" → MCP 优先，回退传统 API；"mcp_only" → 仅 MCP；"traditional" → 传统
    "search_strategy": os.getenv("MCP_SEARCH_STRATEGY", "mcp_first"),
}

# ==================== 输出配置 ====================
OUTPUT_CONFIG = {
    "save_intermediate": True,  # 是否保存中间结果
    "output_dir": "./research_output",  # 输出目录
    "formats": ["markdown", "json"],  # 输出格式（双轨输出）
    "include_ooda_logs": True,  # 是否在输出中包含 OODA 循环日志
    "include_source_assessment": True,  # 是否在输出中包含来源质量评估
}

# ==================== 求职场景配置 ====================
JOB_SEARCH_CONFIG = {
    # 目标岗位映射
    "target_roles": [
        "大模型应用开发工程师",
        "算法工程师",
        "AI工程师",
        "机器学习工程师",
    ],
    # 公司层级
    "company_tiers": ["大厂", "中厂", "外企"],
    # 时间预算选项
    "time_budgets": ["1个月", "2个月", "3个月", "6个月", "1年"],
    # 八股知识点类别
    "interview_categories": [
        "Transformer / Attention机制",
        "RAG / 检索增强生成",
        "Agent框架 / ReAct / CoT",
        "MCP协议 / 工具调用",
        "RLHF / 对齐技术",
        "模型部署与推理优化",
        "向量数据库 / Embedding",
        "Prompt Engineering",
        "多模态 / Vision-Language",
    ],
    # 项目质量阈值
    "project_quality": {
        "min_stars": 50,
        "min_forks": 5,
        "exclude_toy_projects": True,
        "preferred_paradigms": ["RAG", "Agent", "MCP", "RLHF", "多模态"],
    },
    # Critic 审查阈值
    "critic_thresholds": {
        "difficulty_match": 70,
        "coverage": 70,
        "freshness": 70,
        "practical_value": 70,
    },
}
