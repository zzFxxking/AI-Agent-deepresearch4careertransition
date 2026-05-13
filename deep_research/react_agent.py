"""
ReAct-Reflection Agent — 基于 Thought→Action→Observation 循环的深度研究智能体。

用于对已生成的面试准备报告（八股清单/项目推荐 Markdown 文件）进行单点深度追问与扩展。
集成了 Reflection 自反思机制，在生成过程中实时自检内容质量与覆盖度。

使用方式:
    agent = ReActReflectionAgent()
    result = agent.run(
        task="帮我把RLHF八股扩展到15道题",
        context_report_path="research_output/xxx_interview.md",
        max_steps=8,
    )
    print(result.final_content)
"""

import json
import time
from dataclasses import dataclass, field
from typing import Optional

from .tools import get_llm_client, extract_json, format_search_context
from .react_tools import (
    BaseTool, ToolResult,
    SearchTool, ExtractTool, WriteTool, CritiqueTool,
    get_tool_by_name, get_tools_prompt,
)


# ==================== 数据结构 ====================

@dataclass
class ReActStep:
    """单步 ReAct 循环记录"""
    step: int
    thought: str
    action: str
    action_input: dict
    observation: str
    tool_success: bool
    reflection: str = ""


@dataclass
class ReActResult:
    """ReAct Agent 执行结果"""
    task: str
    success: bool
    final_content: str
    steps: list[ReActStep] = field(default_factory=list)
    reflection_summary: str = ""
    quality_score: int = 0
    error: str = ""
    duration: float = 0


# ==================== ReAct Prompt 模板 ====================

REACT_SYSTEM_PROMPT = """你是一个 ReAct（Reasoning + Acting）智能体，专门用于深度扩展AI面试准备内容。

你的工作方式是循环执行：Thought（思考）→ Action（行动）→ Observation（观察）。

## 可用工具
{tools}

## 工作流程
1. 先 **extract** 分析已有报告，识别扩展方向
2. 再 **search** 搜索最新的面试题和技术资料
3. 用 **write** 撰写扩展内容
4. 用 **critique** 自检质量，必要时回到第2步

## 输出格式（严格遵守）
每次响应必须以 JSON 格式输出：

{{
    "thought": "分析当前状态，决定下一步做什么（中文）",
    "action": "工具名称（search/extract/write/critique/finish）",
    "action_input": {{"参数名": "参数值"}},
    "reasoning": "为什么选择这个行动"
}}

当任务完成时，使用 action="finish"，并在 thought 中总结完成的工作。
当选择 finish 时，action_input 中的 content 字段包含最终输出。

## 原则
- 每一步只做一个行动，不要跳步
- 先充分搜索再撰写，确保内容准确
- 撰写后必须自检（critique）
- 深度优先：宁缺毋滥，内容要深入到源码/数学/工程细节
- 时效性优先：搜索 2025-2026 年最新资料
"""


# ==================== ReActReflectionAgent ====================

class ReActReflectionAgent:
    """
    ReAct-Reflection 深度研究 Agent。

    基于 Thought→Action→Observation 循环，对已有面试准备报告进行深度扩展。
    每轮写作后触发 Reflection 自检，发现不足自动补充搜索和修订。
    """

    def __init__(self, verbose: bool = True):
        self.llm = get_llm_client()
        self.verbose = verbose
        self._tools: dict[str, BaseTool] = {
            "search": SearchTool(),
            "extract": ExtractTool(),
            "write": WriteTool(),
            "critique": CritiqueTool(),
        }

    def _log(self, msg: str):
        if self.verbose:
            print(msg)

    def run(
        self,
        task: str,
        context_report: str = "",
        context_report_path: str = "",
        max_steps: int = 8,
        reflection_interval: int = 2,
    ) -> ReActResult:
        """
        执行 ReAct-Reflection 研究循环。

        参数:
            task: 研究任务描述（如 "将RLHF八股扩展到15道题"）
            context_report: 已有报告的完整文本
            context_report_path: 已有报告文件路径（与 context_report 二选一）
            max_steps: 最大 ReAct 步数
            reflection_interval: 每隔多少步触发一次 Reflection

        返回:
            ReActResult: 包含最终内容和完整推理链
        """
        start_time = time.time()
        steps: list[ReActStep] = []
        accumulated_content = ""
        memory: list[str] = []

        # 加载上下文报告
        if context_report_path and not context_report:
            try:
                with open(context_report_path, "r", encoding="utf-8") as f:
                    context_report = f.read()
            except Exception as e:
                return ReActResult(
                    task=task, success=False, final_content="",
                    error=f"读取报告文件失败: {e}", duration=time.time() - start_time,
                )

        # 构建初始提示
        tools_desc = get_tools_prompt()
        system_prompt = REACT_SYSTEM_PROMPT.format(tools=tools_desc)

        task_prompt = f"""<原始任务>
{task}
</原始任务>

<已有报告内容>
{context_report[:10000]}
</已有报告内容>

<当前状态>
- 已完成步数: 0/{max_steps}
- 已累积内容: 暂无
- 记忆: 暂无
</当前状态>

请开始第一步：分析已有报告中与任务相关的现有内容，识别扩展方向。
以 JSON 格式输出你的 thought / action / action_input："""

        self._log(f"\n{'='*50}")
        self._log(f"ReAct Agent 启动: {task[:80]}")
        self._log(f"{'='*50}")

        final_content = ""

        for step_num in range(1, max_steps + 1):
            self._log(f"\n--- Step {step_num}/{max_steps} ---")

            # 1. Thought：LLM 推理下一步
            response = self.llm.chat(
                prompt=task_prompt,
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=2048,
            )

            if not response.success:
                self._log(f"  [ERROR] LLM 调用失败: {response.error_msg}")
                break

            parsed = extract_json(response.content)
            if not parsed:
                self._log(f"  [WARN] 无法解析 LLM 输出，尝试从文本提取")
                # 尝试从文本推断
                thought = response.content[:200]
                action = "finish"
                action_input = {"content": response.content}
            else:
                thought = parsed.get("thought", "")
                action = parsed.get("action", "finish")
                action_input = parsed.get("action_input", {})

            self._log(f"  Thought: {thought[:120]}...")
            self._log(f"  Action: {action}")

            # 2. Act：执行工具
            observation = ""
            tool_success = False

            if action == "finish":
                final_content = action_input.get("content", thought)
                self._log(f"  [FINISH] 任务完成")
                # 最后一次 Reflection
                if accumulated_content:
                    critique_input = final_content + accumulated_content
                    crit_result = self._tools["critique"].execute(
                        content=critique_input,
                        criteria="深度/覆盖度/准确性/实用性",
                        context=task,
                    )
                    if crit_result.success:
                        self._log(f"  [Reflection] 最终自检完成")
                break

            else:
                tool = self._tools.get(action)
                if tool:
                    try:
                        result = tool.execute(**action_input)
                        observation = result.content if result.success else f"错误: {result.error}"
                        tool_success = result.success
                        self._log(f"  Observation: {observation[:150]}...")
                    except Exception as e:
                        observation = f"工具执行异常: {str(e)}"
                        tool_success = False
                        self._log(f"  [ERROR] {observation}")
                else:
                    observation = f"未知工具: {action}，可用工具: {list(self._tools.keys())}"
                    tool_success = False

                # 如果 write 成功，累积内容
                if action == "write" and tool_success:
                    accumulated_content += "\n" + observation

            # 3. 记录步骤
            step_record = ReActStep(
                step=step_num,
                thought=thought,
                action=action,
                action_input=action_input,
                observation=observation[:3000],
                tool_success=tool_success,
            )
            steps.append(step_record)
            memory.append(f"Step{step_num}: [{action}] {observation[:300]}")

            # 4. Reflection：定期自检
            if step_num % reflection_interval == 0 and accumulated_content:
                self._log(f"  [Reflection] 触发自检...")
                crit_result = self._tools["critique"].execute(
                    content=accumulated_content,
                    criteria="深度/覆盖度/准确性/实用性",
                    context=f"{task}\n\n{context_report[:2000]}",
                )

                if crit_result.success:
                    step_record.reflection = crit_result.content
                    crit_parsed = extract_json(crit_result.content)
                    if crit_parsed.get("needs_revision"):
                        issues = crit_parsed.get("critical_issues", [])
                        suggestions = crit_parsed.get("supplementary_searches", [])
                        self._log(f"    [ISSUES] {issues[:2]}")
                        if suggestions:
                            memory.append(f"Reflection: 需要补充搜索 {suggestions[:3]}")
                    else:
                        self._log(f"    [OK] 自检通过")

            # 5. 构建下一步提示
            memory_text = "\n".join(memory[-8:])  # 最近 8 条记忆
            accumulated_summary = accumulated_content[:2000] if accumulated_content else "暂无"

            task_prompt = f"""<原始任务>
{task}
</原始任务>

<已有报告内容>
{context_report[:6000]}
</已有报告内容>

<当前状态>
- 已完成步数: {step_num}/{max_steps}
- 已累积内容（摘要）: {accumulated_summary}
- 执行记忆:
{memory_text}
</当前状态>

请继续执行下一步。基于当前进展和记忆，决定下一个行动。
以 JSON 格式输出你的 thought / action / action_input："""

        # 质量评估
        quality_score = 0
        reflection_summary = ""
        if steps:
            # 检查是否有 critique 步骤
            for step in steps:
                if step.action == "critique" and step.tool_success:
                    crit_data = extract_json(step.observation)
                    if crit_data:
                        scores = [
                            crit_data.get("depth_score", 0),
                            crit_data.get("coverage_score", 0),
                            crit_data.get("accuracy_score", 0),
                            crit_data.get("practicality_score", 0),
                        ]
                        quality_score = sum(scores) // len(scores) if scores else 0
                        reflection_summary = json.dumps(crit_data, ensure_ascii=False, indent=2)

        duration = time.time() - start_time

        # 如果循环结束但没有 final_content，用累积内容
        if not final_content and accumulated_content:
            final_content = accumulated_content

        self._log(f"\n{'='*50}")
        self._log(f"ReAct Agent 完成 | 步数: {len(steps)} | 耗时: {duration:.1f}s | 质量: {quality_score}")
        self._log(f"{'='*50}")

        return ReActResult(
            task=task,
            success=bool(final_content),
            final_content=final_content,
            steps=steps,
            reflection_summary=reflection_summary,
            quality_score=quality_score,
            duration=duration,
        )
