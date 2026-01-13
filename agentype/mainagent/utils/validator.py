#!/usr/bin/env python3
"""
agentype - MainAgent验证器
Author: cuilei
Version: 2.0

MainAgent的验证器，继承基类并保留环境验证方法。
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional
from agentype.common.base_validator import BaseValidator


@dataclass
class ValidationUtils(BaseValidator):
    """MainAgent验证工具类

    继承BaseValidator获得所有共享验证逻辑，
    同时保留MainAgent特有的环境和输入验证方法。
    """
    language: str = "zh"

    def _ok(self, ok: bool, message: str, **extra) -> Dict:
        """构建验证结果字典"""
        d = {"ok": ok, "message": message}
        d.update(extra)
        return d

    def validate_environment(self) -> Dict:
        """环境验证（MainAgent特有）

        验证所需的子包是否可导入。

        Returns:
            验证结果字典
        """
        try:
            # 确保所需子包可导入
            __import__("celltypeSubagent")
            __import__("celltypeDataAgent")
            __import__("celltypeAppAgent")
            return self._ok(True, "environment ready")
        except Exception as e:
            return self._ok(False, f"import error: {e}")

    def validate_gene_analysis_input(self, gene_list: str, tissue_type: Optional[str] = None) -> Dict:
        """基因分析输入验证（MainAgent特有）

        Args:
            gene_list: 逗号分隔的基因列表
            tissue_type: 组织类型（可选）

        Returns:
            验证结果字典
        """
        if not gene_list or not isinstance(gene_list, str):
            return self._ok(False, "gene_list must be a non-empty string")

        # 轻量级格式检查
        items = [g.strip() for g in gene_list.split(",") if g.strip()]
        if not items:
            return self._ok(False, "no valid genes after parsing")

        return self._ok(True, "valid", genes=items, tissue=tissue_type)

    def validate_data_input(self, input_path: str) -> Dict:
        """数据输入验证（MainAgent特有）

        Args:
            input_path: 输入文件路径

        Returns:
            验证结果字典
        """
        try:
            p = Path(input_path)
            if not p.exists():
                return self._ok(False, "file not found", path=str(p))
            if p.is_dir():
                return self._ok(False, "path is a directory", path=str(p))
            return self._ok(True, "ok", path=str(p))
        except Exception as e:
            return self._ok(False, f"error: {e}")
