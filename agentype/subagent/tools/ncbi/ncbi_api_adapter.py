#!/usr/bin/env python3
"""
agentype - NCBI API适配器
Author: cuilei
Version: 1.0
"""

import requests
import json
import time
from typing import List, Dict, Optional, Union, Any
from dataclasses import dataclass
import logging
from pathlib import Path


from .gene_info_manager import GeneInfoManager

logger = logging.getLogger(__name__)

@dataclass
class UnifiedGeneInfo:
    """统一的基因信息数据结构"""
    gene_id: str
    symbol: str
    description: str
    summary: str
    species: str
    tax_id: str
    synonyms: List[str]
    chromosomes: List[str]
    gene_type: str
    go_molecular_functions: List[Dict]
    go_biological_processes: List[Dict]
    go_cellular_components: List[Dict]
    source_api: str  # 标记数据来源API


class NCBIAPIAdapter:
    """NCBI API适配器"""
    
    def __init__(self, prefer_datasets_api: bool = True, max_retries: int = 3):
        """
        初始化API适配器
        
        Args:
            prefer_datasets_api: 是否优先使用Datasets API v2
            max_retries: 最大重试次数
        """
        self.prefer_datasets_api = prefer_datasets_api
        self.max_retries = max_retries
        self.rate_limit_delay = 0.34  # 速率限制延迟
        
        # API URLs
        self.datasets_api_base = "https://api.ncbi.nlm.nih.gov/datasets/v2"
        self.eutils_api_base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        
        # 请求会话
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CellTypeAnnotationTool/1.0',
            'Accept': 'application/json',
        })
        
        # 初始化基因信息管理器用于Symbol转换，使用统一缓存系统
        self.gene_manager = GeneInfoManager()
        
        logger.info(f"NCBI API适配器初始化完成 (优先API: {'Datasets v2' if prefer_datasets_api else 'E-utilities'})")
    
    def convert_symbols_to_ids(self, gene_symbols: List[str], species: str = "human") -> Dict[str, str]:
        """
        将基因Symbol转换为基因ID，支持自动错误恢复
        使用本地基因信息管理器进行快速转换

        Args:
            gene_symbols: 基因Symbol列表
            species: 物种名称 ("human" 或 "mouse")

        Returns:
            Dict[str, str]: {symbol: gene_id} 的映射字典
        """
        logger.info(f"使用本地数据库转换 {len(gene_symbols)} 个基因Symbol为ID (物种: {species})")

        try:
            # 使用基因信息管理器进行转换
            symbol_to_id = self.gene_manager.convert_symbols_to_ids(gene_symbols, species)

            logger.info(f"本地转换成功: {len(symbol_to_id)}/{len(gene_symbols)} 个Symbol")
            return symbol_to_id

        except Exception as e:
            logger.error(f"基因Symbol转换失败: {e}")
            # 如果是数据文件损坏，基因管理器已经自动重试
            # 这里只需要返回空字典，让上层继续处理
            return {}
    
    def get_genes_info(self, gene_ids: List[str], batch_size: int = 50) -> List[UnifiedGeneInfo]:
        """
        获取多个基因的详细信息
        
        Args:
            gene_ids: Gene ID列表
            batch_size: 批处理大小
            
        Returns:
            统一格式的基因信息列表
        """
        all_genes_info = []
        
        # 分批处理
        for i in range(0, len(gene_ids), batch_size):
            batch_ids = gene_ids[i:i + batch_size]
            logger.info(f"处理批次 {i//batch_size + 1}: {len(batch_ids)} 个基因")
            
            batch_results = self._get_batch_genes_info(batch_ids)
            all_genes_info.extend(batch_results)
            
            # 速率限制
            if i + batch_size < len(gene_ids):
                time.sleep(self.rate_limit_delay)
        
        logger.info(f"总共获取了 {len(all_genes_info)} 个基因的详细信息")
        return all_genes_info
    
    def _get_batch_genes_info(self, gene_ids: List[str]) -> List[UnifiedGeneInfo]:
        """
        获取一批基因的详细信息
        
        Args:
            gene_ids: Gene ID列表
            
        Returns:
            基因信息列表
        """
        # 首选API尝试
        if self.prefer_datasets_api:
            primary_results = self._try_datasets_api(gene_ids)
            if primary_results:
                return primary_results
            
            logger.warning("Datasets API失败，切换到E-utilities API")
            return self._try_eutils_api(gene_ids)
        else:
            primary_results = self._try_eutils_api(gene_ids)
            if primary_results:
                return primary_results
                
            logger.warning("E-utilities API失败，切换到Datasets API")
            return self._try_datasets_api(gene_ids)
    
    def _try_datasets_api(self, gene_ids: List[str]) -> List[UnifiedGeneInfo]:
        """尝试使用Datasets API v2"""
        try:
            gene_ids_str = ",".join(gene_ids)
            url = f"{self.datasets_api_base}/gene/id/{gene_ids_str}"
            
            logger.debug(f"尝试Datasets API: {len(gene_ids)} 个基因")
            response = self._make_request_with_retry(url)
            
            if not response:
                return []
            
            data = response.json()
            reports = data.get('reports', [])
            
            results = []
            for report in reports:
                if 'gene' in report:
                    gene_info = self._parse_datasets_api_response(report['gene'])
                    if gene_info:
                        results.append(gene_info)
            
            logger.info(f"Datasets API成功: {len(results)}/{len(gene_ids)} 个基因")
            return results
            
        except Exception as e:
            logger.warning(f"Datasets API调用失败: {e}")
            return []
    
    def _try_eutils_api(self, gene_ids: List[str]) -> List[UnifiedGeneInfo]:
        """尝试使用E-utilities API"""
        try:
            gene_ids_str = ",".join(gene_ids)
            url = f"{self.eutils_api_base}/esummary.fcgi?db=gene&id={gene_ids_str}&retmode=json"
            
            logger.debug(f"尝试E-utilities API: {len(gene_ids)} 个基因")
            response = self._make_request_with_retry(url)
            
            if not response:
                return []
            
            data = response.json()
            result = data.get('result', {})
            
            results = []
            for gene_id in gene_ids:
                if gene_id in result:
                    gene_info = self._parse_eutils_api_response(result[gene_id])
                    if gene_info:
                        results.append(gene_info)
            
            logger.info(f"E-utilities API成功: {len(results)}/{len(gene_ids)} 个基因")
            return results
            
        except Exception as e:
            logger.warning(f"E-utilities API调用失败: {e}")
            return []
    
    def _make_request_with_retry(self, url: str, timeout: int = 180, method: str = 'GET', params: Optional[Dict] = None) -> Optional[requests.Response]:
        """带重试的HTTP请求"""
        for attempt in range(self.max_retries):
            try:
                if method.upper() == 'GET':
                    response = self.session.get(url, timeout=timeout, params=params)
                else:
                    response = self.session.get(url, timeout=timeout)
                    
                if response.status_code == 200:
                    return response
                else:
                    logger.warning(f"HTTP {response.status_code} (尝试 {attempt + 1}/{self.max_retries})")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.rate_limit_delay * (attempt + 1))
            except Exception as e:
                logger.warning(f"请求错误 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.rate_limit_delay * (attempt + 1))
        
        return None
    
    def _parse_datasets_api_response(self, gene_data: Dict) -> Optional[UnifiedGeneInfo]:
        """解析Datasets API v2的响应"""
        try:
            # 提取基本信息
            gene_id = gene_data.get('gene_id', '')
            symbol = gene_data.get('symbol', '')
            description = gene_data.get('description', '')
            tax_id = gene_data.get('tax_id', '')
            taxname = gene_data.get('taxname', '')
            gene_type = gene_data.get('type', '')
            chromosomes = gene_data.get('chromosomes', [])
            synonyms = gene_data.get('synonyms', [])
            
            # 提取摘要
            summary = ""
            summaries = gene_data.get('summary', [])
            if summaries and len(summaries) > 0:
                summary = summaries[0].get('description', '')
            
            # 提取GO术语
            gene_ontology = gene_data.get('gene_ontology', {})
            go_molecular_functions = self._extract_go_terms(gene_ontology, 'molecular_functions')
            go_biological_processes = self._extract_go_terms(gene_ontology, 'biological_processes')
            go_cellular_components = self._extract_go_terms(gene_ontology, 'cellular_components')
            
            return UnifiedGeneInfo(
                gene_id=gene_id,
                symbol=symbol,
                description=description,
                summary=summary,
                species=taxname,
                tax_id=tax_id,
                synonyms=synonyms,
                chromosomes=chromosomes,
                gene_type=gene_type,
                go_molecular_functions=go_molecular_functions,
                go_biological_processes=go_biological_processes,
                go_cellular_components=go_cellular_components,
                source_api="Datasets_v2"
            )
            
        except Exception as e:
            logger.error(f"解析Datasets API响应失败: {e}")
            return None
    
    def _parse_eutils_api_response(self, gene_data: Dict) -> Optional[UnifiedGeneInfo]:
        """解析E-utilities API的响应"""
        try:
            # 提取基本信息
            gene_id = gene_data.get('uid', '')
            symbol = gene_data.get('name', '')
            description = gene_data.get('description', '')
            summary = gene_data.get('summary', '')
            chromosome = gene_data.get('chromosome', '')
            chromosomes = [chromosome] if chromosome else []
            
            # 提取物种信息
            organism = gene_data.get('organism', {})
            species = organism.get('scientificname', '') if isinstance(organism, dict) else ''
            tax_id = str(organism.get('taxid', '')) if isinstance(organism, dict) else ''
            
            # 提取同义词
            other_aliases = gene_data.get('otheraliases', '')
            synonyms = []
            if other_aliases and other_aliases != '-':
                synonyms = [alias.strip() for alias in other_aliases.split(', ') if alias.strip()]
            
            # E-utilities API不提供GO术语信息
            go_molecular_functions = []
            go_biological_processes = []
            go_cellular_components = []
            
            return UnifiedGeneInfo(
                gene_id=gene_id,
                symbol=symbol,
                description=description,
                summary=summary,
                species=species,
                tax_id=tax_id,
                synonyms=synonyms,
                chromosomes=chromosomes,
                gene_type='',  # E-utilities不提供基因类型
                go_molecular_functions=go_molecular_functions,
                go_biological_processes=go_biological_processes,
                go_cellular_components=go_cellular_components,
                source_api="E-utilities"
            )
            
        except Exception as e:
            logger.error(f"解析E-utilities API响应失败: {e}")
            return None
    
    def _extract_go_terms(self, gene_ontology: Dict, category: str, limit: int = 5) -> List[Dict]:
        """提取GO术语"""
        go_terms = gene_ontology.get(category, [])
        
        cleaned_terms = []
        for i, term in enumerate(go_terms):
            if i >= limit:
                break
            cleaned_terms.append({
                'name': term.get('name', ''),
                'go_id': term.get('go_id', ''),
                'evidence_code': term.get('evidence_code', ''),
                'qualifier': term.get('qualifier', '')
            })
        
        return cleaned_terms

