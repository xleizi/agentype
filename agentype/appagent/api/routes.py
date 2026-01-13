#!/usr/bin/env python3
"""
agentype - Routes模块
Author: cuilei
Version: 1.0
"""

import logging
from fastapi import APIRouter, HTTPException, Depends

from agentype.appagent.api.models import (
    CelltypeAnnotationRequest,
    CelltypeAnnotationResponse,
    HealthResponse
)
from agentype.appagent.api.service import CelltypeAnnotationAPIService

logger = logging.getLogger(__name__)
router = APIRouter()

# 全局服务实例
_service_instance = None

def get_api_service() -> CelltypeAnnotationAPIService:
    """依赖注入: 获取API服务实例"""
    global _service_instance
    if _service_instance is None:
        _service_instance = CelltypeAnnotationAPIService()
    return _service_instance

@router.get("/", response_model=HealthResponse)
async def root():
    return HealthResponse(
        status="healthy", 
        version="1.0.0",
        available_methods=["singler", "sctype", "celltypist"]
    )

@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy", 
        version="1.0.0",
        available_methods=["singler", "sctype", "celltypist"]
    )

@router.post("/annotate", response_model=CelltypeAnnotationResponse)
async def annotate_celltype(
    request: CelltypeAnnotationRequest,
    service: CelltypeAnnotationAPIService = Depends(get_api_service)
):
    logger.info(f"收到注释请求: RDS={request.rds_path}, H5AD={request.h5ad_path}")
    try:
        await service.initialize()
        result = await service.run_annotation(request)
        logger.info(f"注释完成: 成功={result.success}")
        return result
    except Exception as e:
        logger.error(f"API调用发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"内部服务器错误: {str(e)}")