"""
agentype - App Agent 配置模块
Author: cuilei
Version: 1.0
"""

from .cache_config import (
    init_cache,
    set_cache_dir,
    get_cache_dir,
    get_cache_subdir,
    get_cache_info,
    clear_cache
)

__all__ = [
    'init_cache',
    'set_cache_dir',
    'get_cache_dir',
    'get_cache_subdir',
    'get_cache_info',
    'clear_cache'
]