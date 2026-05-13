"""
记忆层 - AgentMemory SQLite 本地持久化

线程安全：使用 threading.Lock 保护所有写操作，WAL 模式提升并发读性能
"""

import json
import uuid
import sqlite3
import threading
from typing import Optional, List, Dict
from pathlib import Path

from .user_profile import UserProfile


class AgentMemory:
    """Agent记忆：SQLite本地持久化用户画像和学习历史"""

    def __init__(self, db_path: str = "./data/agent_memory.db"):
        self.db_path = db_path
        self._lock = threading.Lock()

        # 自动从旧 JSON 文件迁移
        self._maybe_migrate_from_json()

        # 初始化 SQLite
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        try:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._init_schema()
        except sqlite3.DatabaseError:
            # 文件存在但不是有效的 SQLite 数据库（如旧 JSON 残留），重建
            self._conn.close()
            Path(self.db_path).unlink(missing_ok=True)
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._init_schema()

    def close(self):
        """关闭数据库连接"""
        try:
            self._conn.close()
        except Exception:
            pass

    def __del__(self):
        self.close()

    def _init_schema(self):
        """创建表和索引"""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS profiles (
                id TEXT PRIMARY KEY,
                target_role TEXT NOT NULL DEFAULT '',
                time_budget TEXT NOT NULL DEFAULT '',
                raw_query TEXT NOT NULL DEFAULT '',
                data TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS weak_points (
                profile_id TEXT PRIMARY KEY,
                points TEXT NOT NULL DEFAULT '[]',
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE INDEX IF NOT EXISTS idx_profiles_lookup
                ON profiles(target_role, time_budget, raw_query);
            CREATE INDEX IF NOT EXISTS idx_records_profile
                ON records(profile_id, created_at DESC);
        """)
        self._conn.commit()

    def _maybe_migrate_from_json(self):
        """检测旧 JSON 文件并自动迁移到 SQLite"""
        db_path = Path(self.db_path)
        json_path = db_path.with_suffix(".json")
        # 处理 ./data/agent_memory.db → ./data/agent_memory.json 的默认情况
        if not json_path.exists() and db_path.stem == "agent_memory":
            json_path = db_path.with_name("agent_memory.json")

        if not json_path.exists():
            return
        if db_path.exists():
            return  # SQLite 数据库已存在，不需要迁移

        print(f"[INFO] AgentMemory 检测到旧 JSON 文件 ({json_path})，正在迁移到 SQLite...")
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[WARN] AgentMemory JSON 文件读取失败，跳过迁移: {e}")
            return

        # 先初始化 SQLite（因为还没调用 _init_schema）
        db_dir = db_path.parent
        db_dir.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

        profiles_data = data.get("profiles", {})
        records_data = data.get("records", {})
        weak_points_data = data.get("weak_points", {})

        # 迁移画像
        for pid, pdata in profiles_data.items():
            self._conn.execute(
                "INSERT OR REPLACE INTO profiles (id, target_role, time_budget, raw_query, data) "
                "VALUES (?, ?, ?, ?, ?)",
                (pid, pdata.get("target_role", ""), pdata.get("time_budget", ""),
                 pdata.get("raw_query", ""), json.dumps(pdata, ensure_ascii=False))
            )
        # 迁移记录
        for pid, recs in records_data.items():
            for rec in recs:
                self._conn.execute(
                    "INSERT INTO records (profile_id, data) VALUES (?, ?)",
                    (pid, json.dumps(rec, ensure_ascii=False))
                )
        # 迁移薄弱点
        for pid, points in weak_points_data.items():
            self._conn.execute(
                "INSERT OR REPLACE INTO weak_points (profile_id, points) VALUES (?, ?)",
                (pid, json.dumps(points, ensure_ascii=False))
            )
        self._conn.commit()

        p_count = len(profiles_data)
        r_count = sum(len(v) for v in records_data.values())
        print(f"[INFO] AgentMemory 迁移完成：{p_count} 个画像，{r_count} 条记录")

        # 备份旧文件
        bak_path = json_path.with_suffix(".json.bak")
        try:
            json_path.rename(bak_path)
            print(f"[INFO] 旧 JSON 文件已备份为 {bak_path}")
        except OSError:
            pass

    # ========== 用户画像 CRUD ==========

    def save_profile(self, profile: UserProfile) -> str:
        """保存用户画像，返回 profile_id"""
        profile_id = str(uuid.uuid4())[:8]
        data_json = profile.model_dump_json() if hasattr(profile, 'model_dump_json') else json.dumps(profile.model_dump(), ensure_ascii=False)
        with self._lock:
            self._conn.execute(
                "INSERT INTO profiles (id, target_role, time_budget, raw_query, data) VALUES (?, ?, ?, ?, ?)",
                (profile_id, profile.target_role, profile.time_budget, profile.raw_query, data_json)
            )
            self._conn.commit()
        return profile_id

    def get_profile(self, profile_id: str) -> Optional[UserProfile]:
        """根据ID获取用户画像"""
        cursor = self._conn.execute("SELECT data FROM profiles WHERE id = ?", (profile_id,))
        row = cursor.fetchone()
        if row:
            return UserProfile(**json.loads(row["data"]))
        return None

    def get_or_create_profile(self, profile: UserProfile) -> str:
        """根据画像特征查找现有记录，不存在则创建"""
        cursor = self._conn.execute(
            "SELECT id FROM profiles WHERE target_role = ? AND time_budget = ? AND raw_query = ?",
            (profile.target_role, profile.time_budget, profile.raw_query)
        )
        row = cursor.fetchone()
        if row:
            return row["id"]
        return self.save_profile(profile)

    # ========== 研究记录 ==========

    def save_research_record(self, profile_id: str, record: Dict) -> None:
        """保存一次研究生成的记录"""
        data_json = json.dumps(record, ensure_ascii=False)
        with self._lock:
            self._conn.execute(
                "INSERT INTO records (profile_id, data) VALUES (?, ?)",
                (profile_id, data_json)
            )
            self._conn.commit()

    def get_recent_records(self, profile_id: str, limit: int = 5) -> List[Dict]:
        """获取用户最近N次生成记录"""
        cursor = self._conn.execute(
            "SELECT data FROM records WHERE profile_id = ? ORDER BY created_at DESC LIMIT ?",
            (profile_id, limit)
        )
        return [json.loads(row["data"]) for row in cursor.fetchall()]

    # ========== 薄弱点管理 ==========

    def extract_and_save_weak_points(self, profile_id: str, critic_result: Dict) -> List[str]:
        """从Critic审查结果中提取薄弱点并保存"""
        weak_points = []
        if not critic_result or not critic_result.get("success"):
            return weak_points

        # 从项目审查中提取
        project_review = critic_result.get("project_review", {})
        for toy in project_review.get("toy_projects", []):
            reason = toy.get("reason", "")
            name = toy.get("name", "")
            if name:
                weak_points.append(f"项目推荐质量: {name} - {reason}")

        # 从八股覆盖度中提取
        coverage = critic_result.get("interview_coverage", {})
        for topic in coverage.get("missing_topics", []):
            weak_points.append(f"八股覆盖不足: 缺少 {topic} 相关知识点")
        for topic in coverage.get("focus_areas_coverage", {}).get("missing", []):
            weak_points.append(f"重点方向覆盖不足: 缺少 {topic} 相关八股")

        # 从学习路径审查中提取
        path_review = critic_result.get("learning_path_review", {})
        if path_review.get("difficulty_match") != "appropriate":
            for issue in path_review.get("difficulty_issues", []):
                weak_points.append(f"学习路径难度: {issue}")
        if not path_review.get("time_realistic", True):
            for issue in path_review.get("time_issues", []):
                weak_points.append(f"学习路径时间: {issue}")

        # 从整体审查中提取
        overall = critic_result.get("overall_review", {})
        for issue in overall.get("critical_issues", []):
            weak_points.append(f"关键问题: {issue}")

        # 去重并保存
        weak_points = list(dict.fromkeys(weak_points))
        points_json = json.dumps(weak_points, ensure_ascii=False)
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO weak_points (profile_id, points, updated_at) "
                "VALUES (?, ?, datetime('now','localtime'))",
                (profile_id, points_json)
            )
            self._conn.commit()
        return weak_points

    def get_weak_points(self, profile_id: str) -> List[str]:
        """获取用户的薄弱点列表"""
        cursor = self._conn.execute(
            "SELECT points FROM weak_points WHERE profile_id = ?", (profile_id,)
        )
        row = cursor.fetchone()
        if row:
            return json.loads(row["points"])
        return []

    # ========== 记忆上下文 ==========

    def get_memory_context(self, profile_id: str, max_records: int = 3) -> str:
        """生成用于Prompt注入的记忆上下文文本"""
        parts = []

        weak_points = self.get_weak_points(profile_id)
        if weak_points:
            parts.append("【历史薄弱点（需重点关注）】\n" + "\n".join(f"- {wp}" for wp in weak_points[:10]))

        records = self.get_recent_records(profile_id, limit=max_records)
        if records:
            parts.append("【近期研究记录】")
            for i, record in enumerate(records, 1):
                ts = record.get("timestamp", "")[:10]
                score = record.get("quality_score", 0)
                task = record.get("task", "")[:50]
                parts.append(f"{i}. [{ts}] 任务: {task}... | 质量分: {score}")

        return "\n\n".join(parts) if parts else ""
