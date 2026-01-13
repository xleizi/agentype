#!/usr/bin/env python3
"""
agentype - Prompt系统统一配置
Author: cuilei
Version: 2.0
"""

# 支持的语言列表
SUPPORTED_LANGUAGES = ['zh', 'en']

# 默认语言
DEFAULT_LANGUAGE = 'zh'

# Prompt版本(用于缓存失效)
PROMPT_VERSION = '2.0.0'

# Agent名称映射
AGENT_NAMES = {
    'mainagent': 'MainAgent',
    'dataagent': 'DataAgent',
    'subagent': 'SubAgent',
    'appagent': 'AppAgent',
}

# 语言代码映射(兼容旧代码，未来可能移除)
LANGUAGE_CODE_MAPPING = {
    'zh': 'zh',
    'en': 'en',
    'zh_CN': 'zh',  # 兼容旧的zh_CN
    'en_US': 'en',  # 兼容旧的en_US
}
