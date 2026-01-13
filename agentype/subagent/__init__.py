"""
agentype - Subagent Package
Author: cuilei
Version: 1.0
"""

from .config.cache_config import (
    init_cache,
    set_cache_dir, 
    get_cache_dir,
    get_cache_info,
    clear_cache
)

__version__ = "1.0.0"
__author__ = "Assistant"

# 导出主要接口
__all__ = [
    'init_cache',
    'set_cache_dir',
    'get_cache_dir', 
    'get_cache_info',
    'clear_cache'
]