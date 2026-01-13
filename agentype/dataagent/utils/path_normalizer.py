#!/usr/bin/env python3
"""
agentype - 文件路径标准化工具
Author: cuilei
Version: 1.0
"""

import os
from pathlib import Path
from typing import Union, Optional, Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)

class PathNormalizer:
    """文件路径标准化工具类"""
    
    def __init__(self, base_dir: Optional[Union[str, Path]] = None):
        """
        初始化路径标准化器
        
        Args:
            base_dir: 基准目录，默认为当前工作目录
        """
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()
        self.base_dir = self.base_dir.resolve()
    
    def normalize_to_absolute_path(self, file_path: Union[str, Path]) -> str:
        """
        将相对路径转换为绝对路径
        
        Args:
            file_path: 输入的文件路径（相对或绝对）
            
        Returns:
            str: 标准化的绝对路径
        """
        if not file_path:
            return ""
        
        try:
            path_obj = Path(file_path)
            
            # 如果已经是绝对路径，直接resolve
            if path_obj.is_absolute():
                return str(path_obj.resolve())
            
            # 相对路径，基于base_dir转换
            absolute_path = (self.base_dir / path_obj).resolve()
            return str(absolute_path)
            
        except Exception as e:
            logger.warning(f"路径标准化失败 {file_path}: {e}")
            return str(file_path)
    
    def validate_and_normalize_paths(self, **file_paths) -> Dict[str, str]:
        """
        验证并标准化多个文件路径
        
        Args:
            **file_paths: 键值对形式的文件路径，如 rds_file="data.rds"
            
        Returns:
            Dict[str, str]: 标准化后的文件路径字典
        """
        normalized_paths = {}
        
        for key, path in file_paths.items():
            if path and isinstance(path, (str, Path)):
                normalized_path = self.normalize_to_absolute_path(path)
                normalized_paths[key] = normalized_path
                
                # 记录路径是否存在
                if Path(normalized_path).exists():
                    logger.info(f"✅ 文件存在: {key} -> {normalized_path}")
                else:
                    logger.warning(f"⚠️  文件不存在: {key} -> {normalized_path}")
            else:
                normalized_paths[key] = ""
        
        return normalized_paths
    
    def get_all_file_paths(self,
                          rds_file: Optional[str] = None,
                          h5ad_file: Optional[str] = None,
                          h5_file: Optional[str] = None,
                          marker_genes_json: Optional[str] = None,
                          **additional_files) -> Dict[str, str]:
        """
        获取所有文件的标准化绝对路径

        Args:
            rds_file: RDS文件路径
            h5ad_file: H5AD文件路径
            h5_file: H5文件路径
            marker_genes_json: Marker基因JSON文件路径
            **additional_files: 其他额外文件

        Returns:
            Dict[str, str]: 所有文件的绝对路径
        """
        all_files = {
            'rds_file': rds_file,
            'h5ad_file': h5ad_file,
            'h5_file': h5_file,
            'marker_genes_json': marker_genes_json
        }
        
        # 添加额外文件
        all_files.update(additional_files)
        
        return self.validate_and_normalize_paths(**all_files)
    
    def detect_platform_and_format(self, path: str) -> str:
        """
        检测当前平台并格式化路径显示
        
        Args:
            path: 输入路径
            
        Returns:
            str: 格式化后的路径字符串，包含平台信息
        """
        if not path:
            return ""
        
        normalized_path = self.normalize_to_absolute_path(path)
        
        # 检测平台
        platform_info = ""
        if os.name == 'nt':  # Windows
            platform_info = "Windows"
        elif os.name == 'posix':
            if 'darwin' in os.sys.platform.lower():  # macOS
                platform_info = "macOS" 
            else:  # Linux and others
                platform_info = "Linux"
        
        return f"{normalized_path} ({platform_info})"
    
    def get_file_info(self, file_path: str) -> Dict[str, any]:
        """
        获取文件详细信息
        
        Args:
            file_path: 文件路径
            
        Returns:
            Dict: 包含文件信息的字典
        """
        if not file_path:
            return {
                'path': '',
                'exists': False,
                'absolute_path': '',
                'size': 0,
                'platform_path': ''
            }
        
        absolute_path = self.normalize_to_absolute_path(file_path)
        path_obj = Path(absolute_path)
        
        return {
            'path': str(file_path),
            'exists': path_obj.exists(),
            'absolute_path': absolute_path,
            'size': path_obj.stat().st_size if path_obj.exists() else 0,
            'platform_path': self.detect_platform_and_format(file_path)
        }

# 全局路径标准化器实例
path_normalizer = PathNormalizer()

def normalize_file_paths(rds_file: Optional[str] = None,
                        h5ad_file: Optional[str] = None,
                        h5_file: Optional[str] = None,
                        marker_genes_json: Optional[str] = None,
                        **kwargs) -> Dict[str, str]:
    """
    便捷函数：标准化所有文件路径

    Args:
        rds_file: RDS文件路径
        h5ad_file: H5AD文件路径
        h5_file: H5文件路径
        marker_genes_json: Marker基因JSON文件路径
        **kwargs: 其他文件路径

    Returns:
        Dict[str, str]: 标准化后的绝对路径字典
    """
    return path_normalizer.get_all_file_paths(
        rds_file=rds_file,
        h5ad_file=h5ad_file,
        h5_file=h5_file,
        marker_genes_json=marker_genes_json,
        **kwargs
    )

def get_absolute_path(file_path: Union[str, Path]) -> str:
    """
    便捷函数：获取单个文件的绝对路径
    
    Args:
        file_path: 文件路径
        
    Returns:
        str: 绝对路径
    """
    return path_normalizer.normalize_to_absolute_path(file_path)