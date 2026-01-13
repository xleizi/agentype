#!/usr/bin/env python3
"""
agentype - 共享通用模块
Author: cuilei
Version: 2.0
"""

from .language_manager import (
    LanguageManager,
    set_global_language,
    get_current_language,
    get_supported_languages,
)

__all__ = [
    'LanguageManager',
    'set_global_language',
    'get_current_language',
    'get_supported_languages',
]
