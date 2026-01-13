#!/usr/bin/env python3
"""
agentype - AppAgent Prompt模板(兼容层)
重定向到新的统一Prompt管理系统

Author: cuilei
Version: 2.0 - 重构为兼容层
"""

from typing import Dict
import importlib
from agentype.prompts import get_prompt_manager
from agentype.prompts.config import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE

__all__ = [
    'SUPPORTED_LANGUAGES',
    'DEFAULT_LANGUAGE',
    'get_system_prompt_template',
    'get_fallback_prompt_template',
    'get_user_query_templates',
    'get_correction_template',
    'get_intelligent_selection_templates',
    'build_user_query',
    'build_unified_user_query',
    'build_intelligent_selection_prompt',
]


def get_system_prompt_template(language: str = DEFAULT_LANGUAGE) -> str:
    """获取系统Prompt模板(兼容旧接口)"""
    manager = get_prompt_manager(language)
    return manager.get_system_prompt('appagent')


def get_fallback_prompt_template(language: str = DEFAULT_LANGUAGE) -> str:
    """获取Fallback Prompt模板"""
    manager = get_prompt_manager(language)
    return manager.get_fallback_prompt('appagent')


def get_user_query_templates(language: str = DEFAULT_LANGUAGE) -> dict:
    """获取用户查询模板"""
    manager = get_prompt_manager(language)
    return manager.get_user_query_templates('appagent')


def get_correction_template(language: str = DEFAULT_LANGUAGE) -> str:
    """获取修正模板"""
    manager = get_prompt_manager(language)
    return manager.get_correction_template('appagent')


def get_intelligent_selection_templates(language: str = DEFAULT_LANGUAGE) -> dict:
    """获取智能选择模板

    注意：此函数需要从原始prompt模块导入
    """
    module = _get_prompt_module(language)
    if hasattr(module, 'get_intelligent_selection_templates'):
        return module.get_intelligent_selection_templates()
    # 兼容旧的常量命名
    attr_name = 'APPAGENT_INTELLIGENT_SELECTION_TEMPLATES_ZH' if language == 'zh' else 'APPAGENT_INTELLIGENT_SELECTION_TEMPLATES_EN'
    return getattr(module, attr_name, {})


def build_user_query(rds_path: str, h5ad_path: str, tissue_description: str = None, language: str = DEFAULT_LANGUAGE) -> str:
    """构建用户查询

    注意：此函数委托给原始prompt模块的辅助函数
    """
    module = _get_prompt_module(language)
    if hasattr(module, 'build_user_query'):
        return module.build_user_query(rds_path, h5ad_path, tissue_description)
    raise AttributeError("Prompt module缺少 build_user_query 函数")


def build_unified_user_query(
    file_paths: dict,
    tissue_description: str = None,
    species: str = None,
    cluster_column: str = None,
    language: str = DEFAULT_LANGUAGE
) -> str:
    """构建统一的用户查询

    注意：此函数委托给原始prompt模块的辅助函数
    """
    module = _get_prompt_module(language)
    if hasattr(module, 'build_unified_user_query'):
        return module.build_unified_user_query(file_paths, tissue_description, species, cluster_column)
    raise AttributeError("Prompt module缺少 build_unified_user_query 函数")


def build_intelligent_selection_prompt(selection_type: str, context: dict, language: str = DEFAULT_LANGUAGE) -> str:
    """构建智能选择提示

    注意：此函数委托给原始prompt模块的辅助函数
    """
    module = _get_prompt_module(language)
    if hasattr(module, 'build_intelligent_selection_prompt'):
        return module.build_intelligent_selection_prompt(selection_type, context)
    raise AttributeError("Prompt module缺少 build_intelligent_selection_prompt 函数")
def _get_prompt_module(language: str):
    """动态加载指定语言的 AppAgent prompt 模块"""
    lang = language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    module_name = f"agentype.prompts.{lang}.appagent_prompts"
    try:
        return importlib.import_module(module_name)
    except ImportError:
        fallback_name = f"agentype.prompts.{DEFAULT_LANGUAGE}.appagent_prompts"
        return importlib.import_module(fallback_name)
