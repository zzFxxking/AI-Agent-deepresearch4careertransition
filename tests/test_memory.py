"""
AgentMemory 单元测试
验证薄弱点提取、记忆上下文生成和持久化
"""

import sys
import json
import tempfile
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deep_research.memory import AgentMemory
from deep_research.user_profile import UserProfile


MOCK_CRITIC_RESULT = {
    "success": True,
    "project_review": {
        "toy_projects": [
            {"name": "miniMind", "reason": "纯教学demo，仅有200 stars"}
        ],
        "quality_projects": [{"name": "RAGFlow", "reason": "生产级RAG系统"}],
        "score": 65,
    },
    "interview_coverage": {
        "missing_topics": ["RAG", "Agent架构", "MCP协议"],
        "focus_areas_coverage": {
            "covered": ["RAG"],
            "missing": ["Agent框架", "MCP协议"]
        },
        "coverage_score": 40,
    },
    "learning_path_review": {
        "difficulty_match": "too_hard",
        "difficulty_issues": ["阶段2任务过重，不适合当前水平"],
        "time_realistic": False,
        "time_issues": ["3个月完成6周项目实战期不现实"],
        "score": 55,
    },
    "overall_review": {
        "score": 62,
        "critical_issues": [
            "混入了toy项目miniMind",
            "八股覆盖度严重不足"
        ],
        "revision_priority": "high",
    }
}


def test_extract_weak_points():
    """测试从Critic结果提取薄弱点"""
    print(f"\n{'='*60}")
    print("[测试] AgentMemory - 薄弱点提取")
    print(f"{'='*60}")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "memory.db")
        memory = AgentMemory(db_path=db_path)
        profile_id = "test_001"

        weak_points = memory.extract_and_save_weak_points(profile_id, MOCK_CRITIC_RESULT)

        assert len(weak_points) > 0, "应提取到薄弱点"
        assert any("miniMind" in wp for wp in weak_points), "应包含toy项目薄弱点"
        assert any("RAG" in wp for wp in weak_points), "应包含八股覆盖薄弱点"
        assert any("Agent框架" in wp for wp in weak_points), "应包含重点方向薄弱点"
        assert any("难度" in wp for wp in weak_points), "应包含学习路径难度薄弱点"
        assert any("时间" in wp for wp in weak_points), "应包含学习路径时间薄弱点"
        assert any("关键问题" in wp for wp in weak_points), "应包含整体关键问题"

        print(f"[OK] 提取到 {len(weak_points)} 个薄弱点")
        for wp in weak_points:
            print(f"   - {wp}")

        # 验证保存后能从文件加载
        memory2 = AgentMemory(db_path=db_path)
        loaded = memory2.get_weak_points(profile_id)
        assert len(loaded) == len(weak_points), "加载的薄弱点应与保存的一致"
        print(f"[OK] 持久化加载成功: {len(loaded)} 个薄弱点")

        memory.close()
        memory2.close()

    print("[通过] AgentMemory - 薄弱点提取")
    return True


def test_get_memory_context():
    """测试记忆上下文生成"""
    print(f"\n{'='*60}")
    print("[测试] AgentMemory - 记忆上下文生成")
    print(f"{'='*60}")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "memory.db")
        memory = AgentMemory(db_path=db_path)
        profile_id = "test_002"

        # 先保存一些数据
        memory.extract_and_save_weak_points(profile_id, MOCK_CRITIC_RESULT)
        memory.save_research_record(profile_id, {
            "task": "准备大模型应用开发面试",
            "quality_score": 62,
            "timestamp": "2026-05-12T10:00:00",
            "output_summary": {"phases": [{"name": "基础巩固期"}]},
        })

        context = memory.get_memory_context(profile_id, max_records=3)
        assert "历史薄弱点" in context, "上下文应包含薄弱点标题"
        assert "近期研究记录" in context, "上下文应包含近期记录标题"
        assert "miniMind" in context, "上下文应包含具体薄弱点"
        assert "准备大模型应用开发面试" in context, "上下文应包含任务描述"

        print(f"[OK] 记忆上下文生成成功 ({len(context)} 字符)")
        print(context)

        # 无记录时应返回空字符串
        empty_context = memory.get_memory_context("unknown_id")
        assert empty_context == "", "未知profile_id应返回空字符串"
        print("[OK] 未知profile_id返回空字符串")

        memory.close()

    print("[通过] AgentMemory - 记忆上下文生成")
    return True


def test_profile_persistence():
    """测试用户画像持久化"""
    print(f"\n{'='*60}")
    print("[测试] AgentMemory - 用户画像持久化")
    print(f"{'='*60}")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "memory.db")
        memory = AgentMemory(db_path=db_path)

        profile = UserProfile(
            target_role="算法工程师",
            time_budget="6个月",
            company_tier="大厂",
            current_level="有机器学习基础",
            focus_areas=["Transformer", "RLHF"],
            avoid_areas=["前端开发"],
            raw_query="想找算法工程师实习",
        )

        profile_id = memory.save_profile(profile)
        assert len(profile_id) == 8, "profile_id应为8位"
        print(f"[OK] 保存画像: profile_id={profile_id}")

        loaded = memory.get_profile(profile_id)
        assert loaded is not None, "应能加载画像"
        assert loaded.target_role == "算法工程师", "目标岗位应一致"
        assert loaded.focus_areas == ["Transformer", "RLHF"], "重点方向应一致"
        print(f"[OK] 加载画像: {loaded.target_role}, 重点: {loaded.focus_areas}")

        # get_or_create_profile: 相同画像应返回相同ID
        pid2 = memory.get_or_create_profile(profile)
        assert pid2 == profile_id, "相同画像应返回相同profile_id"
        print("[OK] get_or_create_profile 去重正确")

        memory.close()

    print("[通过] AgentMemory - 用户画像持久化")
    return True


def test_critic_result_none():
    """测试Critic结果为空或失败时的行为"""
    print(f"\n{'='*60}")
    print("[测试] AgentMemory - 空Critic结果处理")
    print(f"{'='*60}")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "memory.db")
        memory = AgentMemory(db_path=db_path)

        # None 输入
        wp = memory.extract_and_save_weak_points("test", None)
        assert wp == [], "None输入应返回空列表"
        print("[OK] None输入返回空列表")

        # 失败结果
        wp = memory.extract_and_save_weak_points("test", {"success": False})
        assert wp == [], "失败结果应返回空列表"
        print("[OK] 失败结果返回空列表")

        memory.close()

    print("[通过] AgentMemory - 空Critic结果处理")
    return True


def main():
    results = []
    results.append(test_extract_weak_points())
    results.append(test_get_memory_context())
    results.append(test_profile_persistence())
    results.append(test_critic_result_none())

    print(f"\n{'='*60}")
    print(f"[汇总] 通过: {sum(results)}/{len(results)}")
    print(f"{'='*60}")

    if not all(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
