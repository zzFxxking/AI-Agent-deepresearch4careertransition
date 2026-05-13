"""
AI求职助手 - 基于 Orchestrator-Workers 架构的AI求职准备系统

这是一个多智能体协作系统，用于自动化生成面试准备报告：
- Orchestrator: 负责任务拆解、分发、汇总和质量控制
- Workers: 并行执行搜索、分析、写作等子任务
- 输出: 学习路径 + 八股清单 + 项目推荐 + 模拟面试（Markdown + JSON）

使用方法:
    from deep_research import DeepResearchAgent

    agent = DeepResearchAgent()
    result = agent.research(
        "我是数学专业研一，想找大模型应用开发实习",
        target_role="大模型应用开发工程师",
        time_budget="3个月",
    )
    print(result.markdown)
    print(result.json_data)
"""

from .main import DeepResearchAgent
from .user_profile import UserProfile, UserProfileExtractor
from .output_formatter import FormattedOutput
from .memory import AgentMemory

__version__ = "2.0.0"
__all__ = [
    "DeepResearchAgent",
    "UserProfile",
    "UserProfileExtractor",
    "FormattedOutput",
    "AgentMemory",
]
