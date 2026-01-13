#!/usr/bin/env python3
"""
agentype - CellMarker数据获取器
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CellMarkerFetcher:
    """CellMarker数据获取和处理器"""
    
    def __init__(self, cache_dir: str = None):
        # 使用统一的缓存管理器，cellmarker子目录
        self.cache_manager = CacheManager(cache_dir, "cellmarker")
        self.cache_dir = self.cache_manager.cache_dir
        
        # 使用统一的下载器
        self.downloader = FileDownloader(max_retries=3, timeout=120)
        
        # CellMarker数据库URLs
        self.cellmarker_urls = {
            "all": "http://xteam.xbio.top/CellMarker/download/all_cell_markers.txt",
            "human": "http://xteam.xbio.top/CellMarker/download/Human_cell_markers.txt",
            "mouse": "http://xteam.xbio.top/CellMarker/download/Mouse_cell_markers.txt",
            "singlecell": "http://xteam.xbio.top/CellMarker/download/Single_cell_markers.txt"
        }
        
        self.cellmarker2_urls = {
            "all": "http://117.50.127.228/CellMarker/CellMarker_download_files/file/Cell_marker_All.xlsx",
            "human": "http://117.50.127.228/CellMarker/CellMarker_download_files/file/Cell_marker_Human.xlsx", 
            "mouse": "http://117.50.127.228/CellMarker/CellMarker_download_files/file/Cell_marker_Mouse.xlsx",
            "singlecell": "http://117.50.127.228/CellMarker/CellMarker_download_files/file/Cell_marker_Seq.xlsx"
        }
    
    def download_file_with_retry(self, url: str, output_file: Path, max_retries: int = 3) -> bool:
        """下载文件，支持重试 - 使用统一的下载工具"""
        # max_retries 参数保留是为了兼容性，实际使用下载器的配置
        return self.downloader.download_file_with_retry(url, output_file, force_download=False)
    
    def download_cellmarker_data(self, kind: str = "all") -> Path:
        """
        下载CellMarker数据
        
        Args:
            kind: 数据类型 ("all", "human", "mouse", "singlecell")
        
        Returns:
            下载文件的路径
        """
        if kind not in self.cellmarker_urls:
            raise ValueError(f"无效的kind参数: {kind}. 支持的类型: {list(self.cellmarker_urls.keys())}")
        
        url = self.cellmarker_urls[kind]
        filename = f"{kind}_cell_markers.txt"
        output_file = self.cache_dir / filename
        
        if output_file.exists():
            logger.info(f"CellMarker数据已存在: {output_file}")
            return output_file
        
        if self.download_file_with_retry(url, output_file):
            return output_file
        else:
            raise Exception(f"下载CellMarker数据失败: {url}")
    
    def download_cellmarker2_data(self, kind: str = "all") -> Path:
        """
        下载CellMarker2数据
        
        Args:
            kind: 数据类型 ("all", "human", "mouse", "singlecell")
        
        Returns:
            下载文件的路径
        """
        if kind not in self.cellmarker2_urls:
            raise ValueError(f"无效的kind参数: {kind}. 支持的类型: {list(self.cellmarker2_urls.keys())}")
        
        url = self.cellmarker2_urls[kind]
        filename = f"Cell_marker_{kind.capitalize()}.xlsx"
        if kind == "all":
            filename = "Cell_marker_All.xlsx"
        elif kind == "singlecell":
            filename = "Cell_marker_Seq.xlsx"
        
        output_file = self.cache_dir / filename
        
        if output_file.exists():
            logger.info(f"CellMarker2数据已存在: {output_file}")
            return output_file
        
        if self.download_file_with_retry(url, output_file):
            return output_file
        else:
            raise Exception(f"下载CellMarker2数据失败: {url}")
    
    def parse_cellmarker_data(self, file_path: Path) -> Dict[str, Any]:
        """解析CellMarker TSV数据"""
        logger.info(f"解析CellMarker数据: {file_path}")
        
        # 读取TSV文件
        df = pd.read_csv(file_path, sep='\t', encoding='utf-8', low_memory=False)
        logger.info(f"CellMarker原始数据: {len(df)} 条记录")
        
        # 初始化数据结构
        cellmarker_data = {}
        
        for idx, row in df.iterrows():
            try:
                # 提取字段
                species = str(row.get('speciesType', '')).strip().upper()
                tissue = str(row.get('tissueType', '')).strip().upper()
                celltype = str(row.get('cellName', '')).strip().upper()
                
                # 解析基因列表
                gene_symbols_raw = str(row.get('geneSymbol', ''))
                if pd.isna(gene_symbols_raw) or not gene_symbols_raw:
                    continue
                
                # 清理基因符号（去除方括号并分割）
                gene_symbols_raw = gene_symbols_raw.replace('[', '').replace(']', '')
                gene_symbols = [g.strip() for g in gene_symbols_raw.split(',') if g.strip()]
                
                if not gene_symbols:
                    continue
                
                # 构建层次结构
                if species not in cellmarker_data:
                    cellmarker_data[species] = {}
                
                if tissue not in cellmarker_data[species]:
                    cellmarker_data[species][tissue] = {}
                
                if celltype not in cellmarker_data[species][tissue]:
                    cellmarker_data[species][tissue][celltype] = set()
                
                # 添加基因（使用set自动去重）
                cellmarker_data[species][tissue][celltype].update(gene_symbols)
                
            except Exception as e:
                logger.warning(f"处理CellMarker第{idx}行时出错: {e}")
                continue
        
        # 转换set为sorted list
        for species in cellmarker_data:
            for tissue in cellmarker_data[species]:
                for celltype in cellmarker_data[species][tissue]:
                    cellmarker_data[species][tissue][celltype] = sorted(list(cellmarker_data[species][tissue][celltype]))
        
        logger.info(f"CellMarker解析完成")
        return cellmarker_data
    
    def parse_cellmarker2_data(self, file_path: Path) -> Dict[str, Any]:
        """解析CellMarker2 Excel数据"""
        logger.info(f"解析CellMarker2数据: {file_path}")
        
        # 读取Excel文件
        df = pd.read_excel(file_path)
        logger.info(f"CellMarker2原始数据: {len(df)} 条记录")
        
        # 初始化数据结构
        cellmarker2_data = {}
        
        for idx, row in df.iterrows():
            try:
                # 提取字段
                species = str(row.get('species', '')).strip().upper()
                tissue = str(row.get('tissue_class', '')).strip().upper()
                celltype = str(row.get('cell_name', '')).strip().upper()
                marker = str(row.get('marker', '')).strip()
                
                if not marker or pd.isna(marker):
                    continue
                
                # 构建层次结构
                if species not in cellmarker2_data:
                    cellmarker2_data[species] = {}
                
                if tissue not in cellmarker2_data[species]:
                    cellmarker2_data[species][tissue] = {}
                
                if celltype not in cellmarker2_data[species][tissue]:
                    cellmarker2_data[species][tissue][celltype] = set()
                
                # 添加基因
                cellmarker2_data[species][tissue][celltype].add(marker)
                
            except Exception as e:
                logger.warning(f"处理CellMarker2第{idx}行时出错: {e}")
                continue
        
        # 转换set为sorted list
        for species in cellmarker2_data:
            for tissue in cellmarker2_data[species]:
                for celltype in cellmarker2_data[species][tissue]:
                    cellmarker2_data[species][tissue][celltype] = sorted(list(cellmarker2_data[species][tissue][celltype]))
        
        logger.info(f"CellMarker2解析完成")
        return cellmarker2_data
    
    def merge_cellmarker_data(self, cellmarker_data: Dict[str, Any], cellmarker2_data: Dict[str, Any]) -> Dict[str, Any]:
        """合并CellMarker和CellMarker2数据"""
        logger.info("合并CellMarker数据...")
        
        merged_data = {}
        
        # 首先复制CellMarker数据
        for species in cellmarker_data:
            merged_data[species] = {}
            for tissue in cellmarker_data[species]:
                merged_data[species][tissue] = {}
                for celltype in cellmarker_data[species][tissue]:
                    merged_data[species][tissue][celltype] = set(cellmarker_data[species][tissue][celltype])
        
        # 然后合并CellMarker2数据
        for species in cellmarker2_data:
            if species not in merged_data:
                merged_data[species] = {}
            
            for tissue in cellmarker2_data[species]:
                if tissue not in merged_data[species]:
                    merged_data[species][tissue] = {}
                
                for celltype in cellmarker2_data[species][tissue]:
                    if celltype not in merged_data[species][tissue]:
                        merged_data[species][tissue][celltype] = set()
                    
                    # 合并基因列表
                    merged_data[species][tissue][celltype].update(cellmarker2_data[species][tissue][celltype])
        
        # 转换set为sorted list
        for species in merged_data:
            for tissue in merged_data[species]:
                for celltype in merged_data[species][tissue]:
                    merged_data[species][tissue][celltype] = sorted(list(merged_data[species][tissue][celltype]))
        
        logger.info("CellMarker合并完成")
        return merged_data
    
    def save_data(self, data: Dict[str, Any], filename: str):
        """保存数据为JSON文件"""
        output_file = self.cache_dir / filename
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        file_size = output_file.stat().st_size / (1024 * 1024)  # MB
        logger.info(f"数据已保存到 {output_file} ({file_size:.2f} MB)")
    
    def fetch_and_merge_all_data(self, kind: str = "all") -> Dict[str, Any]:
        """获取并合并所有CellMarker数据"""
        logger.info("开始获取并合并CellMarker数据...")
        
        # 下载数据
        cellmarker_file = self.download_cellmarker_data(kind)
        cellmarker2_file = self.download_cellmarker2_data(kind)
        
        # 解析数据
        cellmarker_data = self.parse_cellmarker_data(cellmarker_file)
        cellmarker2_data = self.parse_cellmarker2_data(cellmarker2_file)
        
        # 合并数据
        merged_data = self.merge_cellmarker_data(cellmarker_data, cellmarker2_data)
        
        # 保存合并后的数据
        self.save_data(merged_data, f"cellmarker_merged_{kind}.json")
        
        logger.info("CellMarker数据获取和合并完成")
        return merged_data


