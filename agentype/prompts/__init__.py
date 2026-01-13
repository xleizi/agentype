#!/usr/bin/env python3
"""
agentype - 统一Prompt管理模块
Author: cuilei
Version: 2.0
"""

from .config import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE, PROMPT_VERSION
from .prompt_manager import PromptManager

# 创建全局PromptManager实例
_prompt_manager = None


def get_prompt_manager(language: str = None) -> PromptManager:
    """获取全局PromptManager实例

    Args:
        language: 语言代码，如果为None则使用默认语言

    Returns:
        PromptManager实例
    """
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager(language or DEFAULT_LANGUAGE)
    elif language and _prompt_manager.language != language:
        _prompt_manager.set_language(language)
    return _prompt_manager


def get_system_prompt(agent_name: str, language: str = None) -> str:
    """获取Agent的系统Prompt

    Args:
        agent_name: Agent名称(mainagent/dataagent/subagent/appagent)
        language: 语言代码

    Returns:
        系统Prompt字符串
    """
    manager = get_prompt_manager(language)
    return manager.get_system_prompt(agent_name)


def get_fallback_prompt(agent_name: str, language: str = None) -> str:
    """获取Agent的Fallback Prompt

    Args:
        agent_name: Agent名称
        language: 语言代码

    Returns:
        Fallback Prompt字符串
    """
    manager = get_prompt_manager(language)
    return manager.get_fallback_prompt(agent_name)


def get_user_query_template(agent_name: str, template_key: str, language: str = None) -> str:
    """获取用户查询模板

    Args:
        agent_name: Agent名称
        template_key: 模板键名
        language: 语言代码

    Returns:
        用户查询模板字符串
    """
    manager = get_prompt_manager(language)
    return manager.get_user_query_template(agent_name, template_key)


def get_correction_template(agent_name: str, language: str = None) -> str:
    """获取格式修正模板

    Args:
        agent_name: Agent名称
        language: 语言代码

    Returns:
        格式修正模板字符串
    """
    manager = get_prompt_manager(language)
    return manager.get_correction_template(agent_name)


__all__ = [
    'SUPPORTED_LANGUAGES',
    'DEFAULT_LANGUAGE',
    'PROMPT_VERSION',
    'PromptManager',
    'get_prompt_manager',
    'get_system_prompt',
    'get_fallback_prompt',
    'get_user_query_template',
    'get_correction_template',
]
