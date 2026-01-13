#!/usr/bin/env python3
"""
agentype - App Agent 解析工具模块
Author: cuilei
Version: 1.0
"""

import re
import json
import logging
import os
from typing import Dict, Any, List, Optional, Tuple

# 配置日志系统 - 使用父模块的统一日志配置
logger = logging.getLogger(__name__)

try:
    from agentype.appagent.utils.i18n import _
except ImportError:
    # 简单的占位符函数
    def _(key, **kwargs):
        return key.format(**kwargs) if kwargs else key

class CelltypeReactParser:
    """细胞类型注释React模式解析器"""
    
    @staticmethod
    def extract_action(response: str, available_tools: List[Dict] = None) -> Optional[Dict[str, Any]]:
        """从响应中提取action内容
        
        Args:
            response: AI响应内容
            available_tools: 可用工具列表
            
        Returns:
            提取的action信息，包含function和parameters
        """
        # 匹配 <action>...</action> 标签
        action_pattern = r'<action>(.*?)</action>'
        match = re.search(action_pattern, response, re.DOTALL | re.IGNORECASE)
        
        if not match:
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
            return None
        
        function_name = func_match.group(1)
        
        # 验证工具是否可用（针对细胞类型注释工具）
        if available_tools:
            tool_names = [tool.get('name', '') for tool in available_tools]
            if function_name not in tool_names:
                logger.error(f"❌ 无效的细胞类型注释工具名称: {function_name}")
                logger.error(f"   可用工具: {', '.join(tool_names)}")
                return None
        
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
            return None
        
        params_str = params_content[1:end_pos]  # 去掉首尾括号
        
        return {
            'function': function_name,
            'parameters': params_str.strip()
        }
    
    @staticmethod
    def parse_annotation_parameters(params_str: str, function_name: str = None) -> Dict[str, Any]:
        """解析细胞类型注释相关的参数字符串
        
        Args:
            params_str: 参数字符串
            function_name: 函数名称，用于智能解析参数
            
        Returns:
            解析后的参数字典
        """
        if not params_str or not params_str.strip():
            return {}
        
        params = {}
        
        # 尝试多种解析方式
        # 方式1：键值对格式 param1="value1", param2="value2"
        kv_matches = re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*([^,]+)', params_str)
        if kv_matches:
            for key, value in kv_matches:
                # 清理值
                value = value.strip()
                # 去掉引号
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                
                # 转换数据类型
                params[key] = CelltypeReactParser._convert_value(value)
            return params
        
        # 方式2：位置参数格式 "value1", "value2"
        values = CelltypeReactParser._parse_positional_args(params_str)
        
        # 根据函数名称智能映射参数
        if function_name:
            params = CelltypeReactParser._map_parameters_by_function(values, function_name)
        else:
            # 通用映射逻辑
            params = CelltypeReactParser._map_generic_parameters(values)
        
        return params
    
    @staticmethod
    def _parse_positional_args(params_str: str) -> List[Any]:
        """解析位置参数"""
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
                    values.append(current_value.strip())
                current_value = ""
                continue
            
            current_value += char
        
        if current_value.strip():
            values.append(current_value.strip())
        
        # 清理值并转换
        cleaned_values = []
        for value in values:
            value = value.strip()
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            cleaned_values.append(CelltypeReactParser._convert_value(value))
        
        return cleaned_values
    
    @staticmethod
    def _map_parameters_by_function(values: List[Any], function_name: str) -> Dict[str, Any]:
        """根据函数名称智能映射参数"""
        params = {}
        
        # SingleR相关工具
        if 'singler' in function_name.lower():
            if 'info' in function_name.lower() or 'celldex' in function_name.lower():
                if len(values) >= 1:
                    params['language'] = values[0] if values[0] else "zh"
            elif 'download' in function_name.lower():
                if len(values) >= 1:
                    params['dataset_name'] = values[0]
                if len(values) >= 2:
                    params['cache_dir'] = values[1]
            elif 'annotate' in function_name.lower():
                if len(values) >= 1:
                    params['rds_path'] = values[0]
                if len(values) >= 2:
                    params['reference_path'] = values[1]
                if len(values) >= 3:
                    params['output_path'] = values[2]
        
        # scType相关工具
        elif 'sctype' in function_name.lower():
            if 'tissues' in function_name.lower():
                # get_sctype_tissues_tool 通常无参数
                pass
            elif 'annotate' in function_name.lower():
                if len(values) >= 1:
                    params['rds_path'] = values[0]
                if len(values) >= 2:
                    params['tissue_type'] = values[1] if values[1] else "Immune system"
                if len(values) >= 3:
                    params['output_path'] = values[2]
        
        # CellTypist相关工具
        elif 'celltypist' in function_name.lower():
            if 'models' in function_name.lower():
                # get_celltypist_models_tool 通常无参数
                pass
            elif 'annotate' in function_name.lower():
                if len(values) >= 1:
                    params['data_path'] = values[0]
                if len(values) >= 2:
                    params['model_name'] = values[1]
                if len(values) >= 3:
                    params['output_path'] = values[2]
                if len(values) >= 4:
                    params['auto_detect_species'] = values[3]
        
        # 物种检测工具
        elif 'detect_species' in function_name.lower():
            if len(values) >= 1:
                if 'h5ad' in function_name.lower():
                    params['h5ad_file'] = values[0]
                elif 'rds' in function_name.lower():
                    params['rds_file'] = values[0]
                elif 'json' in function_name.lower():
                    params['marker_genes_json'] = values[0]

        # 文件验证工具
        elif 'validate' in function_name.lower():
            if len(values) >= 1:
                params['marker_genes_json'] = values[0]
        
        # 流水线工具
        elif 'pipeline' in function_name.lower():
            if len(values) >= 1:
                params['rds_path'] = values[0]
            if len(values) >= 2:
                params['h5ad_path'] = values[1]
            if len(values) >= 3:
                params['tissue_description'] = values[2]
        
        else:
            # 通用映射
            params = CelltypeReactParser._map_generic_parameters(values)
        
        return params
    
    @staticmethod
    def _map_generic_parameters(values: List[Any]) -> Dict[str, Any]:
        """通用参数映射逻辑"""
        params = {}
        
        if len(values) >= 1:
            first_value = values[0]
            if isinstance(first_value, str):
                if first_value.endswith(('.rds', '.RDS')):
                    params['rds_path'] = first_value
                elif first_value.endswith(('.h5ad', '.H5AD')):
                    params['h5ad_path'] = first_value
                elif first_value.endswith(('.json', '.JSON')):
                    params['marker_genes_json'] = first_value
                elif first_value.endswith(('.h5', '.H5')):
                    params['h5_file'] = first_value
                else:
                    params['input_data'] = first_value
        
        # 添加其他位置参数
        for i, value in enumerate(values[1:], 1):
            params[f'param_{i}'] = value
        
        return params
    
    @staticmethod
    def parse_parameters(params_str: str) -> Dict[str, Any]:
        """兼容性方法，解析参数字符串"""
        return CelltypeReactParser.parse_annotation_parameters(params_str)
    
    @staticmethod
    def _convert_value(value: str) -> Any:
        """转换值的数据类型"""
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
        """从响应中提取thought内容"""
        pattern = r'<thought>(.*?)</thought>'
        match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
        
        if match:
            return match.group(1).strip()
        
        return None
    
    @staticmethod
    def extract_final_answer(response: str) -> Optional[str]:
        """从响应中提取final_answer内容"""
        pattern = r'<final_answer>(.*?)</final_answer>'
        match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
        
        if match:
            return match.group(1).strip()
        
        return None
    
    @staticmethod
    def extract_annotation_summary(response: str) -> Optional[Dict[str, Any]]:
        """从响应中提取细胞类型注释摘要信息
        
        Args:
            response: AI响应内容
            
        Returns:
            注释摘要信息字典
        """
        summary = {}
        
        # 提取识别的细胞类型
        celltype_pattern = r'<identified_celltypes>(.*?)</identified_celltypes>'
        celltype_match = re.search(celltype_pattern, response, re.DOTALL | re.IGNORECASE)
        if celltype_match:
            celltypes_text = celltype_match.group(1).strip()
            summary['identified_celltypes'] = [ct.strip() for ct in celltypes_text.split(',') if ct.strip()]
        
        # 提取置信度信息
        confidence_pattern = r'<confidence_score>(.*?)</confidence_score>'
        confidence_match = re.search(confidence_pattern, response, re.DOTALL | re.IGNORECASE)
        if confidence_match:
            try:
                summary['confidence_score'] = float(confidence_match.group(1).strip())
            except ValueError:
                summary['confidence_score'] = confidence_match.group(1).strip()
        
        # 提取使用的方法
        methods_pattern = r'<annotation_methods>(.*?)</annotation_methods>'
        methods_match = re.search(methods_pattern, response, re.DOTALL | re.IGNORECASE)
        if methods_match:
            methods_text = methods_match.group(1).strip()
            summary['annotation_methods'] = [m.strip() for m in methods_text.split(',') if m.strip()]
        
        return summary if summary else None
    
    @staticmethod
    def has_final_answer(response: str) -> bool:
        """检查响应是否包含final_answer"""
        return '</final_answer>' in response.lower()
    
    @staticmethod
    def extract_annotation_file_paths(response: str) -> Dict[str, Optional[str]]:
        """从响应中提取细胞类型注释相关的文件路径
        
        Args:
            response: AI响应内容
            
        Returns:
            包含各文件类型路径的字典
        """
        # 使用正则表达式提取XML标签内容
        rds_match = re.search(r'<rds_file>(.*?)</rds_file>', response, re.DOTALL)
        h5ad_match = re.search(r'<h5ad_file>(.*?)</h5ad_file>', response, re.DOTALL)
        h5_match = re.search(r'<h5_file>(.*?)</h5_file>', response, re.DOTALL)
        json_match = re.search(r'<marker_genes_json>(.*?)</marker_genes_json>', response, re.DOTALL)
        
        # 注释结果文件路径
        singler_result_match = re.search(r'<singler_result>(.*?)</singler_result>', response, re.DOTALL)
        sctype_result_match = re.search(r'<sctype_result>(.*?)</sctype_result>', response, re.DOTALL)
        celltypist_result_match = re.search(r'<celltypist_result>(.*?)</celltypist_result>', response, re.DOTALL)
        
        return {
            'rds_file': rds_match.group(1).strip() if rds_match and rds_match.group(1).strip() else None,
            'h5ad_file': h5ad_match.group(1).strip() if h5ad_match and h5ad_match.group(1).strip() else None,
            'h5_file': h5_match.group(1).strip() if h5_match and h5_match.group(1).strip() else None,
            'marker_genes_json': json_match.group(1).strip() if json_match and json_match.group(1).strip() else None,
            'singler_result': singler_result_match.group(1).strip() if singler_result_match and singler_result_match.group(1).strip() else None,
            'sctype_result': sctype_result_match.group(1).strip() if sctype_result_match and sctype_result_match.group(1).strip() else None,
            'celltypist_result': celltypist_result_match.group(1).strip() if celltypist_result_match and celltypist_result_match.group(1).strip() else None
        }
    
    @staticmethod
    def extract_file_paths(response: str) -> Dict[str, Optional[str]]:
        """兼容性方法，提取文件路径"""
        return CelltypeReactParser.extract_annotation_file_paths(response)
    
    @staticmethod
    def has_file_paths(response: str) -> bool:
        """检查响应是否包含file_paths标签"""
        return '<file_paths>' in response and '</file_paths>' in response

    @staticmethod
    def extract_file_paths_after_final_answer(response: str) -> Dict[str, Optional[str]]:
        """优先级1: 提取final_answer后面的独立<file_paths>标签"""
        # 查找</final_answer>后的<file_paths>块
        final_answer_end = response.find('</final_answer>')
        if final_answer_end == -1:
            return {}

        # 在final_answer结束后查找file_paths
        remaining_text = response[final_answer_end + len('</final_answer>'):]
        return CelltypeReactParser.extract_file_paths(remaining_text)

    @staticmethod
    def extract_file_paths_from_final_answer(response: str) -> Dict[str, Optional[str]]:
        """优先级2: 从final_answer内容中提取<file_paths>"""
        final_answer_content = CelltypeReactParser.extract_final_answer(response)
        if final_answer_content:
            return CelltypeReactParser.extract_file_paths(final_answer_content)
        return {}

    @staticmethod
    def extract_file_paths_priority(response: str) -> Dict[str, Optional[str]]:
        """按优先级顺序提取文件路径"""
        # 优先级1: final_answer后面的独立file_paths
        paths = CelltypeReactParser.extract_file_paths_after_final_answer(response)
        if any(paths.values()):  # 如果有任何非空路径
            return paths

        # 优先级2: final_answer内部的file_paths
        paths = CelltypeReactParser.extract_file_paths_from_final_answer(response)
        if any(paths.values()):
            return paths

        # 优先级3: 任何位置的file_paths（原有逻辑）
        return CelltypeReactParser.extract_file_paths(response)
    
    @staticmethod
    def extract_annotation_phase(response: str) -> Optional[str]:
        """从响应中提取当前执行的注释阶段
        
        Args:
            response: AI响应内容
            
        Returns:
            当前执行阶段
        """
        phase_pattern = r'<current_phase>(.*?)</current_phase>'
        match = re.search(phase_pattern, response, re.DOTALL | re.IGNORECASE)
        
        if match:
            return match.group(1).strip()
        
        # 通过关键词推断阶段
        response_lower = response.lower()
        if '第一阶段' in response or 'phase 1' in response_lower or '输入验证' in response:
            return "第一阶段：输入验证和预处理"
        elif '第二阶段' in response or 'phase 2' in response_lower or 'singler' in response_lower:
            return "第二阶段：SingleR注释流程"
        elif '第三阶段' in response or 'phase 3' in response_lower or 'sctype' in response_lower:
            return "第三阶段：scType注释流程"
        elif '第四阶段' in response or 'phase 4' in response_lower or 'celltypist' in response_lower:
            return "第四阶段：CellTypist注释流程"
        elif '第五阶段' in response or 'phase 5' in response_lower or '结果整合' in response:
            return "第五阶段：结果整合"
        
        return None
    
    @staticmethod
    def extract_step_number(response: str) -> Optional[int]:
        """从响应中提取当前步骤编号
        
        Args:
            response: AI响应内容
            
        Returns:
            当前步骤编号
        """
        step_patterns = [
            r'步骤(\d+)',
            r'step\s*(\d+)',
            r'第(\d+)步',
            r'step (\d+)'
        ]
        
        for pattern in step_patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue
        
        return None
    
    @staticmethod
    def split_annotation_response_parts(response: str) -> Dict[str, Any]:
        """将细胞类型注释响应分解为各个部分
        
        Args:
            response: AI响应内容
            
        Returns:
            包含各部分内容的字典
        """
        return {
            'thought': CelltypeReactParser.extract_thought(response),
            'action': CelltypeReactParser.extract_action(response),
            'final_answer': CelltypeReactParser.extract_final_answer(response),
            'annotation_summary': CelltypeReactParser.extract_annotation_summary(response),
            'file_paths': CelltypeReactParser.extract_annotation_file_paths(response),
            'current_phase': CelltypeReactParser.extract_annotation_phase(response),
            'step_number': CelltypeReactParser.extract_step_number(response)
        }
    
    @staticmethod
    def split_response_parts(response: str) -> Dict[str, Any]:
        """兼容性方法，分解响应"""
        return CelltypeReactParser.split_annotation_response_parts(response)