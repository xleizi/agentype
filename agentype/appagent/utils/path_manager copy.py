#!/usr/bin/env python3
"""
agentype - 路径管理工具模块
Author: cuilei
Version: 1.0
"""

import os
from pathlib import Path
from typing import Dict, Optional, Union
import logging

# 设置日志
logger = logging.getLogger(__name__)


def normalize_path(file_path: Union[str, Path, None]) -> str:
    """
    标准化文件路径，转换为绝对路径
    
    Args:
        file_path: 输入的文件路径
        
    Returns:
        标准化后的绝对路径字符串，如果输入为空则返回空字符串
    """
    if not file_path:
        return ""
    
    try:
        # 转换为Path对象
        path = Path(file_path)
        
        # 展开用户目录（~）
        if str(path).startswith('~'):
            path = path.expanduser()
        
        # 转换为绝对路径并解析所有符号链接
        absolute_path = path.resolve()
        
        return str(absolute_path)
        
    except Exception as e:
        logger.warning(f"标准化路径失败 {file_path}: {e}")
        return str(file_path) if file_path else ""


def get_absolute_paths(**kwargs) -> Dict[str, str]:
    """
    获取多个文件路径的标准化绝对路径
    
    Args:
        **kwargs: 键值对，值为文件路径
        
    Returns:
        包含标准化绝对路径的字典
    """
    result = {}
    
    for key, path in kwargs.items():
        if path is not None:
            result[key] = normalize_path(path)
        else:
            result[key] = ""
    
    return result


def validate_path_exists(file_path: str) -> bool:
    """
    验证路径是否存在
    
    Args:
        file_path: 文件路径
        
    Returns:
        路径是否存在
    """
    if not file_path:
        return False
    
    try:
        return Path(file_path).exists()
    except Exception:
        return False


def get_file_extension(file_path: str) -> str:
    """
    获取文件扩展名
    
    Args:
        file_path: 文件路径
        
    Returns:
        文件扩展名（包含点，如'.json'），如果无扩展名则返回空字符串
    """
    if not file_path:
        return ""
    
    try:
        return Path(file_path).suffix.lower()
    except Exception:
        return ""


def get_parent_directory(file_path: str) -> str:
    """
    获取文件的父目录
    
    Args:
        file_path: 文件路径
        
    Returns:
        父目录的绝对路径
    """
    if not file_path:
        return ""
    
    try:
        normalized_path = normalize_path(file_path)
        return str(Path(normalized_path).parent)
    except Exception as e:
        logger.warning(f"获取父目录失败 {file_path}: {e}")
        return ""


def ensure_directory_exists(directory_path: str) -> bool:
    """
    确保目录存在，如果不存在则创建
    
    Args:
        directory_path: 目录路径
        
    Returns:
        目录是否存在或创建成功
    """
    if not directory_path:
        return False
    
    try:
        Path(directory_path).mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"创建目录失败 {directory_path}: {e}")
        return False


def get_relative_path(file_path: str, base_path: str = None) -> str:
    """
    获取相对于基准路径的相对路径
    
    Args:
        file_path: 文件路径
        base_path: 基准路径，默认为当前工作目录
        
    Returns:
        相对路径字符串
    """
    if not file_path:
        return ""
    
    try:
        file_path = normalize_path(file_path)
        
        if base_path:
            base_path = normalize_path(base_path)
        else:
            base_path = str(Path.cwd())
        
        return str(Path(file_path).relative_to(base_path))
        
    except ValueError:
        # 如果无法计算相对路径，返回绝对路径
        return file_path
    except Exception as e:
        logger.warning(f"计算相对路径失败 {file_path}: {e}")
        return file_path


def is_file_type(file_path: str, expected_extensions: list) -> bool:
    """
    检查文件是否为指定类型
    
    Args:
        file_path: 文件路径
        expected_extensions: 预期的扩展名列表（如['.json', '.txt']）
        
    Returns:
        文件是否为指定类型
    """
    if not file_path or not expected_extensions:
        return False
    
    file_ext = get_file_extension(file_path)
    return file_ext in [ext.lower() for ext in expected_extensions]


def get_safe_filename(filename: str, max_length: int = 255) -> str:
    """
    生成安全的文件名，移除非法字符并限制长度
    
    Args:
        filename: 原始文件名
        max_length: 最大长度
        
    Returns:
        安全的文件名
    """
    if not filename:
        return "unnamed_file"
    
    # 移除或替换非法字符
    illegal_chars = '<>:"/\\|?*'
    safe_name = filename
    
    for char in illegal_chars:
        safe_name = safe_name.replace(char, '_')
    
    # 移除控制字符
    safe_name = ''.join(char for char in safe_name if ord(char) >= 32)
    
    # 移除首尾空格和点
    safe_name = safe_name.strip(' .')
    
    # 限制长度
    if len(safe_name) > max_length:
        # 保留扩展名
        path = Path(safe_name)
        stem = path.stem
        suffix = path.suffix
        
        max_stem_length = max_length - len(suffix)
        if max_stem_length > 0:
            safe_name = stem[:max_stem_length] + suffix
        else:
            safe_name = safe_name[:max_length]
    
    # 确保不为空
    if not safe_name:
        safe_name = "unnamed_file"
    
    return safe_name


def join_paths(*paths) -> str:
    """
    安全地连接多个路径
    
    Args:
        *paths: 要连接的路径组件
        
    Returns:
        连接后的标准化绝对路径
    """
    if not paths:
        return ""
    
    try:
        # 过滤掉空路径
        valid_paths = [p for p in paths if p]
        
        if not valid_paths:
            return ""
        
        # 使用Path对象连接路径
        result_path = Path(valid_paths[0])
        for path in valid_paths[1:]:
            result_path = result_path / path
        
        return normalize_path(result_path)
        
    except Exception as e:
        logger.error(f"连接路径失败 {paths}: {e}")
        return ""