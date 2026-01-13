#!/usr/bin/env python3
"""
agentype - AppAgent缓存配置管理模块（兼容性层）
Author: cuilei
Version: 2.0 - 移除对 GlobalConfig 的依赖
"""

import os
from pathlib import Path
from typing import Optional


# 默认缓存路径配置已移除 - 现在必须通过 config 参数传递
# 这确保所有文件保存到用户指定的 output_dir 而不是包目录


def init_cache(cache_dir: Optional[str] = None, config=None) -> Path:
    """初始化缓存目录

    Args:
        cache_dir: 缓存目录路径（已废弃，保留用于向后兼容）
        config: ConfigManager 实例（必需）

    Returns:
        缓存目录的Path对象

    Raises:
        ValueError: 如果未提供 config 参数
    """
    if config is not None:
        # 使用提供的 config
        cache_path = Path(config.cache_dir)
    elif cache_dir is not None:
        # 向后兼容：使用传入的 cache_dir
        cache_path = Path(cache_dir)
    else:
        # 不再使用默认路径！要求明确传递配置
        raise ValueError(
            "必须提供 config 参数。"
            "请在 MCP Server 启动时调用: init_cache(config=_CONFIG)"
        )

    # 确保目录存在
    cache_path.mkdir(parents=True, exist_ok=True)
    return cache_path


def set_cache_dir(cache_dir: str) -> Path:
    """设置缓存目录（已废弃）

    Args:
        cache_dir: 缓存目录路径

    Returns:
        缓存目录的Path对象

    注意: 此函数已废弃，请使用 ConfigManager.cache_dir
    """
    raise DeprecationWarning(
        "set_cache_dir() 已废弃，请使用 ConfigManager.cache_dir"
    )


def get_cache_dir(subdir: str = "", config=None) -> Path:
    """获取缓存目录路径

    Args:
        subdir: 子目录名称
        config: ConfigManager 实例（必需）

    Returns:
        缓存目录路径

    Raises:
        ValueError: 如果未提供 config 参数
    """
    if config is None:
        raise ValueError(
            "必须提供 config 参数。"
            "请传递 ConfigManager 实例而不是使用硬编码路径"
        )

    # 使用 config 提供的路径
    if subdir:
        cache_path = Path(config.cache_dir) / subdir
    else:
        cache_path = Path(config.cache_dir)

    # 确保目录存在
    cache_path.mkdir(parents=True, exist_ok=True)
    return cache_path


def get_cache_subdir(subdir: str) -> Path:
    """获取缓存子目录路径（兼容性函数）

    Args:
        subdir: 子目录名称

    Returns:
        缓存子目录路径
    """
    return get_cache_dir(subdir)


def get_cache_info() -> dict:
    """获取当前缓存配置信息

    Returns:
        缓存配置信息字典
    """
    base_dir = DEFAULT_CACHE_DIR

    if not base_dir.exists():
        return {
            "base_dir": str(base_dir),
            "exists": False,
            "subdirs": [],
            "agent": "celltypeAppAgent"
        }

    # 扫描子目录
    subdirs = [d.name for d in base_dir.iterdir() if d.is_dir()]

    # 计算总大小
    total_size = 0
    file_count = 0
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            file_path = os.path.join(root, file)
            if os.path.exists(file_path):
                total_size += os.path.getsize(file_path)
                file_count += 1

    return {
        "base_dir": str(base_dir),
        "exists": True,
        "subdirs": sorted(subdirs),
        "total_size_mb": total_size / (1024 * 1024),
        "file_count": file_count,
        "agent": "celltypeAppAgent"
    }


def clear_cache(subdir: Optional[str] = None) -> int:
    """清理缓存

    Args:
        subdir: 子目录名称，None表示清理所有缓存

    Returns:
        清理的文件数量
    """
    import shutil

    if subdir:
        cache_dir = get_cache_dir(subdir)
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
            cache_dir.mkdir(parents=True, exist_ok=True)
            return 1
        return 0
    else:
        # 清理整个celltypeAppAgent缓存目录
        base_dir = DEFAULT_CACHE_DIR
        if base_dir.exists():
            file_count = sum(1 for _, _, files in os.walk(base_dir) for _ in files)
            shutil.rmtree(base_dir)
            base_dir.mkdir(parents=True, exist_ok=True)
            return file_count
        return 0


# 自动初始化已移除
# 现在必须在 MCP Server 启动时手动调用 init_cache(config=_CONFIG)
# 这确保使用用户指定的 output_dir 而不是硬编码的相对路径
