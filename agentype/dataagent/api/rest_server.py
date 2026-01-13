#!/usr/bin/env python3
"""
agentype - DataProcessor Agent REST API Server
Author: cuilei
Version: 1.0
"""

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from contextlib import asynccontextmanager

try:
    from fastapi import FastAPI, HTTPException, BackgroundTasks, File, UploadFile, Form
    from fastapi.responses import JSONResponse, FileResponse
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    print("警告: FastAPI不可用，无法启动REST服务器")

import sys
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent  # 需要到celltype-mcp-server目录
sys.path.insert(0, str(project_root))

from agentype.dataagent.agent import DataProcessorReactAgent
from agentype.dataagent.config import ConfigManager
from agentype.dataagent.utils import get_log_manager

# 请求和响应模型
class ProcessingRequest(BaseModel):
    """数据处理请求"""
    input_data: Union[str, Dict[str, Any]] = Field(..., description="输入数据路径或配置")
    task_id: Optional[str] = Field(None, description="可选的任务ID")
    config: Optional[Dict[str, Any]] = Field(None, description="处理配置参数")

class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str
    status: str  # pending, processing, completed, failed
    progress: Optional[float] = None
    message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class ProcessingResponse(BaseModel):
    """处理结果响应"""
    task_id: str
    success: bool
    processing_scenario: Optional[int] = None
    scenario_name: Optional[str] = None
    output_files: Optional[Dict[str, Any]] = None
    statistics: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    processing_time: Optional[float] = None

class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    agent_status: str
    mcp_server_connected: bool
    timestamp: datetime
    version: str = "1.0.0"

# 全局变量
agent: Optional[DataProcessorReactAgent] = None
config: ConfigManager = None
log_manager = None
task_registry: Dict[str, Dict[str, Any]] = {}  # 任务注册表

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global agent, config, log_manager
    
    # 启动时初始化
    print("🚀 启动DataProcessor Agent REST API服务器...")
    
    config = ConfigManager()
    log_manager = get_log_manager()
    agent = DataProcessorReactAgent(config)
    
    try:
        await agent.start()
        log_manager.agent_log("REST API服务器已启动")
        yield
    finally:
        # 关闭时清理
        if agent:
            await agent.stop()
            log_manager.agent_log("REST API服务器已停止")

# 创建FastAPI应用
if FASTAPI_AVAILABLE:
    app = FastAPI(
        title="CellType DataProcessor Agent API",
        description="Single-cell data processing and format conversion API",
        version="1.0.0",
        lifespan=lifespan
    )

    # CORS配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境应限制具体域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.post("/process", response_model=Dict[str, Any])
    async def submit_processing_task(
        request: ProcessingRequest,
        background_tasks: BackgroundTasks
    ) -> Dict[str, Any]:
        """
        提交数据处理任务
        
        支持两种处理模式：
        1. 同步处理：直接返回结果
        2. 异步处理：返回任务ID，通过其他接口查询状态
        """
        try:
            task_id = request.task_id or str(uuid.uuid4())[:8]
            
            # 记录任务开始
            task_registry[task_id] = {
                "status": "processing",
                "started_at": datetime.now(),
                "request": request.dict(),
                "progress": 0.0
            }
            
            log_manager.agent_log(f"接收到处理任务: {task_id}")
            
            # 对于简单任务，直接同步处理
            if isinstance(request.input_data, str) and Path(request.input_data).suffix in ['.json']:
                result = await agent.process_data(request.input_data, task_id)
                
                # 更新任务状态
                task_registry[task_id].update({
                    "status": "completed" if result.get("success") else "failed",
                    "completed_at": datetime.now(),
                    "result": result,
                    "progress": 100.0
                })
                
                return {
                    "task_id": task_id,
                    "status": "completed",
                    "result": result
                }
            
            # 对于复杂任务，使用后台处理
            background_tasks.add_task(process_data_background, request.input_data, task_id)
            
            return {
                "task_id": task_id,
                "status": "processing",
                "message": "任务已提交，请使用task_id查询处理状态",
                "status_url": f"/status/{task_id}",
                "result_url": f"/result/{task_id}"
            }
            
        except Exception as e:
            log_manager.error(f"提交处理任务失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"提交任务失败: {str(e)}")

    @app.get("/status/{task_id}", response_model=TaskStatusResponse)
    async def get_task_status(task_id: str) -> TaskStatusResponse:
        """查询任务处理状态"""
        try:
            if task_id not in task_registry:
                raise HTTPException(status_code=404, detail="任务不存在")
            
            task_info = task_registry[task_id]
            
            return TaskStatusResponse(
                task_id=task_id,
                status=task_info["status"],
                progress=task_info.get("progress"),
                message=task_info.get("message"),
                started_at=task_info.get("started_at"),
                completed_at=task_info.get("completed_at")
            )
            
        except HTTPException:
            raise
        except Exception as e:
            log_manager.error(f"查询任务状态失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"查询状态失败: {str(e)}")

    @app.get("/result/{task_id}", response_model=ProcessingResponse)
    async def get_task_result(task_id: str) -> ProcessingResponse:
        """获取任务处理结果"""
        try:
            if task_id not in task_registry:
                raise HTTPException(status_code=404, detail="任务不存在")
            
            task_info = task_registry[task_id]
            
            if task_info["status"] == "processing":
                raise HTTPException(status_code=202, detail="任务仍在处理中，请稍后查询")
            
            if task_info["status"] == "failed":
                return ProcessingResponse(
                    task_id=task_id,
                    success=False,
                    error=task_info.get("error", "处理失败")
                )
            
            result = task_info.get("result", {})
            
            return ProcessingResponse(
                task_id=task_id,
                success=result.get("success", False),
                processing_scenario=result.get("processing_scenario"),
                scenario_name=result.get("scenario_name"),
                output_files=result.get("output_files"),
                statistics=result.get("statistics"),
                error=result.get("error"),
                processing_time=result.get("processing_time")
            )
            
        except HTTPException:
            raise
        except Exception as e:
            log_manager.error(f"获取任务结果失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"获取结果失败: {str(e)}")

    @app.get("/health", response_model=HealthResponse)
    async def health_check() -> HealthResponse:
        """健康检查接口"""
        try:
            if not agent:
                return HealthResponse(
                    status="error",
                    agent_status="not_initialized",
                    mcp_server_connected=False,
                    timestamp=datetime.now()
                )
            
            agent_status = await agent.get_processing_status()
            
            return HealthResponse(
                status="healthy" if agent_status.get("agent_status") == "running" else "unhealthy",
                agent_status=agent_status.get("agent_status", "unknown"),
                mcp_server_connected=agent_status.get("mcp_server_connected", False),
                timestamp=datetime.now()
            )
            
        except Exception as e:
            log_manager.error(f"健康检查失败: {str(e)}")
            return HealthResponse(
                status="error",
                agent_status="error",
                mcp_server_connected=False,
                timestamp=datetime.now()
            )

    @app.get("/formats")
    async def get_supported_formats() -> Dict[str, Any]:
        """获取支持的数据格式和处理函数"""
        try:
            if not agent:
                raise HTTPException(status_code=503, detail="Agent未初始化")
            
            formats_info = await agent.list_supported_formats()
            return formats_info
            
        except Exception as e:
            log_manager.error(f"获取支持格式失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"获取格式信息失败: {str(e)}")

    @app.get("/tasks")
    async def list_tasks() -> Dict[str, Any]:
        """列出所有任务"""
        return {
            "total_tasks": len(task_registry),
            "tasks": {
                task_id: {
                    "status": info["status"],
                    "started_at": info.get("started_at"),
                    "progress": info.get("progress", 0)
                }
                for task_id, info in task_registry.items()
            }
        }

    @app.delete("/tasks/{task_id}")
    async def cancel_task(task_id: str) -> Dict[str, Any]:
        """取消或删除任务"""
        if task_id not in task_registry:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        task_info = task_registry[task_id]
        if task_info["status"] == "processing":
            # 实际项目中应该实现任务取消逻辑
            task_info["status"] = "cancelled"
            return {"message": f"任务 {task_id} 已取消"}
        else:
            del task_registry[task_id]
            return {"message": f"任务 {task_id} 已删除"}

    @app.post("/upload")
    async def upload_file(
        file: UploadFile = File(...),
        process_immediately: bool = Form(False)
    ) -> Dict[str, Any]:
        """
        文件上传接口
        
        允许用户上传数据文件，可选择立即处理
        """
        try:
            # 保存上传文件
            upload_dir = Path(config.cache_dir) / "uploads"
            upload_dir.mkdir(exist_ok=True)
            
            file_path = upload_dir / file.filename
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            
            log_manager.agent_log(f"文件上传成功: {file.filename}")
            
            result = {
                "filename": file.filename,
                "file_path": str(file_path),
                "file_size": len(content),
                "upload_time": datetime.now()
            }
            
            # 如果选择立即处理
            if process_immediately:
                task_id = str(uuid.uuid4())[:8]
                processing_result = await agent.process_data(str(file_path), task_id)
                result.update({
                    "task_id": task_id,
                    "processing_result": processing_result
                })
            
            return result
            
        except Exception as e:
            log_manager.error(f"文件上传失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")

    @app.get("/download/{task_id}/{file_type}")
    async def download_result_file(task_id: str, file_type: str):
        """
        下载处理结果文件
        
        file_type: marker_genes, h5_file, etc.
        """
        try:
            if task_id not in task_registry:
                raise HTTPException(status_code=404, detail="任务不存在")
            
            task_info = task_registry[task_id]
            result = task_info.get("result", {})
            
            if not result.get("success"):
                raise HTTPException(status_code=400, detail="任务处理失败，无可下载文件")
            
            # 获取对应文件路径
            file_path = None
            if file_type == "marker_genes":
                file_path = result.get("marker_genes_file")
            elif file_type == "h5_file":
                file_path = result.get("h5_file")
            elif file_type == "output_files":
                output_files = result.get("output_files", {})
                if output_files:
                    file_path = list(output_files.values())[0]
            
            if not file_path or not Path(file_path).exists():
                raise HTTPException(status_code=404, detail="文件不存在")
            
            return FileResponse(
                file_path,
                media_type='application/octet-stream',
                filename=Path(file_path).name
            )
            
        except HTTPException:
            raise
        except Exception as e:
            log_manager.error(f"下载文件失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")

    # 后台任务处理函数
    async def process_data_background(input_data: Union[str, Dict[str, Any]], task_id: str):
        """后台数据处理任务"""
        try:
            log_manager.agent_log(f"开始后台处理任务: {task_id}")
            
            # 更新进度
            task_registry[task_id]["progress"] = 10.0
            task_registry[task_id]["message"] = "正在分析输入数据..."
            
            # 执行处理
            result = await agent.process_data(input_data, task_id)
            
            # 更新最终状态
            task_registry[task_id].update({
                "status": "completed" if result.get("success") else "failed",
                "completed_at": datetime.now(),
                "result": result,
                "progress": 100.0,
                "message": "处理完成" if result.get("success") else f"处理失败: {result.get('error')}"
            })
            
            log_manager.agent_log(f"后台任务完成: {task_id}, 成功: {result.get('success')}")
            
        except Exception as e:
            error_msg = f"后台处理任务失败: {str(e)}"
            log_manager.error(error_msg)
            
            task_registry[task_id].update({
                "status": "failed",
                "completed_at": datetime.now(),
                "error": error_msg,
                "progress": 0.0,
                "message": error_msg
            })

else:
    # FastAPI不可用时的替代实现
    class MockApp:
        def __init__(self):
            print("❌ FastAPI不可用，无法启动REST服务器")
            print("请安装FastAPI: pip install fastapi uvicorn")
        
        def run(self):
            raise RuntimeError("FastAPI不可用")
    
    app = MockApp()

# 启动函数
def start_server(host: str = "0.0.0.0", port: int = 8000):
    """启动REST API服务器"""
    if not FASTAPI_AVAILABLE:
        print("❌ 无法启动服务器：FastAPI不可用")
        return
    
    try:
        import uvicorn
        print(f"🚀 启动REST API服务器 http://{host}:{port}")
        uvicorn.run(app, host=host, port=port)
    except ImportError:
        print("❌ 无法启动服务器：uvicorn不可用")
        print("请安装: pip install uvicorn")

if __name__ == "__main__":
    start_server()