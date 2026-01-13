#!/usr/bin/env python3
"""
agentype - MainAgent Prompt模板(兼容层)
重定向到新的统一Prompt管理系统

Author: cuilei
Version: 2.0 - 重构为兼容层
"""

from typing import Dict
from agentype.prompts import get_prompt_manager
from agentype.prompts.config import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE

# 保持向后兼容
__all__ = [
    'SUPPORTED_LANGUAGES',
    'DEFAULT_LANGUAGE',
    'get_system_prompt_template',
    'get_fallback_prompt_template',
    'get_user_query_templates',
    'get_correction_template',
]


def get_system_prompt_template(language: str) -> str:
    """获取系统Prompt模板(兼容旧接口)

    Args:
        language: 语言代码

    Returns:
        系统Prompt模板字符串
    """
    manager = get_prompt_manager(language)
    return manager.get_system_prompt('mainagent')


def get_fallback_prompt_template(language: str) -> str:
    """获取Fallback Prompt模板

    Args:
        language: 语言代码

    Returns:
        Fallback Prompt模板字符串
    """
    manager = get_prompt_manager(language)
    return manager.get_fallback_prompt('mainagent')


def get_user_query_templates(language: str) -> Dict[str, str]:
    """获取用户查询模板

    Args:
        language: 语言代码

    Returns:
        用户查询模板字典
    """
    manager = get_prompt_manager(language)
    return manager.get_user_query_templates('mainagent')


def get_correction_template(language: str) -> str:
    """获取修正模板

    Args:
        language: 语言代码

    Returns:
        修正模板字符串
    """
    manager = get_prompt_manager(language)
    return manager.get_correction_template('mainagent')
