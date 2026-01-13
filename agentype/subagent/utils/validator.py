#!/usr/bin/env python3
"""
agentype - SubAgent验证器
Author: cuilei
Version: 2.0

SubAgent的验证器，直接继承基类无需额外逻辑。
"""

from agentype.common.base_validator import BaseValidator


class ValidationUtils(BaseValidator):
    """SubAgent响应验证工具类

    直接继承BaseValidator，使用所有共享验证逻辑。
    SubAgent不需要特殊的验证规则。
    """
    pass
