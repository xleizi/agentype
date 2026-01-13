#!/usr/bin/env python3
"""
agentype - 国际化支持模块
Author: cuilei
Version: 1.0
"""

import json
import os
from typing import Dict, Any, Optional
from pathlib import Path


# 简化的国际化函数
def _(message: str, language: str = "zh") -> str:
    """简化的翻译函数"""
    return message


class LocalizedLogger:
    """本地化日志记录器"""

    def __init__(self, language: str = "zh"):
        self.language = language

    def info(self, message: str):
        print(f"[INFO] {message}")

    def error(self, message: str):
        print(f"[ERROR] {message}")

    def warning(self, message: str):
        print(f"[WARNING] {message}")


def get_i18n_manager(language: str = "zh") -> 'I18nManager':
    """获取国际化管理器"""
    return I18nManager(language)


class I18nManager:
    """国际化管理器"""

    def __init__(self, language: str = "zh"):
        """
        初始化国际化管理器

        Args:
            language: 语言代码，默认为中文
        """
        self.language = language
        self.messages: Dict[str, Any] = {}
        self.fallback_messages: Dict[str, Any] = {}

        # 获取locales目录路径
        current_dir = Path(__file__).resolve().parent.parent
        self.locales_dir = current_dir / "locales"

        # 加载消息
        self._load_messages()

    def _load_messages(self):
        """加载语言消息文件"""
        try:
            # 尝试加载指定语言
            language_file = self.locales_dir / f"{self.language}.json"
            if language_file.exists():
                with open(language_file, 'r', encoding='utf-8') as f:
                    self.messages = json.load(f)

            # 加载英文作为回退语言
            fallback_file = self.locales_dir / "en.json"
            if fallback_file.exists() and self.language != "en":
                with open(fallback_file, 'r', encoding='utf-8') as f:
                    self.fallback_messages = json.load(f)

        except Exception as e:
            print(f"加载语言文件失败: {e}")

    def get_message(self, key: str, **kwargs) -> str:
        """
        获取本地化消息

        Args:
            key: 消息键，使用点号分隔，如 "system.startup"
            **kwargs: 消息参数

        Returns:
            str: 本地化消息
        """
        # 解析嵌套键
        keys = key.split('.')
        message = self._get_nested_message(self.messages, keys)

        # 如果未找到，尝试回退语言
        if message is None and self.fallback_messages:
            message = self._get_nested_message(self.fallback_messages, keys)

        # 如果仍未找到，返回键名本身
        if message is None:
            message = key

        # 格式化消息
        try:
            return message.format(**kwargs)
        except (KeyError, ValueError):
            return message

    def _get_nested_message(self, messages: Dict[str, Any], keys: list) -> Optional[str]:
        """获取嵌套消息"""
        current = messages
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current if isinstance(current, str) else None

    def set_language(self, language: str):
        """设置语言"""
        if language != self.language:
            self.language = language
            self._load_messages()

    def get_available_languages(self) -> list:
        """获取可用语言列表"""
        languages = []
        if self.locales_dir.exists():
            for file in self.locales_dir.glob("*.json"):
                languages.append(file.stem)
        return languages


# 全局实例
_i18n_manager = None


def init_i18n(language: str = "zh") -> I18nManager:
    """
    初始化国际化管理器

    Args:
        language: 语言代码

    Returns:
        I18nManager: 国际化管理器实例
    """
    global _i18n_manager
    _i18n_manager = I18nManager(language)
    return _i18n_manager


def get_i18n_manager() -> I18nManager:
    """获取国际化管理器实例"""
    global _i18n_manager
    if _i18n_manager is None:
        _i18n_manager = I18nManager()
    return _i18n_manager


def _(key: str, **kwargs) -> str:
    """
    获取本地化消息的简便函数

    Args:
        key: 消息键
        **kwargs: 消息参数

    Returns:
        str: 本地化消息
    """
    manager = get_i18n_manager()
    return manager.get_message(key, **kwargs)


def set_language(language: str):
    """设置全局语言"""
    manager = get_i18n_manager()
    manager.set_language(language)


def get_available_languages() -> list:
    """获取可用语言列表"""
    manager = get_i18n_manager()
    return manager.get_available_languages()


class LocalizedLogger:
    """本地化日志记录器"""

    def __init__(self, name: str, language: str = "zh"):
        """
        初始化本地化日志记录器

        Args:
            name: 日志记录器名称
            language: 语言代码
        """
        self.name = name
        self.i18n = I18nManager(language)

    def info(self, key: str, **kwargs):
        """输出信息日志"""
        message = self.i18n.get_message(key, **kwargs)
        print(f"[INFO] {self.name}: {message}")

    def warning(self, key: str, **kwargs):
        """输出警告日志"""
        message = self.i18n.get_message(key, **kwargs)
        print(f"[WARNING] {self.name}: {message}")

    def error(self, key: str, **kwargs):
        """输出错误日志"""
        message = self.i18n.get_message(key, **kwargs)
        print(f"[ERROR] {self.name}: {message}")

    def debug(self, key: str, **kwargs):
        """输出调试日志"""
        message = self.i18n.get_message(key, **kwargs)
        print(f"[DEBUG] {self.name}: {message}")

    def success(self, key: str, **kwargs):
        """输出成功日志"""
        message = self.i18n.get_message(key, **kwargs)
        print(f"[SUCCESS] {self.name}: {message}")


# 预定义的本地化消息函数
def system_startup():
    """系统启动消息"""
    return _("system.startup")


def system_shutdown():
    """系统关闭消息"""
    return _("system.shutdown")


def agent_connecting(agent_name: str):
    """Agent连接消息"""
    return _("agent.connecting", agent_name=agent_name)


def agent_connected(agent_name: str):
    """Agent连接成功消息"""
    return _("agent.connected", agent_name=agent_name)


def workflow_started(workflow_name: str):
    """工作流开始消息"""
    return _("workflow.started", workflow_name=workflow_name)


def workflow_completed():
    """工作流完成消息"""
    return _("workflow.completed")


def step_started(step_number: int, step_description: str):
    """步骤开始消息"""
    return _("workflow.step_started", step_number=step_number, step_description=step_description)


def step_completed(step_number: int, execution_time: float):
    """步骤完成消息"""
    return _("workflow.step_completed", step_number=step_number, execution_time=execution_time)


def error_message(error_type: str, error: str):
    """错误消息"""
    key = f"error.{error_type}_error"
    return _(key, error=error)


def validation_failed(reason: str):
    """验证失败消息"""
    return _("validation.validation_failed", reason=reason)


def tool_called(tool_name: str):
    """工具调用消息"""
    return _("tools.tool_called", tool_name=tool_name)


def cache_hit(cache_key: str):
    """缓存命中消息"""
    return _("cache.cache_hit", cache_key=cache_key)


def pipeline_executing(pipeline_name: str):
    """流水线执行消息"""
    return _("pipeline.executing", pipeline_name=pipeline_name)