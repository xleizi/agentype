#!/usr/bin/env python3
"""
agentype - PromptManager 统一管理所有Agent的Prompt
Author: cuilei
Version: 2.0
"""

import importlib
from typing import Dict, Any
from functools import lru_cache

from .config import (
    SUPPORTED_LANGUAGES,
    DEFAULT_LANGUAGE,
    LANGUAGE_CODE_MAPPING,
    AGENT_NAMES
)


class PromptManager:
    """Prompt管理器

    负责加载、缓存和提供各Agent的Prompt模板
    """

    def __init__(self, language: str = DEFAULT_LANGUAGE):
        """初始化PromptManager

        Args:
            language: 语言代码(zh/en)
        """
        self.language = self._normalize_language(language)
        self._prompt_cache: Dict[str, Any] = {}
        self._module_cache: Dict[str, Any] = {}

    def _normalize_language(self, language: str) -> str:
        """标准化语言代码"""
        return LANGUAGE_CODE_MAPPING.get(language, DEFAULT_LANGUAGE)

    def _load_prompt_module(self, agent_name: str):
        """动态加载Agent的Prompt模块

        Args:
            agent_name: Agent名称(mainagent/dataagent/subagent/appagent)

        Returns:
            加载的prompt模块

        Raises:
            ImportError: 无法加载模块时抛出
        """
        cache_key = f"{agent_name}_{self.language}"

        if cache_key in self._module_cache:
            return self._module_cache[cache_key]

        try:
            # 动态导入: agentype.prompts.zh.mainagent_prompts
            module_path = f"agentype.prompts.{self.language}.{agent_name}_prompts"
            module = importlib.import_module(module_path)
            self._module_cache[cache_key] = module
            return module
        except ImportError as e:
            # 回退到默认语言
            if self.language != DEFAULT_LANGUAGE:
                fallback_path = f"agentype.prompts.{DEFAULT_LANGUAGE}.{agent_name}_prompts"
                try:
                    module = importlib.import_module(fallback_path)
                    self._module_cache[cache_key] = module
                    return module
                except ImportError:
                    pass
            raise ImportError(f"无法加载Prompt模块: {module_path}, 错误: {e}")

    @lru_cache(maxsize=32)
    def get_system_prompt(self, agent_name: str) -> str:
        """获取Agent的系统Prompt

        Args:
            agent_name: Agent名称

        Returns:
            系统Prompt字符串
        """
        module = self._load_prompt_module(agent_name)
        return getattr(module, 'SYSTEM_PROMPT', '')

    @lru_cache(maxsize=32)
    def get_fallback_prompt(self, agent_name: str) -> str:
        """获取Fallback Prompt

        Args:
            agent_name: Agent名称

        Returns:
            Fallback Prompt字符串
        """
        module = self._load_prompt_module(agent_name)
        return getattr(module, 'FALLBACK_PROMPT', '')

    def get_user_query_templates(self, agent_name: str) -> Dict[str, str]:
        """获取用户查询模板字典

        Args:
            agent_name: Agent名称

        Returns:
            用户查询模板字典
        """
        module = self._load_prompt_module(agent_name)
        return getattr(module, 'USER_QUERY_TEMPLATES', {})

    def get_user_query_template(self, agent_name: str, template_key: str) -> str:
        """获取特定的用户查询模板

        Args:
            agent_name: Agent名称
            template_key: 模板键名

        Returns:
            用户查询模板字符串
        """
        templates = self.get_user_query_templates(agent_name)
        return templates.get(template_key, '')

    def get_correction_template(self, agent_name: str) -> str:
        """获取格式修正模板

        Args:
            agent_name: Agent名称

        Returns:
            格式修正模板字符串
        """
        module = self._load_prompt_module(agent_name)
        return getattr(module, 'CORRECTION_TEMPLATE', '')

    def set_language(self, language: str):
        """切换语言(清除缓存)

        Args:
            language: 新的语言代码
        """
        new_lang = self._normalize_language(language)
        if new_lang != self.language:
            self.language = new_lang
            self._prompt_cache.clear()
            self._module_cache.clear()
            # 清除lru_cache
            self.get_system_prompt.cache_clear()
            self.get_fallback_prompt.cache_clear()

    def get_available_languages(self) -> list:
        """获取可用语言列表

        Returns:
            可用语言列表
        """
        return SUPPORTED_LANGUAGES.copy()

    def get_common_prompt(self, prompt_name: str) -> str:
        """获取共享的common prompt

        Args:
            prompt_name: Prompt名称（如'BASE_CORRECTION_TEMPLATE'）

        Returns:
            Common prompt字符串
        """
        try:
            # 加载common_prompts模块
            module_path = f"agentype.prompts.{self.language}.common_prompts"
            module = importlib.import_module(module_path)
            return getattr(module, prompt_name, '')
        except ImportError:
            # 如果当前语言没有，回退到默认语言
            if self.language != DEFAULT_LANGUAGE:
                try:
                    fallback_path = f"agentype.prompts.{DEFAULT_LANGUAGE}.common_prompts"
                    module = importlib.import_module(fallback_path)
                    return getattr(module, prompt_name, '')
                except ImportError:
                    pass
            return ''

    def get_agent_specific_prompt(self, agent_name: str, prompt_name: str):
        """获取Agent特定的prompt（如跳过检测、注释修正等）

        Args:
            agent_name: Agent名称
            prompt_name: Prompt名称

        Returns:
            Agent特定的prompt
        """
        module = self._load_prompt_module(agent_name)
        return getattr(module, prompt_name, None)

    def validate_agent_name(self, agent_name: str) -> bool:
        """验证Agent名称是否有效

        Args:
            agent_name: Agent名称

        Returns:
            是否有效
        """
        return agent_name in AGENT_NAMES
