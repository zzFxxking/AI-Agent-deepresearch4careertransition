"""
输出格式化层 - 将 ResearchState 转为三轨输出
（主报告 / 八股面试 / 项目推荐）
"""

import json
import re
from datetime import datetime
from typing import Dict, List, Optional

from .user_profile import UserProfile


class OutputFormatter:
    """输出格式化器：将研究结果转换为三轨输出（主报告 / 八股面试 / 项目推荐）"""

    def __init__(self, user_profile: Optional[UserProfile] = None):
        self.user_profile = user_profile

    def format(self, state) -> "FormattedOutput":
        """
        将 ResearchState 转换为三轨输出。
        先尝试从 final_report 中拆分三份报告，再分别解析结构化数据。
        """
        report = state.final_report or ""

        # 拆分三份报告
        reports = self._split_reports(report)

        # 分别构建结构化数据
        structured_main = self._build_structured_output(state, reports["main"])
        structured_interview = self._build_structured_interview(state, reports["interview"])
        structured_projects = self._build_structured_projects(state, reports["projects"])

        # 合并为统一结构化输出
        structured = {
            **structured_main,
            "interview_questions": structured_interview,
            "project_recommendations": structured_projects,
        }

        return FormattedOutput(
            markdown=reports["main"],
            markdown_interview=reports["interview"],
            markdown_projects=reports["projects"],
            json_data=structured,
            metadata={
                "task_id": structured.get("task_id", ""),
                "quality_score": state.quality_score,
                "iterations": state.iteration_count,
                "elapsed_time": f"{state.end_time - state.start_time:.1f}s" if state.end_time else "0s",
            }
        )

    def _split_reports(self, report: str) -> Dict[str, str]:
        """
        从 final_report 中拆分三份报告。
        优先级：① <!-- REPORT:name --> 标记 ② Markdown 一级标题特征匹配 ③ 整份作为主报告
        """
        # 策略1：<!-- REPORT:xxx --> 标记
        pattern = r'<!-- REPORT:(\w+) -->(.*?)<!-- END:\1 -->'
        matches = re.findall(pattern, report, re.DOTALL)

        if matches:
            reports = {k.strip(): v.strip() for k, v in matches}
            reports.setdefault("main", report)
            reports.setdefault("interview", "")
            reports.setdefault("projects", "")
            return reports

        # 策略2：基于 Markdown 一级标题拆分（LLM 常生成的标题模式）
        interview_headers = [
            r'#\s+八股.*?(?:清单|报告|面试)',
            r'#\s+面试.*?(?:八股|准备|问答)',
            r'#\s+知识点.*?(?:清单|总结)',
        ]
        projects_headers = [
            r'#\s+项目推荐.*?(?:清单|报告)?',
            r'#\s+开源项目.*?(?:推荐|清单|报告)?',
        ]
        main_headers = [
            r'#\s+主报告',
            r'#\s+学习路径',
            r'#\s+执行摘要',
        ]

        interview_start = None
        projects_start = None
        main_start = None

        for pattern_str in interview_headers:
            m = re.search(pattern_str, report)
            if m:
                interview_start = m.start()
                break

        for pattern_str in projects_headers:
            m = re.search(pattern_str, report)
            if m:
                projects_start = m.start()
                break

        for pattern_str in main_headers:
            m = re.search(pattern_str, report)
            if m:
                main_start = m.start()
                break

        # 收集所有找到的分割点，按位置排序
        split_points = []
        if interview_start is not None:
            split_points.append(("interview", interview_start))
        if projects_start is not None:
            split_points.append(("projects", projects_start))
        if main_start is not None:
            split_points.append(("main", main_start))

        if len(split_points) >= 2:
            split_points.sort(key=lambda x: x[1])

            result = {"main": "", "interview": "", "projects": ""}
            for i, (section_name, pos) in enumerate(split_points):
                next_pos = split_points[i + 1][1] if i + 1 < len(split_points) else len(report)
                # 向前搜索到最近的 # 标题作为真正起点
                content = report[pos:next_pos].strip()
                result[section_name] = content

            # main 没找到但从其他 header 拆分出来了 → 取第一个 header 之前的内容作为 main
            if not result["main"] and split_points:
                first_pos = split_points[0][1]
                prefix = report[:first_pos].strip()
                if prefix:
                    result["main"] = prefix

            # 确保三个键都存在
            result.setdefault("main", report)
            result.setdefault("interview", "")
            result.setdefault("projects", "")

            # 如果至少 interview 或 projects 其中有一个有内容，返回拆分结果
            if result["interview"] or result["projects"]:
                return result

        # 策略3：整份报告作为主报告（兜底）
        return {
            "main": report,
            "interview": "",
            "projects": "",
        }

    def _build_structured_output(self, state, report: str) -> Dict:
        """构建主报告的结构化 JSON 输出"""
        task_id = f"research_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # 用户画像
        user_profile_data = {}
        if self.user_profile:
            user_profile_data = {
                "target_role": self.user_profile.target_role,
                "time_budget": self.user_profile.time_budget,
                "company_tier": self.user_profile.company_tier,
                "current_level": self.user_profile.current_level,
                "focus_areas": self.user_profile.focus_areas,
                "avoid_areas": self.user_profile.avoid_areas,
            }

        return {
            "task_id": task_id,
            "created_at": datetime.now().isoformat(),
            "user_profile": user_profile_data,
            "learning_path": self._extract_learning_path(report),
            "meta": {
                "quality_score": state.quality_score,
                "iterations": state.iteration_count,
                "elapsed_time": f"{state.end_time - state.start_time:.1f}s" if state.end_time else "0s",
            }
        }

    def _build_structured_interview(self, state, report: str) -> Dict:
        """从八股面试报告中提取结构化数据"""
        categories = self._extract_question_categories(report)
        mock_qa = self._extract_mock_qa(report)
        extended = self._extract_extended_questions(report)

        return {
            "organization": "知识点类别",
            "categories": categories,
            "extended_questions": extended,
            "mock_interview": mock_qa,
        }

    def _build_structured_projects(self, state, report: str) -> List[Dict]:
        """从项目推荐报告中提取结构化数据（严格格式 + fallback）"""
        projects = []
        if not report:
            return projects

        # 严格格式：匹配 ## 项目 标题及其字段
        proj_matches = list(re.finditer(r'(?:^|\n)##\s+项目\s*\d*[:：]?\s*(.+?)(?:\n|$)', report))
        for m in proj_matches:
            proj_name = m.group(1).strip()
            start = m.end()
            next_proj = re.search(r'\n##\s+项目\s*\d*[:：]?', report[start:])
            end = start + next_proj.start() if next_proj else len(report)
            block = report[start:end]

            github_match = re.search(r'\*\*GitHub\*\*[:：]\s*(https?://github\.com/[\w\-]+/[\w\-\.]+)', block)
            github_url = github_match.group(1) if github_match else ""

            stars_match = re.search(r'\*\*Stars\*\*[:：]\s*([\d,]+)', block)
            stars = int(stars_match.group(1).replace(',', '')) if stars_match else 0

            forks_match = re.search(r'\*\*Forks\*\*[:：]\s*([\d,]+)', block)
            forks = int(forks_match.group(1).replace(',', '')) if forks_match else 0

            tech_match = re.search(r'\*\*技术栈\*\*[:：]\s*(.+?)(?:\n|$)', block)
            tech_stack = [t.strip() for t in tech_match.group(1).split(',')] if tech_match else []

            reason_match = re.search(r'\*\*匹配原因\*\*[:：]\s*(.+?)(?:\n|$)', block)
            match_reason = reason_match.group(1).strip() if reason_match else ""

            difficulty_match = re.search(r'\*\*难度分级\*\*[:：]\s*(.+?)(?:\n|$)', block)
            difficulty_level = difficulty_match.group(1).strip() if difficulty_match else ""

            quality_match = re.search(r'\*\*质量门验证\*\*[:：]\s*(.+?)(?:\n|$)', block)
            quality_gate = quality_match.group(1).strip() if quality_match else ""

            desc_match = re.search(r'\*\*完整需求描述\*\*[:：]\s*(.+?)(?:\n|$)', block)
            full_description = desc_match.group(1).strip() if desc_match else ""

            steps_match = re.search(r'\*\*核心实现步骤拆解\*\*[:：](.*?)\n(?=\*\*|##|###|$)', block, re.DOTALL)
            implementation_steps = []
            if steps_match:
                steps_block = steps_match.group(1)
                implementation_steps = [s.strip('- *') for s in re.findall(r'(?:^|\n)\s*[-*]\s*(.+?)(?=\n|$)', steps_block) if s.strip()]

            modules_match = re.search(r'\*\*关键代码模块描述\*\*[:：]\s*(.+?)(?:\n|$)', block)
            key_modules = modules_match.group(1).strip() if modules_match else ""

            mock_qa = self._extract_project_mock_qa(block)

            projects.append({
                "name": proj_name,
                "github_url": github_url,
                "stars": stars,
                "forks": forks,
                "tech_stack": tech_stack,
                "match_reason": match_reason,
                "difficulty_level": difficulty_level,
                "quality_gate": quality_gate,
                "full_description": full_description,
                "implementation_steps": implementation_steps,
                "key_modules": key_modules,
                "mock_qa": mock_qa,
            })

        # Fallback：旧格式（基于 GitHub 链接）
        if not projects:
            github_links = re.findall(r'https?://github\.com/[\w\-]+/[\w\-\.]+', report)
            seen = set()
            for link in github_links[:10]:
                if link in seen:
                    continue
                seen.add(link)
                name = link.split("/")[-1]
                idx = report.find(link)
                context = report[max(0, idx - 150):min(len(report), idx + 400)]
                stars = self._extract_number_after(context, ["stars", "star", "Stars"])
                forks = self._extract_number_after(context, ["forks", "fork", "Forks"])
                tech_stack = []
                tech_pattern = r'`([\w\+\.#]+)`|(?:技术栈|Tech Stack|Stack)[:：]\s*([\w ,\+\.#/]+)'
                tech_matches = re.findall(tech_pattern, context)
                for tm in tech_matches:
                    tech = tm[0] if tm[0] else tm[1]
                    if tech:
                        tech_stack.extend([t.strip() for t in tech.split(",") if t.strip()])
                interview_questions = self._extract_project_interview_questions_old(report, name, link)
                projects.append({
                    "name": name,
                    "github_url": link,
                    "stars": stars,
                    "forks": forks,
                    "tech_stack": list(set(tech_stack))[:8],
                    "match_reason": "报告中提及的项目",
                    "learning_path": "参考报告中的学习路径",
                    "interview_questions": interview_questions,
                })

        return projects

    def _extract_learning_path(self, report: str) -> Dict:
        """从主报告中提取学习路径（支持严格格式 + fallback）"""
        phases = []

        # 严格格式：匹配 ### 阶段名 及其下的 **持续时间** / **核心任务** / **验收标准**
        phase_headers = list(re.finditer(r'\n###\s+(.+?)(?:\n|$)', report))
        for m in phase_headers:
            name = m.group(1).strip()
            start = m.end()
            next_heading = re.search(r'\n(?:#{2,3})\s+', report[start:])
            end = start + next_heading.start() if next_heading else len(report)
            block = report[start:end]

            duration_match = re.search(r'\*\*持续时间\*\*[:：]\s*(.+?)(?:\n|$)', block)
            duration = duration_match.group(1).strip() if duration_match else "待定"

            tasks = []
            tasks_match = re.search(r'\*\*核心任务\*\*[:：](.*?)(?:\n\*\*|\n#{1,3}\s|$)', block, re.DOTALL)
            if tasks_match:
                task_block = tasks_match.group(1)
                tasks = [t.strip('- *') for t in re.findall(r'\n\s*[-*]\s*(.+?)(?:\n|$)', task_block) if t.strip()]

            milestones = []
            milestones_match = re.search(r'\*\*验收标准\*\*[:：](.*?)(?:\n\*\*|\n#{1,3}\s|$)', block, re.DOTALL)
            if milestones_match:
                milestone_block = milestones_match.group(1)
                milestones = [m.strip('- *') for m in re.findall(r'\n\s*[-*]\s*(.+?)(?:\n|$)', milestone_block) if m.strip()]

            phases.append({
                "name": name,
                "duration": duration,
                "tasks": tasks if tasks else ["根据报告制定具体任务"],
                "milestones": milestones if milestones else ["完成阶段目标"],
            })

        # Fallback：旧格式兼容
        if not phases:
            phase_pattern = re.findall(r'[#\*]*\s*(第?[一二三四五12345].*?期|阶段\s*\d?[:：]\s*.*?)(?:\n|$)', report)
            if not phase_pattern:
                phase_pattern = ["基础巩固期", "项目实战期", "面试冲刺期"]
            for i, name in enumerate(phase_pattern[:4]):
                phases.append({
                    "name": name.strip("#* "),
                    "duration": "1个月" if i < len(phase_pattern) - 1 else "剩余时间",
                    "tasks": ["根据报告内容制定具体任务"],
                    "milestones": ["完成阶段目标"]
                })

        return {
            "phases": phases if phases else [
                {"name": "基础巩固期", "duration": "1个月", "tasks": [], "milestones": []},
                {"name": "项目实战期", "duration": "1个月", "tasks": [], "milestones": []},
                {"name": "面试冲刺期", "duration": "1个月", "tasks": [], "milestones": []},
            ]
        }

    def _extract_question_categories(self, report: str) -> List[Dict]:
        """从八股报告中提取知识点类别和问题（严格格式 + fallback）"""
        categories = []
        if not report:
            return []

        # 严格格式：匹配 ## 开头的分类标题（排除 模拟面试）
        cat_matches = list(re.finditer(r'(?:^|\n)##\s+(.+?)(?:\n|$)', report))
        for m in cat_matches:
            cat_name = m.group(1).strip()
            if "模拟面试" in cat_name or "mock" in cat_name.lower():
                continue

            start = m.end()
            next_heading = re.search(r'\n(?:#{1,2})\s+', report[start:])
            end = start + next_heading.start() if next_heading else len(report)
            block = report[start:end]

            questions = self._extract_questions_from_section(block)
            if questions:
                categories.append({
                    "name": cat_name,
                    "questions": questions,
                })

        # Fallback：旧格式兼容
        if not categories:
            heading_pattern = r'(?:^|\n)(#{2,3})\s*(.+?)(?:\n|$)'
            headings = re.findall(heading_pattern, report)
            for level, title in headings:
                title_clean = title.strip()
                if any(k in title_clean for k in ["八股", "面试", "问题", "知识点", "模拟", "Q&A",
                                                    "Transformer", "RAG", "Agent", "MCP", "RLHF",
                                                    "Attention", "部署", "优化", "向量", "检索"]):
                    idx = report.find(title)
                    if idx == -1:
                        continue
                    section = report[idx:idx + 3000]
                    questions = self._extract_questions_from_section_old(section)
                    categories.append({
                        "name": title_clean,
                        "questions": questions,
                    })

        if not categories:
            return []

        return categories

    def _extract_questions_from_section(self, section: str) -> List[Dict]:
        """从严格格式段落中提取问题列表（基于 ### Q 标记）"""
        questions = []
        q_matches = list(re.finditer(r'(?:^|\n)###\s*Q\d*[:：]?\s*(.+?)(?:\n|$)', section))

        for m in q_matches:
            question_text = m.group(1).strip()
            if len(question_text) < 5:
                continue
            start = m.end()
            next_q = re.search(r'\n###\s*Q\d*[:：]?', section[start:])
            end = start + next_q.start() if next_q else len(section)
            block = section[start:end]

            focus_match = re.search(r'\*\*考察点\*\*[:：]\s*(.+?)(?:\n|$)', block)
            focus = focus_match.group(1).strip() if focus_match else ""

            answer_match = re.search(r'\*\*参考答案要点\*\*[:：]\s*(.+?)(?:\n|$)', block)
            answer = answer_match.group(1).strip() if answer_match else ""

            source_match = re.search(r'\*\*来源\*\*[:：]\s*(.+?)(?:\n|$)', block)
            source = source_match.group(1).strip() if source_match else ""

            freq_match = re.search(r'\*\*频率\*\*[:：]\s*(.+?)(?:\n|$)', block)
            frequency = freq_match.group(1).strip() if freq_match else "中"

            questions.append({
                "question": question_text,
                "answer_summary": answer,
                "source": source,
                "frequency": frequency,
                "focus_area": focus,
            })

        return questions

    def _extract_questions_from_section_old(self, section: str) -> List[Dict]:
        """旧格式兼容：从文本段落中提取问题列表"""
        questions = []
        q_pattern = r'(?:^|\n)(?:\d+\.\s*|Q\d+[:：]\s*|[-*]\s*)(.+?)(?=\n(?:\d+\.\s*|Q\d+[:：]\s*|[-*]\s*|#{1,3}\s|$))'
        matches = re.findall(q_pattern, section, re.DOTALL)

        for m in matches[:10]:
            text = m.strip()
            if len(text) < 5:
                continue
            if len(text) > 300:
                text = text[:300] + "..."
            questions.append({
                "question": text,
                "answer_summary": "",
                "frequency": "高",
            })

        return questions

    def _extract_mock_qa(self, report: str) -> List[Dict]:
        """从八股报告中提取模拟面试 Q&A（严格格式 + fallback）"""
        qa_list = []
        if not report:
            return qa_list

        # 严格格式：先找到 ## 模拟面试 区块，再匹配 ### MQ
        mock_section_match = re.search(r'##\s*模拟面试\s*\n(.*?)(?=\n##\s+|$)', report, re.DOTALL)
        if not mock_section_match:
            # 尝试匹配旧格式
            qa_pattern = r'(?:^|\n)(?:\d+\.\s*|[-*]\s*)\*\*(.+?)\*\*(.+?)(?=\n(?:\d+\.\s*|[-*]\s*)\*\*|$)'
            matches = re.findall(qa_pattern, report, re.DOTALL)
            for question, answer in matches[:15]:
                qa_list.append({
                    "question": question.strip(),
                    "key_points": answer.strip()[:500],
                    "difficulty": self._infer_difficulty(question),
                })
            return qa_list

        section = mock_section_match.group(1) or ""
        mq_matches = list(re.finditer(r'(?:^|\n)###\s*MQ\d*[:：]?\s*(.+?)(?:\n|$)', section))

        for m in mq_matches:
            question_text = m.group(1).strip()
            if len(question_text) < 5:
                continue
            start = m.end()
            next_mq = re.search(r'\n###\s*MQ\d*[:：]?', section[start:])
            end = start + next_mq.start() if next_mq else len(section)
            block = section[start:end]

            focus_match = re.search(r'\*\*考察点\*\*[:：]\s*(.+?)(?:\n|$)', block)
            focus = focus_match.group(1).strip() if focus_match else ""

            answer_match = re.search(r'\*\*参考答案要点\*\*[:：]\s*(.+?)(?:\n|$)', block)
            answer = answer_match.group(1).strip() if answer_match else ""

            followup_match = re.search(r'\*\*追问方向\*\*[:：]\s*(.+?)(?:\n|$)', block)
            followups = []
            if followup_match:
                followups = [f.strip() for f in followup_match.group(1).split('；') if f.strip()]

            qa_list.append({
                "question": question_text,
                "focus_area": focus,
                "answer_outline": answer,
                "follow_ups": followups,
                "difficulty": self._infer_difficulty(question_text),
            })

        return qa_list

    def _extract_extended_questions(self, report: str) -> List[Dict]:
        """提取扩展问题（EQ 前缀）"""
        questions = []
        if not report:
            return questions

        eq_matches = list(re.finditer(r'(?:^|\n)###\s*EQ\d*[:：]?\s*(.+?)(?:\n|$)', report))
        for m in eq_matches:
            question_text = m.group(1).strip()
            if len(question_text) < 5:
                continue
            start = m.end()
            next_eq = re.search(r'\n###\s*EQ\d*[:：]?', report[start:])
            end = start + next_eq.start() if next_eq else len(report)
            block = report[start:end]

            focus_match = re.search(r'\*\*考察点\*\*[:：]\s*(.+?)(?:\n|$)', block)
            focus = focus_match.group(1).strip() if focus_match else ""

            answer_match = re.search(r'\*\*参考答案要点\*\*[:：]\s*(.+?)(?:\n|$)', block)
            answer = answer_match.group(1).strip() if answer_match else ""

            project_match = re.search(r'\*\*关联项目\*\*[:：]\s*(.+?)(?:\n|$)', block)
            related_project = project_match.group(1).strip() if project_match else ""

            background_match = re.search(r'\*\*问题背景\*\*[:：]\s*(.+?)(?:\n|$)', block)
            background = background_match.group(1).strip() if background_match else ""

            diff_match = re.search(r'\*\*难度标签\*\*[:：]\s*(.+?)(?:\n|$)', block)
            difficulty = diff_match.group(1).strip() if diff_match else "进阶"

            questions.append({
                "question": question_text,
                "answer_summary": answer,
                "focus_area": focus,
                "related_project": related_project,
                "background": background,
                "difficulty": difficulty,
            })

        return questions

    def _extract_project_mock_qa(self, block: str) -> List[Dict]:
        """从项目区块中提取模拟面试 Q&A（MQ 前缀）"""
        qa_list = []
        mq_matches = list(re.finditer(r'(?:^|\n)####\s*MQ\d*[:：]?\s*(.+?)(?:\n|$)', block))
        for m in mq_matches:
            question_text = m.group(1).strip()
            if len(question_text) < 5:
                continue
            start = m.end()
            next_mq = re.search(r'\n####\s*MQ\d*[:：]?', block[start:])
            end = start + next_mq.start() if next_mq else len(block)
            qa_block = block[start:end]

            focus_match = re.search(r'\*\*考察点\*\*[:：]\s*(.+?)(?:\n|$)', qa_block)
            focus = focus_match.group(1).strip() if focus_match else ""

            answer_match = re.search(r'\*\*参考答案框架\*\*[:：]\s*(.+?)(?:\n|$)', qa_block)
            answer = answer_match.group(1).strip() if answer_match else ""

            followup_match = re.search(r'\*\*追问方向\*\*[:：]\s*(.+?)(?:\n|$)', qa_block)
            followups = []
            if followup_match:
                followups = [f.strip() for f in followup_match.group(1).split('；') if f.strip()]

            qa_list.append({
                "question": question_text,
                "focus_area": focus,
                "answer_outline": answer,
                "follow_ups": followups,
                "difficulty": self._infer_difficulty(question_text),
            })

        return qa_list

    def _extract_project_interview_questions_old(self, report: str, project_name: str, link: str) -> List[str]:
        """提取与特定项目关联的面试题"""
        questions = []
        if not report:
            return questions

        # 在项目名称或链接附近查找面试题
        idx = report.find(link) if link in report else report.find(project_name)
        if idx == -1:
            return questions

        context = report[max(0, idx - 200):min(len(report), idx + 1500)]
        # 查找 "面试题"、"可能的问题" 等关键词后的列表
        q_pattern = r'(?:面试题|关联面试|可能的问题|追问)[:：]?(.*?)(?=\n\n|\n#{1,3}\s|$)'
        block = re.search(q_pattern, context, re.DOTALL)
        if block:
            lines = re.findall(r'(?:\d+\.\s*|[-*]\s*)(.+?)(?:\n|$)', block.group(1))
            questions = [l.strip() for l in lines if len(l.strip()) > 5][:5]

        return questions

    def _extract_number_after(self, text: str, keywords: List[str]) -> int:
        """在文本中查找关键词后的数字"""
        for kw in keywords:
            pattern = rf'{kw}[:\s]*([\d,\.]+)[kK]?'
            m = re.search(pattern, text)
            if m:
                num_str = m.group(1).replace(",", "")
                try:
                    val = float(num_str)
                    # 处理 3.2k 这种格式
                    if 'k' in text[m.end()-2:m.end()].lower():
                        val *= 1000
                    return int(val)
                except ValueError:
                    continue
        return 0

    def _infer_difficulty(self, question: str) -> str:
        """根据问题内容推断难度"""
        q_lower = question.lower()
        if any(k in q_lower for k in ["原理", "推导", "证明", "数学", "公式", "复杂度", "优化", "设计", "架构"]):
            return "压轴"
        if any(k in q_lower for k in ["区别", "比较", "为什么", "如何实现", "机制"]):
            return "进阶"
        return "基础"


class FormattedOutput:
    """三轨输出"""

    def __init__(self, markdown: str, markdown_interview: str, markdown_projects: str,
                 json_data: Dict, metadata: Dict):
        self.markdown = markdown
        self.markdown_interview = markdown_interview
        self.markdown_projects = markdown_projects
        self.json_data = json_data
        self.metadata = metadata
