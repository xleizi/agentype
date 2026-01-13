#!/usr/bin/env python3
"""
agentype - 通用工具函数模块
Author: cuilei
Version: 1.0
"""

import os
import json
import hashlib
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

# 全局时间戳管理器
class GlobalTimestampManager:
    """全局时间戳管理器，用于生成统一的时间戳"""
    
    _current_timestamp = None
    
    @classmethod
    def generate_new_timestamp(cls) -> str:
        """
        生成新的时间戳
        
        Returns:
            格式为 YYYYMMDD_HHMMSS 的时间戳字符串
        """
        cls._current_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return cls._current_timestamp
    
    @classmethod
    def get_current_timestamp(cls) -> Optional[str]:
        """
        获取当前时间戳
        
        Returns:
            当前时间戳，如果没有生成过则返回None
        """
        return cls._current_timestamp
    
    @classmethod
    def get_or_generate_timestamp(cls) -> str:
        """
        获取当前时间戳，如果不存在则生成新的
        
        Returns:
            时间戳字符串
        """
        if cls._current_timestamp is None:
            return cls.generate_new_timestamp()
        return cls._current_timestamp

def safe_json_load(file_path: Union[str, Path], default: Any = None) -> Any:
    """
    安全地加载JSON文件
    
    Args:
        file_path: JSON文件路径
        default: 加载失败时返回的默认值
        
    Returns:
        JSON数据或默认值
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, IOError) as e:
        logging.warning(f"加载JSON文件失败 {file_path}: {e}")
        return default

def safe_json_save(data: Any, file_path: Union[str, Path], indent: int = 2) -> bool:
    """
    安全地保存JSON文件
    
    Args:
        data: 要保存的数据
        file_path: 保存路径
        indent: JSON缩进
        
    Returns:
        是否保存成功
    """
    try:
        # 确保目录存在
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        return True
    except (IOError, TypeError) as e:
        logging.error(f"保存JSON文件失败 {file_path}: {e}")
        return False

def calculate_file_hash(file_path: Union[str, Path], algorithm: str = "md5") -> Optional[str]:
    """
    计算文件哈希值
    
    Args:
        file_path: 文件路径
        algorithm: 哈希算法，支持 md5, sha1, sha256
        
    Returns:
        文件哈希值，计算失败返回None
    """
    try:
        hash_algo = hashlib.new(algorithm)
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_algo.update(chunk)
        
        return hash_algo.hexdigest()
    except (FileNotFoundError, ValueError, IOError) as e:
        logging.warning(f"计算文件哈希失败 {file_path}: {e}")
        return None

def format_file_size(size_bytes: int) -> str:
    """
    格式化文件大小
    
    Args:
        size_bytes: 文件大小（字节）
        
    Returns:
        格式化后的文件大小字符串
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    return f"{size:.1f} {size_names[i]}"

def get_file_info(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    获取文件详细信息
    
    Args:
        file_path: 文件路径
        
    Returns:
        文件信息字典
    """
    path = Path(file_path)
    
    if not path.exists():
        return {
            "exists": False,
            "path": str(path),
            "error": "文件不存在"
        }
    
    try:
        stat = path.stat()
        
        return {
            "exists": True,
            "path": str(path.resolve()),
            "name": path.name,
            "size_bytes": stat.st_size,
            "size_formatted": format_file_size(stat.st_size),
            "created_time": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "is_file": path.is_file(),
            "is_directory": path.is_dir(),
            "suffix": path.suffix,
            "parent": str(path.parent)
        }
    except (OSError, IOError) as e:
        return {
            "exists": True,
            "path": str(path),
            "error": f"获取文件信息失败: {e}"
        }

def ensure_directory(directory_path: Union[str, Path]) -> bool:
    """
    确保目录存在
    
    Args:
        directory_path: 目录路径
        
    Returns:
        目录是否存在或创建成功
    """
    try:
        Path(directory_path).mkdir(parents=True, exist_ok=True)
        return True
    except (OSError, IOError) as e:
        logging.error(f"创建目录失败 {directory_path}: {e}")
        return False

def clean_filename(filename: str, replacement: str = "_") -> str:
    """
    清理文件名，移除非法字符
    
    Args:
        filename: 原始文件名
        replacement: 替换非法字符的字符
        
    Returns:
        清理后的文件名
    """
    # 定义非法字符
    illegal_chars = '<>:"/\\|?*'
    
    cleaned = filename
    for char in illegal_chars:
        cleaned = cleaned.replace(char, replacement)
    
    # 移除控制字符
    cleaned = ''.join(char for char in cleaned if ord(char) >= 32)
    
    # 移除首尾空格和点
    cleaned = cleaned.strip(' .')
    
    # 确保不为空
    if not cleaned:
        cleaned = "unnamed"
    
    return cleaned

def validate_file_extension(file_path: Union[str, Path], allowed_extensions: List[str]) -> bool:
    """
    验证文件扩展名
    
    Args:
        file_path: 文件路径
        allowed_extensions: 允许的扩展名列表（包含点，如 ['.json', '.txt']）
        
    Returns:
        文件扩展名是否合法
    """
    path = Path(file_path)
    return path.suffix.lower() in [ext.lower() for ext in allowed_extensions]

def merge_configs(*configs: Dict[str, Any]) -> Dict[str, Any]:
    """
    合并多个配置字典
    
    Args:
        *configs: 要合并的配置字典
        
    Returns:
        合并后的配置字典
    """
    merged = {}
    
    for config in configs:
        if not isinstance(config, dict):
            continue
            
        for key, value in config.items():
            if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
                # 递归合并嵌套字典
                merged[key] = merge_configs(merged[key], value)
            else:
                merged[key] = value
    
    return merged

def setup_logging(
    level: int = logging.INFO,
    format_string: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    log_file: Optional[Union[str, Path]] = None
) -> logging.Logger:
    """
    设置日志配置
    
    Args:
        level: 日志级别
        format_string: 日志格式字符串
        log_file: 可选的日志文件路径
        
    Returns:
        配置好的logger对象
    """
    # 创建logger
    logger = logging.getLogger("celltypeAppAgent")
    logger.setLevel(level)
    
    # 清除现有handlers
    logger.handlers.clear()
    
    # 创建formatter
    formatter = logging.Formatter(format_string)
    
    # 添加console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 添加file handler（如果指定了日志文件）
    if log_file:
        log_path = Path(log_file)
        ensure_directory(log_path.parent)
        
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

class ProgressTracker:
    """进度跟踪器"""
    
    def __init__(self, total_steps: int, description: str = "Processing"):
        self.total_steps = total_steps
        self.current_step = 0
        self.description = description
        self.start_time = datetime.now()
    
    def update(self, step: int = None, message: str = None):
        """更新进度"""
        if step is not None:
            self.current_step = step
        else:
            self.current_step += 1
        
        progress = (self.current_step / self.total_steps) * 100
        elapsed = datetime.now() - self.start_time
        
        status_message = f"{self.description}: {self.current_step}/{self.total_steps} ({progress:.1f}%)"
        if message:
            status_message += f" - {message}"
        
        logging.info(status_message)
    
    def complete(self, message: str = "完成"):
        """标记完成"""
        elapsed = datetime.now() - self.start_time
        logging.info(f"{self.description} {message}，耗时: {elapsed}")