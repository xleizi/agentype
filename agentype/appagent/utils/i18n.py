#!/usr/bin/env python3
"""
agentype - 国际化 (i18n) 管理器（AppAgent）
Author: cuilei
Version: 1.0
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class I18nManager:
    def __init__(self):
        self.current_language = "zh"
        self.fallback_language = "zh"
        self.messages: Dict[str, Dict[str, Any]] = {}
        self.locales_dir = Path(__file__).parent.parent / "locales"
        self.supported_languages = ["zh", "en"]

        env_lang = os.getenv("CELLTYPE_LANG", "zh").strip()
        if env_lang in self.supported_languages:
            self.current_language = env_lang
        else:
            logger.warning(f"Unsupported CELLTYPE_LANG: {env_lang}, using default {self.current_language}")

        # preload
        self._load_language(self.current_language)

    def _load_language(self, language: str) -> bool:
        if language in self.messages:
            return True
        try:
            locale_file = self.locales_dir / f"{language}.json"
            if not locale_file.exists():
                logger.warning(f"Locale file not found: {locale_file}")
                return False
            with open(locale_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.messages[language] = data
            return True
        except Exception as e:
            logger.error(f"Failed to load locale {language}: {e}")
            return False

    def set_language(self, language: str) -> bool:
        if language not in self.supported_languages:
            logger.warning(f"Unsupported language: {language}")
            return False
        if not self._load_language(language):
            return False
        self.current_language = language
        return True

    def get_language(self) -> str:
        return self.current_language

    def get_message(self, key: str, **kwargs) -> str:
        # try current
        msg = self._get_nested(self.messages.get(self.current_language, {}), key)
        if msg is None and self.fallback_language != self.current_language:
            msg = self._get_nested(self.messages.get(self.fallback_language, {}), key)
        if msg is None:
            # if provided default in kwargs, use it; else return key
            default = kwargs.pop("default", None)
            msg = default if default is not None else key
        try:
            return msg.format(**kwargs) if kwargs else msg
        except Exception:
            return msg

    def _get_nested(self, data: Dict[str, Any], dotted_key: str) -> Optional[str]:
        try:
            cur: Any = data
            for part in dotted_key.split('.'):
                if isinstance(cur, dict) and part in cur:
                    cur = cur[part]
                else:
                    return None
            return str(cur) if cur is not None else None
        except Exception:
            return None


# global instance
i18n_manager = I18nManager()


def _(key: str, **kwargs) -> str:
    return i18n_manager.get_message(key, **kwargs)


def set_language(language: str) -> bool:
    return i18n_manager.set_language(language)


def get_language() -> str:
    return i18n_manager.get_language()


def add_translation(language: str, translations: Dict[str, Any]):
    """Add or update translations at runtime (shallow merge)."""
    if language not in i18n_manager.supported_languages:
        i18n_manager.supported_languages.append(language)
    # ensure language loaded or create bucket
    if language not in i18n_manager.messages:
        i18n_manager.messages[language] = {}
    try:
        # shallow merge
        i18n_manager.messages[language].update(translations)
        return True
    except Exception:
        return False


def get_available_languages() -> list:
    return list(i18n_manager.supported_languages)


def translate_dict(data: Dict[str, Any], language: str = None) -> Dict[str, Any]:
    """Translate string values in a dict by treating them as keys."""
    lang_backup = i18n_manager.get_language()
    try:
        if language:
            i18n_manager.set_language(language)

        def _tv(v):
            if isinstance(v, str):
                return _(v)
            if isinstance(v, dict):
                return {k: _tv(val) for k, val in v.items()}
            if isinstance(v, list):
                return [_tv(x) for x in v]
            return v

        return {k: _tv(v) for k, v in data.items()}
    finally:
        i18n_manager.set_language(lang_backup)
