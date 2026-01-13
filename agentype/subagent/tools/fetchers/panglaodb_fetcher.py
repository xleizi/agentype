#!/usr/bin/env python3
"""
agentype - PanglaoDB Database Fetcher
Author: cuilei
Version: 1.0
"""

import pandas as pd
import json
from pathlib import Path
import logging
from typing import Dict, Any

# 导入通用工具
from agentype.subagent.utils.common import FileDownloader, CacheManager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PanglaoDBFetcher:
    """PanglaoDB数据获取和处理器"""
    
    def __init__(self, cache_dir: str = None):
        """
        初始化PanglaoDB获取器
        
        Args:
            cache_dir: 缓存目录路径，None表示使用全局缓存配置
        """
        # 使用统一的缓存管理器，panglaodb子目录
        self.cache_manager = CacheManager(cache_dir, "panglaodb")
        self.cache_dir = self.cache_manager.cache_dir
        
        # 使用统一的下载器
        self.downloader = FileDownloader(max_retries=3, timeout=60)
        
        # PanglaoDB数据库URL
        self.panglaodb_url = "https://panglaodb.se/markers/PanglaoDB_markers_27_Mar_2020.tsv.gz"
        self.panglaodb_cache_file = self.cache_manager.get_cache_file_path("panglaodb_markers.tsv.gz")
    
    def download_file_with_retry(self, url: str, output_file: Path, max_retries: int = 3) -> bool:
        """下载文件，支持重试 - 使用统一的下载工具"""
        return self.downloader.download_file_with_retry(url, output_file, force_download=False)
    
    def download_panglaodb_data(self) -> Path:
        """下载PanglaoDB数据文件"""
        # 检查缓存文件是否存在
        if not self.panglaodb_cache_file.exists():
            logger.info("PanglaoDB数据未找到缓存，开始下载...")
            if not self.download_file_with_retry(self.panglaodb_url, self.panglaodb_cache_file):
                raise Exception("PanglaoDB数据下载失败")
        else:
            logger.info(f"PanglaoDB数据已存在: {self.panglaodb_cache_file}")
        
        return self.panglaodb_cache_file
    
    def parse_panglaodb_data(self, data_file: Path) -> pd.DataFrame:
        """加载、清理和标准化PanglaoDB数据"""
        try:
            # 读取PanglaoDB数据
            logger.info(f"正在加载PanglaoDB数据: {data_file}")
            data = pd.read_csv(
                data_file, 
                sep='\t', 
                compression='gzip',
                encoding='utf-8',
                low_memory=False
            )
            
            logger.info(f"PanglaoDB原始列名: {list(data.columns)}")
            
            # 标准化列名
            column_mapping = {
                'cell type': 'cell_type',
                'official gene symbol': 'gene_symbol', 
                'species': 'species',
                'organ': 'organ',
                'canonical marker': 'canonical_marker',
                'ubiquity index': 'ubiquity_index',
                'product description': 'product_description'
            }
            
            # 重命名存在的列
            for old_col, new_col in column_mapping.items():
                if old_col in data.columns:
                    data = data.rename(columns={old_col: new_col})
            
            logger.info(f"列名映射后: {list(data.columns)}")
            
            # 数据清理
            required_columns = ['cell_type', 'gene_symbol', 'species']
            available_columns = [col for col in required_columns if col in data.columns]
            
            if len(available_columns) < 3:
                raise ValueError(f"缺少必需列. 可用列: {available_columns}")
            
            # 清理数据
            data = data.dropna(subset=available_columns)
            
            # 数据类型转换
            if 'canonical_marker' in data.columns:
                data['canonical_marker'] = pd.to_numeric(
                    data['canonical_marker'], errors='coerce'
                ).fillna(0)
            
            if 'ubiquity_index' in data.columns:
                data['ubiquity_index'] = pd.to_numeric(
                    data['ubiquity_index'], errors='coerce'
                ).fillna(0)
            
            logger.info(f"PanglaoDB数据清理完成: {len(data)} 条记录")
            logger.info(f"示例数据:\n{data[['cell_type', 'gene_symbol', 'species']].head()}")
            
            # 显示物种分布
            if 'species' in data.columns:
                species_counts = data['species'].value_counts()
                logger.info(f"物种分布: {dict(species_counts.head())}")
            
            return data
            
        except Exception as e:
            logger.error(f"PanglaoDB数据处理错误: {e}")
            raise
    
    def convert_to_nested_format(self, data: pd.DataFrame) -> Dict[str, Any]:
        """将数据转换为嵌套的物种-组织-细胞类型-基因格式"""
        try:
            logger.info("转换数据为嵌套格式...")
            
            # 创建嵌套字典结构
            nested_data = {}
            
            # 按物种、器官、细胞类型分组处理数据
            for _, row in data.iterrows():
                species = row.get('species', 'Unknown')
                organ = str(row.get('organ', 'Unknown')).upper().strip()
                cell_type = str(row.get('cell_type', 'Unknown')).upper().strip()
                gene_symbol = str(row.get('gene_symbol', '')).strip()
                
                # 跳过空基因
                if not gene_symbol or gene_symbol == 'nan':
                    continue
                
                # 跳过UNKNOWN物种（None, 4等无效标识符）
                if species in ['None', '4']:
                    continue
                
                # 确定目标物种列表
                target_species = []
                if species == 'Hs':
                    target_species = ['HUMAN']
                elif species == 'Mm':
                    target_species = ['MOUSE']
                elif species == 'Mm Hs':
                    # Mm Hs数据同时保存到MOUSE和HUMAN
                    target_species = ['MOUSE', 'HUMAN']
                else:
                    # 跳过其他未知物种
                    continue
                
                # 为每个目标物种创建数据条目
                for species_name in target_species:
                    # 创建嵌套结构
                    if species_name not in nested_data:
                        nested_data[species_name] = {}
                    
                    if organ not in nested_data[species_name]:
                        nested_data[species_name][organ] = {}
                    
                    if cell_type not in nested_data[species_name][organ]:
                        nested_data[species_name][organ][cell_type] = set()
                    
                    # 添加基因（使用set自动去重）
                    nested_data[species_name][organ][cell_type].add(gene_symbol)
            
            # 转换set为sorted list
            for species_name in nested_data:
                for organ in nested_data[species_name]:
                    for cell_type in nested_data[species_name][organ]:
                        nested_data[species_name][organ][cell_type] = sorted(list(nested_data[species_name][organ][cell_type]))
            
            # 统计信息
            total_genes = sum(
                len(genes) for species_data in nested_data.values()
                for organ_data in species_data.values()
                for genes in organ_data.values()
            )
            
            total_cell_types = sum(
                len(organ_data) for species_data in nested_data.values()
                for organ_data in species_data.values()
            )
            
            logger.info(f"嵌套格式转换完成:")
            logger.info(f"  物种数: {len(nested_data)}")
            logger.info(f"  细胞类型数: {total_cell_types}")
            logger.info(f"  基因记录数: {total_genes}")
            
            return nested_data
            
        except Exception as e:
            logger.error(f"数据格式转换错误: {e}")
            raise
    
    def save_data(self, data: Dict[str, Any], filename: str):
        """保存数据为JSON文件"""
        output_file = self.cache_dir / filename
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        file_size = output_file.stat().st_size / (1024 * 1024)  # MB
        logger.info(f"数据已保存到 {output_file} ({file_size:.2f} MB)")
        
        return output_file
    
    def fetch_and_process_data(self) -> Dict[str, Any]:
        """获取并处理PanglaoDB数据的完整流程"""
        logger.info("=== 开始PanglaoDB数据处理流程 ===")
        
        try:
            # 下载数据
            data_file = self.download_panglaodb_data()
            
            # 解析数据
            processed_data = self.parse_panglaodb_data(data_file)
            
            # 转换为嵌套格式
            nested_data = self.convert_to_nested_format(processed_data)
            
            # 保存数据
            output_file = self.save_data(nested_data, "panglaodb_markers.json")
            
            logger.info(f"=== PanglaoDB数据处理完成 ===")
            logger.info(f"嵌套JSON数据保存至: {output_file}")
            
            return nested_data
            
        except Exception as e:
            logger.error(f"PanglaoDB数据处理失败: {e}")
            raise

