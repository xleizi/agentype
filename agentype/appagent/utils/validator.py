#!/usr/bin/env python3
"""
agentype - App Agent 验证工具模块
Author: cuilei
Version: 1.0
"""

import re
import json
import os
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
try:
    from agentype.appagent.utils.i18n import _
except ImportError:
    # 简单的占位符函数
    def _(key, **kwargs):
        return key.format(**kwargs) if kwargs else key

class CelltypeValidationUtils:
    """细胞类型注释应用验证工具类"""
    
    @staticmethod
    def validate_response_format(response: str) -> Dict[str, Any]:
        """验证响应格式是否正确
        
        Args:
            response: AI响应内容
            
        Returns:
            验证结果字典，包含是否有效和问题列表
        """
        issues = []
        
        # 检查基本标签
        if "<thought>" not in response:
            issues.append(_("validation.missing_thought_tag"))
        
        # 检查是否有action或final_answer
        has_action = "<action>" in response
        has_final_answer = "<final_answer>" in response
        
        if not has_action and not has_final_answer:
            issues.append(_("validation.missing_action_or_final_answer"))
        
        # 检查标签是否成对
        if "<thought>" in response and "</thought>" not in response:
            issues.append(_("validation.unclosed_thought_tag"))
        
        if has_action and "</action>" not in response:
            issues.append(_("validation.unclosed_action_tag"))
        
        if has_final_answer and "</final_answer>" not in response:
            issues.append(_("validation.unclosed_final_answer_tag"))
        
        # 检查是否有多余的observation标签（AI不应该生成observation）
        if "<observation>" in response:
            issues.append(_("validation.unexpected_observation_tag"))
        
        return {
            "valid": len(issues) == 0,
            "issues": issues
        }
    
    @staticmethod
    def validate_json_structure(json_str: str) -> Dict[str, Any]:
        """验证JSON结构是否正确
        
        Args:
            json_str: JSON字符串
            
        Returns:
            验证结果字典
        """
        try:
            data = json.loads(json_str)
            return {
                "valid": True,
                "data": data,
                "error": None
            }
        except json.JSONDecodeError as e:
            return {
                "valid": False,
                "data": None,
                "error": _("validation.json_decode_error", error=str(e))
            }
    
    @staticmethod
    def validate_file_path(file_path: str, expected_extensions: List[str] = None) -> Dict[str, Any]:
        """验证文件路径格式和存在性
        
        Args:
            file_path: 文件路径
            expected_extensions: 期望的文件扩展名列表（如['.rds', '.h5ad', '.json']）
            
        Returns:
            验证结果字典
        """
        issues = []
        
        if not file_path:
            issues.append(_("validation.empty_file_path"))
            return {"valid": False, "issues": issues}
        
        path = Path(file_path)
        
        # 检查路径格式
        try:
            resolved_path = path.resolve()
        except Exception as e:
            issues.append(_("validation.invalid_path_format", error=str(e)))
            return {"valid": False, "issues": issues}
        
        # 检查文件是否存在
        if not path.exists():
            issues.append(_("validation.file_not_exist", path=file_path))
        
        # 检查是否为文件而非目录
        if path.exists() and path.is_dir():
            issues.append(_("validation.path_is_directory", path=file_path))
        
        # 检查文件扩展名
        if expected_extensions and path.exists() and not path.is_dir():
            file_extension = path.suffix.lower()
            if file_extension not in [ext.lower() for ext in expected_extensions]:
                issues.append(_("validation.invalid_file_extension", 
                              extension=file_extension, 
                              expected=', '.join(expected_extensions)))
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "resolved_path": str(resolved_path) if path.exists() else None,
            "file_extension": path.suffix if path.exists() else None
        }
    
    @staticmethod
    def validate_annotation_files(rds_path: str = None, h5ad_path: str = None, 
                                marker_json_path: str = None) -> Dict[str, Any]:
        """验证细胞类型注释所需的文件
        
        Args:
            rds_path: RDS文件路径（用于SingleR和scType）
            h5ad_path: H5AD文件路径（用于CellTypist）
            marker_json_path: marker基因JSON文件路径（可选）
            
        Returns:
            验证结果字典
        """
        issues = []
        file_status = {}
        
        # 验证RDS文件
        if rds_path:
            rds_result = CelltypeValidationUtils.validate_file_path(
                rds_path, ['.rds', '.RDS']
            )
            file_status['rds'] = rds_result
            if not rds_result['valid']:
                issues.extend([f"RDS文件: {issue}" for issue in rds_result['issues']])
        
        # 验证H5AD文件
        if h5ad_path:
            h5ad_result = CelltypeValidationUtils.validate_file_path(
                h5ad_path, ['.h5ad', '.H5AD']
            )
            file_status['h5ad'] = h5ad_result
            if not h5ad_result['valid']:
                issues.extend([f"H5AD文件: {issue}" for issue in h5ad_result['issues']])
        
        # 验证marker基因JSON文件
        if marker_json_path:
            json_result = CelltypeValidationUtils.validate_file_path(
                marker_json_path, ['.json', '.JSON']
            )
            file_status['marker_json'] = json_result
            if not json_result['valid']:
                issues.extend([f"Marker基因文件: {issue}" for issue in json_result['issues']])
        
        # 检查是否至少提供了一个必要的文件
        if not any([rds_path, h5ad_path]):
            issues.append(_("validation.no_input_files_provided"))
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "file_status": file_status
        }
    
    @staticmethod
    def validate_annotation_method(method: str) -> Dict[str, Any]:
        """验证注释方法是否有效
        
        Args:
            method: 注释方法名称
            
        Returns:
            验证结果字典
        """
        valid_methods = ['SingleR', 'scType', 'CellTypist', 'pipeline']
        method_lower = method.lower() if method else ""
        
        method_mapping = {
            'singler': 'SingleR',
            'sctype': 'scType',
            'celltypist': 'CellTypist',
            'pipeline': 'pipeline'
        }
        
        normalized_method = method_mapping.get(method_lower)
        
        if not normalized_method:
            return {
                "valid": False,
                "error": _("validation.invalid_annotation_method", 
                          method=method, 
                          valid=', '.join(valid_methods))
            }
        
        method_descriptions = {
            'SingleR': _("annotation_method.singler_desc"),
            'scType': _("annotation_method.sctype_desc"),
            'CellTypist': _("annotation_method.celltypist_desc"),
            'pipeline': _("annotation_method.pipeline_desc")
        }
        
        return {
            "valid": True,
            "method": normalized_method,
            "description": method_descriptions.get(normalized_method, _("annotation_method.unknown"))
        }
    
    @staticmethod
    def validate_species(species: str) -> Dict[str, Any]:
        """验证物种是否支持
        
        Args:
            species: 物种名称
            
        Returns:
            验证结果字典
        """
        supported_species = ['Human', 'Mouse', 'human', 'mouse', 'Homo sapiens', 'Mus musculus']
        species_mapping = {
            'human': 'Human',
            'homo sapiens': 'Human',
            'h. sapiens': 'Human',
            'mouse': 'Mouse',
            'mus musculus': 'Mouse',
            'm. musculus': 'Mouse'
        }
        
        if not species:
            return {
                "valid": False,
                "error": _("validation.empty_species")
            }
        
        species_lower = species.lower().strip()
        normalized_species = species_mapping.get(species_lower, species)
        
        if normalized_species not in ['Human', 'Mouse']:
            return {
                "valid": False,
                "error": _("validation.unsupported_species", 
                          species=species, 
                          supported='Human, Mouse')
            }
        
        return {
            "valid": True,
            "species": normalized_species,
            "original": species
        }
    
    @staticmethod
    def validate_tissue_type(tissue_type: str) -> Dict[str, Any]:
        """验证组织类型描述
        
        Args:
            tissue_type: 组织类型描述
            
        Returns:
            验证结果字典
        """
        if not tissue_type or not tissue_type.strip():
            return {
                "valid": True,  # 组织类型是可选的
                "tissue_type": None,
                "note": _("validation.tissue_type_optional")
            }
        
        # 基本的组织类型关键词检查
        common_tissues = [
            'immune', 'blood', 'brain', 'lung', 'liver', 'heart', 
            'kidney', 'skin', 'muscle', 'bone',
            '免疫', '血液', '大脑', '肺', '肝', '心脏', '肾', '皮肤', '肌肉', '骨骼'
        ]
        
        tissue_lower = tissue_type.lower()
        recognized_keywords = [t for t in common_tissues if t in tissue_lower]
        
        return {
            "valid": True,
            "tissue_type": tissue_type.strip(),
            "recognized_keywords": recognized_keywords,
            "has_recognized_keywords": len(recognized_keywords) > 0
        }
    
    @staticmethod
    def validate_annotation_parameters(params: Dict[str, Any]) -> Dict[str, Any]:
        """验证注释参数
        
        Args:
            params: 注释参数字典
            
        Returns:
            验证结果字典
        """
        issues = []
        
        # 验证p值阈值
        pval_threshold = params.get('pval_threshold', 0.05)
        if not isinstance(pval_threshold, (int, float)) or pval_threshold <= 0 or pval_threshold > 1:
            issues.append(_("validation.invalid_pval_threshold", threshold=pval_threshold))
        
        # 验证输出路径
        output_path = params.get('output_path')
        if output_path:
            try:
                output_dir = Path(output_path).parent
                if not output_dir.exists():
                    issues.append(_("validation.output_dir_not_exist", dir=str(output_dir)))
            except Exception as e:
                issues.append(_("validation.invalid_output_path", error=str(e)))
        
        # 验证缓存目录
        cache_dir = params.get('cache_dir', '~/.cache/agentype')
        try:
            cache_path = Path(cache_dir).expanduser()
            # 尝试创建缓存目录
            cache_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            issues.append(_("validation.invalid_cache_dir", dir=cache_dir, error=str(e)))
        
        return {
            "valid": len(issues) == 0,
            "issues": issues
        }
    
    @staticmethod
    def validate_marker_json_content(json_data: Union[str, Dict]) -> Dict[str, Any]:
        """验证marker基因JSON文件内容格式
        
        Args:
            json_data: JSON字符串或已解析的字典
            
        Returns:
            验证结果字典
        """
        if isinstance(json_data, str):
            try:
                data = json.loads(json_data)
            except json.JSONDecodeError as e:
                return {
                    "valid": False,
                    "error": _("validation.json_decode_error", error=str(e))
                }
        else:
            data = json_data
        
        issues = []
        
        # 检查基本结构
        if not isinstance(data, dict):
            issues.append(_("validation.marker_json_not_dict"))
            return {"valid": False, "issues": issues}
        
        # 检查是否包含基因信息
        has_genes = False
        gene_count = 0
        
        for cluster, genes in data.items():
            if isinstance(genes, list) and genes:
                has_genes = True
                gene_count += len(genes)
                
                # 验证基因名格式
                invalid_genes = []
                for gene in genes:
                    if not isinstance(gene, str) or not re.match(r'^[A-Za-z0-9_.-]+$', gene):
                        invalid_genes.append(str(gene))
                
                if invalid_genes and len(invalid_genes) <= 5:  # 只显示前5个无效基因
                    issues.append(_("validation.invalid_genes_in_cluster", 
                                  cluster=cluster, 
                                  genes=', '.join(invalid_genes[:5])))
        
        if not has_genes:
            issues.append(_("validation.marker_json_no_genes"))
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "cluster_count": len(data),
            "total_genes": gene_count,
            "avg_genes_per_cluster": gene_count / len(data) if data else 0
        }
    
    @staticmethod
    def build_annotation_correction_prompt(validation_result: Dict[str, Any],
                                          available_tools: List[Dict],
                                          language: str = "zh") -> str:
        """构建细胞类型注释相关的修正提示

        Args:
            validation_result: 验证结果
            available_tools: 可用工具列表
            language: 语言

        Returns:
            修正提示字符串
        """
        from agentype.prompts import get_prompt_manager

        manager = get_prompt_manager(language)
        template = manager.get_agent_specific_prompt('appagent', 'ANNOTATION_CORRECTION_TEMPLATE')

        if not template:
            # 回退到通用修正模板
            template = manager.get_common_prompt('BASE_CORRECTION_TEMPLATE')

        issues = validation_result.get('issues', [])
        issues_text = '\n'.join(['- ' + issue for issue in issues])
        tools_text = ', '.join([tool.get('name', '未知') for tool in available_tools])

        return template.format(
            issues=issues_text,
            available_tools=tools_text
        )