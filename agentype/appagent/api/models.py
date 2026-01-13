#!/usr/bin/env python3
"""
agentype - Models模块
Author: cuilei
Version: 1.0
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional

class CelltypeAnnotationRequest(BaseModel):
    rds_path: Optional[str] = Field(None, description="RDS文件路径")
    h5ad_path: Optional[str] = Field(None, description="H5AD文件路径") 
    tissue_description: Optional[str] = Field(None, description="组织描述，如'免疫系统组织'、'骨髓'等")
    annotation_methods: Optional[List[str]] = Field(["singler", "sctype", "celltypist"], 
                                                   description="注释方法列表，支持singler、sctype、celltypist")
    species: Optional[str] = Field(None, description="物种，如human、mouse，不指定时自动检测")
    output_dir: Optional[str] = Field(None, description="输出目录路径")
    pval_threshold: Optional[float] = Field(0.05, description="P值阈值")

class CelltypeAnnotationResponse(BaseModel):
    success: bool = Field(..., description="注释是否成功")
    annotation_results: Optional[Dict] = Field(None, description="注释结果汇总")
    output_file_paths: Optional[Dict] = Field(None, description="输出文件路径")
    summary: Optional[Dict] = Field(None, description="结果统计摘要")
    processing_log: List[Dict] = Field(..., description="处理日志")
    error_message: Optional[str] = Field(None, description="错误信息")

class HealthResponse(BaseModel):
    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="服务版本")
    available_methods: List[str] = Field(..., description="可用的注释方法")