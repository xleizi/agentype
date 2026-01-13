#!/usr/bin/env python3
"""
agentype - Path Manager模块
Author: cuilei
Version: 1.0
"""

from __future__ import annotations

from pathlib import Path


class MainPathManager:
    base_dir: Path
    package_root: Path
    package_dir: Path

    def __init__(self) -> None:
        self.base_dir = Path(__file__).resolve().parents[1]
        # 为了与其他路径管理器保持一致，添加这些属性
        self.package_root = Path(__file__).resolve().parent.parent.parent
        self.package_dir = self.base_dir

    def get_mcp_server_path(self) -> Path:
        candidates = [
            self.base_dir / "services" / "mcp_server.py",
        ]
        for p in candidates:
            if p.exists():
                return p

        # 支持打包环境：尝试使用 importlib.resources 查找包内资源
        try:
            try:
                # Python 3.9+
                from importlib.resources import files
                # 尝试在当前包路径中查找
                package_path = files('agentype.mainagent.services')
                mcp_server_file = package_path / 'mcp_server.py'
                if mcp_server_file.is_file():
                    return Path(str(mcp_server_file))
            except (ImportError, AttributeError):
                # Python < 3.9 兼容性
                import pkg_resources
                try:
                    resource_path = pkg_resources.resource_filename(
                        'agentype.mainagent.services', 'mcp_server.py'
                    )
                    if Path(resource_path).exists():
                        return Path(resource_path)
                except (pkg_resources.DistributionNotFound, FileNotFoundError):
                    pass
        except Exception:
            pass

        raise FileNotFoundError(f"Main MCP server script not found. Tried: {candidates}")


path_manager = MainPathManager()

