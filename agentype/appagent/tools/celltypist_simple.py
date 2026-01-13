#!/usr/bin/env python3
"""
agentype - CellTypist 极简Python工具
Author: cuilei
Version: 1.0
"""

import json
import os
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict, Any
import warnings
warnings.filterwarnings('ignore')

# 设置日志
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



def standardize_cluster_name(cluster):
    """标准化簇名称，确保与scType/SingleR一致

    将浮点数形式的簇编号（如 0.0, 1.0）转换为整数形式（如 0, 1），
    以保持与其他注释工具的命名一致性。

    Args:
        cluster: 簇编号（可能是整数、浮点数或字符串）

    Returns:
        标准化的簇名称字符串，格式为 "cluster{整数编号}"
    """
    cluster_str = str(cluster)
    # 如果是浮点数形式（如 "0.0", "1.0"），转换为整数
    if '.' in cluster_str:
        try:
            return f"cluster{int(float(cluster))}"
        except ValueError:
            # 如果转换失败，保持原样
            return f"cluster{cluster}"
    return f"cluster{cluster}"


class SpeciesDetector:
    """统一的物种检测工具类
    
    根据基因符号自动判断物种类型
    """
    
    def __init__(self, 
                 uppercase_threshold: float = 0.9,
                 min_genes_required: int = 1):
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
            (物种名称, 检测详情) - 物种名称为 "human" 或 "mouse"
        """
        if not gene_symbols:
            logger.warning("基因列表为空，默认返回人类")
            return "human", {
                "total_genes": 0,
                "valid_genes": 0,
                "uppercase_count": 0,
                "uppercase_ratio": 0.0,
                "threshold": self.uppercase_threshold,
                "reason": "empty_gene_list"
            }
        
        # 过滤掉空字符串和无效基因
        valid_genes = [gene.strip() for gene in gene_symbols 
                      if gene and gene.strip() and gene.strip().upper() not in ['', 'NA', 'NULL', 'NONE']]
        
        if len(valid_genes) < self.min_genes_required:
            logger.warning(f"有效基因数量不足 ({len(valid_genes)} < {self.min_genes_required})，默认返回人类")
            return "human", {
                "total_genes": len(gene_symbols),
                "valid_genes": len(valid_genes),
                "uppercase_count": 0,
                "uppercase_ratio": 0.0,
                "threshold": self.uppercase_threshold,
                "reason": "insufficient_valid_genes"
            }
        
        # 计算全大写基因的比例
        uppercase_count = sum(1 for gene in valid_genes if gene.isupper())
        uppercase_ratio = uppercase_count / len(valid_genes)
        
        # 判断物种
        if uppercase_ratio >= self.uppercase_threshold:
            species = "human"
            logger.debug(f"检测到人类基因 (大写比例: {uppercase_ratio:.2f})")
        else:
            species = "mouse"
            logger.debug(f"检测到小鼠基因 (大写比例: {uppercase_ratio:.2f})")
        
        detection_info = {
            "total_genes": len(gene_symbols),
            "valid_genes": len(valid_genes),
            "uppercase_count": uppercase_count,
            "uppercase_ratio": uppercase_ratio,
            "threshold": self.uppercase_threshold,
            "detected_species": species,
            "confidence": "high" if abs(uppercase_ratio - self.uppercase_threshold) > 0.1 else "medium"
        }
        
        return species, detection_info
    
    def detect_species_simple(self, gene_symbols: List[str]) -> str:
        """简化的物种检测，只返回物种名称
        
        Args:
            gene_symbols: 基因符号列表
            
        Returns:
            物种名称 ("human" 或 "mouse")
        """
        species, _ = self.detect_species_from_genes(gene_symbols)
        return species
    
    @staticmethod
    def standardize_species_name(species: str) -> str:
        """标准化物种名称
        
        Args:
            species: 原始物种名称
            
        Returns:
            标准化的物种名称
        """
        species_lower = species.lower().strip()
        
        if species_lower in ['human', 'homo sapiens', 'hs', 'h_sapiens', 'homo_sapiens']:
            return 'human'
        elif species_lower in ['mouse', 'mus musculus', 'mm', 'm_musculus', 'mus_musculus']:
            return 'mouse'
        else:
            logger.warning(f"未知物种名称: {species}，默认返回 human")
            return 'human'


def celltypist_annotate(data_path, model_name=None, output_path=None, auto_detect_species=True, cluster_column=None, max_cells_per_cluster=2000, random_seed=42):
    """
    使用CellTypist进行细胞类型注释

    参数:
        data_path: H5AD文件路径
        model_name: CellTypist模型名称，为None时根据物种自动选择
        output_path: 输出JSON文件路径，默认保存到 .agentype_cache/ 目录
        auto_detect_species: 是否自动检测物种并选择合适模型
        cluster_column: 聚类列名，为None时自动搜索 ['seurat_clusters', 'leiden', 'louvain']
        max_cells_per_cluster: 每个簇最多保留的细胞数，默认2000
        random_seed: 随机种子，用于确保抽样结果可重复，默认42

    返回:
        注释结果的字典，包含每个簇对应的细胞类型
    """
    
    # 检查依赖
    try:
        import scanpy as sc
        import celltypist
        from celltypist import models
    except ImportError as e:
        raise RuntimeError(f"缺少必要的依赖包: {e}. 请安装: pip install celltypist scanpy")
    
    # 检查文件
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"数据文件不存在: {data_path}")
    
    # 检测文件格式
    file_ext = os.path.splitext(data_path)[1].lower()
    if file_ext not in ['.h5ad', '.h5']:
        raise ValueError(f"不支持的文件格式: {file_ext}，仅支持 .h5ad 和 .h5 格式")
    
    is_h5_format = file_ext == '.h5'
    
    # 设置输出文件
    if output_path is None:
        # 使用统一配置系统
        from agentype.config import get_session_id_for_filename
        from agentype.appagent.services import mcp_server
        output_dir = mcp_server._CONFIG.get_results_dir()
        session_id = get_session_id_for_filename()
        output_path = output_dir / f"celltypist_annotation_result_{session_id}.json"
    
    try:
        # 根据文件格式读取数据
        print(f"读取数据: {data_path}")
        if is_h5_format:
            # 使用easySCFpy读取H5文件
            try:
                from easySCFpy import loadH5
                print("使用easySCFpy读取H5格式数据...")
                adata = loadH5(data_path)

            except ImportError:
                print("easySCFpy不可用，尝试使用scanpy读取H5文件...")
                adata = sc.read_10x_h5(data_path)
                adata.var_names_unique()
                
        else:
            # 读取H5AD文件
            adata = sc.read_h5ad(data_path)
            
        print(f"数据: {adata.n_obs} 细胞, {adata.n_vars} 基因")
        
        # 数据验证和标准化
        if not hasattr(adata, 'raw') or adata.raw is None:
            # 如果没有raw数据，需要确保数据格式正确
            if hasattr(adata, 'X') and adata.X is not None:
                # 保存原始数据到raw
                adata.raw = adata
            else:
                raise ValueError("数据文件缺少有效的表达矩阵")
        
        # 物种检测和模型选择
        detected_species = None
        species_info = None
        
        if model_name is None and auto_detect_species:
            # 自动检测物种并选择模型
            detector = SpeciesDetector()
            gene_symbols = list(adata.var_names)
            detected_species, species_info = detector.detect_species_from_genes(gene_symbols)
            
            # 根据物种选择默认模型
            if detected_species == "human":
                model_name = "Immune_All_High.pkl"
                print(f"✓ 检测到人类数据，使用默认模型: {model_name}")
            else:  # mouse
                model_name = "Mouse_Whole_Brain.pkl"
                print(f"✓ 检测到小鼠数据，使用默认模型: {model_name}")
            
            print(f"物种检测结果: {species_info}")
        elif model_name is None:
            # 如果没有指定模型且不自动检测，使用人类默认模型
            model_name = "Immune_All_High.pkl"
            print(f"使用默认人类模型: {model_name}")
        else:
            print(f"使用指定模型: {model_name}")
        
        # 下载模型
        print(f"下载模型: {model_name}")
        models.download_models(model=model_name, force_update=False)

        # ========== 按簇抽样（预处理之前）==========
        print("\n开始按簇抽样（预处理前）...")

        # 检测聚类列
        detected_cluster_col = cluster_column or 'seurat_clusters'
        if detected_cluster_col not in adata.obs.columns:
            for col in ['leiden', 'louvain', 'clusters']:
                if col in adata.obs.columns:
                    detected_cluster_col = col
                    break

        if detected_cluster_col not in adata.obs.columns:
            # 未找到聚类列，进行整体随机抽样
            print("警告: 未找到聚类信息列（已尝试: seurat_clusters, leiden, louvain, clusters）")
            print(f"将进行整体随机抽样: 最多 20000 个细胞")

            original_count = adata.n_obs
            original_adata = adata

            # 如果细胞数超过20000，随机抽样20000个
            if adata.n_obs > 20000:
                np.random.seed(random_seed)
                sampled_indices = np.random.choice(
                    adata.n_obs,
                    size=20000,
                    replace=False
                )
                adata = original_adata[sampled_indices, :].copy()
            else:
                # 细胞数不足20000，保留所有细胞
                print(f"细胞数 {adata.n_obs} 少于 20000，保留所有细胞")
                adata = original_adata.copy()

            # 释放原始数据内存
            del original_adata
            import gc
            gc.collect()

            print(f"整体抽样完成: {original_count} → {adata.n_obs} 细胞")
            if original_count > 20000:
                print(f"减少比例: {(1 - adata.n_obs/original_count)*100:.1f}%")
            print(f"原始数据内存已释放\n")
        else:
            # 找到聚类列，按簇抽样
            print(f"使用聚类列: {detected_cluster_col}")
            print(f"每个簇抽样: {max_cells_per_cluster} 个细胞")

            original_count = adata.n_obs

            # 保存原始对象引用用于后续删除
            original_adata = adata

            # 使用 groupby + sample 进行分层抽样
            sampled_obs = adata.obs.groupby(detected_cluster_col, group_keys=False).apply(
                lambda x: x.sample(
                    n=min(len(x), max_cells_per_cluster),
                    random_state=random_seed,
                    replace=False
                )
            )

            # 创建抽样后的新 AnnData 对象
            adata = original_adata[sampled_obs.index, :].copy()

            # 释放原始数据内存
            del original_adata
            del sampled_obs
            import gc
            gc.collect()

            print(f"按簇抽样完成: {original_count} → {adata.n_obs} 细胞 "
                  f"({(1 - adata.n_obs/original_count)*100:.1f}% 减少)")
            print(f"原始数据内存已释放\n")

        # 数据预处理（在抽样后的数据上执行）
        print("数据预处理（抽样后数据）...")
        # 处理稀疏矩阵
        import scipy.sparse as sp
        adata = adata.raw.to_adata()
        if sp.issparse(adata.X):
            adata.X = adata.X.toarray()
        
        # 清理异常值
        adata.X = np.nan_to_num(adata.X, nan=0.0, posinf=0.0, neginf=0.0)
        if np.any(adata.X < 0):
            adata.X = np.abs(adata.X)
        
        # 标准化
        sc.pp.normalize_total(adata, target_sum=1e4)
        sc.pp.log1p(adata)
        adata.X = np.nan_to_num(adata.X, nan=0.0, posinf=0.0, neginf=0.0)
        adata.uns['log1p'] = {'base': None}

        # CellTypist注释
        print("开始CellTypist注释...")
        predictions = celltypist.annotate(adata, model=model_name, majority_voting=True)
        print("注释完成")
        
        # 分析聚类结果
        predicted_labels = predictions.predicted_labels
        cluster_annotations = {}
        
        # 查找聚类信息
        if cluster_column:
            # 用户指定了聚类列
            if cluster_column in adata.obs.columns:
                print(f"✓ 使用指定的聚类列: {cluster_column}")
            else:
                print(f"⚠️ 指定的聚类列 '{cluster_column}' 不存在，尝试自动搜索")
                cluster_column = None

        if cluster_column is None:
            # 自动搜索聚类列
            for key in ['seurat_clusters', 'leiden', 'louvain']:
                if key in adata.obs.columns:
                    cluster_column = key
                    print(f"✓ 使用 {cluster_column} 聚类信息")
                    break

        if cluster_column is None:
            # 没有聚类信息，使用整体结果
            print("⚠ 未找到聚类信息，使用整体注释结果")
            celltype_counts = predicted_labels['predicted_labels'].value_counts()
            dominant_celltype = celltype_counts.index[0]
            # 使用标准化的簇名称
            cluster_annotations[standardize_cluster_name(0)] = {
                "celltype": str(dominant_celltype),
                "proportion": round(float(celltype_counts.iloc[0]) / len(predicted_labels), 4)
            }
            return cluster_annotations
        
        # 分析每个聚类
        clusters = adata.obs[cluster_column].unique()
        for cluster in sorted(clusters):
            cluster_mask = adata.obs[cluster_column] == cluster
            cluster_predictions = predicted_labels.loc[cluster_mask, 'predicted_labels']

            if len(cluster_predictions) > 0:
                celltype_counts = cluster_predictions.value_counts()
                dominant_celltype = celltype_counts.index[0]
                proportion = celltype_counts.iloc[0] / len(cluster_predictions)

                # 使用标准化的簇名称，确保与scType/SingleR一致
                cluster_annotations[standardize_cluster_name(cluster)] = {
                    "celltype": str(dominant_celltype),
                    "proportion": round(float(proportion), 4)
                }
        
        # 保存详细结果
        result = {
            "cluster_annotations": cluster_annotations,
            "model_used": model_name,
            "total_cells": int(adata.n_obs),
            "annotation_date": str(datetime.now().date())
        }
        
        # 添加物种检测信息
        if detected_species and species_info:
            result["species_detection"] = {
                "detected_species": detected_species,
                "detection_info": species_info,
                "auto_model_selection": True
            }
        elif detected_species:
            result["species_detection"] = {
                "detected_species": detected_species,
                "auto_model_selection": False
            }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"结果已保存到: {output_path}")
        
        return {
            "success": True,
            "method": "CellTypist",
            "output_file": str(output_path),
            "input_file": data_path,
            "model_name": model_name,
        }
        
    except Exception as e:
        raise RuntimeError(f"CellTypist注释失败: {e}")


if __name__ == "__main__":
    try:
        # 使用自动物种检测和模型选择
        result = celltypist_annotate("/root/code/gitpackage/agentype/utils/data.h5ad", 
                                   model_name=None, 
                                   auto_detect_species=True)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"注释失败: {e}")
