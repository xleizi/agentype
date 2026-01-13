#!/usr/bin/env python3
"""
agentype - Annotation MCP Server
Author: cuilei
Version: 1.0
"""

import sys
import asyncio
import json
import pandas as pd
from typing import Optional, List
from pathlib import Path

# 导入项目模块

# 导入国际化支持
from agentype.subagent.utils.i18n import _

try:
    from mcp.server.fastmcp import FastMCP
    from agentype.subagent.tools.ncbi.ncbi_api_adapter import NCBIAPIAdapter
    from agentype.subagent.tools.fetchers.cellmarker_fetcher import CellMarkerFetcher
    from agentype.subagent.tools.fetchers.panglaodb_fetcher import PanglaoDBFetcher
    from agentype.subagent.tools.analysis.gene_enrichment import GeneEnrichmentAnalyzer
    # 导入通用工具
    from agentype.subagent.utils.common import SpeciesDetector, GlobalCacheManager
except ImportError as e:
    # 获取项目根目录
    current_file = Path(__file__).resolve()

    print(_("mcp.import.failed", error=e))
    print(_("mcp.import.install_deps"))
    print(_("mcp.import.current_dir", path=Path.cwd()))
    print(_("mcp.import.python_path", paths=sys.path[:3]))
    sys.exit(1)

# 缓存目录（将在 __main__ 块中初始化，使用 ConfigManager 提供的路径）
cache_dir = None

# 初始化FastMCP服务器
mcp = FastMCP("celltype-annotation", log_level="INFO")

# 配置对象（在 __main__ 块中初始化）
_CONFIG = None

# 全局实例（延迟初始化）
_ncbi_adapter = None
_cellmarker_fetcher = None
_panglaodb_fetcher = None
_enrichment_analyzer = None
_species_detector = None

def get_species_detector() -> SpeciesDetector:
    """获取物种检测器实例"""
    global _species_detector
    if _species_detector is None:
        _species_detector = SpeciesDetector()
    return _species_detector

def get_ncbi_adapter() -> NCBIAPIAdapter:
    """获取NCBI适配器实例"""
    global _ncbi_adapter
    if _ncbi_adapter is None:
        _ncbi_adapter = NCBIAPIAdapter()
    return _ncbi_adapter

def get_cellmarker_fetcher() -> CellMarkerFetcher:
    """获取CellMarker获取器实例"""
    global _cellmarker_fetcher
    if _cellmarker_fetcher is None:
        _cellmarker_fetcher = CellMarkerFetcher()  # 使用统一缓存系统
    return _cellmarker_fetcher

def get_panglaodb_fetcher() -> PanglaoDBFetcher:
    """获取PanglaoDB获取器实例"""
    global _panglaodb_fetcher
    if _panglaodb_fetcher is None:
        _panglaodb_fetcher = PanglaoDBFetcher()  # 使用统一缓存系统
    return _panglaodb_fetcher

def get_enrichment_analyzer(top_n: int = 5, cutoff: float = 0.05, organism: str = 'Human') -> GeneEnrichmentAnalyzer:
    """获取基因富集分析器实例"""
    global _enrichment_analyzer
    # 每次都创建新实例，因为参数可能不同
    _enrichment_analyzer = GeneEnrichmentAnalyzer(
        top_n=top_n,
        cutoff=cutoff,
        organism=organism,
        auto_detect=False
    )
    return _enrichment_analyzer

def detect_species_from_genes(gene_symbols: List[str]) -> str:
    """
    根据基因符号自动判断物种 - 使用统一的物种检测器
    注意：此方法仅用于数据库选择，不会修改基因名称格式
    
    Args:
        gene_symbols: 基因符号列表
        
    Returns:
        物种名称 ("Human" 或 "Mouse")
    """
    detector = get_species_detector()
    species, info = detector.detect_species_from_genes(gene_symbols)
    
    # 打印检测结果
    species_name = _("gene.detection.species_human") if species == 'human' else _("gene.detection.species_mouse")
    print(_("gene.detection.species", species=species_name, ratio=info['uppercase_ratio']))
    
    # 转换为大写形式（用于数据库选择）
    return "Human" if species == "human" else "Mouse"


@mcp.tool()
async def get_gene_info(
    gene_ids: str,
    max_genes: int = 10
) -> str:
    """从NCBI获取基因的详细信息，包括完整的summary和GO通路
    
    Args:
        gene_ids: 基因ID或基因符号，支持逗号分隔的多个（如: "915,920,916" 或 "CD3D,CD4,CD8A"）
        max_genes: 最大处理基因数量，默认10个，不能超过10个
        
    Returns:
        JSON格式的基因详细信息，包含完整描述、summary和具体GO通路名称
    """
    try:
        # 解析基因ID/符号列表
        if isinstance(gene_ids, str):
            input_list = [g.strip() for g in gene_ids.split(',') if g.strip()]
        else:
            input_list = list(gene_ids)
        
        if not input_list:
            return json.dumps({
                "error": _("gene.info.empty_list"),
                "success": False
            }, ensure_ascii=False, indent=2)
        
        if max_genes > 10:
            max_genes = 10
            
        # 限制处理数量
        if len(input_list) > max_genes:
            input_list = input_list[:max_genes]
        
        ncbi_adapter = get_ncbi_adapter()
        
        # 分离纯数字ID和基因符号
        pure_ids = []
        gene_symbols = []
        
        for item in input_list:
            if item.isdigit():
                pure_ids.append(item)
            else:
                gene_symbols.append(item)
        
        final_gene_ids = pure_ids.copy()
        symbol_to_id_mapping = {}
        detected_species = "human"  # 默认物种
        
        # 将基因符号转换为ID
        if gene_symbols:
            print(_("gene.detection.converting", genes=gene_symbols))
            
            # 自动检测物种
            detected_species = detect_species_from_genes(gene_symbols)
            print(_("gene.detection.detected_species", species=detected_species))
            
            try:
                # 使用检测到的物种进行symbol转ID
                converted_ids = ncbi_adapter.convert_symbols_to_ids(gene_symbols, detected_species.lower())
                for symbol, gene_id in converted_ids.items():
                    if gene_id:
                        final_gene_ids.append(gene_id)
                        symbol_to_id_mapping[gene_id] = symbol
                        print(_("gene.detection.converted_success", symbol=symbol, gene_id=gene_id))
                    else:
                        print(_("gene.detection.converted_failed", symbol=symbol))
            except Exception as e:
                print(_("gene.detection.conversion_failed", error=e))
                # 如果转换失败，尝试直接使用符号作为ID
                final_gene_ids.extend(gene_symbols)
        
        print(_("gene.detection.final_ids", ids=final_gene_ids))
        
        if not final_gene_ids:
            return json.dumps({
                "error": _("gene.info.no_valid_ids"),
                "success": False
            }, ensure_ascii=False, indent=2)
        
        # 获取基因信息
        genes_info = ncbi_adapter.get_genes_info(final_gene_ids)
        
        if not genes_info:
            return json.dumps({
                "error": _("gene.info.no_results"),
                "success": False
            }, ensure_ascii=False, indent=2)
        
        # 格式化结果
        formatted_genes = []
        for gene in genes_info:
            # 如果这个基因ID是从符号转换来的，添加原始符号信息
            original_symbol = symbol_to_id_mapping.get(gene.gene_id)
            
            # 返回完整信息
            description = gene.description
            summary = gene.summary
            
            # 返回GO terms信息，只保留名称
            go_terms = {
                "molecular_functions": [
                    term.get("name", term.get("term", ""))
                    for term in gene.go_molecular_functions
                ],
                "biological_processes": [
                    term.get("name", term.get("term", ""))
                    for term in gene.go_biological_processes
                ],
                "cellular_components": [
                    term.get("name", term.get("term", ""))
                    for term in gene.go_cellular_components
                ]
            }
            
            gene_data = {
                "gene_id": gene.gene_id,
                "symbol": gene.symbol,
                "original_input_symbol": original_symbol,  # 用户输入的原始符号
                "description": description,
                "summary": summary,
                "species": gene.species,
                "gene_type": gene.gene_type,
                "chromosome": getattr(gene, 'chromosome', ''),
                "map_location": getattr(gene, 'map_location', ''),
                "aliases": getattr(gene, 'aliases', []),
                "go_terms": go_terms,
                "source_api": gene.source_api
            }
            formatted_genes.append(gene_data)
        
        result = {
            "success": True,
            "total_requested": len(input_list),
            "total_retrieved": len(formatted_genes),
            "detected_species": detected_species,
            "symbol_to_id_mapping": symbol_to_id_mapping,
            "genes": formatted_genes
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": _("gene.info.get_failed", error=str(e)),
            "success": False
        }, ensure_ascii=False, indent=2)

@mcp.tool()
async def query_cellmarker(
    species: str = "HUMAN",
    tissue: Optional[str] = None,
    cell_type: Optional[str] = None
) -> str:
    """从CellMarker数据库查询细胞类型和标记基因
    
    Args:
        species: 物种名称，默认"HUMAN"，也支持"MOUSE"
        tissue: 组织类型（可选），如"BLOOD"、"BRAIN"等，为空则返回所有组织
        cell_type: 细胞类型（可选），如"T CELL"等，为空则返回所有细胞类型
        
    Returns:
        JSON格式的CellMarker数据库查询结果
    """
    try:
        cellmarker_fetcher = get_cellmarker_fetcher()
        
        # 检查本地是否有缓存数据
        cache_file = GlobalCacheManager.get_cache_dir("cellmarker") / "cellmarker_merged_all.json"
        if not cache_file.exists():
            # 下载并处理数据
            await asyncio.get_event_loop().run_in_executor(
                None, cellmarker_fetcher.fetch_and_merge_all_data, "all"
            )
        
        # 加载数据
        with open(cache_file, 'r', encoding='utf-8') as f:
            cellmarker_data = json.load(f)
        
        # 规范化物种名称
        species = species.upper()
        if species not in cellmarker_data:
            available_species = list(cellmarker_data.keys())
            return json.dumps({
                "error": _("database.cellmarker.species_not_exist", species=species),
                "available_species": available_species,
                "success": False
            }, ensure_ascii=False, indent=2)
        
        species_data = cellmarker_data[species]
        
        # 如果指定了组织类型
        if tissue:
            tissue = tissue.upper()
            if tissue not in species_data:
                available_tissues = list(species_data.keys())
                return json.dumps({
                    "error": _("database.cellmarker.tissue_not_exist", tissue=tissue, species=species),
                    "available_tissues": available_tissues[:20],  # 显示前20个
                    "success": False
                }, ensure_ascii=False, indent=2)
            
            tissue_data = species_data[tissue]
            
            # 如果指定了细胞类型
            if cell_type:
                cell_type = cell_type.upper()
                if cell_type not in tissue_data:
                    available_cell_types = list(tissue_data.keys())
                    return json.dumps({
                        "error": _("database.cellmarker.celltype_not_exist", celltype=cell_type, species=species, tissue=tissue),
                        "available_cell_types": available_cell_types[:20],
                        "success": False
                    }, ensure_ascii=False, indent=2)
                
                result = {
                    "success": True,
                    "species": species,
                    "tissue": tissue,
                    "cell_type": cell_type,
                    "marker_genes": tissue_data[cell_type],
                    "gene_count": len(tissue_data[cell_type])
                }
            else:
                # 返回该组织的所有细胞类型
                cell_types_summary = {}
                for ct, genes in tissue_data.items():
                    cell_types_summary[ct] = {
                        "gene_count": len(genes),
                        "sample_genes": genes[:5]  # 显示前5个基因作为示例
                    }
                
                result = {
                    "success": True,
                    "species": species,
                    "tissue": tissue,
                    "cell_types_count": len(cell_types_summary),
                    "cell_types": cell_types_summary
                }
        else:
            # 返回该物种的组织概况
            tissues_summary = {}
            for t, cell_types in species_data.items():
                tissues_summary[t] = {
                    "cell_types_count": len(cell_types),
                    "total_genes": sum(len(genes) for genes in cell_types.values())
                }
            
            result = {
                "success": True,
                "species": species,
                "tissues_count": len(tissues_summary),
                "tissues": tissues_summary
            }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": _("database.cellmarker.query_failed", error=str(e)),
            "success": False
        }, ensure_ascii=False, indent=2)

@mcp.tool()
async def query_panglaodb(
    species: str = "HUMAN", 
    organ: Optional[str] = None,
    cell_type: Optional[str] = None
) -> str:
    """从PanglaoDB数据库查询细胞类型和标记基因
    
    Args:
        species: 物种名称，默认"HUMAN"，也支持"MOUSE"
        organ: 器官类型（可选），如"BLOOD"、"BRAIN"等，为空则返回所有器官
        cell_type: 细胞类型（可选），如"T CELLS"等，为空则返回所有细胞类型
        
    Returns:
        JSON格式的PanglaoDB数据库查询结果
    """
    try:
        panglaodb_fetcher = get_panglaodb_fetcher()
        
        # 检查本地是否有缓存数据
        cache_file = GlobalCacheManager.get_cache_dir("panglaodb") / "panglaodb_markers.json"
        if not cache_file.exists():
            # 下载并处理数据
            await asyncio.get_event_loop().run_in_executor(
                None, panglaodb_fetcher.fetch_and_process_data
            )
        
        # 加载数据
        with open(cache_file, 'r', encoding='utf-8') as f:
            panglaodb_data = json.load(f)
        
        # 规范化物种名称
        species = species.upper()
        if species not in panglaodb_data:
            available_species = list(panglaodb_data.keys())
            return json.dumps({
                "error": _("database.cellmarker.species_not_exist", species=species),
                "available_species": available_species,
                "success": False
            }, ensure_ascii=False, indent=2)
        
        species_data = panglaodb_data[species]
        
        # 如果指定了器官类型
        if organ:
            organ = organ.upper()
            if organ not in species_data:
                available_organs = list(species_data.keys())
                return json.dumps({
                    "error": _("database.panglaodb.organ_not_exist", organ=organ, species=species),
                    "available_organs": available_organs[:20],
                    "success": False
                }, ensure_ascii=False, indent=2)
            
            organ_data = species_data[organ]
            
            # 如果指定了细胞类型
            if cell_type:
                cell_type = cell_type.upper()
                if cell_type not in organ_data:
                    available_cell_types = list(organ_data.keys())
                    return json.dumps({
                        "error": _("database.panglaodb.celltype_not_exist", celltype=cell_type, species=species, organ=organ),
                        "available_cell_types": available_cell_types[:20],
                        "success": False
                    }, ensure_ascii=False, indent=2)
                
                result = {
                    "success": True,
                    "species": species,
                    "organ": organ,
                    "cell_type": cell_type,
                    "marker_genes": organ_data[cell_type],
                    "gene_count": len(organ_data[cell_type])
                }
            else:
                # 返回该器官的所有细胞类型
                cell_types_summary = {}
                for ct, genes in organ_data.items():
                    cell_types_summary[ct] = {
                        "gene_count": len(genes),
                        "sample_genes": genes[:5]
                    }
                
                result = {
                    "success": True,
                    "species": species,
                    "organ": organ,
                    "cell_types_count": len(cell_types_summary),
                    "cell_types": cell_types_summary
                }
        else:
            # 返回该物种的器官概况
            organs_summary = {}
            for o, cell_types in species_data.items():
                organs_summary[o] = {
                    "cell_types_count": len(cell_types),
                    "total_genes": sum(len(genes) for genes in cell_types.values())
                }
            
            result = {
                "success": True,
                "species": species,
                "organs_count": len(organs_summary),
                "organs": organs_summary
            }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": _("database.panglaodb.query_failed", error=str(e)),
            "success": False
        }, ensure_ascii=False, indent=2)

@mcp.tool()
async def cellmarker_enrichment(
    gene_list: str,
    species: str = "HUMAN",
    min_overlap: int = 2
) -> str:
    """使用CellMarker数据库对用户提供的基因列表进行细胞类型富集分析
    
    Args:
        gene_list: 基因列表，支持逗号分隔的多个基因（如: "CD3D,CD4,CD8A"）
        species: 物种名称，默认"HUMAN"，也支持"MOUSE"
        min_overlap: 最小重叠基因数量，默认2
        
    Returns:
        JSON格式的富集分析结果，包含前5个可信度最高的细胞类型
    """
    try:
        # 解析基因列表
        if isinstance(gene_list, str):
            genes_set = set([g.strip().upper() for g in gene_list.split(',') if g.strip()])
        else:
            genes_set = set([str(g).upper() for g in list(gene_list)])
        
        if not genes_set:
            return json.dumps({
                "error": _("database.enrichment.empty_genes"),
                "success": False
            }, ensure_ascii=False, indent=2)
        
        cellmarker_fetcher = get_cellmarker_fetcher()
        
        # 检查本地是否有缓存数据
        cache_file = GlobalCacheManager.get_cache_dir("cellmarker") / "cellmarker_merged_all.json"
        if not cache_file.exists():
            # 下载并处理数据
            await asyncio.get_event_loop().run_in_executor(
                None, cellmarker_fetcher.fetch_and_merge_all_data, "all"
            )
        
        # 加载数据
        with open(cache_file, 'r', encoding='utf-8') as f:
            cellmarker_data = json.load(f)
        
        # 规范化物种名称
        species = species.upper()
        if species not in cellmarker_data:
            available_species = list(cellmarker_data.keys())
            return json.dumps({
                "error": _("database.cellmarker.species_not_exist", species=species),
                "available_species": available_species,
                "success": False
            }, ensure_ascii=False, indent=2)
        
        species_data = cellmarker_data[species]
        
        # 计算富集分析
        enrichment_results = []
        
        for tissue, tissue_data in species_data.items():
            for cell_type, marker_genes in tissue_data.items():
                # 转换为大写进行比较
                marker_genes_upper = set([g.upper() for g in marker_genes])
                
                # 计算重叠
                overlap_genes = genes_set.intersection(marker_genes_upper)
                overlap_count = len(overlap_genes)
                
                if overlap_count >= min_overlap:
                    # 计算富集指标
                    total_markers = len(marker_genes_upper)
                    total_input = len(genes_set)
                    
                    # 计算Jaccard系数作为可信度指标
                    union_count = len(genes_set.union(marker_genes_upper))
                    jaccard_score = overlap_count / union_count if union_count > 0 else 0
                    
                    # 计算覆盖率
                    coverage_rate = overlap_count / total_input
                    precision_rate = overlap_count / total_markers if total_markers > 0 else 0
                    
                    # 综合得分 (加权平均)
                    confidence_score = (jaccard_score * 0.4 + coverage_rate * 0.4 + precision_rate * 0.2)
                    
                    enrichment_results.append({
                        "cell_type": f"{cell_type}-{tissue}-{species}",
                        "overlap_count": overlap_count,
                        "overlap_genes": sorted(list(overlap_genes)),
                        "total_input_genes": total_input,
                        "total_marker_genes": total_markers,
                        "jaccard_score": round(jaccard_score, 4),
                        "coverage_rate": round(coverage_rate, 4),
                        "precision_rate": round(precision_rate, 4),
                        "confidence_score": round(confidence_score, 4)
                    })
        
        # 按照可信度得分排序，取前5个
        enrichment_results.sort(key=lambda x: x["confidence_score"], reverse=True)
        top_results = enrichment_results[:5]
        
        result = {
            "success": True,
            "database": "CellMarker",
            "input_genes": sorted(list(genes_set)),
            "input_gene_count": len(genes_set),
            "species": species,
            "min_overlap": min_overlap,
            "total_matches": len(enrichment_results),
            "top_cell_types": top_results
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": _("database.cellmarker.enrichment_failed", error=str(e)),
            "success": False
        }, ensure_ascii=False, indent=2)

@mcp.tool()
async def panglaodb_enrichment(
    gene_list: str,
    species: str = "HUMAN",
    min_overlap: int = 2
) -> str:
    """使用PanglaoDB数据库对用户提供的基因列表进行细胞类型富集分析
    
    Args:
        gene_list: 基因列表，支持逗号分隔的多个基因（如: "CD3D,CD4,CD8A"）
        species: 物种名称，默认"HUMAN"，也支持"MOUSE"
        min_overlap: 最小重叠基因数量，默认2
        
    Returns:
        JSON格式的富集分析结果，包含前5个可信度最高的细胞类型
    """
    try:
        # 解析基因列表
        if isinstance(gene_list, str):
            genes_set = set([g.strip().upper() for g in gene_list.split(',') if g.strip()])
        else:
            genes_set = set([str(g).upper() for g in list(gene_list)])
        
        if not genes_set:
            return json.dumps({
                "error": _("database.enrichment.empty_genes"),
                "success": False
            }, ensure_ascii=False, indent=2)
        
        panglaodb_fetcher = get_panglaodb_fetcher()
        
        # 检查本地是否有缓存数据
        cache_file = GlobalCacheManager.get_cache_dir("panglaodb") / "panglaodb_markers.json"
        if not cache_file.exists():
            # 下载并处理数据
            await asyncio.get_event_loop().run_in_executor(
                None, panglaodb_fetcher.fetch_and_process_data
            )
        
        # 加载数据
        with open(cache_file, 'r', encoding='utf-8') as f:
            panglaodb_data = json.load(f)
        
        # 规范化物种名称
        if species.upper() == "HUMAN":
            species_key = "HUMAN"
        elif species.upper() == "MOUSE":
            species_key = "MOUSE"
        else:
            return json.dumps({
                "error": _("database.panglaodb.species_not_supported", species=species),
                "success": False
            }, ensure_ascii=False, indent=2)
        
        if species_key not in panglaodb_data:
            available_species = list(panglaodb_data.keys())
            return json.dumps({
                "error": _("database.panglaodb.species_not_exist", species=species_key),
                "available_species": available_species,
                "success": False
            }, ensure_ascii=False, indent=2)
        
        species_data = panglaodb_data[species_key]
        
        # 计算富集分析
        enrichment_results = []
        
        for organ, organ_data in species_data.items():
            for cell_type, marker_genes in organ_data.items():
                # 转换为大写进行比较
                marker_genes_upper = set([g.upper() for g in marker_genes])
                
                # 计算重叠
                overlap_genes = genes_set.intersection(marker_genes_upper)
                overlap_count = len(overlap_genes)
                
                if overlap_count >= min_overlap:
                    # 计算富集指标
                    total_markers = len(marker_genes_upper)
                    total_input = len(genes_set)
                    
                    # 计算Jaccard系数作为可信度指标
                    union_count = len(genes_set.union(marker_genes_upper))
                    jaccard_score = overlap_count / union_count if union_count > 0 else 0
                    
                    # 计算覆盖率
                    coverage_rate = overlap_count / total_input
                    precision_rate = overlap_count / total_markers if total_markers > 0 else 0
                    
                    # 综合得分 (加权平均)
                    confidence_score = (jaccard_score * 0.4 + coverage_rate * 0.4 + precision_rate * 0.2)
                    
                    enrichment_results.append({
                        "cell_type": f"{cell_type}-{organ}-{species_key}",
                        "overlap_count": overlap_count,
                        "overlap_genes": sorted(list(overlap_genes)),
                        "total_input_genes": total_input,
                        "total_marker_genes": total_markers,
                        "jaccard_score": round(jaccard_score, 4),
                        "coverage_rate": round(coverage_rate, 4),
                        "precision_rate": round(precision_rate, 4),
                        "confidence_score": round(confidence_score, 4)
                    })
        
        # 按照可信度得分排序，取前5个
        enrichment_results.sort(key=lambda x: x["confidence_score"], reverse=True)
        top_results = enrichment_results[:5]
        
        result = {
            "success": True,
            "database": "PanglaoDB",
            "input_genes": sorted(list(genes_set)),
            "input_gene_count": len(genes_set),
            "species": species_key,
            "min_overlap": min_overlap,
            "total_matches": len(enrichment_results),
            "top_cell_types": top_results
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": _("database.panglaodb.enrichment_failed", error=str(e)),
            "success": False
        }, ensure_ascii=False, indent=2)

@mcp.tool()
async def get_cellmarker_tissues(
    species: str = "HUMAN"
) -> str:
    """获取CellMarker数据库中指定物种的所有组织类型列表
    
    Args:
        species: 物种名称，默认"HUMAN"，也支持"MOUSE"
        
    Returns:
        JSON格式的组织类型列表
    """
    try:
        cellmarker_fetcher = get_cellmarker_fetcher()
        
        # 检查本地是否有缓存数据
        cache_file = GlobalCacheManager.get_cache_dir("cellmarker") / "cellmarker_merged_all.json"
        if not cache_file.exists():
            # 下载并处理数据
            await asyncio.get_event_loop().run_in_executor(
                None, cellmarker_fetcher.fetch_and_merge_all_data, "all"
            )
        
        # 加载数据
        with open(cache_file, 'r', encoding='utf-8') as f:
            cellmarker_data = json.load(f)
        
        # 规范化物种名称
        species = species.upper()
        if species not in cellmarker_data:
            available_species = list(cellmarker_data.keys())
            return json.dumps({
                "error": _("database.cellmarker.species_not_exist", species=species),
                "available_species": available_species,
                "success": False
            }, ensure_ascii=False, indent=2)
        
        species_data = cellmarker_data[species]
        
        # 获取所有组织类型及其统计信息 (简化版，减少数据量)
        tissues_list = []
        for tissue_name, tissue_data in species_data.items():
            tissue_info = {
                "tissue_name": tissue_name,
                "cell_types_count": len(tissue_data),
                "total_marker_genes": sum(len(genes) for genes in tissue_data.values()),
                # 移除详细的细胞类型列表以减少数据量
                # "cell_types": list(tissue_data.keys())  # 这行会产生大量数据
            }
            tissues_list.append(tissue_info)
        
        # 按细胞类型数量排序
        tissues_list.sort(key=lambda x: x["cell_types_count"], reverse=True)
        
        result = {
            "success": True,
            "database": "CellMarker",
            "species": species,
            "tissues_count": len(tissues_list),
            "total_cell_types": sum(t["cell_types_count"] for t in tissues_list),
            "total_marker_genes": sum(t["total_marker_genes"] for t in tissues_list),
            "tissues": tissues_list
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": _("database.cellmarker.tissues_failed", error=str(e)),
            "success": False
        }, ensure_ascii=False, indent=2)

@mcp.tool()
async def get_panglaodb_organs(
    species: str = "HUMAN"
) -> str:
    """获取PanglaoDB数据库中指定物种的所有器官/组织类型列表
    
    Args:
        species: 物种名称，默认"HUMAN"，也支持"MOUSE"
        
    Returns:
        JSON格式的器官/组织类型列表
    """
    try:
        panglaodb_fetcher = get_panglaodb_fetcher()
        
        # 检查本地是否有缓存数据
        cache_file = GlobalCacheManager.get_cache_dir("panglaodb") / "panglaodb_markers.json"
        if not cache_file.exists():
            # 下载并处理数据
            await asyncio.get_event_loop().run_in_executor(
                None, panglaodb_fetcher.fetch_and_process_data
            )
        
        # 加载数据
        with open(cache_file, 'r', encoding='utf-8') as f:
            panglaodb_data = json.load(f)
        
        # 规范化物种名称
        species = species.upper()
        if species not in panglaodb_data:
            available_species = list(panglaodb_data.keys())
            return json.dumps({
                "error": _("database.cellmarker.species_not_exist", species=species),
                "available_species": available_species,
                "success": False
            }, ensure_ascii=False, indent=2)
        
        species_data = panglaodb_data[species]
        
        # 获取所有器官类型及其统计信息 (简化版，减少数据量)
        organs_list = []
        for organ_name, organ_data in species_data.items():
            organ_info = {
                "organ_name": organ_name,
                "cell_types_count": len(organ_data),
                "total_marker_genes": sum(len(genes) for genes in organ_data.values()),
                # 移除详细的细胞类型列表以减少数据量
                # "cell_types": list(organ_data.keys())  # 这行会产生大量数据
            }
            organs_list.append(organ_info)
        
        # 按细胞类型数量排序
        organs_list.sort(key=lambda x: x["cell_types_count"], reverse=True)
        
        result = {
            "success": True,
            "database": "PanglaoDB",
            "species": species,
            "organs_count": len(organs_list),
            "total_cell_types": sum(o["cell_types_count"] for o in organs_list),
            "total_marker_genes": sum(o["total_marker_genes"] for o in organs_list),
            "organs": organs_list
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": _("database.panglaodb.organs_failed", error=str(e)),
            "success": False
        }, ensure_ascii=False, indent=2)

@mcp.tool()
async def get_cellmarker_celltypes_by_tissue(
    species: str = "HUMAN",
    tissue: str = ""
) -> str:
    """根据物种和组织类型从CellMarker数据库获取该组织的所有细胞类型
    
    Args:
        species: 物种名称，默认"HUMAN"，也支持"MOUSE"
        tissue: 组织类型，支持单个或多个（逗号分隔），如"BLOOD"、"BRAIN"或"BLOOD,BRAIN"等
        
    Returns:
        JSON格式的细胞类型列表，包含标记基因信息
    """
    try:
        if not tissue:
            return json.dumps({
                "error": _("errors.missing_tissue"),
                "success": False
            }, ensure_ascii=False, indent=2)
        
        cellmarker_fetcher = get_cellmarker_fetcher()
        
        # 检查本地是否有缓存数据
        cache_file = GlobalCacheManager.get_cache_dir("cellmarker") / "cellmarker_merged_all.json"
        if not cache_file.exists():
            # 下载并处理数据
            await asyncio.get_event_loop().run_in_executor(
                None, cellmarker_fetcher.fetch_and_merge_all_data, "all"
            )
        
        # 加载数据
        with open(cache_file, 'r', encoding='utf-8') as f:
            cellmarker_data = json.load(f)
        
        # 规范化参数
        species = species.upper()
        # 处理多个组织类型（逗号分隔）
        tissues = [t.strip().upper() for t in tissue.split(',') if t.strip()]
        
        # 检查物种是否存在
        if species not in cellmarker_data:
            available_species = list(cellmarker_data.keys())
            return json.dumps({
                "error": _("database.cellmarker.species_not_exist", species=species),
                "available_species": available_species,
                "success": False
            }, ensure_ascii=False, indent=2)
        
        species_data = cellmarker_data[species]
        
        # 处理多个组织类型
        result_tissues = {}
        not_found_tissues = []
        
        for tissue_name in tissues:
            if tissue_name in species_data:
                tissue_data = species_data[tissue_name]
                cell_types_list = sorted(list(tissue_data.keys()))
                result_tissues[tissue_name] = cell_types_list
            else:
                not_found_tissues.append(tissue_name)
        
        # 如果所有组织都不存在，返回错误
        if not result_tissues:
            available_tissues = list(species_data.keys())
            return json.dumps({
                "error": f"所有指定的组织类型都不存在: {', '.join(tissues)}",
                "available_tissues": available_tissues,
                "success": False
            }, ensure_ascii=False, indent=2)
        
        # 合并所有组织的细胞类型
        all_cell_types = set()
        for cell_types_list in result_tissues.values():
            all_cell_types.update(cell_types_list)
        
        result = {
            "success": True,
            "database": "CellMarker",
            "species": species,
            "tissues": list(result_tissues.keys()),
            "tissues_detail": result_tissues,
            "cell_types": sorted(list(all_cell_types)),
            "not_found_tissues": not_found_tissues if not_found_tissues else None
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": _("database.cellmarker.celltypes_failed", error=str(e)),
            "success": False
        }, ensure_ascii=False, indent=2)

@mcp.tool()
async def get_panglaodb_celltypes_by_organ(
    species: str = "HUMAN",
    organ: str = ""
) -> str:
    """根据物种和器官类型从PanglaoDB数据库获取该器官的所有细胞类型
    
    Args:
        species: 物种名称，默认"HUMAN"，也支持"MOUSE"
        organ: 器官类型，支持单个或多个（逗号分隔），如"BLOOD"、"BRAIN"或"BLOOD,BRAIN"等
        
    Returns:
        JSON格式的细胞类型列表，包含标记基因信息
    """
    try:
        if not organ:
            return json.dumps({
                "error": "请提供器官类型参数",
                "success": False
            }, ensure_ascii=False, indent=2)
        
        panglaodb_fetcher = get_panglaodb_fetcher()
        
        # 检查本地是否有缓存数据
        cache_file = GlobalCacheManager.get_cache_dir("panglaodb") / "panglaodb_markers.json"
        if not cache_file.exists():
            # 下载并处理数据
            await asyncio.get_event_loop().run_in_executor(
                None, panglaodb_fetcher.fetch_and_process_data
            )
        
        # 加载数据
        with open(cache_file, 'r', encoding='utf-8') as f:
            panglaodb_data = json.load(f)
        
        # 规范化参数
        species = species.upper()
        # 处理多个器官类型（逗号分隔）
        organs = [o.strip().upper() for o in organ.split(',') if o.strip()]
        
        # 检查物种是否存在
        if species not in panglaodb_data:
            available_species = list(panglaodb_data.keys())
            return json.dumps({
                "error": _("database.cellmarker.species_not_exist", species=species),
                "available_species": available_species,
                "success": False
            }, ensure_ascii=False, indent=2)
        
        species_data = panglaodb_data[species]
        
        # 处理多个器官类型
        result_organs = {}
        not_found_organs = []
        
        for organ_name in organs:
            if organ_name in species_data:
                organ_data = species_data[organ_name]
                cell_types_list = sorted(list(organ_data.keys()))
                result_organs[organ_name] = cell_types_list
            else:
                not_found_organs.append(organ_name)
        
        # 如果所有器官都不存在，返回错误
        if not result_organs:
            available_organs = list(species_data.keys())
            return json.dumps({
                "error": f"所有指定的器官类型都不存在: {', '.join(organs)}",
                "available_organs": available_organs,
                "success": False
            }, ensure_ascii=False, indent=2)
        
        # 合并所有器官的细胞类型
        all_cell_types = set()
        for cell_types_list in result_organs.values():
            all_cell_types.update(cell_types_list)
        
        result = {
            "success": True,
            "database": "PanglaoDB",
            "species": species,
            "organs": list(result_organs.keys()),
            "organs_detail": result_organs,
            "cell_types": sorted(list(all_cell_types)),
            "not_found_organs": not_found_organs if not_found_organs else None
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"获取PanglaoDB细胞类型失败: {str(e)}",
            "success": False
        }, ensure_ascii=False, indent=2)

@mcp.tool()
async def gene_enrichment_analysis(
    gene_list: str,
    top_n: int = 5,
    cutoff: float = 0.05,
    organism: str = "Human"
) -> str:
    """使用GSEApy进行基因富集分析（GO和KEGG通路分析）
    
    Args:
        gene_list: 基因列表，支持逗号分隔的多个基因（如: "TP53,BRCA1,MYC"）
        top_n: 每个数据库返回的前N个结果，默认5
        cutoff: P值阈值，默认0.05
        organism: 物种，默认'Human'，也可指定'Mouse'
        
    Returns:
        JSON格式的富集分析结果，包含GO和KEGG通路信息
    """
    try:
        # 解析基因列表
        if isinstance(gene_list, str):
            genes_list = [g.strip() for g in gene_list.split(',') if g.strip()]
        else:
            genes_list = list(gene_list)
        
        if not genes_list:
            return json.dumps({
                "error": _("database.enrichment.empty_genes"),
                "success": False
            }, ensure_ascii=False, indent=2)
        
        # 获取富集分析器实例
        analyzer = get_enrichment_analyzer(top_n=top_n, cutoff=cutoff, organism=organism)
        
        # 在后台线程执行分析（避免阻塞）
        enrichment_results = await asyncio.get_event_loop().run_in_executor(
            None, analyzer.analyze, genes_list
        )
        
        if not enrichment_results:
            return json.dumps({
                "error": "富集分析未返回任何结果，请检查基因名称或网络连接",
                "success": False
            }, ensure_ascii=False, indent=2)
        
        # 格式化结果
        formatted_results = {}
        total_significant_results = 0
        
        for db_name, df in enrichment_results.items():
            if df.empty:
                formatted_results[db_name] = {
                    "status": "无显著富集结果",
                    "result_count": 0,
                    "results": []
                }
            else:
                # 转换DataFrame为字典格式
                results_list = []
                for _, row in df.iterrows():
                    result_dict = {
                        "term": row['Term'],
                        "p_value": float(row['P-value']),
                        "adjusted_p_value": float(row['Adjusted P-value']),
                        "odds_ratio": float(row['Odds Ratio']) if 'Odds Ratio' in row else None,
                        "combined_score": float(row['Combined Score']) if 'Combined Score' in row else None,
                        "genes": row['Genes'].split(';') if 'Genes' in row and pd.notna(row['Genes']) else [],
                        "gene_count": len(row['Genes'].split(';')) if 'Genes' in row and pd.notna(row['Genes']) else 0
                    }
                    results_list.append(result_dict)
                
                formatted_results[db_name] = {
                    "status": "成功",
                    "result_count": len(results_list),
                    "results": results_list
                }
                total_significant_results += len(results_list)
        
        # 构建最终结果
        final_result = {
            "success": True,
            "input_genes": genes_list,
            "input_gene_count": len(genes_list),
            "analysis_parameters": {
                "organism": analyzer.organism if hasattr(analyzer, 'organism') else organism,
                "top_n": top_n,
                "p_value_cutoff": cutoff
            },
            "databases_analyzed": list(formatted_results.keys()),
            "total_significant_results": total_significant_results,
            "results": formatted_results
        }
        
        return json.dumps(final_result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": _("database.enrichment.analysis_failed", error=str(e)),
            "success": False,
            "details": {
                "error_type": type(e).__name__,
                "input_genes": genes_list if 'genes_list' in locals() else None
            }
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_token_stats() -> str:
    """获取SubAgent的token消耗统计信息

    Returns:
        str: JSON格式的token统计信息
    """
    try:
        # 由于MCP服务器是独立进程，这里返回默认的空统计
        # 实际的token统计需要通过agent实例获取
        from agentype.common.token_statistics import TokenStatistics

        # 创建一个空的统计对象作为占位符
        # 实际应该通过某种IPC机制或共享存储获取真实数据
        stats = TokenStatistics(agent_name="SubAgent")

        return json.dumps({
            "success": True,
            "data": stats.to_dict(),
            "message": "SubAgent token统计 (MCP服务器独立进程)"
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"获取token统计失败: {str(e)}",
            "data": {}
        }, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    """
    启动 SubAgent MCP 服务器

    配置通过混合方案传递：
    - 敏感信息（API Key）通过环境变量 OPENAI_API_KEY
    - 非敏感配置通过命令行参数
    """
    import argparse
    import os
    import sys
    from pathlib import Path
    from agentype.mainagent.config.session_config import set_session_id

    # 1. 解析命令行参数
    parser = argparse.ArgumentParser(description='CellType SubAgent MCP Server')
    parser.add_argument('--api-base', type=str, help='LLM API Base URL (required)')
    parser.add_argument('--model', type=str, default='gpt-4o', help='LLM Model name')
    parser.add_argument('--output-dir', type=str, required=True, help='Output directory (required)')
    parser.add_argument('--language', type=str, default='zh', choices=['zh', 'en'], help='Language')
    parser.add_argument('--enable-streaming', type=str, default='true', help='Enable streaming output')
    parser.add_argument('--enable-thinking', type=str, default='false', help='Enable thinking output')
    parser.add_argument('--session-id', type=str, help='Session ID for tracking')
    args = parser.parse_args()

    # 2. 从环境变量读取 API Key（安全）
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ 错误: 未设置 OPENAI_API_KEY 环境变量", file=sys.stderr)
        print("   SubAgent MCP Server 需要 API Key 才能运行", file=sys.stderr)
        sys.exit(1)

    # 3. 验证必需的命令行参数
    if not args.api_base:
        print("❌ 错误: 缺少必需参数 --api-base", file=sys.stderr)
        sys.exit(1)

    # 4. 创建输出目录
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # 4.5. 创建ConfigManager并设置为模块级配置对象
    from agentype.subagent.config.settings import ConfigManager

    enable_thinking = args.enable_thinking.lower() in ('true', '1', 'yes')

    _CONFIG = ConfigManager(
        openai_api_base=args.api_base,
        openai_api_key=api_key,
        openai_model=args.model,
        output_dir=str(output_dir),  # 传递output_dir，让ConfigManager自动派生cache_dir
        enable_thinking=enable_thinking
    )

    # 设置全局缓存目录（从 _CONFIG 获取）
    GlobalCacheManager.set_global_cache_dir(_CONFIG.cache_dir)

    print(f"✅ SubAgent ConfigManager 已初始化:", file=sys.stderr)
    print(f"   Output Dir: {_CONFIG.output_dir}", file=sys.stderr)
    print(f"   Results Dir: {_CONFIG.results_dir}", file=sys.stderr)
    print(f"   Cache Dir: {_CONFIG.cache_dir}", file=sys.stderr)

    # 初始化缓存（使用 ConfigManager）
    from agentype.subagent import init_cache
    cache_dir = init_cache(config=_CONFIG)

    # 设置工具模块的全局配置（用于 file_paths_tools）
    from agentype.mainagent.tools.file_paths_tools import set_global_config
    set_global_config(_CONFIG)

    # 5. 设置 session_id
    if args.session_id:
        set_session_id(args.session_id)
        print(f"✅ SubAgent MCP Server 使用 session_id: {args.session_id}", file=sys.stderr)

    # 6. 打印配置信息
    print(f"✅ SubAgent MCP Server 配置:", file=sys.stderr)
    print(f"   API Base: {args.api_base}", file=sys.stderr)
    print(f"   Model: {args.model}", file=sys.stderr)
    
    # 启动MCP服务器 (标准stdio传输)
    print(_("mcp.server.starting"))
    print(_("mcp.server.protocol"))
    print(_("mcp.server.tool_count"))
    print(_("mcp.server.functions"))
    print(_("mcp.server.tool_list.get_gene_info"))
    print(_("mcp.server.tool_list.query_cellmarker"))
    print(_("mcp.server.tool_list.query_panglaodb"))
    print(_("mcp.server.tool_list.cellmarker_enrichment"))
    print(_("mcp.server.tool_list.panglaodb_enrichment"))
    print(_("mcp.server.tool_list.gene_enrichment_analysis"))
    print(_("mcp.server.tool_list.get_cellmarker_tissues"))
    print(_("mcp.server.tool_list.get_panglaodb_organs"))
    print(_("mcp.server.tool_list.get_cellmarker_celltypes_by_tissue"))
    print(_("mcp.server.tool_list.get_panglaodb_celltypes_by_organ"))
    print(_("mcp.server.separator"))
    mcp.run(transport='stdio')