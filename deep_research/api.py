"""
Deep Research Agent - FastAPI 服务

提供 RESTful API 接口，支持：
- 提交研究任务
- 查询任务状态
- 获取研究报告
- SSE 流式进度推送

启动服务：
    uvicorn deep_research.api:app --reload --port 8000

或者：
    python -m deep_research.api
"""

import asyncio
import json
import uuid
import time
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .orchestrator import Orchestrator, ResearchState
from .workers import search_worker_factory
from .config import AGENT_CONFIG
from .user_profile import UserProfileExtractor
from .output_formatter import OutputFormatter


# ==================== 数据模型 ====================

class ResearchRequest(BaseModel):
    """研究任务请求（求职场景：task + 可选用户画像字段）"""
    task: str = Field(..., description="研究任务描述（自然语言）", min_length=1)
    max_workers: Optional[int] = Field(None, description="最大并行Worker数", ge=1, le=10)
    max_iterations: Optional[int] = Field(None, description="最大迭代次数", ge=1, le=10)
    quality_threshold: Optional[int] = Field(None, description="质量阈值", ge=0, le=100)
    # 用户画像字段（全部可选，向后兼容通用研究场景）
    target_role: Optional[str] = Field(None, description="目标岗位，如「大模型应用开发工程师」")
    time_budget: Optional[str] = Field(None, description="可用准备时间，如「3个月」")
    company_tier: Optional[str] = Field(None, description="目标公司层级，如「大厂」「中厂」「外企」")
    current_level: Optional[str] = Field(None, description="当前水平，如「有Python和PyTorch基础」")
    focus_areas: Optional[List[str]] = Field(None, description="希望重点加强的方向，如['RAG', 'Agent框架']")
    avoid_areas: Optional[List[str]] = Field(None, description="明确不需要的方向，如['前端开发']")

    class Config:
        json_schema_extra = {
            "example": {
                "task": "我是数学专业研一学生，想找大模型应用开发方向的暑期实习，有3个月准备时间",
                "target_role": "大模型应用开发工程师",
                "time_budget": "3个月",
                "company_tier": "大厂",
                "current_level": "有Python和PyTorch基础，没做过完整项目",
                "focus_areas": ["RAG", "Agent框架", "MCP协议"],
                "avoid_areas": ["前端开发", "嵌入式"],
                "max_workers": 6,
                "max_iterations": 5,
                "quality_threshold": 80
            }
        }


class ResearchResponse(BaseModel):
    """研究任务响应"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态")
    message: str = Field(..., description="状态信息")
    created_at: str = Field(..., description="创建时间")


class TaskStatus(BaseModel):
    """任务状态"""
    task_id: str
    status: str  # pending, running, completed, failed
    progress: Dict[str, Any]
    original_task: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    quality_score: Optional[int] = None
    iteration_count: Optional[int] = None
    error_message: Optional[str] = None


class TaskResult(BaseModel):
    """任务结果"""
    task_id: str
    status: str
    report: Optional[str] = None
    quality_score: Optional[int] = None
    iteration_count: Optional[int] = None
    duration: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    structured_output: Optional[Dict[str, Any]] = Field(None, description="结构化JSON输出（学习路径/八股/项目推荐/模拟面试）")


# ==================== 任务管理器 ====================

class TaskManager:
    """任务管理器 - 管理所有研究任务的生命周期"""

    def __init__(self):
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.executor = ThreadPoolExecutor(max_workers=3)  # 最多同时运行3个研究任务

    def create_task(self, request: ResearchRequest) -> str:
        """创建新任务"""
        task_id = str(uuid.uuid4())[:8]
        self.tasks[task_id] = {
            "task_id": task_id,
            "original_task": request.task,
            "status": "pending",
            "progress": [],
            "progress_summary": {},
            "config": {
                "max_workers": request.max_workers or AGENT_CONFIG["max_workers"],
                "max_iterations": request.max_iterations or AGENT_CONFIG["max_iterations"],
                "quality_threshold": request.quality_threshold or AGENT_CONFIG["quality_threshold"],
            },
            "user_profile": {
                "target_role": request.target_role,
                "time_budget": request.time_budget,
                "company_tier": request.company_tier,
                "current_level": request.current_level,
                "focus_areas": request.focus_areas,
                "avoid_areas": request.avoid_areas,
            },
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
        }
        return task_id

    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取任务信息"""
        return self.tasks.get(task_id)

    def update_progress(self, task_id: str, stage: str, data: dict):
        """更新任务进度"""
        if task_id in self.tasks:
            progress_event = {
                "stage": stage,
                "data": data,
                "timestamp": datetime.now().isoformat(),
            }
            self.tasks[task_id]["progress"].append(progress_event)
            self.tasks[task_id]["progress_summary"] = {
                "current_stage": stage,
                "last_update": progress_event["timestamp"],
                **data,
            }

    def set_running(self, task_id: str):
        """设置任务为运行中"""
        if task_id in self.tasks:
            self.tasks[task_id]["status"] = "running"
            self.tasks[task_id]["started_at"] = datetime.now().isoformat()

    def set_completed(self, task_id: str, state: ResearchState):
        """设置任务为已完成"""
        if task_id in self.tasks:
            self.tasks[task_id]["status"] = "completed"
            self.tasks[task_id]["completed_at"] = datetime.now().isoformat()
            self.tasks[task_id]["result"] = {
                "report": state.final_report,
                "quality_score": state.quality_score,
                "iteration_count": state.iteration_count,
                "duration": state.end_time - state.start_time,
                "structured_output": state.structured_output,
            }

    def set_failed(self, task_id: str, error: str):
        """设置任务为失败"""
        if task_id in self.tasks:
            self.tasks[task_id]["status"] = "failed"
            self.tasks[task_id]["completed_at"] = datetime.now().isoformat()
            self.tasks[task_id]["error"] = error

    def list_tasks(self) -> list:
        """列出所有任务"""
        return [
            {
                "task_id": t["task_id"],
                "original_task": t["original_task"][:50] + "..." if len(t["original_task"]) > 50 else t["original_task"],
                "status": t["status"],
                "created_at": t["created_at"],
                "quality_score": t["result"]["quality_score"] if t["result"] else None,
            }
            for t in self.tasks.values()
        ]


# ==================== 全局实例 ====================

task_manager = TaskManager()
_config_lock = threading.Lock()  # 保护 AGENT_CONFIG 并发修改


# ==================== FastAPI 应用 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    print("🚀 Deep Research API 服务启动")

    # 初始化 MCP 连接
    try:
        from .tools import init_mcp_from_config
        init_mcp_from_config()
        from .tools import get_mcp_manager
        mgr = get_mcp_manager()
        if mgr.enabled:
            print("✅ MCP 工具服务已初始化")
    except Exception as e:
        print(f"⚠️  MCP 初始化失败（不影响正常使用）: {e}")

    yield
    print("👋 Deep Research API 服务关闭")
    task_manager.executor.shutdown(wait=False)


app = FastAPI(
    title="Deep Research Agent API",
    description="基于 Orchestrator-Workers 架构的深度研究智能体服务",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 研究任务执行 ====================

def run_research_task(task_id: str, request: ResearchRequest):
    """在后台线程中执行研究任务"""
    try:
        task_manager.set_running(task_id)
        task_info = task_manager.get_task(task_id)
        config = task_info["config"]

        # 创建进度回调
        def on_progress(stage: str, data: dict):
            task_manager.update_progress(task_id, stage, data)

        # 提取用户画像
        extractor = UserProfileExtractor()
        user_profile = extractor.extract(
            request.task,
            target_role=request.target_role,
            time_budget=request.time_budget,
            company_tier=request.company_tier,
            current_level=request.current_level,
            focus_areas=request.focus_areas,
            avoid_areas=request.avoid_areas,
        )

        # 临时修改配置（加锁保护，防止并发覆盖）
        with _config_lock:
            original_config = {
                "max_iterations": AGENT_CONFIG["max_iterations"],
                "quality_threshold": AGENT_CONFIG["quality_threshold"],
            }
            AGENT_CONFIG["max_iterations"] = config["max_iterations"]
            AGENT_CONFIG["quality_threshold"] = config["quality_threshold"]

            try:
                # 创建 Orchestrator（传入用户画像以启用求职场景功能）
                orchestrator = Orchestrator(
                    worker_factory=search_worker_factory,
                    max_workers=config["max_workers"],
                    on_progress=on_progress,
                    user_profile=user_profile.model_dump(),
                )

                state = orchestrator.run(request.task, user_profile=user_profile.model_dump())

                if state.status == "completed":
                    # 生成结构化输出
                    formatter = OutputFormatter(user_profile=user_profile)
                    formatted = formatter.format(state)
                    state.structured_output = formatted.json_data
                    task_manager.set_completed(task_id, state)
                else:
                    task_manager.set_failed(task_id, state.error_msg or "未知错误")

            finally:
                # 恢复配置
                AGENT_CONFIG["max_iterations"] = original_config["max_iterations"]
                AGENT_CONFIG["quality_threshold"] = original_config["quality_threshold"]

    except Exception as e:
        task_manager.set_failed(task_id, str(e))


# ==================== API 路由 ====================

@app.get("/", tags=["系统"])
async def root():
    """服务根路径 - 返回服务信息"""
    return {
        "service": "Deep Research Agent API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "submit": "POST /research",
            "status": "GET /research/{task_id}",
            "result": "GET /research/{task_id}/result",
            "stream": "GET /research/{task_id}/stream",
            "list": "GET /research",
        }
    }


@app.get("/health", tags=["系统"])
async def health_check():
    """健康检查"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/research", response_model=ResearchResponse, tags=["研究任务"])
async def submit_research(request: ResearchRequest, background_tasks: BackgroundTasks):
    """
    提交研究任务（支持通用研究 + 求职场景）

    - **task**: 研究任务描述/自然语言输入（必填）
    - **target_role**: 目标岗位（可选，如「大模型应用开发工程师」）
    - **time_budget**: 可用准备时间（可选，如「3个月」）
    - **company_tier**: 目标公司层级（可选，如「大厂」）
    - **current_level**: 当前水平（可选）
    - **focus_areas**: 重点加强方向（可选，如["RAG", "Agent框架"]）
    - **avoid_areas**: 排除方向（可选，如["前端开发"]）
    - **max_workers**: 最大并行Worker数（可选，默认6）
    - **max_iterations**: 最大迭代次数（可选，默认5）
    - **quality_threshold**: 质量阈值（可选，默认80）

    返回任务ID，可用于查询进度和获取结果（含structured_output）。
    """
    # 创建任务
    task_id = task_manager.create_task(request)

    # 在后台执行研究
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        task_manager.executor,
        run_research_task,
        task_id,
        request,
    )

    return ResearchResponse(
        task_id=task_id,
        status="pending",
        message="研究任务已提交，正在启动...",
        created_at=datetime.now().isoformat(),
    )


@app.get("/research", tags=["研究任务"])
async def list_research_tasks():
    """列出所有研究任务"""
    return {
        "total": len(task_manager.tasks),
        "tasks": task_manager.list_tasks(),
    }


@app.get("/research/{task_id}", response_model=TaskStatus, tags=["研究任务"])
async def get_task_status(task_id: str):
    """
    获取任务状态

    返回任务的当前状态和进度信息。
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    return TaskStatus(
        task_id=task["task_id"],
        status=task["status"],
        progress=task["progress_summary"],
        original_task=task["original_task"],
        created_at=task["created_at"],
        started_at=task["started_at"],
        completed_at=task["completed_at"],
        quality_score=task["result"]["quality_score"] if task["result"] else None,
        iteration_count=task["result"]["iteration_count"] if task["result"] else None,
        error_message=task["error"],
    )


@app.get("/research/{task_id}/result", response_model=TaskResult, tags=["研究任务"])
async def get_task_result(task_id: str):
    """
    获取任务结果

    任务完成后返回研究报告和元数据。
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    if task["status"] == "pending":
        raise HTTPException(status_code=202, detail="任务尚未开始")

    if task["status"] == "running":
        raise HTTPException(status_code=202, detail="任务正在执行中")

    if task["status"] == "failed":
        return TaskResult(
            task_id=task_id,
            status="failed",
            metadata={"error": task["error"]},
        )

    result = task["result"]
    return TaskResult(
        task_id=task_id,
        status="completed",
        report=result["report"],
        quality_score=result["quality_score"],
        iteration_count=result["iteration_count"],
        duration=result["duration"],
        metadata={
            "original_task": task["original_task"],
            "created_at": task["created_at"],
            "completed_at": task["completed_at"],
        },
        structured_output=result.get("structured_output"),
    )


@app.get("/research/{task_id}/stream", tags=["研究任务"])
async def stream_task_progress(task_id: str):
    """
    SSE 流式进度推送

    实时推送任务执行进度，直到任务完成。

    使用方法：
    ```javascript
    const eventSource = new EventSource('/research/{task_id}/stream');
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log(data);
    };
    ```
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    async def event_generator():
        """生成 SSE 事件流"""
        last_progress_count = 0

        while True:
            task = task_manager.get_task(task_id)
            if not task:
                break

            # 发送新的进度事件
            current_progress = task["progress"]
            if len(current_progress) > last_progress_count:
                for event in current_progress[last_progress_count:]:
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                last_progress_count = len(current_progress)

            # 检查是否完成
            if task["status"] in ["completed", "failed"]:
                # 发送最终状态
                final_event = {
                    "stage": "final",
                    "data": {
                        "status": task["status"],
                        "quality_score": task["result"]["quality_score"] if task["result"] else None,
                        "iteration_count": task["result"]["iteration_count"] if task["result"] else None,
                        "duration": task["result"]["duration"] if task["result"] else None,
                        "error": task["error"],
                    },
                    "timestamp": datetime.now().isoformat(),
                }
                yield f"data: {json.dumps(final_event, ensure_ascii=False)}\n\n"
                break

            await asyncio.sleep(0.5)  # 每0.5秒检查一次

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.delete("/research/{task_id}", tags=["研究任务"])
async def delete_task(task_id: str):
    """删除任务记录"""
    if task_id not in task_manager.tasks:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    task = task_manager.tasks[task_id]
    if task["status"] == "running":
        raise HTTPException(status_code=400, detail="无法删除正在执行的任务")

    del task_manager.tasks[task_id]
    return {"message": f"任务 {task_id} 已删除"}


# ==================== 启动入口 ====================

def main():
    """命令行启动入口"""
    import uvicorn
    uvicorn.run(
        "deep_research.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
