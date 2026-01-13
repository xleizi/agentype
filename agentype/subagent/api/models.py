#!/usr/bin/env python3
"""
agentype - Models模块
Author: cuilei
Version: 1.0
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional

class CellTypeAnalysisRequest(BaseModel):
    gene_list: str = Field(..., description="基因列表，逗号分隔")
    tissue_type: Optional[str] = Field(None, description="组织类型（可选），如'骨髓'、'血液'、'肌肉'等")
    cell_type: Optional[str] = Field(None, description="细胞类型提示（可选），用于优先判断细胞亚群")
    openai_api_base: Optional[str] = Field("https://api.siliconflow.cn/v1", description="OpenAI API基础URL")
    openai_api_key: Optional[str] = Field("sk-paypkckrtunjtcmrfagtmpqotnjrhcrhsmtpnsmwquxxvokd", description="OpenAI API密钥")
    openai_model: Optional[str] = Field("Pro/deepseek-ai/DeepSeek-V3", description="OpenAI模型名称")
    http_proxy: Optional[str] = Field(None, description="HTTP代理地址")
    https_proxy: Optional[str] = Field(None, description="HTTPS代理地址")
    max_iterations: int = Field(50, description="最大迭代次数")
    max_retries_per_call: int = Field(5, description="每次调用的最大重试次数")

class CellTypeAnalysisResponse(BaseModel):
    success: bool = Field(..., description="分析是否成功")
    cell_type: Optional[str] = Field(None, description="推断的细胞类型")
    final_llm_output: Optional[str] = Field(None, description="最后一次LLM输出")
    total_iterations: int = Field(..., description="总迭代次数")
    analysis_log: List[Dict] = Field(..., description="分析日志")
    error_message: Optional[str] = Field(None, description="错误信息")

class HealthResponse(BaseModel):
    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="服务版本")
