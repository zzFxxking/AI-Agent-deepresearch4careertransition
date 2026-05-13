"""
ReAct 工具集 — 供 ReActReflectionAgent 在 Thought→Action→Observation 循环中调用。

每个工具继承 BaseTool，提供 name / description / parameters 元数据供 LLM 选择，
以及 execute() 方法执行实际操作。
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    content: str
    metadata: dict = field(default_factory=dict)
    error: str = ""


class BaseTool:
    """ReAct 工具基类"""
    name: str = ""
    description: str = ""
    parameters: dict = {}

    def execute(self, **kwargs) -> ToolResult:
        raise NotImplementedError

    def to_prompt_desc(self) -> str:
        """生成供 LLM 理解的工具描述"""
        params_desc = ", ".join(
            f"{k}: {v}" for k, v in self.parameters.items()
        )
        return f"- **{self.name}**: {self.description}  参数: ({params_desc})"


# ==================== 搜索工具 ====================

class SearchTool(BaseTool):
    """在线搜索工具 — 复用现有搜索客户端"""

    name = "search"
    description = "在线搜索，获取最新面经、技术文章、项目信息。"
    parameters = {
        "query": "搜索关键词（string）",
        "source_type": "来源类型（github/bocha/interview），默认 bocha",
    }

    def execute(self, query: str = "", source_type: str = "bocha", **kwargs) -> ToolResult:
        try:
            from .search_clients.base import SearchResponse
            from .workers import SearchWorker

            # 构建临时 SubTask 以复用 SearchWorker
            class _TempTask:
                id = "react_search"
                name = "ReAct搜索"
                description = query
                search_queries = [query]
                expected_sources = [source_type] if source_type != "bocha" else []
                expected_output = ""
                research_objective = query
                priority = "high"
                scope_boundaries = ""

            worker = SearchWorker(max_queries=3, max_analysis_cycles=1)
            result = worker.execute(_TempTask())

            findings = result.get("key_findings", [])
            summary = result.get("summary", "")
            formatted = f"搜索完成: {len(findings)} 条结果\n{summary}\n"
            for f in findings[:5]:
                formatted += f"\n- {f.get('finding', '')} (来源: {f.get('source', '')})"

            return ToolResult(success=True, content=formatted, metadata={"findings": findings})

        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))


# ==================== 提取工具 ====================

class ExtractTool(BaseTool):
    """信息提取工具 — 从报告/搜索结果中提取关键信息"""

    name = "extract"
    description = "从已有报告文本或搜索结果中提取指定主题的关键信息。"
    parameters = {
        "topic": "要提取的主题（string），如 'RLHF'、'RAG'",
        "source_text": "源文本（string），如报告片段或搜索结果",
    }

    def execute(self, topic: str = "", source_text: str = "", **kwargs) -> ToolResult:
        if not source_text:
            return ToolResult(success=False, content="", error="source_text 为空")

        try:
            from .tools import get_llm_client
            llm = get_llm_client()

            prompt = f"""请从以下文本中提取与 "{topic}" 相关的所有关键信息：

<源文本>
{source_text[:8000]}
</源文本>

请提取：
1. 核心知识点（有哪些关键概念）
2. 已覆盖的内容（已经讲到了什么）
3. 缺失的内容（还应补充什么）
4. 深度评估（内容是否足够深入）

以 JSON 格式输出：
{{"core_concepts": [...], "covered": [...], "missing": [...], "depth_assessment": "..."}}"""

            response = llm.chat(prompt=prompt, temperature=0.2)
            if response.success:
                return ToolResult(success=True, content=response.content)
            return ToolResult(success=False, content="", error=response.error_msg)

        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))


# ==================== 写作工具 ====================

class WriteTool(BaseTool):
    """内容撰写工具 — 撰写/扩展八股题目或项目分析"""

    name = "write"
    description = "撰写或扩展面试八股题目、项目分析等结构化的面试准备内容。"
    parameters = {
        "section": "撰写的内容类型（interview_question/project_analysis/learning_path），string",
        "topic": "主题（string），如 'RLHF DPO vs PPO'",
        "requirements": "具体要求（string），如 '5道扩展八股题，每题含考察点、参考答案、难度'",
        "context": "参考上下文（string），如已有的相关题目",
    }

    def execute(self, section: str = "", topic: str = "", requirements: str = "",
                context: str = "", **kwargs) -> ToolResult:
        try:
            from .tools import get_llm_client
            llm = get_llm_client()

            prompt = f"""你是一位资深 AI 面试官。请撰写面试准备内容。

<撰写类型>
{section}
</撰写类型>

<主题>
{topic}
</主题>

<撰写要求>
{requirements}
</撰写要求>

<参考上下文>
{context[:5000]}
</参考上下文>

请按照以下标准撰写：
1. 八股题目须含：问题、考察点、参考答案要点、难度标签（基础/进阶/压轴）、频率（高/中/低）
2. 项目分析须含：技术栈解析、核心实现分析、学习建议
3. 内容须贴合 2025-2026 年最新技术趋势
4. 区分事实与推测，标注信息来源
5. 语言风格：专业严谨，面试官口吻

请直接输出撰写的内容（Markdown 格式）："""

            response = llm.chat(prompt=prompt, temperature=0.5, max_tokens=4096)
            if response.success:
                return ToolResult(success=True, content=response.content)
            return ToolResult(success=False, content="", error=response.error_msg)

        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))


# ==================== 自反思审查工具 ====================

class CritiqueTool(BaseTool):
    """自反思审查工具 — 对已生成内容进行质量自检"""

    name = "critique"
    description = "对已生成的内容进行质量自检，识别不足并给出改进建议。"
    parameters = {
        "content": "待审查的内容（string）",
        "criteria": "审查维度（string），如 '深度/覆盖度/准确性/实用性'",
        "context": "原始任务上下文（string），用于判断是否满足要求",
    }

    def execute(self, content: str = "", criteria: str = "深度/覆盖度/准确性/实用性",
                context: str = "", **kwargs) -> ToolResult:
        if not content:
            return ToolResult(success=False, content="", error="content 为空")

        try:
            from .tools import get_llm_client
            llm = get_llm_client()

            prompt = f"""请对以下面试准备内容进行质量自检。

<原始任务>
{context[:2000]}
</原始任务>

<审查维度>
{criteria}
</审查维度>

<待审查内容>
{content[:6000]}
</待审查内容>

请从以下角度审查并给出 JSON 输出：
1. 深度：内容是否足够深入？是否仅停留在表面概念？
2. 覆盖度：是否遗漏了关键知识点？
3. 准确性：是否有错误或过时信息？
4. 实用性：对求职者是否有实际帮助？

JSON 格式：
{{
    "depth_score": 75,
    "coverage_score": 80,
    "accuracy_score": 85,
    "practicality_score": 80,
    "critical_issues": ["必须修复的问题"],
    "improvement_suggestions": ["具体改进建议"],
    "needs_revision": true,
    "supplementary_searches": ["建议补充搜索的关键词"]
}}"""

            response = llm.chat(prompt=prompt, temperature=0.2)
            if response.success:
                return ToolResult(success=True, content=response.content)
            return ToolResult(success=False, content="", error=response.error_msg)

        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))


# ==================== 工具注册表 ====================

ALL_TOOLS: list[BaseTool] = [
    SearchTool(),
    ExtractTool(),
    WriteTool(),
    CritiqueTool(),
]


def get_tool_by_name(name: str) -> Optional[BaseTool]:
    """根据名称获取工具"""
    for tool in ALL_TOOLS:
        if tool.name == name:
            return tool
    return None


def get_tools_prompt() -> str:
    """生成所有工具的 LLM 提示描述"""
    return "\n".join(tool.to_prompt_desc() for tool in ALL_TOOLS)
