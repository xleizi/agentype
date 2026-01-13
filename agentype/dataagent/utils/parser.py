#!/usr/bin/env python3
"""
agentype - DataAgent解析器
Author: cuilei
Version: 2.0

DataAgent的解析器，直接继承基类无需额外逻辑。
"""

from agentype.common.base_parser import BaseReactParser


class ReactParser(BaseReactParser):
    """DataAgent React解析器

    直接继承BaseReactParser，使用所有共享解析逻辑。
    DataAgent不需要特殊的解析规则。
    """
    pass
