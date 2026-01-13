#!/usr/bin/env python3
"""
agentype - MainAgent解析器
Author: cuilei
Version: 2.0

MainAgent的解析器，直接继承基类无需额外逻辑。
"""

from agentype.common.base_parser import BaseReactParser


class ReactParser(BaseReactParser):
    """MainAgent React解析器

    直接继承BaseReactParser，使用所有共享解析逻辑。
    MainAgent不需要特殊的解析规则。

    注：extract_file_paths_priority() 方法已在基类中定义，
    MainAgent可以直接继承使用。
    """
    pass
