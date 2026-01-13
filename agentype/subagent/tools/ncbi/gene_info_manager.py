#!/usr/bin/env python3
"""
agentype - NCBI基因信息管理器
Author: cuilei
Version: 1.0
"""

import os
import gzip
import pandas as pd
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import logging

# 导入通用工具
from agentype.subagent.utils.common import FileDownloader, SpeciesDetector, CacheManager

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GeneInfoManager:
    """NCBI基因信息管理器"""
    
    def __init__(self, data_dir: str = None):
        """
        初始化基因信息管理器
        
        Args:
            data_dir: 数据存储目录，None表示使用全局缓存配置
        """
        # 使用统一的缓存管理器，ncbi子目录
        self.cache_manager = CacheManager(data_dir, "ncbi")
        self.data_dir = self.cache_manager.cache_dir
        
        # 使用统一的下载器和物种检测器
        self.downloader = FileDownloader(max_retries=3, timeout=60)
        self.species_detector = SpeciesDetector()
        
        # NCBI基因信息文件URL
        self.gene_info_urls = {
            "human": "https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz",
            "mouse": "https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Mus_musculus.gene_info.gz"
        }
        
        # 本地文件路径和文件名
        self.species_files = {
            "human": "Homo_sapiens.gene_info.gz",
            "mouse": "Mus_musculus.gene_info.gz"
        }
        
        self.gene_info_files = {
            "human": self.data_dir / "Homo_sapiens.gene_info.gz",
            "mouse": self.data_dir / "Mus_musculus.gene_info.gz"
        }
        
        # 映射数据文件路径
        self.mapping_files = {
            "human": self.data_dir / "human_gene_mapping.json",
            "mouse": self.data_dir / "mouse_gene_mapping.json"
        }
        
        # 内存中的映射数据
        self.gene_mappings = {}
        
        # 请求配置
        self.max_retries = 3
        self.timeout = 60
        
        logger.info("基因信息管理器初始化完成")
    
    def download_gene_info_files(self, species: Optional[str] = None, force_download: bool = False) -> Dict[str, bool]:
        """
        下载基因信息文件
        
        Args:
            species: 指定物种 ("human" 或 "mouse")，None表示下载所有
            force_download: 是否强制重新下载
            
        Returns:
            下载结果字典 {species: success}
        """
        species_list = [species] if species else ["human", "mouse"]
        results = {}
        
        for sp in species_list:
            logger.info(f"开始处理{sp}基因信息文件...")
            
            # 检查文件是否已存在
            local_file = self.gene_info_files[sp]
            if local_file.exists() and not force_download:
                file_size = local_file.stat().st_size / (1024 * 1024)  # MB
                logger.info(f"{sp}基因信息文件已存在 ({file_size:.1f} MB)，跳过下载")
                results[sp] = True
                continue
            
            # 下载文件
            url = self.gene_info_urls[sp]
            success = self._download_file_with_retry(url, local_file)
            results[sp] = success
            
            if success:
                file_size = local_file.stat().st_size / (1024 * 1024)  # MB
                logger.info(f"{sp}基因信息文件下载成功 ({file_size:.1f} MB)")
            else:
                logger.error(f"{sp}基因信息文件下载失败")
        
        return results
    
    def _download_file_with_retry(self, url: str, output_file: Path) -> bool:
        """
        带重试的文件下载 - 使用统一的下载工具
        
        Args:
            url: 下载URL
            output_file: 输出文件路径
            
        Returns:
            下载是否成功
        """
        return self.downloader.download_file_with_retry(url, output_file, force_download=False)
    
    def parse_gene_info_file(self, species: str, force_rebuild: bool = False) -> Dict[str, Dict]:
        """
        解析基因信息文件，建立映射关系，支持自动错误恢复

        Args:
            species: 物种 ("human" 或 "mouse")
            force_rebuild: 是否强制重新解析

        Returns:
            基因映射字典
        """
        # 检查是否已有解析好的映射文件
        mapping_file = self.mapping_files[species]
        if mapping_file.exists() and not force_rebuild:
            logger.info(f"加载已解析的{species}基因映射...")
            try:
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    mapping_data = json.load(f)

                # 验证映射文件完整性
                gene_count = len(mapping_data.get('symbol_to_id', {}))
                min_expected_genes = self._get_min_expected_gene_count(species)

                if gene_count < min_expected_genes:
                    logger.warning(f"{species}基因映射文件基因数量异常 ({gene_count} < {min_expected_genes})，重新解析")
                    # 删除不完整的映射文件
                    mapping_file.unlink(missing_ok=True)
                else:
                    self.gene_mappings[species] = mapping_data
                    logger.info(f"{species}基因映射加载完成: {gene_count} 个基因")
                    return self.gene_mappings[species]
            except Exception as e:
                logger.warning(f"加载{species}基因映射失败: {e}，将重新解析")
                mapping_file.unlink(missing_ok=True)

        # 检查原始文件是否存在
        gene_info_file = self.gene_info_files[species]
        if not gene_info_file.exists():
            logger.error(f"{species}基因信息文件不存在: {gene_info_file}")
            return {}

        logger.info(f"开始解析{species}基因信息文件...")

        try:
            return self._parse_gene_info_with_recovery(species, gene_info_file)
        except Exception as e:
            logger.error(f"解析{species}基因信息文件失败: {e}")
            return {}

    def _get_min_expected_gene_count(self, species: str) -> int:
        """获取物种的最小预期基因数量"""
        expected_counts = {
            "human": 25000,  # 人类至少25,000个基因
            "mouse": 20000   # 小鼠至少20,000个基因
        }
        return expected_counts.get(species, 10000)

    def _clean_corrupted_files(self, species: str):
        """清理指定物种的损坏文件"""
        # 删除损坏的基因信息文件
        gene_info_file = self.gene_info_files[species]
        if gene_info_file.exists():
            gene_info_file.unlink()
            logger.info(f"已删除损坏的{species}基因信息文件")

        # 删除对应的映射文件
        mapping_file = self.mapping_files[species]
        if mapping_file.exists():
            mapping_file.unlink()
            logger.info(f"已删除{species}基因映射文件")

        # 清理内存中的映射数据
        if species in self.gene_mappings:
            del self.gene_mappings[species]
            logger.info(f"已清理内存中的{species}基因映射数据")

    def _parse_gene_info_with_recovery(self, species: str, gene_info_file: Path, retry_count: int = 0) -> Dict[str, Dict]:
        """带自动恢复的基因信息文件解析"""
        max_retries = 2
        mapping_file = self.mapping_files[species]

        try:
            # 尝试读取压缩文件
            with gzip.open(gene_info_file, 'rt', encoding='utf-8') as f:
                # 读取表头
                header_line = f.readline().strip()
                if header_line.startswith('#'):
                    header = header_line[1:].split('\t')
                else:
                    header = header_line.split('\t')

                logger.info(f"文件列名: {header}")

                # 解析数据行
                symbol_to_id = {}
                id_to_info = {}
                alias_to_id = {}

                line_count = 0
                for line in f:
                    line_count += 1
                    if line_count % 10000 == 0:
                        logger.info(f"已处理 {line_count} 行")

                    fields = line.strip().split('\t')
                    if len(fields) < len(header):
                        continue

                    # 创建字段字典
                    record = dict(zip(header, fields))

                    # 提取关键信息
                    gene_id = record.get('GeneID', '')
                    symbol = record.get('Symbol', '')
                    synonyms = record.get('Synonyms', '-')
                    symbol_from_nomenclature = record.get('Symbol_from_nomenclature_authority', '-')
                    full_name = record.get('Full_name_from_nomenclature_authority', '')
                    other_designations = record.get('Other_designations', '-')

                    if not gene_id or not symbol or gene_id == '-' or symbol == '-':
                        continue

                    # 主要Symbol映射（保持原始大小写）
                    symbol_to_id[symbol] = gene_id

                    # 存储基因详细信息
                    id_to_info[gene_id] = {
                        'gene_id': gene_id,
                        'symbol': symbol,
                        'symbol_from_nomenclature': symbol_from_nomenclature,
                        'full_name': full_name,
                        'synonyms': synonyms,
                        'other_designations': other_designations,
                        'species': species
                    }

                    # 处理同义词/别名（保持原始大小写）
                    if synonyms and synonyms != '-':
                        synonym_list = [syn.strip() for syn in synonyms.split('|') if syn.strip()]
                        for syn in synonym_list:
                            if syn and syn != '-':
                                alias_to_id[syn] = gene_id

                    # 处理nomenclature符号（保持原始大小写）
                    if symbol_from_nomenclature and symbol_from_nomenclature != '-':
                        alias_to_id[symbol_from_nomenclature] = gene_id

                logger.info(f"解析完成: 处理了 {line_count} 行")
                logger.info(f"主要符号: {len(symbol_to_id)} 个")
                logger.info(f"别名映射: {len(alias_to_id)} 个")
                logger.info(f"基因信息: {len(id_to_info)} 个")

                # 验证解析结果
                if len(symbol_to_id) < self._get_min_expected_gene_count(species):
                    raise ValueError(f"解析的基因数量过少: {len(symbol_to_id)}")

                # 构建简化映射（只保留映射关系）
                complete_mapping = {
                    'symbol_to_id': symbol_to_id,
                    'alias_to_id': alias_to_id,
                    'stats': {
                        'species': species,
                        'build_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'symbols': len(symbol_to_id),
                        'aliases': len(alias_to_id),
                        'total_genes': len(symbol_to_id)
                    }
                }

                # 保存到内存
                self.gene_mappings[species] = complete_mapping

                # 保存到文件
                with open(mapping_file, 'w', encoding='utf-8') as f:
                    json.dump(complete_mapping, f, indent=2, ensure_ascii=False)

                logger.info(f"{species}基因映射构建完成，已保存到 {mapping_file}")
                return complete_mapping

        except (OSError, gzip.BadGzipFile, EOFError, ValueError) as e:
            # 捕获文件损坏相关的错误
            if retry_count < max_retries:
                logger.warning(f"{species}基因信息文件读取失败: {e}")
                logger.info(f"尝试重新下载并解析 (第{retry_count + 1}次重试)")

                # 删除损坏的文件
                self._clean_corrupted_files(species)

                # 重新下载
                success = self.download_gene_info_files(species, force_download=True)
                if success[species]:
                    # 递归重试解析
                    return self._parse_gene_info_with_recovery(species, gene_info_file, retry_count + 1)
                else:
                    logger.error(f"{species}基因信息文件重新下载失败")
                    raise
            else:
                logger.error(f"{species}基因信息文件多次重试后仍然失败")
                raise

    def _load_gene_mapping_with_recovery(self, species: str, retry_count: int = 0):
        """带自动恢复的基因映射加载"""
        max_retries = 2

        try:
            # 检查基因信息文件是否存在，不存在则下载
            gene_info_file = self.data_dir / f"{self.species_files[species]}"
            if not gene_info_file.exists():
                logger.info(f"{species}基因信息文件不存在，正在下载...")
                success = self.download_gene_info_files(species)
                if not success[species]:
                    raise RuntimeError(f"{species}基因信息文件下载失败")

            # 解析基因信息文件
            self.parse_gene_info_file(species)

            # 验证加载结果
            if species not in self.gene_mappings:
                raise RuntimeError(f"{species}基因映射数据加载失败")

            mapping_data = self.gene_mappings[species]
            gene_count = len(mapping_data.get('symbol_to_id', {}))

            if gene_count < self._get_min_expected_gene_count(species):
                raise ValueError(f"{species}基因映射数据不完整: {gene_count} 个基因")

        except Exception as e:
            if retry_count < max_retries:
                logger.warning(f"{species}基因映射加载失败: {e}")
                logger.info(f"清理损坏文件并重试 (第{retry_count + 1}次)")

                # 清理损坏的文件
                self._clean_corrupted_files(species)

                # 递归重试
                self._load_gene_mapping_with_recovery(species, retry_count + 1)
            else:
                logger.error(f"{species}基因映射多次重试后仍然失败")
                raise

    def convert_symbols_to_ids(self, gene_symbols: List[str], species: str = "human") -> Dict[str, str]:
        """
        将基因符号转换为Gene ID，支持自动错误恢复

        Args:
            gene_symbols: 基因符号列表
            species: 物种

        Returns:
            符号到ID的映射字典
        """
        if species not in self.gene_mappings:
            logger.info(f"{species}基因映射数据未加载，开始按需加载...")

            try:
                # 尝试加载基因映射
                self._load_gene_mapping_with_recovery(species)
            except Exception as e:
                logger.error(f"{species}基因映射加载失败: {e}")
                return {}

        if species not in self.gene_mappings:
            logger.error(f"{species}基因映射数据加载失败")
            return {}
        
        mapping_data = self.gene_mappings[species]
        symbol_to_id = mapping_data['symbol_to_id']
        alias_to_id = mapping_data['alias_to_id']
        
        results = {}
        not_found = []
        
        for symbol in gene_symbols:
            # 首先查找主要符号（使用原始大小写）
            if symbol in symbol_to_id:
                results[symbol] = symbol_to_id[symbol]
                continue
            
            # 然后查找别名（使用原始大小写）
            if symbol in alias_to_id:
                results[symbol] = alias_to_id[symbol]
                continue
            
            # 未找到
            not_found.append(symbol)
        
        success_rate = len(results) / len(gene_symbols) * 100
        logger.info(f"{species}基因转换结果: {len(results)}/{len(gene_symbols)} ({success_rate:.1f}%)")
        
        if not_found:
            logger.warning(f"未找到的基因符号: {', '.join(not_found[:10])}")
            if len(not_found) > 10:
                logger.warning(f"... 以及另外 {len(not_found) - 10} 个")
        
        return results
    
    def detect_species_from_genes(self, gene_symbols: List[str]) -> str:
        """
        根据基因符号自动判断物种 - 使用统一的物种检测器
        
        Args:
            gene_symbols: 基因符号列表
            
        Returns:
            物种名称 ("human" 或 "mouse")
        """
        return self.species_detector.detect_species_simple(gene_symbols)
    
