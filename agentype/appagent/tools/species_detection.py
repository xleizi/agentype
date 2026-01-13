#!/usr/bin/env python3
"""
agentype - 物种检测工具模块
Author: cuilei
Version: 1.0
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import logging

# 设置日志
logger = logging.getLogger(__name__)

class SpeciesDetector:
    """统一的物种检测工具类
    
    根据基因符号自动判断物种类型
    """
    
    def __init__(self, 
                 uppercase_threshold: float = 0.8,
                 min_genes_required: int = 10):
        """初始化物种检测器
        
        Args:
            uppercase_threshold: 大写基因比例阈值，超过此值判断为人类
            min_genes_required: 检测所需的最少基因数量
        """
        self.uppercase_threshold = uppercase_threshold
        self.min_genes_required = min_genes_required
    
    def detect_species_from_genes(self, gene_symbols: List[str]) -> Tuple[str, Dict[str, Any]]:
        """根据基因符号自动判断物种
        
        Args:
            gene_symbols: 基因符号列表
            
        Returns:
            (物种名称, 检测详情) - 物种名称为 "Human" 或 "Mouse"
        """
        if not gene_symbols:
            logger.warning("基因列表为空，默认返回人类")
            return "Human", {
                "total_genes": 0,
                "valid_genes": 0,
                "uppercase_count": 0,
                "uppercase_ratio": 0.0,
                "threshold": self.uppercase_threshold,
                "confidence": "low",
                "reason": "empty_gene_list"
            }
        
        # 过滤掉空字符串和无效基因
        valid_genes = [gene.strip() for gene in gene_symbols 
                      if gene and gene.strip() and gene.strip().upper() not in ['', 'NA', 'NULL', 'NONE']]
        
        if len(valid_genes) < self.min_genes_required:
            logger.warning(f"有效基因数量不足 ({len(valid_genes)} < {self.min_genes_required})，默认返回人类")
            return "Human", {
                "total_genes": len(gene_symbols),
                "valid_genes": len(valid_genes),
                "uppercase_count": 0,
                "uppercase_ratio": 0.0,
                "threshold": self.uppercase_threshold,
                "confidence": "low",
                "reason": "insufficient_valid_genes"
            }
        
        # 计算全大写基因的比例
        uppercase_count = sum(1 for gene in valid_genes if gene.isupper())
        uppercase_ratio = uppercase_count / len(valid_genes)
        
        # 判断物种
        if uppercase_ratio >= self.uppercase_threshold:
            species = "Human"
            logger.debug(f"检测到人类基因 (大写比例: {uppercase_ratio:.3f})")
        else:
            species = "Mouse"
            logger.debug(f"检测到小鼠基因 (大写比例: {uppercase_ratio:.3f})")
        
        # 计算置信度
        confidence_diff = abs(uppercase_ratio - self.uppercase_threshold)
        if confidence_diff > 0.3:
            confidence = "high"
        elif confidence_diff > 0.1:
            confidence = "medium"
        else:
            confidence = "low"
        
        detection_info = {
            "total_genes": len(gene_symbols),
            "valid_genes": len(valid_genes),
            "uppercase_count": uppercase_count,
            "uppercase_ratio": round(uppercase_ratio, 3),
            "threshold": self.uppercase_threshold,
            "detected_species": species,
            "confidence": confidence,
            "confidence_score": round(confidence_diff, 3)
        }
        
        return species, detection_info


def detect_species_from_h5ad(h5ad_file: str) -> Tuple[str, Dict[str, Any]]:
    """从H5AD文件检测物种
    
    Args:
        h5ad_file: H5AD文件路径
        
    Returns:
        (物种名称, 检测详情)
    """
    try:
        import scanpy as sc
        
        # 检查文件是否存在
        if not os.path.exists(h5ad_file):
            raise FileNotFoundError(f"H5AD文件不存在: {h5ad_file}")
        
        logger.info(f"正在从H5AD文件检测物种: {h5ad_file}")
        
        # 读取H5AD文件
        adata = sc.read_h5ad(h5ad_file)
        
        # 获取基因名称
        gene_names = adata.var.index.tolist()
        
        logger.info(f"从H5AD文件提取到 {len(gene_names)} 个基因")
        
        # 使用物种检测器进行检测（调整参数以适应小样本）
        detector = SpeciesDetector(min_genes_required=1, uppercase_threshold=0.7)
        species, detection_info = detector.detect_species_from_genes(gene_names)
        
        # 添加文件信息
        detection_info.update({
            "input_file": h5ad_file,
            "file_type": "h5ad",
            "n_cells": adata.n_obs,
            "n_genes": adata.n_vars
        })
        
        logger.info(f"H5AD文件物种检测完成: {species} (置信度: {detection_info['confidence']})")
        
        return species, detection_info
        
    except ImportError:
        error_msg = "缺少scanpy依赖，无法读取H5AD文件"
        logger.error(error_msg)
        return "Human", {
            "error": error_msg,
            "input_file": h5ad_file,
            "file_type": "h5ad",
            "confidence": "low"
        }
    except Exception as e:
        error_msg = f"读取H5AD文件时发生错误: {str(e)}"
        logger.error(error_msg)
        return "Human", {
            "error": error_msg,
            "input_file": h5ad_file,
            "file_type": "h5ad",
            "confidence": "low"
        }


def detect_species_from_rds(rds_file: str) -> Tuple[str, Dict[str, Any]]:
    """从RDS文件检测物种
    
    Args:
        rds_file: RDS文件路径
        
    Returns:
        (物种名称, 检测详情)
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(rds_file):
            raise FileNotFoundError(f"RDS文件不存在: {rds_file}")
        
        logger.info(f"正在从RDS文件检测物种: {rds_file}")
        
        # 创建临时R脚本来提取基因名称
        r_script = f'''
        # 加载必要的库
        library(Seurat)
        library(jsonlite)
        
        # 读取RDS文件
        tryCatch({{
            seurat_obj <- readRDS("{rds_file}")
            
            # 获取基因名称
            if (class(seurat_obj)[1] == "Seurat") {{
                gene_names <- rownames(seurat_obj)
                n_cells <- ncol(seurat_obj)
                n_genes <- nrow(seurat_obj)
            }} else {{
                # 尝试其他可能的对象类型
                gene_names <- rownames(seurat_obj)
                n_cells <- ifelse(is.null(ncol(seurat_obj)), 0, ncol(seurat_obj))
                n_genes <- length(gene_names)
            }}
            
            # 创建结果
            result <- list(
                success = TRUE,
                gene_names = gene_names,
                n_cells = n_cells,
                n_genes = n_genes,
                object_class = class(seurat_obj)[1]
            )
            
            # 输出JSON结果
            cat(toJSON(result, auto_unbox = TRUE))
            
        }}, error = function(e) {{
            result <- list(
                success = FALSE,
                error = as.character(e),
                gene_names = character(0),
                n_cells = 0,
                n_genes = 0
            )
            cat(toJSON(result, auto_unbox = TRUE))
        }})
        '''
        
        # 写入临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.R', delete=False) as f:
            f.write(r_script)
            temp_r_file = f.name
        
        try:
            # 执行R脚本
            result = subprocess.run(
                ['Rscript', temp_r_file],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"R脚本执行失败: {result.stderr}")
            
            # 解析R脚本输出
            r_output = json.loads(result.stdout.strip())
            
            if not r_output.get('success', False):
                raise RuntimeError(f"R脚本内部错误: {r_output.get('error', '未知错误')}")
            
            gene_names = r_output.get('gene_names', [])
            
            logger.info(f"从RDS文件提取到 {len(gene_names)} 个基因")
            
            # 使用物种检测器进行检测
            detector = SpeciesDetector()
            species, detection_info = detector.detect_species_from_genes(gene_names)
            
            # 添加文件信息
            detection_info.update({
                "input_file": rds_file,
                "file_type": "rds",
                "n_cells": r_output.get('n_cells', 0),
                "n_genes": r_output.get('n_genes', 0),
                "object_class": r_output.get('object_class', 'unknown')
            })
            
            logger.info(f"RDS文件物种检测完成: {species} (置信度: {detection_info['confidence']})")
            
            return species, detection_info
            
        finally:
            # 清理临时文件
            if os.path.exists(temp_r_file):
                os.unlink(temp_r_file)
        
    except FileNotFoundError as e:
        error_msg = str(e)
        logger.error(error_msg)
        return "Human", {
            "error": error_msg,
            "input_file": rds_file,
            "file_type": "rds",
            "confidence": "low"
        }
    except Exception as e:
        error_msg = f"读取RDS文件时发生错误: {str(e)}"
        logger.error(error_msg)
        return "Human", {
            "error": error_msg,
            "input_file": rds_file,
            "file_type": "rds",
            "confidence": "low"
        }


def detect_species_from_marker_json(marker_genes_json: str) -> Tuple[str, Dict[str, Any]]:
    """从marker基因JSON文件检测物种

    Args:
        marker_genes_json: marker基因JSON文件路径

    Returns:
        (物种名称, 检测详情)
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(marker_genes_json):
            raise FileNotFoundError(f"JSON文件不存在: {marker_genes_json}")

        logger.info(f"正在从JSON文件检测物种: {marker_genes_json}")

        # 读取JSON文件
        with open(marker_genes_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 提取基因名称
        gene_names = []
        
        # 尝试不同的JSON结构来提取基因
        if isinstance(data, dict):
            # 情况1: {"cell_type1": ["gene1", "gene2"], "cell_type2": ["gene3", "gene4"]}
            if all(isinstance(v, list) for v in data.values()):
                for gene_list in data.values():
                    gene_names.extend(gene_list)
            
            # 情况2: {"genes": ["gene1", "gene2", "gene3"]}
            elif 'genes' in data and isinstance(data['genes'], list):
                gene_names = data['genes']
            
            # 情况3: {"markers": [{"gene": "gene1"}, {"gene": "gene2"}]}
            elif 'markers' in data and isinstance(data['markers'], list):
                gene_names = [item.get('gene', '') for item in data['markers'] if isinstance(item, dict)]
            
            # 情况4: 查找所有可能包含基因的字段
            else:
                possible_keys = ['gene', 'genes', 'symbol', 'symbols', 'marker', 'markers']
                for key in data:
                    if key.lower() in possible_keys:
                        if isinstance(data[key], list):
                            gene_names.extend(data[key])
                        elif isinstance(data[key], str):
                            gene_names.append(data[key])
        
        elif isinstance(data, list):
            # 情况5: [{"gene": "gene1"}, {"gene": "gene2"}]
            if all(isinstance(item, dict) for item in data):
                for item in data:
                    if 'gene' in item:
                        gene_names.append(item['gene'])
                    elif 'symbol' in item:
                        gene_names.append(item['symbol'])
            
            # 情况6: ["gene1", "gene2", "gene3"]
            elif all(isinstance(item, str) for item in data):
                gene_names = data
        
        # 去除重复和空值
        gene_names = list(set(gene for gene in gene_names if gene and isinstance(gene, str)))
        
        logger.info(f"从JSON文件提取到 {len(gene_names)} 个基因")
        
        if len(gene_names) == 0:
            raise ValueError("JSON文件中未找到有效的基因信息")
        
        # 使用物种检测器进行检测（调整参数以适应小样本）
        detector = SpeciesDetector(min_genes_required=1, uppercase_threshold=0.7)
        species, detection_info = detector.detect_species_from_genes(gene_names)
        
        # 添加文件信息
        detection_info.update({
            "input_file": marker_genes_json,
            "file_type": "marker_json",
            "json_structure": type(data).__name__,
            "unique_genes": len(gene_names)
        })

        logger.info(f"JSON文件物种检测完成: {species} (置信度: {detection_info['confidence']})")

        return species, detection_info

    except FileNotFoundError as e:
        error_msg = str(e)
        logger.error(error_msg)
        return "Human", {
            "error": error_msg,
            "input_file": marker_genes_json,
            "file_type": "marker_json",
            "confidence": "low"
        }
    except json.JSONDecodeError as e:
        error_msg = f"JSON文件格式错误: {str(e)}"
        logger.error(error_msg)
        return "Human", {
            "error": error_msg,
            "input_file": marker_genes_json,
            "file_type": "marker_json",
            "confidence": "low"
        }
    except Exception as e:
        error_msg = f"读取JSON文件时发生错误: {str(e)}"
        logger.error(error_msg)
        return "Human", {
            "error": error_msg,
            "input_file": marker_genes_json,
            "file_type": "marker_json",
            "confidence": "low"
        }