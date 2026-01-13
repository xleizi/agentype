#!/usr/bin/env python3
"""
agentype - Rest Api Server模块
Author: cuilei
Version: 1.0
"""

import uvicorn
import sys
import socket
from pathlib import Path

# 添加项目根目录到 Python 路径
current_dir = Path(__file__).resolve().parent  # celltypeSubagent/services
celltypeSubagent_dir = current_dir.parent  # celltypeSubagent
project_root = celltypeSubagent_dir.parent  # celltype-mcp-server
sys.path.insert(0, str(project_root))

# 初始化统一缓存系统（必须在其他导入之前）
from agentype.subagent import init_cache

from agentype.subagent.api.main import app

def find_available_port(start_port: int = 8585, max_attempts: int = 100) -> int:
    """查找可用端口，从start_port开始，如果被占用则依次加1"""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(('localhost', port))
                return port
        except OSError:
            continue
    
    raise RuntimeError(f"无法在 {start_port}-{start_port + max_attempts - 1} 端口范围内找到可用端口")

if __name__ == "__main__":
    # 初始化统一缓存系统
    cache_dir = init_cache()
    print(f"📂 REST API服务缓存目录已初始化: {cache_dir}")
    
    # 查找可用端口
    try:
        port = find_available_port(8585)
        print(f"🔌 使用端口: {port}")
        
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=port,
            log_level="info"
        )
    except RuntimeError as e:
        print(f"❌ 端口分配失败: {e}")
        sys.exit(1)