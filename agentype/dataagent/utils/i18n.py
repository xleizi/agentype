#!/usr/bin/env python3
"""
agentype - 国际化 (i18n) 管理器
Author: cuilei
Version: 1.0
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# 设置日志
logger = logging.getLogger(__name__)

class I18nManager:
    """国际化管理器
    
    负责多语言消息的加载、缓存和获取
    """
    
    def __init__(self):
        """初始化国际化管理器"""
        self.current_language = "zh"  # 默认中文
        self.fallback_language = "zh"  # 回退语言
        self.messages = {}  # 消息缓存
        self.locales_dir = Path(__file__).parent.parent / "locales"
        
        # 支持的语言列表
        self.supported_languages = ["zh", "en"]
        
        # 从环境变量读取语言设置
        env_lang = os.getenv("CELLTYPE_LANG", "zh").strip()
        if env_lang in self.supported_languages:
            self.current_language = env_lang
            logger.debug(f"从环境变量设置语言: {env_lang}")
        else:
            logger.warning(f"不支持的环境变量语言设置: {env_lang}, 使用默认语言: {self.current_language}")
        
        # 预加载默认语言
        self._load_language(self.current_language)
    
    def _load_language(self, language: str) -> bool:
        """加载指定语言的消息文件
        
        Args:
            language: 语言代码 (zh_CN, en_US)
            
        Returns:
            加载是否成功
        """
        if language in self.messages:
            return True  # 已加载
        
        try:
            locale_file = self.locales_dir / f"{language}.json"
            
            if not locale_file.exists():
                logger.warning(f"语言文件不存在: {locale_file}")
                return False
            
            with open(locale_file, 'r', encoding='utf-8') as f:
                messages = json.load(f)
            
            self.messages[language] = messages
            logger.debug(f"成功加载语言文件: {language} ({len(messages)} 条消息)")
            return True
            
        except Exception as e:
            logger.error(f"加载语言文件失败 {language}: {e}")
            return False
    
    def set_language(self, language: str) -> bool:
        """设置当前语言
        
        Args:
            language: 语言代码 (zh_CN, en_US)
            
        Returns:
            设置是否成功
        """
        if language not in self.supported_languages:
            logger.warning(f"不支持的语言: {language}, 支持的语言: {self.supported_languages}")
            return False
        
        # 尝试加载语言文件
        if not self._load_language(language):
            logger.error(f"无法加载语言文件: {language}")
            return False
        
        self.current_language = language
        logger.info(f"语言已切换至: {language}")
        return True
    
    def get_language(self) -> str:
        """获取当前语言
        
        Returns:
            当前语言代码
        """
        return self.current_language
    
    def get_supported_languages(self) -> list:
        """获取支持的语言列表
        
        Returns:
            支持的语言代码列表
        """
        return self.supported_languages.copy()
    
    def get_message(self, key: str, **kwargs) -> str:
        """获取国际化消息
        
        Args:
            key: 消息键，支持点号分隔的层级键 (如: "mcp.server.starting")
            **kwargs: 消息参数，用于字符串格式化
            
        Returns:
            本地化后的消息字符串
        """
        # 确保当前语言已加载
        if self.current_language not in self.messages:
            self._load_language(self.current_language)
        
        # 尝试获取当前语言的消息
        message = self._get_nested_message(self.messages.get(self.current_language, {}), key)
        
        # 如果当前语言没有找到，尝试回退语言
        if message is None and self.current_language != self.fallback_language:
            if self.fallback_language not in self.messages:
                self._load_language(self.fallback_language)
            message = self._get_nested_message(self.messages.get(self.fallback_language, {}), key)
        
        # 如果仍然没有找到，返回键本身
        if message is None:
            logger.warning(f"未找到消息键: {key}")
            message = key
        
        # 应用参数格式化
        if kwargs:
            try:
                message = message.format(**kwargs)
            except Exception as e:
                logger.warning(f"消息格式化失败 {key}: {e}")
        
        return message
    
    def _get_nested_message(self, messages: Dict[str, Any], key: str) -> Optional[str]:
        """获取嵌套结构中的消息
        
        Args:
            messages: 消息字典
            key: 点号分隔的键路径
            
        Returns:
            消息字符串或None
        """
        try:
            keys = key.split('.')
            current = messages
            
            for k in keys:
                if isinstance(current, dict) and k in current:
                    current = current[k]
                else:
                    return None
            
            return str(current) if current is not None else None
            
        except Exception:
            return None
    
    def has_message(self, key: str) -> bool:
        """检查是否存在指定的消息键
        
        Args:
            key: 消息键
            
        Returns:
            是否存在该消息键
        """
        # 检查当前语言
        if self.current_language in self.messages:
            if self._get_nested_message(self.messages[self.current_language], key) is not None:
                return True
        
        # 检查回退语言
        if self.fallback_language in self.messages:
            if self._get_nested_message(self.messages[self.fallback_language], key) is not None:
                return True
        
        return False
    
    def reload_languages(self) -> bool:
        """重新加载所有语言文件
        
        Returns:
            重新加载是否成功
        """
        try:
            # 清空缓存
            self.messages.clear()
            
            # 重新加载当前语言
            success = self._load_language(self.current_language)
            
            # 重新加载回退语言
            if self.current_language != self.fallback_language:
                success = success and self._load_language(self.fallback_language)
            
            logger.info("语言文件重新加载完成")
            return success
            
        except Exception as e:
            logger.error(f"重新加载语言文件失败: {e}")
            return False


# 创建全局实例
i18n_manager = I18nManager()

# 提供便捷的函数接口
def _(key: str, **kwargs) -> str:
    """获取国际化消息的便捷函数
    
    Args:
        key: 消息键
        **kwargs: 格式化参数
        
    Returns:
        本地化后的消息
    """
    return i18n_manager.get_message(key, **kwargs)

def set_language(language: str) -> bool:
    """设置语言的便捷函数
    
    Args:
        language: 语言代码
        
    Returns:
        设置是否成功
    """
    return i18n_manager.set_language(language)

def get_language() -> str:
    """获取当前语言的便捷函数
    
    Returns:
        当前语言代码
    """
    return i18n_manager.get_language()

def get_supported_languages() -> list:
    """获取支持语言列表的便捷函数
    
    Returns:
        支持的语言代码列表
    """
    return i18n_manager.get_supported_languages()