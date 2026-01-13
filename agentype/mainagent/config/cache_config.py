#!/usr/bin/env python3
"""
agentype - MainAgent缓存配置管理（兼容性层）
Author: cuilei
Version: 2.0 - 移除对 GlobalConfig 的依赖
"""

import sys
from pathlib import Path
from typing import Optional

# 添加根目录config到路径
current_dir = Path(__file__).resolve().parent.parent.parent  # 回到根目录
sys.path.insert(0, str(current_dir))


class CacheManager:
    """MainAgent缓存管理器"""

    def __init__(self, cache_dir: Optional[str] = None, config=None):
        """
        初始化缓存管理器

        Args:
            cache_dir: 缓存目录路径（已废弃，保留用于向后兼容）
            config: ConfigManager 实例（必需）

        Raises:
            ValueError: 如果未提供 config 参数

        Note:
            推荐通过 MainReactAgent.config 获取路径配置
        """
        if config is not None:
            # 使用提供的 config
            self.cache_dir = Path(config.cache_dir)
            self.results_cache_dir = Path(config.results_dir) if hasattr(config, 'results_dir') else Path(config.output_dir) / "results"
            self.logs_cache_dir = Path(config.log_dir)
        else:
            # 不再使用默认路径！要求明确传递配置
            raise ValueError(
                "必须提供 config 参数。"
                "请传递 ConfigManager 实例而不是使用硬编码路径"
            )


def init_cache(cache_dir: Optional[str] = None, config=None) -> CacheManager:
    """
    初始化缓存管理器

    Args:
        cache_dir: 缓存目录路径（已废弃，保留用于向后兼容）
        config: ConfigManager 实例（必需）

    Returns:
        CacheManager: 缓存管理器实例

    Raises:
        ValueError: 如果未提供 config 参数
    """
    return CacheManager(cache_dir, config)


# 兼容性函数，与其他Agent保持一致的接口
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
    base_cache_dir = Path(config.cache_dir)
    if subdir:
        cache_path = base_cache_dir / subdir
    else:
        cache_path = base_cache_dir

    # 确保目录存在
    cache_path.mkdir(parents=True, exist_ok=True)
    return cache_path
