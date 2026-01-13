#!/usr/bin/env python3
"""
agentype - App Agent MCP Server
Author: cuilei
Version: 1.0
"""

import sys
import asyncio
import json
import os
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime

# 导入项目模块

# 导入国际化支持
try:
    from agentype.appagent.utils.i18n import _
except ImportError:
    # 如果国际化模块不存在，提供简单的占位符
    def _(key, **kwargs):
        return key.format(**kwargs) if kwargs else key

# 导入统一配置系统的session_id函数
try:
    from agentype.config import get_session_id_for_filename
except ImportError:
    # 如果导入失败，提供备用实现
    def get_session_id_for_filename():
        from datetime import datetime
        return f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

try:
    from mcp.server.fastmcp import FastMCP
    # 导入现有的工具函数
    from agentype.appagent.tools.celldex_info_tool import get_celldex_projects_info
    from agentype.appagent.tools.celldex_download_tool import download_celldex_dataset
    from agentype.appagent.tools.singleR_simple import singleR_annotate
    from agentype.appagent.tools.get_sctype_tissues import get_sctype_tissues
    from agentype.appagent.tools.sctype_simple import sctype_annotate
    from agentype.appagent.tools.get_celltypist_models import get_celltypist_models
    from agentype.appagent.tools.celltypist_simple import celltypist_annotate
    
    # 导入新的物种检测和文件验证工具
    from agentype.appagent.tools.species_detection import (
        detect_species_from_h5ad, 
        detect_species_from_rds, 
        detect_species_from_marker_json
    )
    from agentype.appagent.tools.file_validators import validate_marker_json

    # 导入路径管理工具
    from agentype.mainagent.tools.file_paths_tools import (
        save_file_paths_bundle as _save_file_paths_bundle,
        load_file_paths_bundle as _load_file_paths_bundle,
        load_and_validate_bundle as _load_and_validate_bundle
    )

except ImportError as e:
    # 获取项目根目录
    current_file = Path(__file__).resolve()
    # project_root 不再需要

    print(f"导入依赖失败: {e}")
    print("请检查MCP包安装：pip install mcp")
    print(f"当前工作目录: {Path.cwd()}")
    #
    print(f"Python路径: {sys.path[:3]}")
    sys.exit(1)

# 缓存目录（将在 __main__ 块中初始化，使用 ConfigManager 提供的路径）
cache_dir = None

# 导入路径管理器
try:
    from agentype.appagent.utils.path_manager import normalize_path
except ImportError:
    # 简单的备用实现
    def normalize_path(file_path):
        return str(Path(file_path).resolve()) if file_path else ""
    def get_absolute_paths(**kwargs):
        return {k: normalize_path(v) for k, v in kwargs.items()}

# 初始化FastMCP服务器
mcp = FastMCP("celltype-app-agent", log_level="INFO")

# 缓存目录配置（在 __main__ 块中初始化）
CACHE_DIR = None

# 配置对象（在 __main__ 块中初始化）
_CONFIG = None

def ensure_cache_dir() -> str:
    """确保缓存目录存在"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    return CACHE_DIR

# ============ SingleR 相关工具 ============

@mcp.tool()
async def get_celldex_projects_info_tool(language: str = "zh") -> str:
    """
    获取celldex所有参考数据集信息
    
    Args:
        language: 输出语言，"zh"为中文，"en"为英文
    
    Returns:
        包含所有celldex数据集信息的JSON字符串
    """
    try:
        ensure_cache_dir()
        
        # 使用异步执行器调用处理函数
        result = await asyncio.get_event_loop().run_in_executor(
            None, get_celldex_projects_info, language
        )
        
        return json.dumps({
            "success": True,
            "data": result,
            "message": "成功获取celldex数据集信息",
            "timestamp": get_session_id_for_filename()
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"获取celldex数据集信息时发生异常: {str(e)}",
            "timestamp": get_session_id_for_filename()
        }, ensure_ascii=False, indent=2)

@mcp.tool()
async def download_celldex_dataset_tool(dataset_name: str, cache_dir: str = "~/.cache/agentype") -> str:
    """
    下载celldex参考数据集
    
    Args:
        dataset_name: 数据集名称，支持完整名称或简写
        cache_dir: 缓存目录路径
    
    Returns:
        下载结果的JSON字符串
    """
    try:
        ensure_cache_dir()
        
        # 使用异步执行器调用处理函数
        result = await asyncio.get_event_loop().run_in_executor(
            None, download_celldex_dataset, dataset_name, cache_dir
        )
        
        return json.dumps({
            "success": True,
            "data": result,
            "message": f"celldex数据集 {dataset_name} 处理完成",
            "timestamp": get_session_id_for_filename()
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"下载celldex数据集 {dataset_name} 时发生异常: {str(e)}",
            "timestamp": get_session_id_for_filename()
        }, ensure_ascii=False, indent=2)

@mcp.tool()
async def singleR_annotate_tool(
    reference_path: str,
    rds_path: Optional[str] = None,
    cluster_column: str = "seurat_clusters",
) -> str:
    """
    使用SingleR进行细胞类型注释（自动化版本）

    此工具完全自动化处理SingleR注释流程：
    1. 自动从bundle读取Seurat数据文件路径（优先rds_file，降级h5_file）
    2. 自动生成输出文件路径，使用session_id命名
    3. 自动更新bundle，保存singler_result路径

    Args:
        reference_path: 参考数据库RDS文件路径（必需，外部数据）
        rds_path: Seurat对象的RDS文件路径（可选，不指定则自动从bundle读取）
        output_path: 输出JSON文件路径（可选，已废弃，自动生成）
        cluster_column: 聚类列名，默认"seurat_clusters"

    Returns:
        注释结果的JSON字符串
    """
    try:
        # 1. 使用智能fallback自动获取Seurat文件路径
        try:
            from agentype.mainagent.tools.file_paths_tools import auto_get_input_path
            rds_path = auto_get_input_path(
                manual_path=rds_path,
                bundle_keys=['rds_file', 'sce_h5', 'scanpy_h5', 'h5_file'],
                tool_name='singleR_annotate_tool'
            )
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"自动获取Seurat路径失败: {e}"
            }, ensure_ascii=False, indent=2)

        # MCP层自动生成output_path（使用 _CONFIG 的 results_dir）
        ts = get_session_id_for_filename() or datetime.now().strftime("%Y%m%d_%H%M%S")
        results_dir = _CONFIG.get_results_dir()
        output_path = str(results_dir / f'singleR_annotation_result_{ts}.json')

        # 🔬 执行SingleR注释（记录到日志，避免污染 MCP stdout）

        # 使用异步执行器调用处理函数
        result = await asyncio.get_event_loop().run_in_executor(
            None, singleR_annotate, rds_path, reference_path, output_path, cluster_column
        )

        # 统一提取输出路径
        resolved_output = output_path
        if isinstance(result, dict) and result.get("output_file"):
            resolved_output = result.get("output_file")

        # 2. 自动更新bundle，保存singler_result路径
        try:
            from agentype.mainagent.tools.file_paths_tools import auto_update_bundle
            auto_update_bundle('singler_result', resolved_output)
        except Exception as e:
            print(f"⚠️ 更新bundle失败（不影响主流程）: {e}")

        return json.dumps({
            "success": True,
            "data": result,
            "input_file": rds_path,
            "reference_file": reference_path,
            "output_file": resolved_output,
            "cluster_column": cluster_column,
            "message": "SingleR注释完成",
            "timestamp": get_session_id_for_filename()
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"SingleR注释时发生异常: {str(e)}",
            "timestamp": get_session_id_for_filename()
        }, ensure_ascii=False, indent=2)

# ============ scType 相关工具 ============

@mcp.tool()
async def get_sctype_tissues_tool() -> str:
    """
    获取scType支持的所有组织类型
    
    Returns:
        包含组织类型列表的JSON字符串
    """
    try:
        ensure_cache_dir()
        
        # 使用异步执行器调用处理函数
        result = await asyncio.get_event_loop().run_in_executor(
            None, get_sctype_tissues
        )
        
        return json.dumps({
            "success": True,
            "data": result,
            "message": "成功获取scType组织类型",
            "timestamp": get_session_id_for_filename()
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"获取scType组织类型时发生异常: {str(e)}",
            "timestamp": get_session_id_for_filename()
        }, ensure_ascii=False, indent=2)

@mcp.tool()
async def sctype_annotate_tool(
    tissue_type: str = "Immune system",
    rds_path: Optional[str] = None,
    cluster_column: str = "seurat_clusters",
) -> str:
    """
    使用scType进行细胞类型注释（自动化版本）

    此工具完全自动化处理scType注释流程：
    1. 自动从bundle读取Seurat数据文件路径（优先rds_file，降级h5_file）
    2. 自动生成输出文件路径，使用session_id命名
    3. 自动更新bundle，保存sctype_result路径

    Args:
        tissue_type: 组织类型，默认"Immune system"
        rds_path: Seurat对象的RDS文件路径（可选，不指定则自动从bundle读取）
        output_path: 输出JSON文件路径（可选，已废弃，自动生成）
        cluster_column: 聚类列名，默认"seurat_clusters"

    Returns:
        注释结果的JSON字符串
    """
    try:
        # 1. 使用智能fallback自动获取Seurat文件路径
        try:
            from agentype.mainagent.tools.file_paths_tools import auto_get_input_path
            rds_path = auto_get_input_path(
                manual_path=rds_path,
                bundle_keys=['rds_file', 'sce_h5', 'scanpy_h5', 'h5_file'],
                tool_name='sctype_annotate_tool'
            )
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"自动获取Seurat路径失败: {e}"
            }, ensure_ascii=False, indent=2)

        # MCP层自动生成output_path（使用 _CONFIG 的 results_dir）
        ts = get_session_id_for_filename() or datetime.now().strftime("%Y%m%d_%H%M%S")
        results_dir = _CONFIG.get_results_dir()
        output_path = str(results_dir / f'sctype_annotation_result_{ts}.json')

        # 🔬 执行scType注释（记录到日志，避免污染 MCP stdout）

        # 使用异步执行器调用处理函数
        result = await asyncio.get_event_loop().run_in_executor(
            None, sctype_annotate, rds_path, tissue_type, output_path, cluster_column
        )

        resolved_output = output_path
        if isinstance(result, dict) and result.get("output_file"):
            resolved_output = result.get("output_file")

        # 2. 自动更新bundle，保存sctype_result路径
        try:
            from agentype.mainagent.tools.file_paths_tools import auto_update_bundle
            auto_update_bundle('sctype_result', resolved_output)
        except Exception as e:
            print(f"⚠️ 更新bundle失败（不影响主流程）: {e}")

        return json.dumps({
            "success": True,
            "data": result,
            "input_file": rds_path,
            "tissue_type": tissue_type,
            "output_file": resolved_output,
            "cluster_column": cluster_column,
            "message": "scType注释完成",
            "timestamp": get_session_id_for_filename()
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"scType注释时发生异常: {str(e)}",
            "timestamp": get_session_id_for_filename()
        }, ensure_ascii=False, indent=2)

# ============ CellTypist 相关工具 ============

@mcp.tool()
async def get_celltypist_models_tool() -> str:
    """
    获取CellTypist所有可用模型
    
    Returns:
        包含模型列表的JSON字符串
    """
    try:
        ensure_cache_dir()
        
        # 使用异步执行器调用处理函数
        result = await asyncio.get_event_loop().run_in_executor(
            None, get_celltypist_models
        )
        
        return json.dumps({
            "success": True,
            "data": result,
            "message": "成功获取CellTypist模型",
            "timestamp": get_session_id_for_filename()
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"获取CellTypist模型时发生异常: {str(e)}",
            "timestamp": get_session_id_for_filename()
        }, ensure_ascii=False, indent=2)

@mcp.tool()
async def celltypist_annotate_tool(
    data_path: Optional[str] = None,
    model_name: Optional[str] = None,
    auto_detect_species: bool = True,
    cluster_column: Optional[str] = None,
) -> str:
    """
    使用CellTypist进行细胞类型注释（自动化版本）

    此工具完全自动化处理CellTypist注释流程：
    1. 自动从bundle读取H5AD数据文件路径（优先h5ad_file，降级h5_file）
    2. 自动生成输出文件路径，使用session_id命名
    3. 自动更新bundle，保存celltypist_result路径

    Args:
        data_path: H5AD文件路径（可选，不指定则自动从bundle读取）
        model_name: CellTypist模型名称，为None时根据物种自动选择
        output_path: 输出JSON文件路径（可选，已废弃，自动生成）
        auto_detect_species: 是否自动检测物种并选择合适模型
        cluster_column: 聚类列名，为None时自动搜索

    Returns:
        注释结果的JSON字符串
    """
    try:
        # 1. 使用智能fallback自动获取H5AD文件路径
        try:
            from agentype.mainagent.tools.file_paths_tools import auto_get_input_path
            data_path = auto_get_input_path(
                manual_path=data_path,
                bundle_keys=['h5ad_file', 'scanpy_h5', 'sce_h5', 'h5_file'],
                tool_name='celltypist_annotate_tool'
            )
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"自动获取H5AD路径失败: {e}"
            }, ensure_ascii=False, indent=2)

        # MCP层自动生成output_path（不接受外部输入）
        ts = get_session_id_for_filename() or datetime.now().strftime("%Y%m%d_%H%M%S")
        results_dir = _CONFIG.get_results_dir()
        output_path = str(results_dir / f'celltypist_annotation_result_{ts}.json')

        # 🔬 执行CellTypist注释（记录到日志，避免污染 MCP stdout）

        # 使用异步执行器调用处理函数
        result = await asyncio.get_event_loop().run_in_executor(
            None, celltypist_annotate, data_path, model_name, output_path, auto_detect_species, cluster_column
        )

        resolved_output = output_path
        if isinstance(result, dict) and result.get("output_file"):
            resolved_output = result.get("output_file")

        # 2. 自动更新bundle，保存celltypist_result路径
        try:
            from agentype.mainagent.tools.file_paths_tools import auto_update_bundle
            auto_update_bundle('celltypist_result', resolved_output)
        except Exception as e:
            print(f"⚠️ 更新bundle失败（不影响主流程）: {e}")

        return json.dumps({
            "success": True,
            "data": result,
            "input_file": data_path,
            "model_name": model_name,
            "output_file": resolved_output,
            "auto_detect_species": auto_detect_species,
            "cluster_column": cluster_column,
            "message": "CellTypist注释完成",
            "timestamp": get_session_id_for_filename()
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"CellTypist注释时发生异常: {str(e)}",
            "timestamp": get_session_id_for_filename()
        }, ensure_ascii=False, indent=2)

# ============ 物种检测相关工具 ============

@mcp.tool()
async def detect_species_from_h5ad_tool(h5ad_file: str) -> str:
    """
    从H5AD文件检测物种
    
    Args:
        h5ad_file: H5AD文件路径
    
    Returns:
        物种检测结果的JSON字符串
    """
    try:
        ensure_cache_dir()
        
        # 🔬 从H5AD文件检测物种（记录到日志，避免污染 MCP stdout）
        
        # 使用异步执行器调用处理函数
        species, detection_info = await asyncio.get_event_loop().run_in_executor(
            None, detect_species_from_h5ad, h5ad_file
        )
        
        return json.dumps({
            "success": True,
            "detected_species": species,
            "detection_details": detection_info,
            "message": f"H5AD文件物种检测完成: {species}",
            "timestamp": get_session_id_for_filename()
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"H5AD文件物种检测时发生异常: {str(e)}",
            "detected_species": "Human",
            "timestamp": get_session_id_for_filename()
        }, ensure_ascii=False, indent=2)

@mcp.tool()
async def detect_species_from_rds_tool(rds_file: str) -> str:
    """
    从RDS文件检测物种
    
    Args:
        rds_file: RDS文件路径
    
    Returns:
        物种检测结果的JSON字符串
    """
    try:
        ensure_cache_dir()
        
        # 🔬 从RDS文件检测物种（记录到日志，避免污染 MCP stdout）
        
        # 使用异步执行器调用处理函数
        species, detection_info = await asyncio.get_event_loop().run_in_executor(
            None, detect_species_from_rds, rds_file
        )
        
        return json.dumps({
            "success": True,
            "detected_species": species,
            "detection_details": detection_info,
            "message": f"RDS文件物种检测完成: {species}",
            "timestamp": get_session_id_for_filename()
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"RDS文件物种检测时发生异常: {str(e)}",
            "detected_species": "Human",
            "timestamp": get_session_id_for_filename()
        }, ensure_ascii=False, indent=2)

@mcp.tool()
async def detect_species_from_marker_json_tool(marker_genes_json: str) -> str:
    """
    从marker基因JSON文件检测物种

    Args:
        marker_genes_json: marker基因JSON文件路径

    Returns:
        物种检测结果的JSON字符串
    """
    try:
        ensure_cache_dir()

        # 🔬 从JSON文件检测物种（记录到日志，避免污染 MCP stdout）

        # 使用异步执行器调用处理函数
        species, detection_info = await asyncio.get_event_loop().run_in_executor(
            None, detect_species_from_marker_json, marker_genes_json
        )
        
        return json.dumps({
            "success": True,
            "detected_species": species,
            "detection_details": detection_info,
            "message": f"JSON文件物种检测完成: {species}",
            "timestamp": get_session_id_for_filename()
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"JSON文件物种检测时发生异常: {str(e)}",
            "detected_species": "Human",
            "timestamp": get_session_id_for_filename()
        }, ensure_ascii=False, indent=2)

# ============ 文件验证相关工具 ============

@mcp.tool()
async def validate_marker_json_tool(marker_genes_json: str) -> str:
    """
    验证marker基因JSON文件格式

    Args:
        marker_genes_json: marker基因JSON文件路径

    Returns:
        文件验证结果的JSON字符串
    """
    try:
        ensure_cache_dir()

        # 📋 验证marker基因JSON文件（记录到日志，避免污染 MCP stdout）

        # 使用异步执行器调用处理函数
        validation_result = await asyncio.get_event_loop().run_in_executor(
            None, validate_marker_json, marker_genes_json
        )
        
        return json.dumps({
            "success": True,
            "validation_result": validation_result,
            "message": f"JSON文件验证完成: {'有效' if validation_result.get('valid') else '无效'}",
            "timestamp": get_session_id_for_filename()
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"验证JSON文件时发生异常: {str(e)}",
            "validation_result": {"valid": False, "errors": [str(e)]},
            "timestamp": get_session_id_for_filename()
        }, ensure_ascii=False, indent=2)

@mcp.tool()
async def get_token_stats() -> str:
    """获取AppAgent的token消耗统计信息

    Returns:
        str: JSON格式的token统计信息
    """
    try:
        # 由于MCP服务器是独立进程，这里返回默认的空统计
        # 实际的token统计需要通过agent实例获取
        from agentype.common.token_statistics import TokenStatistics

        # 创建一个空的统计对象作为占位符
        # 实际应该通过某种IPC机制或共享存储获取真实数据
        stats = TokenStatistics(agent_name="AppAgent")

        return json.dumps({
            "success": True,
            "data": stats.to_dict(),
            "message": "AppAgent token统计 (MCP服务器独立进程)"
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"获取token统计时发生异常: {str(e)}"
        }, ensure_ascii=False, indent=2)


# ========== 路径管理工具 ==========

@mcp.tool()
async def save_file_paths_bundle(
    rds_file: Optional[str] = None,
    h5ad_file: Optional[str] = None,
    h5_file: Optional[str] = None,
    marker_genes_json: Optional[str] = None,
    singler_result: Optional[str] = None,
    sctype_result: Optional[str] = None,
    celltypist_result: Optional[str] = None
) -> str:
    """保存所有7个核心文件路径到cache目录（AppAgent版本）

    此工具用于在细胞注释完成后保存所有关键文件路径，包括数据文件和注释结果文件。

    Args:
        rds_file: RDS文件路径
        h5ad_file: H5AD文件路径
        h5_file: H5文件路径（easySCF格式）
        marker_genes_json: Marker基因JSON文件路径
        singler_result: SingleR注释结果文件路径
        sctype_result: scType注释结果文件路径
        celltypist_result: CellTypist注释结果文件路径

    Returns:
        JSON格式的保存结果，包含成功状态、session_id、保存路径等信息

    使用场景：
        - 在完成细胞类型注释后立即调用，保存所有生成的文件路径
        - 确保路径格式正确（特别注意中文路径的分隔符）
        - 如果保存失败，检查错误信息并修正路径后重试
    """
    try:
        # marker_genes_json 是 AppAgent 的必需输入
        if not marker_genes_json or marker_genes_json.strip() == "":
            return json.dumps({
                "success": False,
                "error": "❌ marker_genes_json 是必需的！AppAgent 需要 marker 基因 JSON 文件进行细胞类型注释。",
                "action_required": "请尝试以下操作：",
                "available_actions": [
                    "1. 使用 load_file_paths_bundle 工具加载之前 DataAgent 保存的路径",
                    "2. 检查 DataAgent 是否成功完成数据处理并生成了 JSON 文件",
                    "3. 如果 JSON 文件确实缺失，请通知 MainAgent 重新运行 DataAgent 步骤"
                ]
            }, ensure_ascii=False, indent=2)

        # 构建 metadata（自动添加 AppAgent 标记）
        metadata_dict = {
            "agent": "AppAgent",
            "stage": "annotation"
        }

        # 调用核心函数（session_id 由底层函数自动获取，使用默认过期时间）
        result = _save_file_paths_bundle(
            rds_file=rds_file,
            h5ad_file=h5ad_file,
            h5_file=h5_file,
            marker_genes_json=marker_genes_json,
            singler_result=singler_result,
            sctype_result=sctype_result,
            celltypist_result=celltypist_result,
            metadata=metadata_dict
        )

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"保存文件路径包异常: {e}"
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def load_file_paths_bundle() -> str:
    """从cache目录加载当前会话的文件路径

    此工具用于加载之前保存的文件路径信息，包括所有数据文件和注释结果文件。

    Returns:
        JSON格式的路径信息，包含 rds_file, h5ad_file, h5_file, marker_genes_json,
        singler_result, sctype_result, celltypist_result 等

    使用场景：
        - 当需要获取之前保存的文件路径时
        - 跨步骤传递文件路径信息
    """
    try:
        result = _load_and_validate_bundle()  # 使用验证版本更安全
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"加载文件路径包异常: {e}"
        }, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    """
    启动 AppAgent MCP 服务器

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
    parser = argparse.ArgumentParser(description='CellType AppAgent MCP Server')
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
        print("   AppAgent MCP Server 需要 API Key 才能运行", file=sys.stderr)
        sys.exit(1)

    # 3. 验证必需的命令行参数
    if not args.api_base:
        print("❌ 错误: 缺少必需参数 --api-base", file=sys.stderr)
        sys.exit(1)

    # 4. 创建输出目录
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # 4.5. 创建ConfigManager并设置为模块级配置对象
    from agentype.appagent.config.settings import ConfigManager

    enable_thinking = args.enable_thinking.lower() in ('true', '1', 'yes')

    _CONFIG = ConfigManager(
        openai_api_base=args.api_base,
        openai_api_key=api_key,
        openai_model=args.model,
        output_dir=str(output_dir),  # 传递output_dir，让ConfigManager自动派生cache_dir
        enable_thinking=enable_thinking
    )

    # 更新全局 CACHE_DIR（从 _CONFIG 获取）
    CACHE_DIR = _CONFIG.cache_dir

    print(f"✅ AppAgent ConfigManager 已初始化:", file=sys.stderr)
    print(f"   Output Dir: {_CONFIG.output_dir}", file=sys.stderr)
    print(f"   Results Dir: {_CONFIG.results_dir}", file=sys.stderr)
    print(f"   Cache Dir: {_CONFIG.cache_dir}", file=sys.stderr)

    # 初始化缓存（使用 ConfigManager）
    from agentype.appagent.config.cache_config import init_cache
    cache_dir = init_cache(config=_CONFIG)

    # 设置工具模块的全局配置（用于 file_paths_tools）
    from agentype.mainagent.tools.file_paths_tools import set_global_config
    set_global_config(_CONFIG)

    # 5. 设置 session_id
    if args.session_id:
        set_session_id(args.session_id)
        print(f"✅ AppAgent MCP Server 使用 session_id: {args.session_id}", file=sys.stderr)

    # 6. 打印配置信息
    print(f"✅ AppAgent MCP Server 配置:", file=sys.stderr)
    print(f"   API Base: {args.api_base}", file=sys.stderr)
    print(f"   Model: {args.model}", file=sys.stderr)
    
    # 启动MCP服务器 (标准stdio传输)
    # 🚀 启动CellType App Agent MCP服务器（静默模式）
    # 📋 协议: Model Context Protocol (MCP)
    # 🔧 可用工具: 15个
    # 📊 核心工具（静默模式，避免污染 MCP stdout）
    # 1️⃣  get_celldex_projects_info_tool - 获取celldex数据集信息
    # 2️⃣  download_celldex_dataset_tool - 下载celldex数据集
    # 3️⃣  singleR_annotate_tool - SingleR细胞类型注释
    # 4️⃣  get_sctype_tissues_tool - 获取scType组织类型
    # 5️⃣  sctype_annotate_tool - scType细胞类型注释
    # 6️⃣  get_celltypist_models_tool - 获取CellTypist模型
    # 7️⃣  celltypist_annotate_tool - CellTypist细胞类型注释
    # 8️⃣  celltype_annotation_pipeline - 统一注释流水线
    # 9️⃣  detect_species_from_h5ad_tool - 从H5AD文件检测物种
    # 🔟  detect_species_from_rds_tool - 从RDS文件检测物种
    # 1️⃣1️⃣ detect_species_from_marker_json_tool - 从JSON文件检测物种
    # 1️⃣2️⃣ validate_marker_json_tool - 验证marker基因JSON文件
    # 1️⃣3️⃣ get_token_stats - 获取token统计信息
    # 1️⃣4️⃣ save_file_paths_bundle - 保存文件路径到cache
    # 1️⃣5️⃣ load_file_paths_bundle - 从cache加载文件路径
    # MCP 服务器启动完成（静默模式）
    mcp.run(transport='stdio')
