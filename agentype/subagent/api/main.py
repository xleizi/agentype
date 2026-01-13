#!/usr/bin/env python3
"""
agentype - Main模块
Author: cuilei
Version: 1.0
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

# 初始化统一缓存系统
from agentype.subagent import init_cache

from agentype.subagent.api.routes import router

def create_app() -> FastAPI:
    # 初始化统一缓存系统
    cache_dir = init_cache()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 添加缓存目录信息到日志
    logging.getLogger(__name__).info(f"📂 API服务缓存目录已初始化: {cache_dir}")
    
    app = FastAPI(
        title="细胞类型分析API服务",
        description="基于React Agent的细胞类型分析API，支持基因列表分析",
        version="1.0.0"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router, prefix="/api/v1")
    
    return app

app = create_app()
