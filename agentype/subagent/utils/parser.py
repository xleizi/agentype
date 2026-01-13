#!/usr/bin/env python3
"""
agentype - SubAgent解析器
Author: cuilei
Version: 2.0

SubAgent的解析器，直接继承基类无需额外逻辑。
"""

from agentype.common.base_parser import BaseReactParser


class ReactParser(BaseReactParser):
    """SubAgent React解析器

    直接继承BaseReactParser，使用所有共享解析逻辑。
    SubAgent不需要特殊的解析规则。
    """
    pass
