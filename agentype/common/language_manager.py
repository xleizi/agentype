#!/usr/bin/env python3
"""
agentype - 统一语言管理模块
负责协调prompts和i18n系统的语言设置

Author: cuilei
Version: 2.0
"""

import os
from typing import Optional
from agentype.prompts.config import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE


class LanguageManager:
    """统一管理 prompts 和 i18n 的语言设置

    这是一个单例类，确保整个系统使用统一的语言设置
    """

    _instance: Optional['LanguageManager'] = None
    _current_language: str = DEFAULT_LANGUAGE

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # 从环境变量读取默认语言
            env_lang = os.getenv("CELLTYPE_LANG", DEFAULT_LANGUAGE).strip()
            if env_lang in SUPPORTED_LANGUAGES:
                cls._current_language = env_lang
        return cls._instance

    @classmethod
    def set_language(cls, language: str) -> bool:
        """设置全局语言

        Args:
            language: 语言代码('zh'或'en')

        Returns:
            设置是否成功
        """
        if language not in SUPPORTED_LANGUAGES:
            return False

        cls._current_language = language

        # 同步到所有 Agent 的 i18n
        try:
            from agentype.mainagent.utils.i18n import set_language as set_main_lang
            set_main_lang(language)
        except ImportError:
            pass

        try:
            from agentype.appagent.utils.i18n import set_language as set_app_lang
            set_app_lang(language)
        except ImportError:
            pass

        try:
            from agentype.dataagent.utils.i18n import set_language as set_data_lang
            set_data_lang(language)
        except ImportError:
            pass

        try:
            from agentype.subagent.utils.i18n import set_language as set_sub_lang
            set_sub_lang(language)
        except ImportError:
            pass

        # 同步到prompts系统
        try:
            from agentype.prompts import get_prompt_manager
            manager = get_prompt_manager()
            manager.set_language(language)
        except ImportError:
            pass

        return True

    @classmethod
    def get_language(cls) -> str:
        """获取当前语言

        Returns:
            当前语言代码
        """
        return cls._current_language

    @classmethod
    def get_supported_languages(cls) -> list:
        """获取支持的语言列表

        Returns:
            支持的语言列表
        """
        return SUPPORTED_LANGUAGES.copy()

    @classmethod
    def is_language_supported(cls, language: str) -> bool:
        """检查语言是否支持

        Args:
            language: 语言代码

        Returns:
            是否支持
        """
        return language in SUPPORTED_LANGUAGES


# 全局便捷函数

def set_global_language(language: str) -> bool:
    """设置全局语言（便捷函数）

    Args:
        language: 语言代码

    Returns:
        设置是否成功
    """
    manager = LanguageManager()
    return manager.set_language(language)


def get_current_language() -> str:
    """获取当前语言（便捷函数）

    Returns:
        当前语言代码
    """
    manager = LanguageManager()
    return manager.get_language()


def get_supported_languages() -> list:
    """获取支持的语言列表（便捷函数）

    Returns:
        支持的语言列表
    """
    manager = LanguageManager()
    return manager.get_supported_languages()


__all__ = [
    'LanguageManager',
    'set_global_language',
    'get_current_language',
    'get_supported_languages',
]
