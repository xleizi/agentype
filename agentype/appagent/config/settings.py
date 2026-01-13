#!/usr/bin/env python3
"""
agentype - 配置管理
Author: cuilei
Version: 2.0 - 添加路径管理功能
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any

class ConfigManager:
    """CellType App Agent 配置管理类"""

    def __init__(self,
                 openai_api_base: str = None,
                 openai_api_key: str = None,
                 openai_model: str = "gpt-4o",
                 proxy: str = None,
                 cache_dir: str = None,
                 log_dir: str = None,
                 output_dir: str = None,
                 enable_thinking: bool = False):
        self.openai_api_base = openai_api_base
        self.openai_api_key = openai_api_key
        self.openai_model = openai_model
        self.proxy = proxy
        self.enable_thinking = enable_thinking

        # 路径配置：必须显式提供 output_dir
        if output_dir:
            self.output_dir = Path(output_dir).resolve()
        else:
            raise ValueError(
                "必须提供 output_dir 参数。"
                "ConfigManager 不再支持自动使用当前工作目录，以避免文件保存到错误位置。"
            )

        # 派生路径（基于output_dir）
        self.results_dir = self.output_dir / "results" / "celltypeAppAgent"
        self.downloads_dir = self.output_dir / "downloads"
        self.temp_dir = self.output_dir / "temp"

        # 创建必要目录
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # cache_dir 和 log_dir：优先使用传入值，否则基于output_dir
        if cache_dir:
            self.cache_dir = cache_dir
        else:
            self.cache_dir = str(self.output_dir / "cache" / "celltypeAppAgent")

        if log_dir:
            self.log_dir = log_dir
        else:
            self.log_dir = str(self.output_dir / "logs")

        # LLM日志目录（基于log_dir）
        self.llm_log_dir = str(Path(self.log_dir) / "llm" / "app_agent")
        Path(self.llm_log_dir).mkdir(parents=True, exist_ok=True)

        # SingleR 配置
        self.singler_config = {
            "default_dataset": "HumanPrimaryCellAtlasData",
            "output_format": "json"
        }

        # scType 配置
        self.sctype_config = {
            "default_tissue": "Immune system",
            "output_format": "json"
        }

        # CellTypist 配置
        self.celltypist_config = {
            "auto_detect_species": True,
            "default_model": None,  # 自动检测
            "output_format": "json"
        }

        # 注释流水线配置
        self.pipeline_config = {
            "max_retries": 3,
            "timeout_seconds": 300,
            "enable_parallel": False,  # 是否并行执行三种方法
            "save_intermediate_results": True
        }

        # 物种检测配置
        self.species_detection_config = {
            "confidence_threshold": 0.7,
            "default_species": "Human",
            "supported_species": ["Human", "Mouse"]
        }

        # 文件处理配置
        self.file_config = {
            "max_file_size_mb": 1000,
            "supported_rds_extensions": [".rds", ".RDS"],
            "supported_h5ad_extensions": [".h5ad", ".H5AD"],
            "supported_json_extensions": [".json", ".JSON"]
        }

        # API 配置（如果启用 REST API）
        self.api_config = {
            "host": "0.0.0.0",
            "port": 8080,
            "debug": False,
            "cors_enabled": True
        }

        # 国际化配置
        self.i18n_config = {
            "default_language": "zh",
            "supported_languages": ["zh", "en"],
            "locale_dir": "locales"
        }

        # 设置代理环境变量
        if self.proxy:
            os.environ['HTTP_PROXY'] = self.proxy
            os.environ['HTTPS_PROXY'] = self.proxy

    def get_cache_path(self, filename: str = None) -> str:
        """获取缓存文件路径"""
        cache_path = os.path.join(self.cache_dir)
        os.makedirs(cache_path, exist_ok=True)

        if filename:
            return os.path.join(cache_path, filename)
        return cache_path

    def get_log_path(self, filename: str = None) -> str:
        """获取日志文件路径"""
        log_path = os.path.join(self.log_dir)
        os.makedirs(log_path, exist_ok=True)

        if filename:
            return os.path.join(log_path, filename)
        return log_path

    def get_llm_log_path(self, filename: str = None) -> str:
        """获取LLM日志文件路径"""
        llm_log_path = os.path.join(self.llm_log_dir)
        os.makedirs(llm_log_path, exist_ok=True)

        if filename:
            return os.path.join(llm_log_path, filename)
        return llm_log_path

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

    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典格式"""
        return {
            "openai_api_base": self.openai_api_base,
            "openai_api_key": "***" if self.openai_api_key else None,
            "openai_model": self.openai_model,
            "proxy": self.proxy,
            "cache_dir": self.cache_dir,
            "log_dir": self.log_dir,
            "llm_log_dir": self.llm_log_dir,
            "output_dir": str(self.output_dir),
            "results_dir": str(self.results_dir),
            "downloads_dir": str(self.downloads_dir),
            "temp_dir": str(self.temp_dir),
            "singler_config": self.singler_config,
            "sctype_config": self.sctype_config,
            "celltypist_config": self.celltypist_config,
            "pipeline_config": self.pipeline_config,
            "species_detection_config": self.species_detection_config,
            "file_config": self.file_config,
            "api_config": self.api_config,
            "i18n_config": self.i18n_config
        }


# 全局配置实例（不再在模块级初始化，避免导入时出错）
# 请在需要时显式创建 ConfigManager 实例
config = None
