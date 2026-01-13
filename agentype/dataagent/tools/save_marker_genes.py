#!/usr/bin/env python3
"""
agentype - Save Marker Genes模块
Author: cuilei
Version: 1.0
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

# 导入项目模块

# 导入统一配置系统
from agentype.config import get_session_id_for_filename

def save_marker_genes_to_json(sce, pval_threshold: float = 0.05, config=None) -> Optional[Dict[str, List[str]]]:
    """
    将rank_genes_groups的结果保存为简化的JSON格式

    参数:
    sce: AnnData对象，包含rank_genes_groups结果
    pval_threshold: p值阈值，默认为0.05

    返回:
    marker_genes: 包含每个分簇marker基因的字典，失败时返回None

    注意:
    输出文件会自动保存到配置的结果目录，使用 session_id 命名
    """
    # 使用 session_id 作为文件名
    session_id = get_session_id_for_filename()
    if config:
        results_dir = config.get_results_dir()
    else:
        # 降级：从mcp_server模块获取
        from agentype.dataagent.services import mcp_server
        results_dir = mcp_server._CONFIG.get_results_dir()
    output_file = str(results_dir / f'cluster_marker_genes_{session_id}.json')
    
    try:
        # 检查是否存在rank_genes_groups结果
        if 'rank_genes_groups' not in sce.uns:
            print("错误：未找到rank_genes_groups结果，请先运行sc.tl.rank_genes_groups")
            return None
        
        # 确保输出目录存在
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        # 提取rank_genes_groups结果
        rank_genes_groups = sce.uns['rank_genes_groups']
        
        # 获取分簇名称
        cluster_names = rank_genes_groups['names'].dtype.names
        
        # 初始化marker基因字典
        marker_genes = {}
        
        total_significant_genes = 0
        
        for cluster in cluster_names:
            # 获取基因名称和调整后的p值
            genes = rank_genes_groups['names'][cluster]
            pvals_adj = rank_genes_groups['pvals_adj'][cluster]
            
            # 筛选显著的基因
            cluster_markers = []
            for i, gene in enumerate(genes):
                if i < len(pvals_adj) and pvals_adj[i] < pval_threshold:
                    cluster_markers.append(str(gene))  # 确保基因名为字符串
            
            # 保存到字典中
            marker_genes[f'cluster{cluster}'] = cluster_markers
            total_significant_genes += len(cluster_markers)
        
        # 保存为JSON文件
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(marker_genes, f, ensure_ascii=False, indent=2)
        
        # 打印统计信息
        print(f"✓ 成功提取 {len(marker_genes)} 个分簇的marker基因")
        print(f"✓ 总计 {total_significant_genes} 个显著的marker基因 (p < {pval_threshold})")
        print(f"✓ 结果已保存到 {output_file}")
        
        # 打印每个分簇的marker基因数量
        for cluster, markers in marker_genes.items():
            print(f"  {cluster}: {len(markers)} 个显著的marker基因")
        
        return marker_genes
        
    except Exception as e:
        print(f"✗ 保存marker基因时发生错误: {e}")
        return None

def load_marker_genes_from_json(marker_genes_json: str) -> Optional[Dict[str, List[str]]]:
    """
    从JSON文件中加载marker基因

    参数:
    marker_genes_json: JSON文件路径

    返回:
    成功时返回marker基因字典，失败时返回None
    """
    try:
        if not os.path.exists(marker_genes_json):
            print(f"错误：文件不存在: {marker_genes_json}")
            return None

        with open(marker_genes_json, 'r', encoding='utf-8') as f:
            marker_genes = json.load(f)
        
        print(f"✓ 成功加载marker基因，包含 {len(marker_genes)} 个分簇")
        
        # 显示每个分簇的基因数量
        for cluster, markers in marker_genes.items():
            print(f"  {cluster}: {len(markers)} 个基因")
        
        return marker_genes
        
    except Exception as e:
        print(f"✗ 加载marker基因时发生错误: {e}")
        return None

def validate_marker_genes_format(marker_genes: Dict[str, List[str]]) -> bool:
    """
    验证marker基因字典的格式是否正确
    
    参数:
    marker_genes: marker基因字典
    
    返回:
    格式正确时返回True，否则返回False
    """
    try:
        if not isinstance(marker_genes, dict):
            print("错误：marker_genes应该是字典格式")
            return False
        
        for cluster, genes in marker_genes.items():
            if not isinstance(cluster, str):
                print(f"错误：分簇名 {cluster} 应该是字符串")
                return False
            
            if not cluster.startswith('cluster'):
                print(f"警告：分簇名 {cluster} 不符合标准格式（应以'cluster'开头）")
            
            if not isinstance(genes, list):
                print(f"错误：分簇 {cluster} 的基因列表应该是列表格式")
                return False
            
            for gene in genes:
                if not isinstance(gene, str):
                    print(f"错误：基因名 {gene} 应该是字符串")
                    return False
        
        print("✓ marker基因格式验证通过")
        return True
        
    except Exception as e:
        print(f"✗ 验证格式时发生错误: {e}")
        return False
