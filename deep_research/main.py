"""
主程序 - Deep Research Agent 入口

提供简洁的 API 接口，用于执行深度研究任务。
"""

import os
import json
import time
from datetime import datetime
from typing import Optional, Callable

from .orchestrator import Orchestrator, ResearchState
from .workers import search_worker_factory, WorkerFactory
from .config import AGENT_CONFIG, OUTPUT_CONFIG
from .user_profile import UserProfile, UserProfileExtractor
from .output_formatter import OutputFormatter, FormattedOutput
from .memory import AgentMemory


# ==================== 控制台输出格式化 ====================

class ConsoleReporter:
    """控制台进度报告器"""

    # ANSI 颜色码
    COLORS = {
        "reset": "\033[0m",
        "bold": "\033[1m",
        "dim": "\033[2m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "cyan": "\033[96m",
        "red": "\033[91m",
    }

    STAGE_ICONS = {
        "decomposing": "[搜索]",
        "decomposed": "[清单]",
        "dispatching": "[启动]",
        "worker_started": "[开始]",
        "worker_completed": "[完成]",
        "worker_failed": "[失败]",
        "synthesizing": "[编写]",
        "synthesized": "[报告]",
        "quality_checking": "[检查]",
        "quality_checked": "[评分]",
        "completed": "[完成]",
        "failed": "[错误]",
        "revision_needed": "[修订]",
        # 迭代优化相关
        "iteration_start": "[迭代]",
        "iteration_evaluated": "[评估]",
        "iteration_continue": "[继续]",
        "iteration_end": "[结束]",
        "quality_passed": "[通过]",
        "analyzing_gaps": "[分析]",
        "gaps_analyzed": "[差距]",
        "dispatching_supplementary": "[补充]",
        "supplementary_worker_started": "[开始]",
        "supplementary_worker_completed": "[完成]",
        "supplementary_worker_failed": "[失败]",
        "refining_report": "[优化]",
        "report_refined": "[报告]",
        "no_supplementary_tasks": "[信息]",
    }

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.start_time = time.time()

    def _color(self, text: str, color: str) -> str:
        """添加颜色"""
        return f"{self.COLORS.get(color, '')}{text}{self.COLORS['reset']}"

    def _elapsed(self) -> str:
        """获取已用时间"""
        elapsed = time.time() - self.start_time
        return f"[{elapsed:.1f}s]"

    def report(self, stage: str, data: dict):
        """报告进度"""
        if not self.verbose:
            return

        icon = self.STAGE_ICONS.get(stage, "[标记]")
        elapsed = self._elapsed()

        if stage == "decomposing":
            print(f"\n{icon} {self._color('正在分析任务...', 'cyan')}")

        elif stage == "decomposed":
            count = data.get("subtask_count", 0)
            print(f"{icon} {self._color(f'任务拆解完成，共 {count} 个子任务', 'green')}")
            for st in data.get("subtasks", []):
                print(f"   - {st['name']}")

        elif stage == "dispatching":
            count = data.get("worker_count", 0)
            parallel = data.get("parallel_workers", count)
            print(f"\n{icon} {self._color(f'共 {count} 个子任务，并行 {parallel} 个 Workers...', 'cyan')}")

        elif stage == "worker_started":
            name = data.get("task_name", "")
            print(f"   {icon} {self._color(f'[开始] {name}', 'dim')}")

        elif stage == "worker_completed":
            name = data.get("task_name", "")
            print(f"   {icon} {self._color(f'[完成] {name}', 'green')} {elapsed}")

        elif stage == "worker_failed":
            name = data.get("task_name", "")
            error = data.get("error", "")
            print(f"   {icon} {self._color(f'[失败] {name}: {error}', 'red')}")

        elif stage == "synthesizing":
            print(f"\n{icon} {self._color('正在生成研究报告...', 'cyan')}")

        elif stage == "synthesized":
            length = data.get("report_length", 0)
            print(f"{icon} {self._color(f'报告生成完成 ({length} 字符)', 'green')}")

        elif stage == "quality_checking":
            print(f"\n{icon} {self._color('正在进行质量检查...', 'cyan')}")

        elif stage == "quality_checked":
            score = data.get("score", 0)
            color = "green" if score >= 80 else "yellow" if score >= 60 else "red"
            print(f"{icon} 质量评分: {self._color(f'{score}分', color)}")

        elif stage == "completed":
            duration = data.get("duration", 0)
            score = data.get("quality_score", 0)
            iterations = data.get("iterations", 1)
            print(f"\n{icon} {self._color('研究完成!', 'bold')}")
            print(f"   [时钟] 总耗时: {duration:.1f} 秒")
            print(f"   [图表] 质量评分: {score} 分")
            print(f"   [循环] 迭代次数: {iterations} 次")

        elif stage == "failed":
            error = data.get("error", "")
            print(f"\n{icon} {self._color(f'研究失败: {error}', 'red')}")

        # ========== 迭代优化相关事件 ==========
        elif stage == "iteration_start":
            iteration = data.get("iteration", 1)
            max_iter = data.get("max_iterations", 5)
            print(f"\n{icon} {self._color(f'━━━ 第 {iteration}/{max_iter} 次迭代 ━━━', 'magenta')}")

        elif stage == "iteration_evaluated":
            iteration = data.get("iteration", 1)
            score = data.get("score", 0)
            threshold = data.get("threshold", 80)
            passed = data.get("passed", False)
            status = "通过" if passed else "未通过"
            color = "green" if passed else "yellow"
            print(f"   {icon} 质量评分: {self._color(f'{score}分', color)} (阈值:{threshold}) [{status}]")

        elif stage == "quality_passed":
            score = data.get("score", 0)
            print(f"\n{icon} {self._color(f'质量检查通过！最终评分: {score}分', 'green')}")

        elif stage == "iteration_continue":
            reason = data.get("reason", "")
            print(f"   {icon} {self._color(f'继续优化: {reason}', 'yellow')}")

        elif stage == "analyzing_gaps":
            print(f"   {icon} {self._color('正在分析报告差距...', 'cyan')}")

        elif stage == "gaps_analyzed":
            gap_count = data.get("gap_count", 0)
            task_count = data.get("task_count", 0)
            print(f"   {icon} 识别到 {gap_count} 个差距，生成 {task_count} 个补充任务")

        elif stage == "dispatching_supplementary":
            task_count = data.get("task_count", 0)
            print(f"   {icon} {self._color(f'分发 {task_count} 个补充研究任务...', 'cyan')}")

        elif stage == "supplementary_worker_started":
            name = data.get("task_name", "")
            print(f"      {icon} {self._color(f'[补充] {name}', 'dim')}")

        elif stage == "supplementary_worker_completed":
            name = data.get("task_name", "")
            print(f"      {icon} {self._color(f'[完成] {name}', 'green')} {elapsed}")

        elif stage == "supplementary_worker_failed":
            name = data.get("task_name", "")
            error = data.get("error", "")
            print(f"      {icon} {self._color(f'[失败] {name}: {error}', 'red')}")

        elif stage == "refining_report":
            print(f"   {icon} {self._color('正在修订报告...', 'cyan')}")

        elif stage == "report_refined":
            length = data.get("new_length", 0)
            print(f"   {icon} {self._color(f'报告修订完成 ({length} 字符)', 'green')}")

        elif stage == "no_supplementary_tasks":
            print(f"   {icon} {self._color('无需补充研究', 'dim')}")

        elif stage == "diminishing_returns_stop":
            reason = data.get("reasoning", "")
            print(f"   {icon} {self._color('收益递减检测触发提前终止', 'yellow')}")
            if reason:
                print(f"      原因: {reason}")

        elif stage == "gap_analysis_stop":
            reason = data.get("reasoning", "")
            print(f"   {icon} {self._color('差距分析建议停止迭代', 'yellow')}")
            if reason:
                print(f"      原因: {reason}")

        elif stage == "iteration_end":
            pass  # 静默结束


# ==================== Deep Research Agent ====================

class DeepResearchAgent:
    """
    Deep Research Agent - AI求职助手入口

    基于 Orchestrator-Workers 架构的AI求职准备系统。

    使用示例:
        agent = DeepResearchAgent()
        result = agent.research(
            "我是数学专业研一，想找大模型应用开发实习",
            target_role="大模型应用开发工程师",
            time_budget="3个月",
        )
        print(result.markdown)
    """

    def __init__(
        self,
        verbose: bool = True,
        save_output: bool = True,
        output_dir: str = None,
        memory: Optional[AgentMemory] = None,
    ):
        """
        初始化 Deep Research Agent

        参数:
            verbose: 是否显示详细进度信息
            save_output: 是否保存输出文件
            output_dir: 输出目录路径
            memory: AgentMemory 实例（可选）
        """
        self.verbose = verbose
        self.save_output = save_output
        self.output_dir = output_dir or OUTPUT_CONFIG["output_dir"]
        self.reporter = ConsoleReporter(verbose=verbose)
        self.memory = memory or AgentMemory()
        self.profile_extractor = UserProfileExtractor()

    def research(
        self,
        task: str,
        max_workers: int = None,
        callback: Callable[[str, dict], None] = None,
        user_profile: Optional[UserProfile] = None,
        **profile_fields,
    ) -> FormattedOutput:
        """
        执行深度研究任务（求职场景）

        参数:
            task: 用户原始描述
            max_workers: 最大并行 Worker 数（可选）
            callback: 自定义进度回调函数（可选）
            user_profile: 预解析的用户画像（如未提供则自动提取）
            **profile_fields: 结构化字段（target_role, time_budget等）

        返回:
            FormattedOutput: 包含markdown报告和结构化JSON
        """
        # 初始化 MCP（首次调用时连接外部工具服务）
        from .tools import init_mcp_from_config
        init_mcp_from_config()

        # 提取用户画像
        if user_profile is None:
            user_profile = self.profile_extractor.extract(task, **profile_fields)

        # 保存用户画像到记忆
        profile_id = self.memory.get_or_create_profile(user_profile)

        # 打印欢迎信息
        if self.verbose:
            self._print_header(task, user_profile)

        # 创建进度回调
        def on_progress(stage: str, data: dict):
            self.reporter.report(stage, data)
            if callback:
                callback(stage, data)

        # 创建 Orchestrator（传入 memory 和 profile_id 以支持记忆机制）
        orchestrator = Orchestrator(
            worker_factory=search_worker_factory,
            max_workers=max_workers or AGENT_CONFIG["max_workers"],
            on_progress=on_progress,
            user_profile=user_profile.model_dump(),
            memory=self.memory,
            profile_id=profile_id,
        )

        # 执行研究
        state = orchestrator.run(task, user_profile=user_profile.model_dump())

        # 格式化输出
        formatter = OutputFormatter(user_profile=user_profile)
        formatted_output = formatter.format(state)
        state.structured_output = formatted_output.json_data

        # 保存输出
        if self.save_output and state.status == "completed":
            self._save_output(state, formatted_output)

        # 保存研究记录到记忆
        self.memory.save_research_record(profile_id, {
            "task": task,
            "quality_score": state.quality_score,
            "timestamp": datetime.now().isoformat(),
            "output_summary": formatted_output.json_data.get("learning_path", {}),
        })

        # 打印结果
        if self.verbose:
            self._print_footer(state)

        return formatted_output

    def research_stream(
        self,
        task: str,
        max_workers: int = None,
        user_profile: Optional[UserProfile] = None,
        **profile_fields,
    ):
        """
        流式执行深度研究任务（生成器模式）

        参数:
            task: 用户原始描述
            max_workers: 最大并行 Worker 数
            user_profile: 预解析的用户画像
            **profile_fields: 结构化字段

        Yields:
            tuple: (stage, data) 进度信息
        """
        if user_profile is None:
            user_profile = self.profile_extractor.extract(task, **profile_fields)

        progress_events = []

        def collect_progress(stage: str, data: dict):
            progress_events.append((stage, data))

        # 创建 Orchestrator
        orchestrator = Orchestrator(
            worker_factory=search_worker_factory,
            max_workers=max_workers or AGENT_CONFIG["max_workers"],
            on_progress=collect_progress,
            user_profile=user_profile.model_dump(),
        )

        # 执行研究
        state = orchestrator.run(task, user_profile=user_profile.model_dump())

        # 格式化输出
        formatter = OutputFormatter(user_profile=user_profile)
        formatted_output = formatter.format(state)

        # 输出所有进度事件
        for stage, data in progress_events:
            yield ("progress", {"stage": stage, "data": data})

        # 输出最终结果
        yield ("result", {
            "report": formatted_output.markdown,
            "json_data": formatted_output.json_data,
            "quality_score": state.quality_score,
            "status": state.status,
            "duration": state.end_time - state.start_time,
        })

    def _print_header(self, task: str, user_profile: UserProfile):
        """打印研究开始信息"""
        print("\n" + "=" * 60)
        print("[实验] AI求职助手 - Deep Research Agent")
        print("=" * 60)
        print(f"\n[任务] 求职目标: {task}")
        print(f"[岗位] 目标岗位: {user_profile.target_role}")
        print(f"[时间] 准备周期: {user_profile.time_budget}")
        print(f"[层级] 目标公司: {user_profile.company_tier}")
        print(f"[时间] 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 60)

    def _print_footer(self, state: ResearchState):
        """打印研究结束信息"""
        print("\n" + "=" * 60)
        if state.status == "completed":
            print("[通过] 面试准备报告已生成")
            if self.save_output:
                print(f"[目录] 输出目录: {self.output_dir}")
                print(f"[文件] 主报告 + 八股面试 + 项目推荐（各含 Markdown + JSON）")
        else:
            print(f"[失败] 生成失败: {state.error_msg}")
        print("=" * 60 + "\n")

    def _save_output(self, state: ResearchState, formatted_output: FormattedOutput):
        """保存三轨输出文件（3 份 Markdown + 合并 JSON + 元数据）"""
        # 创建输出目录
        os.makedirs(self.output_dir, exist_ok=True)

        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"research_{timestamp}"

        # 保存主报告 Markdown
        md_main_path = os.path.join(self.output_dir, f"{base_name}_main.md")
        with open(md_main_path, "w", encoding="utf-8") as f:
            f.write(formatted_output.markdown)

        # 保存八股面试 Markdown
        md_interview_path = os.path.join(self.output_dir, f"{base_name}_interview.md")
        with open(md_interview_path, "w", encoding="utf-8") as f:
            f.write(formatted_output.markdown_interview)

        # 保存项目推荐 Markdown
        md_projects_path = os.path.join(self.output_dir, f"{base_name}_projects.md")
        with open(md_projects_path, "w", encoding="utf-8") as f:
            f.write(formatted_output.markdown_projects)

        # 保存结构化 JSON 输出
        json_path = os.path.join(self.output_dir, f"{base_name}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(formatted_output.json_data, f, ensure_ascii=False, indent=2)

        # 保存元数据（兼容旧版）
        meta_path = os.path.join(self.output_dir, f"{base_name}_meta.json")
        meta = {
            "original_task": state.original_task,
            "status": state.status,
            "quality_score": state.quality_score,
            "duration": state.end_time - state.start_time,
            "timestamp": timestamp,
            "task_plan": {
                "understanding": state.task_plan.task_understanding if state.task_plan else {},
                "subtask_count": len(state.task_plan.subtasks) if state.task_plan else 0,
                "report_structure": state.task_plan.report_structure if state.task_plan else {},
            },
            "worker_results_count": len(state.worker_results),
            "iteration_count": state.iteration_count,
            "iteration_history": [
                {
                    "iteration": record.iteration,
                    "quality_score": record.quality_score,
                    "report_length": len(record.report),
                    "gap_count": len(record.gap_analysis.get("missing_aspects", [])) if record.gap_analysis else 0,
                    "supplementary_task_count": len(record.supplementary_results),
                }
                for record in state.iteration_history
            ],
            "structured_output": state.structured_output,
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)


# ==================== CLI 入口 ====================

def main():
    """命令行入口 — 支持 research / react 两种模式"""
    import argparse

    parser = argparse.ArgumentParser(
        description="AI求职助手 - Deep Research Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 广度模式：一键生成三份面试准备报告
  python -m deep_research "我是数学专业研一，想找大模型应用开发实习" --target-role "大模型应用开发工程师" --time-budget "3个月"
  python -m deep_research "准备算法工程师面试" --workers 4 --company-tier "大厂"

  # 深度模式：基于已有报告进行 ReAct-Reflection 深度扩展
  python -m deep_research react --mode interview --task "扩展RLHF八股到15道" --context-report research_output/xxx_interview.md
  python -m deep_research react --mode project --task "深入分析Dify项目" --context-report research_output/xxx_projects.md
  python -m deep_research react --mode qa --task "Transformer的KV Cache工作原理" --context-report research_output/xxx_main.md
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="运行模式")

    # ========== 子命令1: research（默认/广度模式） ==========
    research_parser = subparsers.add_parser("research", help="广度模式：一键生成三份面试准备报告")
    _add_research_args(research_parser)

    # ========== 子命令2: react（深度模式） ==========
    react_parser = subparsers.add_parser("react", help="深度模式：ReAct-Reflection 对已有报告进行深度扩展")
    _add_react_args(react_parser)

    # 兼容旧用法：直接传 task 参数（默认 research 模式）
    parser.add_argument(
        "task", nargs="?", type=str, default="",
        help="求职需求描述（兼容旧用法）",
    )
    _add_research_args(parser)

    args = parser.parse_args()

    # 判断模式
    if args.command == "react":
        _run_react_mode(args)
    else:
        _run_research_mode(args, parser)


def _add_research_args(p):
    """为 research 模式添加参数"""
    p.add_argument("--target-role", type=str, default="", help="目标岗位")
    p.add_argument("--time-budget", type=str, default="", help="可用准备时间")
    p.add_argument("--company-tier", type=str, default="", help="目标公司层级")
    p.add_argument("--current-level", type=str, default="", help="当前水平描述")
    p.add_argument("--focus-areas", type=str, default="", help="重点加强方向（逗号分隔）")
    p.add_argument("--avoid-areas", type=str, default="", help="排除方向（逗号分隔）")
    p.add_argument("--workers", "-w", type=int, default=None, help="最大并行 Worker 数")
    p.add_argument("--output", "-o", type=str, default=None, help="输出目录路径")
    p.add_argument("--quiet", "-q", action="store_true", help="安静模式")
    p.add_argument("--no-save", action="store_true", help="不保存输出文件")


def _add_react_args(p):
    """为 react 模式添加参数"""
    p.add_argument("--mode", type=str, required=True,
                   choices=["interview", "project", "qa"],
                   help="扩展模式: interview(八股扩展) / project(项目分析) / qa(追问)")
    p.add_argument("--task", type=str, required=True, help="深度研究任务描述")
    p.add_argument("--context-report", type=str, required=True, help="已有报告文件路径（.md）")
    p.add_argument("--max-steps", type=int, default=8, help="最大 ReAct 步数 (默认8)")
    p.add_argument("--output", "-o", type=str, default="./research_output", help="输出目录")
    p.add_argument("--quiet", "-q", action="store_true", help="安静模式")


def _run_research_mode(args, parser):
    """执行广度模式（Orchestrator-Workers）"""
    if not args.task:
        parser.print_help()
        return

    focus_areas = [x.strip() for x in args.focus_areas.split(",") if x.strip()] if args.focus_areas else []
    avoid_areas = [x.strip() for x in args.avoid_areas.split(",") if x.strip()] if args.avoid_areas else []

    agent = DeepResearchAgent(
        verbose=not args.quiet,
        save_output=not args.no_save,
        output_dir=args.output,
    )

    result = agent.research(
        task=args.task,
        max_workers=args.workers,
        target_role=args.target_role,
        time_budget=args.time_budget,
        company_tier=args.company_tier,
        current_level=args.current_level,
        focus_areas=focus_areas,
        avoid_areas=avoid_areas,
    )

    if args.quiet:
        print(result.markdown)


def _run_react_mode(args):
    """执行深度模式（ReAct-Reflection）"""
    import os
    from datetime import datetime

    mode_labels = {
        "interview": "八股扩展",
        "project": "项目分析",
        "qa": "追问",
    }

    print(f"\n{'='*50}")
    print(f"ReAct-Reflection 深度扩展模式")
    print(f"  模式: {mode_labels.get(args.mode, args.mode)}")
    print(f"  任务: {args.task}")
    print(f"  上下文: {args.context_report}")
    print(f"  最大步数: {args.max_steps}")
    print(f"{'='*50}\n")

    from .react_agent import ReActReflectionAgent

    agent = ReActReflectionAgent(verbose=not args.quiet)

    result = agent.run(
        task=args.task,
        context_report_path=args.context_report,
        max_steps=args.max_steps,
        reflection_interval=2,
    )

    print(f"\n{'='*50}")
    print(f"ReAct-Reflection 完成")
    print(f"  成功: {result.success}")
    print(f"  步数: {len(result.steps)}")
    print(f"  质量评分: {result.quality_score}")
    print(f"  耗时: {result.duration:.1f}s")
    print(f"{'='*50}")

    if result.success:
        # 保存结果
        os.makedirs(args.output, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(args.output, f"react_{timestamp}_{args.mode}.md")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# ReAct-Reflection 深度扩展\n\n")
            f.write(f"**模式**: {mode_labels.get(args.mode, args.mode)}\n")
            f.write(f"**任务**: {args.task}\n")
            f.write(f"**上下文**: {args.context_report}\n")
            f.write(f"**步数**: {len(result.steps)} | **质量**: {result.quality_score} | **耗时**: {result.duration:.1f}s\n\n")
            f.write("---\n\n")
            f.write(result.final_content)
            f.write("\n\n---\n\n## 推理链\n\n")
            for step in result.steps:
                f.write(f"### Step {step.step}: {step.action}\n")
                f.write(f"- **Thought**: {step.thought[:300]}\n")
                f.write(f"- **Observation**: {step.observation[:300]}\n")
                if step.reflection:
                    f.write(f"- **Reflection**: {step.reflection[:200]}\n")
                f.write("\n")

        print(f"\n结果已保存至: {output_path}")

        if args.quiet:
            print(result.final_content)
    else:
        print(f"\n错误: {result.error}")


if __name__ == "__main__":
    main()
