#!/usr/bin/env python3
"""
agentype - Main模块
Author: cuilei
Version: 1.0
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from agentype.appagent.api.routes import router

def create_app() -> FastAPI:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logging.getLogger(__name__).info("📂 细胞类型注释API服务启动")
    
    app = FastAPI(
        title="细胞类型注释API服务",
        description="基于CellType App Agent的细胞类型注释API，支持SingleR、scType、CellTypist综合注释",
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