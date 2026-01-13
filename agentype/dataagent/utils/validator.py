#!/usr/bin/env python3
"""
agentype - DataAgent验证器
Author: cuilei
Version: 2.0

DataAgent的验证器，直接继承基类无需额外逻辑。
"""

from agentype.common.base_validator import BaseValidator


class ValidationUtils(BaseValidator):
    """DataAgent响应验证工具类

    直接继承BaseValidator，使用所有共享验证逻辑。
    DataAgent不需要特殊的验证规则。
    """
    pass
