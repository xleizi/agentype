#!/usr/bin/env python3
"""
agentype - 配置管理
Author: cuilei
Version: 2.0 - 添加路径管理功能
"""

import os
from pathlib import Path

class ConfigManager:
    """配置管理类"""

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

        # 数据处理相关的必需配置
        self.pval_threshold = 0.05
        self.max_retries = 3

        # 路径配置：必须显式提供 output_dir
        if output_dir:
            self.output_dir = Path(output_dir).resolve()
        else:
            raise ValueError(
                "必须提供 output_dir 参数。"
                "ConfigManager 不再支持自动使用当前工作目录，以避免文件保存到错误位置。"
            )

        # 派生路径（基于output_dir）
        self.results_dir = self.output_dir / "results" / "celltypeDataAgent"
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
            self.cache_dir = str(self.output_dir / "cache" / "celltypeDataAgent")

        if log_dir:
            self.log_dir = log_dir
        else:
            self.log_dir = str(self.output_dir / "logs")

        # 设置代理环境变量
        if self.proxy:
            os.environ['HTTP_PROXY'] = self.proxy
            os.environ['HTTPS_PROXY'] = self.proxy

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
