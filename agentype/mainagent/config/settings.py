#!/usr/bin/env python3
"""
agentype - 配置管理
Author: cuilei
Version: 2.0 - 添加路径管理功能
"""

from __future__ import annotations

import os
from dataclasses import dataclass, asdict, field
from typing import Dict, Optional, List
from pathlib import Path


@dataclass
class SubAgentConfig:
    """子Agent连接配置"""
    name: str
    server_script: str
    enabled: bool = True
    max_retries: int = 3


@dataclass
class ConfigManager:
    """MainAgent配置管理器

    负责管理MainAgent及其与子Agent的连接配置
    """

    # LLM配置
    openai_api_base: Optional[str] = None
    openai_api_key: Optional[str] = None
    openai_model: Optional[str] = "gpt-4o"

    # MainAgent配置
    language: str = "zh"
    enable_streaming: bool = True
    enable_thinking: bool = False
    max_parallel_tasks: int = 3

    # 缓存和日志配置
    cache_dir: Optional[str] = None
    log_dir: Optional[str] = None
    enable_logging: bool = True

    # 路径配置
    output_dir: Optional[str] = None

    # 派生路径（将在__post_init__中初始化）
    results_dir: Path = field(init=False, default=None)
    downloads_dir: Path = field(init=False, default=None)
    temp_dir: Path = field(init=False, default=None)

    # 子Agent连接配置
    subagents: Dict[str, SubAgentConfig] = field(default_factory=dict)

    def __post_init__(self):
        """初始化后处理"""
        if not self.subagents:
            self._setup_default_subagents()

        # 路径配置：必须显式提供 output_dir
        if self.output_dir:
            output_path = Path(self.output_dir).resolve()
        else:
            raise ValueError(
                "必须提供 output_dir 参数。"
                "ConfigManager 不再支持自动使用当前工作目录，以避免文件保存到错误位置。"
            )

        # 规范化 output_dir 为绝对路径（确保 MCPClient 可以正确传递）
        self.output_dir = str(output_path)

        # 派生路径（基于output_dir）
        self.results_dir = output_path / "results" / "celltypeMainagent"
        self.downloads_dir = output_path / "downloads"
        self.temp_dir = output_path / "temp"

        # 创建必要目录
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # cache_dir 和 log_dir：优先使用传入值，否则基于output_dir
        if not self.cache_dir:
            self.cache_dir = str(output_path / "cache" / "celltypeMainagent")
        if not self.log_dir:
            self.log_dir = str(output_path / "logs")

    def _setup_default_subagents(self):
        """设置默认的子Agent配置"""
        current_dir = Path(__file__).resolve().parent.parent.parent

        self.subagents = {
            "celltypeSubagent": SubAgentConfig(
                name="celltypeSubagent",
                server_script=str(current_dir / "subagent" / "services" / "mcp_server.py")
            ),
            "celltypeDataAgent": SubAgentConfig(
                name="celltypeDataAgent",
                server_script=str(current_dir / "dataagent" / "services" / "mcp_server.py")
            ),
            "celltypeAppAgent": SubAgentConfig(
                name="celltypeAppAgent",
                server_script=str(current_dir / "appagent" / "services" / "mcp_server.py")
            )
        }

    def get_subagent_config(self, name: str) -> Optional[SubAgentConfig]:
        """获取指定子Agent的配置"""
        return self.subagents.get(name)

    def get_enabled_subagents(self) -> Dict[str, SubAgentConfig]:
        """获取启用的子Agent配置字典"""
        return {name: config for name, config in self.subagents.items() if config.enabled}

    def get_results_dir(self, subdir: str = "") -> Path:
        """获取结果目录

        Args:
            subdir: 子目录名称（可选）

        Returns:
            结果目录的Path对象
        """
        if subdir:
            result_path = self.results_dir / subdir
            result_path.mkdir(parents=True, exist_ok=True)
            return result_path
        return self.results_dir

    def get_downloads_dir(self, subdir: str = "") -> Path:
        """获取下载目录

        Args:
            subdir: 子目录名称（可选）

        Returns:
            下载目录的Path对象
        """
        if subdir:
            dl_path = self.downloads_dir / subdir
            dl_path.mkdir(parents=True, exist_ok=True)
            return dl_path
        return self.downloads_dir

    def get_temp_dir(self, subdir: str = "") -> Path:
        """获取临时目录

        Args:
            subdir: 子目录名称（可选）

        Returns:
            临时目录的Path对象
        """
        if subdir:
            tmp_path = self.temp_dir / subdir
            tmp_path.mkdir(parents=True, exist_ok=True)
            return tmp_path
        return self.temp_dir

    def validate(self) -> bool:
        """验证配置有效性"""
        # 验证子Agent服务器脚本存在
        for name, subagent in self.subagents.items():
            if subagent.enabled:
                server_path = Path(subagent.server_script)
                if not server_path.exists():
                    print(f"警告: 子Agent服务器脚本不存在: {server_path}")
                    return False

        # 验证目录权限
        try:
            Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
            Path(self.log_dir).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"警告: 无法创建缓存或日志目录: {e}")
            return False

        return True

    def to_dict(self) -> Dict:
        """转换为字典格式"""
        result = asdict(self)
        # 转换SubAgentConfig对象
        result['subagents'] = {name: asdict(config) for name, config in self.subagents.items()}
        # 转换Path对象为字符串
        if self.results_dir:
            result['results_dir'] = str(self.results_dir)
        if self.downloads_dir:
            result['downloads_dir'] = str(self.downloads_dir)
        if self.temp_dir:
            result['temp_dir'] = str(self.temp_dir)
        return result

    @classmethod
    def from_env(cls) -> "ConfigManager":
        """从环境变量创建配置"""
        return cls(
            openai_api_base=os.getenv("OPENAI_API_BASE"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            language=os.getenv("CELLTYPE_LANGUAGE", "zh"),
            enable_streaming=os.getenv("CELLTYPE_ENABLE_STREAMING", "true").lower() == "true",
            enable_logging=os.getenv("CELLTYPE_ENABLE_LOGGING", "true").lower() == "true",
            output_dir=os.getenv("CELLTYPE_OUTPUT_DIR")
        )
