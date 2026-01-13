#!/usr/bin/env python3
"""
agentype - 路径管理器模块
Author: cuilei
Version: 1.0
"""

from pathlib import Path
from typing import Optional
import sys

# GlobalConfig 已废弃，使用默认路径
from pathlib import Path

class PathManager:
    """统一的路径管理器"""
    
    def __init__(self):
        # 获取包的根目录（agentype目录）
        self.package_root = Path(__file__).resolve().parent.parent.parent
        # 针对历史与当前目录结构，维护一组可能的SubAgent目录
        self.package_dirs = [
            self.package_root / "subagent",
            self.package_root / "celltypeSubagent",
        ]
        # 选择第一个存在的目录作为主要包目录，若都不存在则回退到首个候选项
        self.package_dir = next((d for d in self.package_dirs if d.exists()), self.package_dirs[0])
        
    def get_mcp_server_path(self) -> Path:
        """获取MCP服务器脚本的路径"""
        candidate_paths = []

        # 优先检查当前规范结构 subagent/services
        for directory in self.package_dirs:
            candidate = directory / "services" / "mcp_server.py"
            candidate_paths.append(candidate)
            if candidate.exists():
                return candidate

        # 兼容旧的结构，在包根目录查找
        old_services_path = self.package_root / "services" / "mcp_server.py"
        candidate_paths.append(old_services_path)
        if old_services_path.exists():
            return old_services_path

        # 如果不存在，尝试相对于当前工作目录的常见结构
        cwd_candidates = [
            Path.cwd() / "agentype" / "subagent" / "services" / "mcp_server.py",
            Path.cwd() / "celltypeSubagent" / "services" / "mcp_server.py",
        ]

        for candidate in cwd_candidates:
            candidate_paths.append(candidate)
            if candidate.exists():
                return candidate

        raise FileNotFoundError(
            f"MCP服务器脚本未找到。搜索路径: {candidate_paths}"
        )
    
    def get_cache_dir(self, custom_dir: Optional[str] = None) -> Path:
        """获取缓存目录

        ⚠️ 注意：推荐使用 SubAgent ConfigManager 代替此方法
        示例：config.get_cache_dir("celltypeSubagent")
        """
        if custom_dir:
            return Path(custom_dir).resolve()
        # 使用相对路径作为默认值（移除硬编码的绝对路径）
        default_cache = Path.cwd() / "outputs" / "downloads"
        cache_dir = default_cache / "celltypeSubagent"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    def get_log_dir(self, log_dir: str = "logs") -> Path:
        """获取日志目录

        ⚠️ 注意：推荐使用 SubAgent ConfigManager 代替此方法
        示例：config.get_logs_dir("celltypeSubagent")
        """
        # 使用相对路径作为默认值（移除硬编码的绝对路径）
        default_logs = Path.cwd() / "outputs" / "logs"
        log_path = default_logs / "celltypeSubagent"
        log_path.mkdir(parents=True, exist_ok=True)
        return log_path

    def get_llm_log_dir(self, log_dir: str = "llm_logs") -> Path:
        """获取LLM日志目录

        ⚠️ 注意：推荐使用 SubAgent ConfigManager 代替此方法
        示例：config.get_logs_dir("celltypeSubagent/llm")
        """
        # 使用相对路径作为默认值（移除硬编码的绝对路径）
        default_logs = Path.cwd() / "outputs" / "logs"
        llm_log_path = default_logs / "celltypeSubagent" / "llm"
        llm_log_path.mkdir(parents=True, exist_ok=True)
        return llm_log_path

# 全局路径管理器实例
path_manager = PathManager()
