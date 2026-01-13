#!/usr/bin/env python3
"""
agentype - 文件验证工具模块
Author: cuilei
Version: 1.0
"""

import json
import os
from typing import Dict, Any, List, Union
from pathlib import Path
import logging

# 设置日志
logger = logging.getLogger(__name__)


def validate_marker_json(marker_genes_json: str) -> Dict[str, Any]:
    """验证marker基因JSON文件格式

    Args:
        marker_genes_json: JSON文件路径

    Returns:
        验证结果字典，包含是否有效、错误信息等
    """
    result = {
        "valid": False,
        "file_path": marker_genes_json,
        "file_exists": False,
        "file_size": 0,
        "json_valid": False,
        "structure_valid": False,
        "gene_count": 0,
        "errors": [],
        "warnings": [],
        "structure_type": None,
        "detected_fields": []
    }

    try:
        # 检查文件是否存在
        if not os.path.exists(marker_genes_json):
            result["errors"].append(f"文件不存在: {marker_genes_json}")
            return result

        result["file_exists"] = True
        result["file_size"] = os.path.getsize(marker_genes_json)

        # 检查文件大小
        if result["file_size"] == 0:
            result["errors"].append("文件为空")
            return result

        if result["file_size"] > 100 * 1024 * 1024:  # 100MB
            result["warnings"].append("文件过大（>100MB），可能影响处理性能")

        # 读取并验证JSON格式
        try:
            with open(marker_genes_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            result["json_valid"] = True
        except json.JSONDecodeError as e:
            result["errors"].append(f"JSON格式错误: {str(e)}")
            return result
        except UnicodeDecodeError as e:
            result["errors"].append(f"文件编码错误: {str(e)}")
            return result

        # 验证JSON结构和内容
        gene_count, structure_info = _validate_json_structure(data)

        result.update(structure_info)
        result["gene_count"] = gene_count

        # 判断结构是否有效
        if gene_count > 0:
            result["structure_valid"] = True
            result["valid"] = True
        else:
            result["errors"].append("未找到有效的基因信息")

        # 添加建议和警告
        if gene_count < 10:
            result["warnings"].append(f"基因数量较少（{gene_count}个），可能影响物种检测准确性")

        logger.info(f"JSON文件验证完成: {marker_genes_json} - 有效: {result['valid']}, 基因数: {gene_count}")

        return result

    except Exception as e:
        result["errors"].append(f"验证过程中发生未知错误: {str(e)}")
        logger.error(f"验证JSON文件时发生错误: {str(e)}")
        return result


def _validate_json_structure(data: Union[Dict, List]) -> tuple[int, Dict[str, Any]]:
    """验证JSON结构并提取基因信息
    
    Args:
        data: 解析后的JSON数据
        
    Returns:
        (基因数量, 结构信息字典)
    """
    structure_info = {
        "structure_type": None,
        "detected_fields": [],
        "sample_genes": [],
        "cell_types": []
    }
    
    gene_names = set()
    
    try:
        if isinstance(data, dict):
            structure_info["detected_fields"] = list(data.keys())
            
            # 结构类型1: {"cell_type1": ["gene1", "gene2"], "cell_type2": ["gene3"]}
            if all(isinstance(v, list) for v in data.values()):
                structure_info["structure_type"] = "cell_type_to_genes"
                structure_info["cell_types"] = list(data.keys())
                
                for cell_type, genes in data.items():
                    if isinstance(genes, list):
                        valid_genes = [g for g in genes if isinstance(g, str) and g.strip()]
                        gene_names.update(valid_genes)
            
            # 结构类型2: {"genes": ["gene1", "gene2", "gene3"]}
            elif 'genes' in data and isinstance(data['genes'], list):
                structure_info["structure_type"] = "simple_gene_list"
                valid_genes = [g for g in data['genes'] if isinstance(g, str) and g.strip()]
                gene_names.update(valid_genes)
            
            # 结构类型3: {"markers": [{"gene": "gene1", "cell_type": "T cell"}, ...]}
            elif 'markers' in data and isinstance(data['markers'], list):
                structure_info["structure_type"] = "marker_objects"
                for item in data['markers']:
                    if isinstance(item, dict):
                        # 查找基因字段
                        gene_fields = ['gene', 'symbol', 'marker', 'gene_symbol']
                        for field in gene_fields:
                            if field in item and isinstance(item[field], str):
                                gene_names.add(item[field].strip())
                                break
                        
                        # 记录细胞类型
                        if 'cell_type' in item:
                            structure_info["cell_types"].append(item['cell_type'])
            
            # 结构类型4: 通用字段搜索
            else:
                structure_info["structure_type"] = "mixed_structure"
                possible_keys = ['gene', 'genes', 'symbol', 'symbols', 'marker', 'markers']
                
                for key, value in data.items():
                    if key.lower() in possible_keys:
                        if isinstance(value, list):
                            valid_genes = [g for g in value if isinstance(g, str) and g.strip()]
                            gene_names.update(valid_genes)
                        elif isinstance(value, str) and value.strip():
                            gene_names.add(value.strip())
        
        elif isinstance(data, list):
            # 结构类型5: [{"gene": "gene1"}, {"gene": "gene2"}]
            if data and isinstance(data[0], dict):
                structure_info["structure_type"] = "object_list"
                gene_fields = ['gene', 'symbol', 'marker', 'gene_symbol']
                
                for item in data:
                    if isinstance(item, dict):
                        for field in gene_fields:
                            if field in item and isinstance(item[field], str):
                                gene_names.add(item[field].strip())
                                if field not in structure_info["detected_fields"]:
                                    structure_info["detected_fields"].append(field)
                                break
            
            # 结构类型6: ["gene1", "gene2", "gene3"]
            elif data and isinstance(data[0], str):
                structure_info["structure_type"] = "string_list"
                valid_genes = [g.strip() for g in data if isinstance(g, str) and g.strip()]
                gene_names.update(valid_genes)
        
        else:
            structure_info["structure_type"] = "unknown"
        
        # 生成样例基因列表（最多显示10个）
        gene_list = list(gene_names)
        structure_info["sample_genes"] = gene_list[:10]
        
        # 去重细胞类型
        structure_info["cell_types"] = list(set(structure_info["cell_types"]))[:20]  # 最多显示20个
        
        return len(gene_names), structure_info
        
    except Exception as e:
        logger.error(f"解析JSON结构时发生错误: {str(e)}")
        return 0, structure_info


def validate_file_accessibility(file_path: str) -> Dict[str, Any]:
    """验证文件是否可访问
    
    Args:
        file_path: 文件路径
        
    Returns:
        验证结果字典
    """
    result = {
        "accessible": False,
        "exists": False,
        "readable": False,
        "file_size": 0,
        "file_type": None,
        "absolute_path": None,
        "errors": []
    }
    
    try:
        # 转换为绝对路径
        abs_path = os.path.abspath(file_path)
        result["absolute_path"] = abs_path
        
        # 检查文件是否存在
        if not os.path.exists(abs_path):
            result["errors"].append(f"文件不存在: {abs_path}")
            return result
        
        result["exists"] = True
        
        # 检查是否为文件（而不是目录）
        if not os.path.isfile(abs_path):
            result["errors"].append(f"路径不是文件: {abs_path}")
            return result
        
        # 检查文件是否可读
        if not os.access(abs_path, os.R_OK):
            result["errors"].append(f"文件不可读: {abs_path}")
            return result
        
        result["readable"] = True
        
        # 获取文件信息
        result["file_size"] = os.path.getsize(abs_path)
        
        # 根据扩展名推断文件类型
        file_ext = Path(abs_path).suffix.lower()
        extension_map = {
            '.json': 'marker_json',
            '.h5ad': 'h5ad',
            '.rds': 'rds',
            '.h5': 'h5',
            '.csv': 'csv',
            '.tsv': 'tsv',
            '.txt': 'text'
        }
        result["file_type"] = extension_map.get(file_ext, 'unknown')
        
        result["accessible"] = True
        
        return result
        
    except Exception as e:
        result["errors"].append(f"验证文件访问性时发生错误: {str(e)}")
        return result


def get_file_summary(file_path: str) -> Dict[str, Any]:
    """获取文件概要信息
    
    Args:
        file_path: 文件路径
        
    Returns:
        文件概要信息字典
    """
    try:
        access_info = validate_file_accessibility(file_path)
        
        summary = {
            "file_path": file_path,
            "absolute_path": access_info.get("absolute_path"),
            "accessible": access_info.get("accessible", False),
            "file_type": access_info.get("file_type"),
            "file_size": access_info.get("file_size", 0),
            "file_size_readable": _format_file_size(access_info.get("file_size", 0)),
            "errors": access_info.get("errors", [])
        }
        
        # 如果是JSON文件，进行详细验证
        if access_info.get("file_type") == "marker_json" and access_info.get("accessible"):
            json_validation = validate_marker_json(file_path)
            summary.update({
                "json_valid": json_validation.get("json_valid", False),
                "structure_valid": json_validation.get("structure_valid", False),
                "gene_count": json_validation.get("gene_count", 0),
                "structure_type": json_validation.get("structure_type"),
                "validation_errors": json_validation.get("errors", []),
                "validation_warnings": json_validation.get("warnings", [])
            })
        
        return summary
        
    except Exception as e:
        return {
            "file_path": file_path,
            "accessible": False,
            "error": f"获取文件概要时发生错误: {str(e)}"
        }


def _format_file_size(size_bytes: int) -> str:
    """格式化文件大小
    
    Args:
        size_bytes: 文件大小（字节）
        
    Returns:
        格式化后的文件大小字符串
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    return f"{size:.1f} {size_names[i]}"