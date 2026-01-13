#!/usr/bin/env python3
"""
agentype - Routes模块
Author: cuilei
Version: 1.0
"""

import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, Depends

from agentype.subagent.api.models import (
    CellTypeAnalysisRequest, 
    CellTypeAnalysisResponse, 
    HealthResponse
)
from agentype.subagent.api.service import CellTypeAPIService
from agentype.subagent.config.settings import ConfigManager

logger = logging.getLogger(__name__)
router = APIRouter()

# 依赖注入: 创建并返回一个 CellTypeAPIService 实例
# 注意：在实际生产中，你可能希望这是一个单例，
# 这里为了简单，每次请求都会创建一个新的 service 实例，
# 但 agent 的初始化只会在第一次调用时发生。
# 更优化的方案是使用全局变量或FastAPI的生命周期事件来管理单例。
def get_api_service(request: CellTypeAnalysisRequest) -> CellTypeAPIService:
    config = ConfigManager(
        openai_api_base=request.openai_api_base or "https://api.openai.com/v1",
        openai_api_key=request.openai_api_key or "",
        openai_model=request.openai_model or "gpt-4o",
        proxy=request.http_proxy or request.https_proxy
    )
    return CellTypeAPIService(config=config)

@router.get("/", response_model=HealthResponse)
async def root():
    return HealthResponse(status="healthy", version="1.0.0")

@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="healthy", version="1.0.0")

@router.post("/analyze", response_model=CellTypeAnalysisResponse)
async def analyze_celltype(
    request: CellTypeAnalysisRequest,
    service: CellTypeAPIService = Depends(get_api_service)
):
    logger.info(f"收到分析请求: 基因列表={request.gene_list[:50]}...")
    try:
        await service.initialize()
        result = await service.analyze_celltype(request)
        logger.info(f"分析完成: 成功={result.success}, 细胞类型={result.cell_type}")
        return result
    except Exception as e:
        logger.error(f"API调用发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"内部服务器错误: {str(e)}")