"""
用户画像层 - 解析和验证用户输入
"""

from pydantic import BaseModel, Field
from typing import Optional, List


class UserProfile(BaseModel):
    """标准化用户画像"""
    target_role: str = Field(..., description="目标岗位，决定八股范围和路径方向")
    time_budget: str = Field(..., description="可用准备时间，决定路径密度")
    company_tier: str = Field(..., description="目标公司层级，决定面试深度")
    current_level: Optional[str] = Field(None, description="当前水平，决定路径起点")
    focus_areas: List[str] = Field(default_factory=list, description="希望重点加强的方向")
    avoid_areas: List[str] = Field(default_factory=list, description="明确不需要的方向")
    raw_query: str = Field(..., description="用户原始自然语言输入")
    background_type: Optional[str] = Field(
        default=None,
        description="由LLM根据用户current_level和原始输入推断的背景类型，如'计算机科班'、'金融转AI'、'数学物理背景'等"
    )


class UserProfileExtractor:
    """用户画像提取器"""

    def __init__(self, llm_client=None):
        self.llm = llm_client

    def extract(self, query: str, **structured_fields) -> UserProfile:
        """
        提取用户画像。优先使用提供的结构化字段，缺失的从query中推断或设默认值。
        """
        # 防御：query 为 None 或非字符串时回退
        if not query:
            query = ""
        query = str(query)

        # Tier 1 字段（高决策价值）
        target_role = structured_fields.get("target_role", "")
        time_budget = structured_fields.get("time_budget", "")
        company_tier = structured_fields.get("company_tier", "")

        # Tier 2 字段（中等决策价值）
        current_level = structured_fields.get("current_level", "")
        focus_areas = structured_fields.get("focus_areas", []) or []
        avoid_areas = structured_fields.get("avoid_areas", []) or []

        # 如果缺少必填字段，尝试从 query 中用简单规则推断
        if not target_role:
            target_role = self._infer_target_role(query)
        if not time_budget:
            time_budget = self._infer_time_budget(query)
        if not company_tier:
            company_tier = self._infer_company_tier(query)
        if not current_level:
            current_level = self._infer_current_level(query)

        # 确保 focus_areas 和 avoid_areas 是列表（同时兼容中英文逗号）
        if isinstance(focus_areas, str):
            focus_areas = [x.strip() for x in focus_areas.replace("，", ",").split(",") if x.strip()]
        if isinstance(avoid_areas, str):
            avoid_areas = [x.strip() for x in avoid_areas.replace("，", ",").split(",") if x.strip()]

        return UserProfile(
            target_role=target_role or "大模型应用开发工程师",
            time_budget=time_budget or "3个月",
            company_tier=company_tier or "大厂",
            current_level=current_level,
            focus_areas=focus_areas,
            avoid_areas=avoid_areas,
            raw_query=query,
        )

    def _infer_target_role(self, query: str) -> str:
        """从query中推断目标岗位"""
        q = query.lower()
        if "算法" in q or "算法工程师" in q:
            return "算法工程师"
        if "应用" in q or "agent" in q or "开发" in q:
            return "大模型应用开发工程师"
        return "大模型应用开发工程师"

    def _infer_time_budget(self, query: str) -> str:
        """从query中推断准备时间"""
        import re
        q = query.lower()
        match = re.search(r'(\d+)\s*个月', q)
        if match:
            return f"{match.group(1)}个月"
        match = re.search(r'(\d+)\s*月', q)
        if match:
            return f"{match.group(1)}个月"
        return "3个月"

    def _infer_company_tier(self, query: str) -> str:
        """从query中推断目标公司层级"""
        q = query.lower()
        if "大厂" in q or "一线" in q or "bat" in q or "字节" in q or "阿里" in q or "腾讯" in q:
            return "大厂"
        if "中厂" in q or "二线" in q:
            return "中厂"
        if "外企" in q or "外资" in q:
            return "外企"
        return "大厂"

    def _infer_current_level(self, query: str) -> str:
        """从query中推断当前水平"""
        q = query.lower()
        if "零基础" in q or "刚开始" in q:
            return "零基础"
        if "基础" in q:
            return "有Python和PyTorch基础"
        return "有Python和PyTorch基础"
