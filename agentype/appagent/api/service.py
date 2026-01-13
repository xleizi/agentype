#!/usr/bin/env python3
"""
agentype - Service模块
Author: cuilei
Version: 1.0
"""

import logging
from typing import Optional

from agentype.appagent.agent.celltype_annotation_agent import CelltypeAnnotationAgent
from agentype.appagent.api.models import CelltypeAnnotationRequest, CelltypeAnnotationResponse

logger = logging.getLogger(__name__)

class CelltypeAnnotationAPIService:
    """细胞类型注释API服务类"""
    
    def __init__(self):
        self.agent: Optional[CelltypeAnnotationAgent] = CelltypeAnnotationAgent()
        self.is_initialized = False
    
    async def initialize(self):
        """初始化Agent"""
        if not self.is_initialized and self.agent:
            try:
                # CelltypeAnnotationAgent 不需要异步初始化
                self.is_initialized = True
                logger.info("细胞类型注释Agent初始化成功")
            except Exception as e:
                logger.error(f"初始化agent时发生错误: {str(e)}")
    
    async def run_annotation(self, request: CelltypeAnnotationRequest) -> CelltypeAnnotationResponse:
        """执行细胞类型注释"""
        if not self.is_initialized or not self.agent:
            return CelltypeAnnotationResponse(
                success=False,
                annotation_results=None,
                output_file_paths=None,
                summary=None,
                processing_log=[],
                error_message="Agent未初始化或初始化失败"
            )
        
        try:
            logger.info("🚀 开始细胞类型注释...")
            logger.info(f"📋 RDS文件: {request.rds_path}")
            logger.info(f"📋 H5AD文件: {request.h5ad_path}")
            logger.info(f"🏥 组织描述: {request.tissue_description}")
            
            # 调用完整的注释流水线
            result = self.agent.run_full_annotation_pipeline(
                rds_path=request.rds_path,
                h5ad_path=request.h5ad_path,
                tissue_description=request.tissue_description
            )
            
            logger.info(f"✅ 注释完成: {result}")
            
            return CelltypeAnnotationResponse(
                success=True,
                annotation_results=result.get('annotation_results', {}),
                output_file_paths=result.get('output_file_paths', {}),
                summary=result.get('summary', {}),
                processing_log=result.get('processing_log', []),
                error_message=None
            )
            
        except Exception as e:
            error_msg = f"注释错误: {str(e)}"
            logger.error(f"注释过程中发生错误: {str(e)}")
            
            return CelltypeAnnotationResponse(
                success=False,
                annotation_results=None,
                output_file_paths=None,
                summary=None,
                processing_log=[],
                error_message=error_msg
            )
    
    async def cleanup(self):
        """清理资源"""
        if self.agent:
            try:
                # CelltypeAnnotationAgent 没有异步清理方法
                self.agent = None
                self.is_initialized = False
                logger.info("资源清理完成")
            except Exception as e:
                logger.error(f"清理资源时发生错误: {str(e)}")