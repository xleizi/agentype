#!/usr/bin/env python3
"""
agentype - 基因富集分析工具 - 基于类的实现
Author: cuilei
Version: 1.0
"""

# -*- coding: utf-8 -*-


import pandas as pd
import gseapy as gp
import logging
from typing import List, Dict

# 导入通用工具
from agentype.subagent.utils.common import SpeciesDetector



class GeneEnrichmentAnalyzer:
    """
    基因富集分析类 - 简化版本，只提供核心分析功能
    """
    
    def __init__(self, top_n: int = 5, cutoff: float = 0.05, organism: str = 'Human', auto_detect: bool = False):
        """
        初始化富集分析器
        
        参数:
            top_n: 每个数据库返回的前N个结果 (默认5)
            cutoff: P值阈值 (默认0.05)
            organism: 物种 (默认'Human'，可选'Human'、'Mouse'或'Auto')
            auto_detect: 是否自动检测物种 (默认False)
        """
        self.top_n = top_n
        self.cutoff = cutoff
        self.organism = organism
        self.auto_detect = auto_detect
        
        # 使用统一的物种检测器
        self.species_detector = SpeciesDetector()
        
        # 设置日志级别，减少输出
        logging.getLogger('gseapy').setLevel(logging.ERROR)
    
    def detect_species_from_genes(self, gene_symbols: List[str]) -> str:
        """
        根据基因符号自动判断物种 - 使用统一的物种检测器
        注意：此方法仅用于数据库选择，不会修改基因名称格式
        
        Args:
            gene_symbols: 基因符号列表
            
        Returns:
            物种名称 ("Human" 或 "Mouse")
        """
        species = self.species_detector.detect_species_simple(gene_symbols)
        # 转换为大写形式（用于数据库选择）
        return "Human" if species == "human" else "Mouse"
    
    @staticmethod
    def get_default_databases(organism: str = 'Human'):
        """根据物种获取默认的数据库列表"""
        if organism.lower() in ['human', 'homo sapiens']:
            return [
                # GO数据库 - 最新2025版本
                ('GO_Biological_Process_2025', 'GO_BP_2025'),
                ('GO_Molecular_Function_2025', 'GO_MF_2025'), 
                ('GO_Cellular_Component_2025', 'GO_CC_2025'),
                
                # 通路数据库 - 最新版本
                ('KEGG_2021_Human', 'KEGG_2021'),
                ('Reactome_2022', 'Reactome_2022'),
            ]
        elif organism.lower() in ['mouse', 'mus musculus']:
            return [
                # GO数据库 - 小鼠版本
                ('GO_Biological_Process_2025', 'GO_BP_2025'),
                ('GO_Molecular_Function_2025', 'GO_MF_2025'), 
                ('GO_Cellular_Component_2025', 'GO_CC_2025'),
                
                # 通路数据库 - 小鼠版本
                ('KEGG_2021_Mouse', 'KEGG_2021_Mouse'),
                ('Reactome_2022', 'Reactome_2022'),
            ]
        else:
            # 默认使用人类数据库
            return [
                ('GO_Biological_Process_2025', 'GO_BP_2025'),
                ('GO_Molecular_Function_2025', 'GO_MF_2025'), 
                ('GO_Cellular_Component_2025', 'GO_CC_2025'),
                ('KEGG_2021_Human', 'KEGG_2021'),
                ('Reactome_2022', 'Reactome_2022'),
            ]
    
    def analyze(self, gene_list: List[str]) -> Dict[str, pd.DataFrame]:
        """
        进行基因富集分析 - 简化接口
        
        参数:
            gene_list: 基因列表（字符串列表）
        
        返回:
            字典格式的结果，键为数据库名称，值为DataFrame包含前N个结果
        """
        # 确定物种
        if self.auto_detect or self.organism.lower() == 'auto':
            detected_organism = self.detect_species_from_genes(gene_list)
        else:
            detected_organism = self.organism
        
        # 根据物种获取相应的数据库
        databases = self.get_default_databases(detected_organism)
        
        # 清理基因列表，保持原始格式
        genes = [gene.strip() for gene in gene_list if gene.strip()]
        
        if not genes:
            print('错误: 没有有效的基因')
            return {}
        
        print(f'正在分析 {len(genes)} 个基因，物种: {detected_organism}')
        print(f'使用 {len(databases)} 个数据库: {[name for _, name in databases]}')
        
        results = {}
        
        # 对每个数据库进行富集分析
        for lib, lib_name in databases:
            print(f'正在进行 {lib_name} 富集分析...')
            try:
                enr = gp.enrichr(
                    gene_list=genes,
                    gene_sets=lib,
                    organism=detected_organism,
                    outdir=None,
                    cutoff=self.cutoff,
                    no_plot=True
                )
                
                if not enr.results.empty:
                    # 获取显著结果
                    significant_results = enr.results[enr.results['P-value'] <= self.cutoff]
                    
                    if len(significant_results) > 0:
                        # 获取前N个结果
                        top_results = significant_results.head(self.top_n).copy()
                        top_results['Database'] = lib_name
                        results[lib_name] = top_results
                        
                        print(f'{lib_name} 显著富集结果数量: {len(significant_results)}，返回前{len(top_results)}个')
                    else:
                        print(f'{lib_name} 没有显著富集结果 (P < {self.cutoff})')
                        results[lib_name] = pd.DataFrame()
                else:
                    print(f'{lib_name} 没有富集结果')
                    results[lib_name] = pd.DataFrame()
                    
            except Exception as e:
                print(f'{lib_name} 分析失败: {e}')
                results[lib_name] = pd.DataFrame()
                continue
        
        return results


def enrichment_analysis(gene_list: List[str], top_n: int = 5, cutoff: float = 0.05, organism: str = 'Auto') -> Dict[str, pd.DataFrame]:
    """
    基因富集分析函数 - 简化接口，直接返回结果
    
    参数:
        gene_list: 基因列表（字符串列表）
        top_n: 每个数据库返回的前N个结果 (默认5)
        cutoff: P值阈值 (默认0.05)
        organism: 物种 (默认'Auto'自动检测，也可指定'Human'或'Mouse')
    
    返回:
        字典格式的结果，键为数据库名称，值为DataFrame包含前N个结果
    
    使用示例:
        # 自动检测物种（推荐）
        genes = ['TP53', 'BRCA1', 'MYC']
        results = enrichment_analysis(genes, top_n=3)
        
        # 手动指定物种
        results = enrichment_analysis(genes, organism='Human')
        
        for db_name, df in results.items():
            if not df.empty:
                print(f'{db_name}: {len(df)} 个显著结果')
    """
    analyzer = GeneEnrichmentAnalyzer(top_n=top_n, cutoff=cutoff, organism=organism)
    return analyzer.analyze(gene_list)

