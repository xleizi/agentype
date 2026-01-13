#!/usr/bin/env python3
"""
agentype - 解析器基类
Author: cuilei
Version: 2.0

所有Agent解析器的共享逻辑，提供统一的React响应解析功能。
"""

import re
import json
from typing import Dict, Any, List, Optional


class BaseReactParser:
    """React模式解析器基类 - 所有Agent解析器的共享逻辑"""

    @staticmethod
    def extract_action(response: str, available_tools: List[Dict] = None) -> Optional[Dict[str, Any]]:
        """从响应中提取action内容，返回详细错误信息（共享逻辑）

        Args:
            response: AI响应内容
            available_tools: 可用工具列表

        Returns:
            成功: {'function': str, 'parameters': str, 'raw': str}
            失败: {'error': str, 'message': str, ...其他诊断信息}
            无action: None (仅当响应中确实没有 <action> 标签时)
        """
        # 匹配 <action>...</action> 标签
        action_pattern = r'<action>(.*?)</action>'
        match = re.search(action_pattern, response, re.DOTALL | re.IGNORECASE)

        if not match:
            # 没有找到 <action> 标签 - 这可能是正常的(如有 final_answer)
            return None

        action_content = match.group(1).strip()

        # 解析函数调用格式：function_name(param1=value1, param2=value2)
        # 支持多种格式：
        # 1. function_name(param1="value1", param2="value2")
        # 2. function_name(param1=value1, param2=value2)
        # 3. function_name("value1", "value2")

        # 提取函数名
        func_pattern = r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
        func_match = re.match(func_pattern, action_content)

        if not func_match:
            # action 格式不正确
            return {
                'error': 'invalid_action_format',
                'message': 'action 格式不正确，应为: function_name(param1=value1, param2=value2)',
                'action_text': action_content,
                'text_preview': response[:200]
            }

        function_name = func_match.group(1)

        # 验证工具是否可用
        if available_tools:
            tool_names = [tool.get('name', '') for tool in available_tools]
            if function_name not in tool_names:
                # 工具名称无效 - 返回详细错误信息
                return {
                    'error': 'invalid_tool_name',
                    'func_name': function_name,
                    'available_tools': tool_names,
                    'message': f'工具 "{function_name}" 不在可用列表中',
                    'action_text': action_content
                }

        # 提取参数部分
        params_start = func_match.end() - 1  # -1 因为要包含 '('
        params_content = action_content[params_start:]

        # 找到匹配的右括号
        bracket_count = 0
        end_pos = -1
        for i, char in enumerate(params_content):
            if char == '(':
                bracket_count += 1
            elif char == ')':
                bracket_count -= 1
                if bracket_count == 0:
                    end_pos = i
                    break

        if end_pos == -1:
            return {
                'error': 'invalid_action_format',
                'message': 'action 括号不匹配',
                'action_text': action_content
            }

        params_str = params_content[1:end_pos]  # 去掉首尾括号

        # 成功提取
        return {
            'function': function_name,
            'parameters': params_str.strip(),
            'raw': action_content
        }

    @staticmethod
    def parse_parameters(params_str: str) -> Dict[str, Any]:
        """解析参数字符串（共享逻辑）

        支持格式：
        1. JSON: {"key": "value"}
        2. 键值对: key="value", key2="value2"
        3. 位置参数: "value1", "value2"

        Args:
            params_str: 参数字符串

        Returns:
            解析后的参数字典
        """
        if not params_str or not params_str.strip():
            return {}

        params = {}

        # 尝试多种解析方式

        # 1. 尝试作为 JSON 解析
        try:
            # 如果看起来像 JSON 对象
            if params_str.strip().startswith('{'):
                return json.loads(params_str)
        except json.JSONDecodeError:
            pass

        # 2. 尝试作为 key=value 格式解析
        try:
            # 使用正则表达式匹配 key="value" 或 key=value 格式
            # 修复：支持引号内包含逗号的长值（如基因列表）
            # 正则说明：
            # (\w+) - 参数名
            # \s*=\s* - 等号
            # "([^"]*)" - 双引号内的值（可以包含逗号）
            # '([^']*)' - 单引号内的值（可以包含逗号）
            # ([^,\s]+) - 不带引号的值（不能包含逗号和空格）
            key_value_pattern = r'(\w+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^,\s]+))'
            matches = re.findall(key_value_pattern, params_str)

            if matches:
                for match in matches:
                    key = match[0]
                    # match[1] = 双引号内的值
                    # match[2] = 单引号内的值
                    # match[3] = 不带引号的值
                    value = match[1] or match[2] or match[3]
                    params[key] = BaseReactParser._convert_value(value)
                return params
        except Exception:
            pass

        # 3. 尝试作为位置参数解析 (如 "value1", "value2")
        try:
            # 分割逗号分隔的值
            values = []
            current_value = ""
            in_quotes = False
            quote_char = None

            for char in params_str:
                if char in ['"', "'"] and not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char and in_quotes:
                    in_quotes = False
                    quote_char = None
                elif char == ',' and not in_quotes:
                    if current_value.strip():
                        values.append(current_value.strip().strip('"\''))
                    current_value = ""
                    continue

                current_value += char

            # 添加最后一个值
            if current_value.strip():
                values.append(current_value.strip().strip('"\''))

            # 如果只有一个值，可能是主要参数
            if len(values) == 1:
                # 常见的主要参数名
                first_value = BaseReactParser._convert_value(values[0])
                if isinstance(first_value, str) and ('/' in first_value or
                    first_value.endswith(('.csv', '.h5ad', '.rds', '.h5', '.json'))):
                    params['input_data'] = first_value
        except Exception:
            pass

        return params

    @staticmethod
    def _convert_value(value: str) -> Any:
        """转换值的数据类型（共享逻辑）

        Args:
            value: 字符串值

        Returns:
            转换后的值
        """
        if not isinstance(value, str):
            return value

        # 尝试转换为数字
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass

        # 尝试转换为布尔值
        if value.lower() in ['true', 'false']:
            return value.lower() == 'true'

        # 尝试转换为None
        if value.lower() in ['none', 'null']:
            return None

        # 保持为字符串
        return value

    @staticmethod
    def extract_thought(response: str) -> Optional[str]:
        """从响应中提取thought内容（共享逻辑）

        Args:
            response: AI响应内容

        Returns:
            提取的thought内容
        """
        pattern = r'<thought>(.*?)</thought>'
        match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)

        if match:
            return match.group(1).strip()

        return None

    @staticmethod
    def extract_final_answer(response: str) -> Optional[str]:
        """从响应中提取final_answer内容（共享逻辑）

        Args:
            response: AI响应内容

        Returns:
            提取的final_answer内容
        """
        pattern = r'<final_answer>(.*?)</final_answer>'
        match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)

        if match:
            return match.group(1).strip()

        return None

    @staticmethod
    def extract_celltype(response: str) -> Optional[str]:
        """从响应中提取celltype内容（如果有的话）

        Args:
            response: AI响应内容

        Returns:
            提取的celltype内容
        """
        pattern = r'<celltype>(.*?)</celltype>'
        match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)

        if match:
            return match.group(1).strip()

        return None

    @staticmethod
    def has_final_answer(response: str) -> bool:
        """检查响应是否包含final_answer（共享逻辑）

        Args:
            response: AI响应内容

        Returns:
            是否包含final_answer
        """
        return '</final_answer>' in response.lower()

    @staticmethod
    def has_file_paths(response: str) -> bool:
        """检查响应是否包含文件路径XML块"""
        return "<file_paths>" in response and "</file_paths>" in response

    @staticmethod
    def extract_file_paths(response: str) -> Dict[str, str]:
        """提取XML文件路径块中的路径信息（通用方法）"""
        paths = {}
        file_paths_match = re.search(r'<file_paths>(.*?)</file_paths>', response, re.DOTALL)
        if file_paths_match:
            file_paths_content = file_paths_match.group(1)
            # 提取各种文件类型路径
            path_patterns = {
                'rds_file': r'<rds_file>(.*?)</rds_file>',
                'h5ad_file': r'<h5ad_file>(.*?)</h5ad_file>',
                'h5_file': r'<h5_file>(.*?)</h5_file>',
                'marker_genes_json': r'<marker_genes_json>(.*?)</marker_genes_json>',
                'singler_result': r'<singler_result>(.*?)</singler_result>',
                'sctype_result': r'<sctype_result>(.*?)</sctype_result>',
                'celltypist_result': r'<celltypist_result>(.*?)</celltypist_result>',
                'mapping_json': r'<mapping_json>(.*?)</mapping_json>',
                'seurat_output_rds': r'<seurat_output_rds>(.*?)</seurat_output_rds>',
                'adata_output_file': r'<adata_output_file>(.*?)</adata_output_file>'
            }
            for file_type, pattern in path_patterns.items():
                match = re.search(pattern, file_paths_content, re.DOTALL)
                if match:
                    path = match.group(1).strip()
                    paths[file_type] = path if path and not path.startswith("/abs/path/or-empty") else ""
        return paths

    @staticmethod
    def extract_file_paths_after_final_answer(response: str) -> Dict[str, str]:
        """优先级1: 提取final_answer后面的独立<file_paths>标签"""
        # 查找</final_answer>后的<file_paths>块
        final_answer_end = response.find('</final_answer>')
        if final_answer_end == -1:
            return {}

        # 在final_answer结束后查找file_paths
        remaining_text = response[final_answer_end + len('</final_answer>'):]
        return BaseReactParser.extract_file_paths(remaining_text)

    @staticmethod
    def extract_file_paths_from_final_answer(response: str) -> Dict[str, str]:
        """优先级2: 从final_answer内容中提取<file_paths>"""
        final_answer_content = BaseReactParser.extract_final_answer(response)
        if final_answer_content:
            return BaseReactParser.extract_file_paths(final_answer_content)
        return {}

    @staticmethod
    def extract_file_paths_priority(response: str) -> Dict[str, str]:
        """按优先级顺序提取文件路径"""
        # 优先级1: final_answer后面的独立file_paths
        paths = BaseReactParser.extract_file_paths_after_final_answer(response)
        if paths:
            return paths

        # 优先级2: final_answer内部的file_paths
        paths = BaseReactParser.extract_file_paths_from_final_answer(response)
        if paths:
            return paths

        # 优先级3: 任何位置的file_paths（原有逻辑）
        return BaseReactParser.extract_file_paths(response)
