#!/usr/bin/env python3
"""
agentype - 统一配置管理器

基于参数传递的配置系统，完全移除配置文件依赖。
Author: cuilei
Version: 2.0
"""

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class ConfigManager:
    """
    统一配置管理器 - 适用于所有 Agent

    通过参数传递配置，不再依赖配置文件。

    Args:
        api_base: OpenAI API 基础 URL (必需)
        api_key: OpenAI API 密钥 (必需)
        model: 模型名称 (必需)
        output_dir: 项目输出目录 (可选，默认 "./outputs"，会转换为绝对路径)
        max_tokens: 最大 token 数 (可选，None 表示无限制)
        language: 语言设置 (可选，默认 "zh")
        enable_streaming: 是否启用流式输出 (可选，默认 True)

    Example:
        >>> config = ConfigManager(
        ...     api_base="https://api.siliconflow.cn/v1",
        ...     api_key="sk-your-key-here",
        ...     model="gpt-4o",
        ...     output_dir="./outputs",
        ...     language="zh",
        ...     enable_streaming=True
        ... )
        >>> cache_dir = config.get_cache_dir("celltypeMainagent")
    """

    # LLM 配置（必需）
    api_base: str
    api_key: str
    model: str

    # 项目配置（可选）
    output_dir: Path = Path("./outputs")
    max_tokens: Optional[int] = None  # None = 无限制
    language: str = "zh"
    enable_streaming: bool = True
    enable_thinking: bool = False

    # 这些属性由 __post_init__ 自动设置
    cache_dir: Path = None
    logs_dir: Path = None
    results_dir: Path = None
    temp_dir: Path = None
    downloads_dir: Path = None

    # 兼容旧代码的属性别名
    openai_api_base: str = None
    openai_api_key: str = None
    openai_model: str = None

    def __post_init__(self):
        """初始化后处理：创建目录结构和设置别名"""

        # 1. 转换为绝对路径
        if isinstance(self.output_dir, str):
            self.output_dir = Path(self.output_dir)

        # 确保是绝对路径
        self.output_dir = self.output_dir.resolve()

        # 2. 创建子目录结构
        self.cache_dir = self.output_dir / "cache"
        self.logs_dir = self.output_dir / "logs"
        self.results_dir = self.output_dir / "results"
        self.temp_dir = self.output_dir / "temp"
        self.downloads_dir = self.output_dir / "downloads"

        # 3. 创建所有必要的目录
        for dir_path in [
            self.output_dir,
            self.cache_dir,
            self.logs_dir,
            self.results_dir,
            self.temp_dir,
            self.downloads_dir
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)

        # 4. 为每个 Agent 创建专门的缓存目录
        for agent_name in ["celltypeMainagent", "celltypeSubagent", "celltypeDataAgent", "celltypeAppAgent"]:
            agent_cache_dir = self.cache_dir / agent_name
            agent_cache_dir.mkdir(parents=True, exist_ok=True)

        # 5. 设置兼容旧代码的属性别名
        self.openai_api_base = self.api_base
        self.openai_api_key = self.api_key
        self.openai_model = self.model

        # 6. 验证必需参数
        if not self.api_base or not self.api_base.strip():
            raise ValueError("api_base 不能为空")
        if not self.api_key or not self.api_key.strip():
            raise ValueError("api_key 不能为空")
        if not self.model or not self.model.strip():
            raise ValueError("model 不能为空")

    def get_cache_dir(self, subdir: str = "") -> Path:
        """
        获取缓存目录路径

        Args:
            subdir: 子目录名称（可选）

        Returns:
            Path: 缓存目录的绝对路径

        Example:
            >>> config.get_cache_dir("celltypeMainagent")
            PosixPath('/path/to/outputs/cache/celltypeMainagent')
        """
        if subdir:
            cache_path = self.cache_dir / subdir
            cache_path.mkdir(parents=True, exist_ok=True)
            return cache_path
        return self.cache_dir

    def get_logs_dir(self, subdir: str = "") -> Path:
        """
        获取日志目录路径

        Args:
            subdir: 子目录名称（可选）

        Returns:
            Path: 日志目录的绝对路径

        Example:
            >>> config.get_logs_dir("llm/main_agent")
            PosixPath('/path/to/outputs/logs/llm/main_agent')
        """
        if subdir:
            logs_path = self.logs_dir / subdir
            logs_path.mkdir(parents=True, exist_ok=True)
            return logs_path
        return self.logs_dir

    def get_results_dir(self, subdir: str = "") -> Path:
        """
        获取结果目录路径

        Args:
            subdir: 子目录名称（可选）

        Returns:
            Path: 结果目录的绝对路径

        Example:
            >>> config.get_results_dir("celltypeMainagent")
            PosixPath('/path/to/outputs/results/celltypeMainagent')
        """
        if subdir:
            results_path = self.results_dir / subdir
            results_path.mkdir(parents=True, exist_ok=True)
            return results_path
        return self.results_dir

    def get_downloads_dir(self, subdir: str = "") -> Path:
        """
        获取下载目录路径

        Args:
            subdir: 子目录名称（可选）

        Returns:
            Path: 下载目录的绝对路径

        Example:
            >>> config.get_downloads_dir("databases")
            PosixPath('/path/to/outputs/downloads/databases')
        """
        if subdir:
            downloads_path = self.downloads_dir / subdir
            downloads_path.mkdir(parents=True, exist_ok=True)
            return downloads_path
        return self.downloads_dir

    def get_temp_dir(self, subdir: str = "") -> Path:
        """
        获取临时目录路径

        Args:
            subdir: 子目录名称（可选）

        Returns:
            Path: 临时目录的绝对路径

        Example:
            >>> config.get_temp_dir("conversions")
            PosixPath('/path/to/outputs/temp/conversions')
        """
        if subdir:
            temp_path = self.temp_dir / subdir
            temp_path.mkdir(parents=True, exist_ok=True)
            return temp_path
        return self.temp_dir

    @property
    def project_root(self) -> Path:
        """
        获取项目根目录（output_dir 的父目录）

        Returns:
            Path: 项目根目录的绝对路径
        """
        return self.output_dir.parent

    @classmethod
    def from_env(cls, output_dir: Optional[str] = None) -> "ConfigManager":
        """
        从环境变量创建配置管理器

        Args:
            output_dir: 输出目录（可选，默认使用环境变量或 "./outputs"）

        Returns:
            ConfigManager: 配置管理器实例

        Raises:
            ValueError: 如果必需的环境变量未设置

        Example:
            >>> os.environ["OPENAI_API_BASE"] = "https://api.siliconflow.cn/v1"
            >>> os.environ["OPENAI_API_KEY"] = "sk-xxx"
            >>> os.environ["OPENAI_MODEL"] = "gpt-4o"
            >>> config = ConfigManager.from_env()
        """
        api_base = os.getenv("OPENAI_API_BASE")
        api_key = os.getenv("OPENAI_API_KEY")
        model = os.getenv("OPENAI_MODEL")

        if not api_base:
            raise ValueError("环境变量 OPENAI_API_BASE 未设置")
        if not api_key:
            raise ValueError("环境变量 OPENAI_API_KEY 未设置")
        if not model:
            raise ValueError("环境变量 OPENAI_MODEL 未设置")

        if output_dir is None:
            output_dir = os.getenv("CELLTYPE_OUTPUT_DIR", "./outputs")

        max_tokens_str = os.getenv("CELLTYPE_MAX_TOKENS")
        max_tokens = int(max_tokens_str) if max_tokens_str else None

        return cls(
            api_base=api_base,
            api_key=api_key,
            model=model,
            output_dir=output_dir,
            max_tokens=max_tokens,
            language=os.getenv("CELLTYPE_LANGUAGE", "zh"),
            enable_streaming=os.getenv("CELLTYPE_ENABLE_STREAMING", "true").lower() == "true"
        )

    def __repr__(self) -> str:
        """返回配置的字符串表示"""
        return (
            f"ConfigManager(\n"
            f"  api_base='{self.api_base}',\n"
            f"  model='{self.model}',\n"
            f"  output_dir='{self.output_dir}',\n"
            f"  language='{self.language}',\n"
            f"  enable_streaming={self.enable_streaming},\n"
            f"  max_tokens={self.max_tokens}\n"
            f")"
        )


# 便捷函数 - 保持向后兼容但提示迁移
def _deprecated_function(func_name: str):
    """生成废弃函数的错误提示"""
    raise RuntimeError(
        f"\n{'='*80}\n"
        f"❌ {func_name}() 已废弃\n"
        f"{'='*80}\n\n"
        f"配置系统已重构为基于参数传递，不再使用配置文件。\n\n"
        f"旧方式（已废弃）:\n"
        f"  from agentype.config import get_global_config\n"
        f"  global_config = get_global_config()\n"
        f"  api_base = global_config.llm.api_base\n\n"
        f"新方式（推荐）:\n"
        f"  from agentype.config import ConfigManager\n"
        f"  config = ConfigManager(\n"
        f"      api_base='https://api.siliconflow.cn/v1',\n"
        f"      api_key='sk-your-key',\n"
        f"      model='gpt-4o',\n"
        f"      output_dir='./outputs'\n"
        f"  )\n\n"
        f"或从环境变量加载:\n"
        f"  config = ConfigManager.from_env()\n\n"
        f"详情请参阅文档: docs/CONFIGURATION.md\n"
        f"{'='*80}\n"
    )


def get_global_config():
    """废弃的函数 - 提示用户迁移到新的配置方式"""
    _deprecated_function("get_global_config")


def check_and_update_config(*args, **kwargs):
    """废弃的函数 - 提示用户迁移到新的配置方式"""
    _deprecated_function("check_and_update_config")


def get_cache_dir(*args, **kwargs):
    """废弃的函数 - 提示用户迁移到新的配置方式"""
    _deprecated_function("get_cache_dir")


def get_logs_dir(*args, **kwargs):
    """废弃的函数 - 提示用户迁移到新的配置方式"""
    _deprecated_function("get_logs_dir")


def get_results_dir(*args, **kwargs):
    """废弃的函数 - 提示用户迁移到新的配置方式"""
    _deprecated_function("get_results_dir")


def get_downloads_dir(*args, **kwargs):
    """废弃的函数 - 提示用户迁移到新的配置方式"""
    _deprecated_function("get_downloads_dir")


def get_temp_dir(*args, **kwargs):
    """废弃的函数 - 提示用户迁移到新的配置方式"""
    _deprecated_function("get_temp_dir")


def get_paths(*args, **kwargs):
    """废弃的函数 - 提示用户迁移到新的配置方式"""
    _deprecated_function("get_paths")
