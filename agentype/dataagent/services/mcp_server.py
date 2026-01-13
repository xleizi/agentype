#!/usr/bin/env python3
"""
agentype - Data Processor MCP Server
Author: cuilei
Version: 1.0
"""

import sys
import asyncio
import json
import os
from typing import Optional, Dict, Any
from pathlib import Path

# 导入项目模块

# 导入国际化支持
try:
    from agentype.dataagent.utils.i18n import _
except ImportError:
    # 如果国际化模块不存在，提供简单的占位符
    def _(key, **kwargs):
        return key.format(**kwargs) if kwargs else key

try:
    from mcp.server.fastmcp import FastMCP
    # 直接导入核心处理函数
    from agentype.dataagent.tools.data_converters import (
        run_r_findallmarkers,
        run_r_sce_to_h5,
        convert_r_markers_csv_to_json,
        easyscfpy_h5_to_json,
        scanpy_path_to_json,
        convert_scanpy_file_to_h5
    )
    # 导入配置函数用于构建实际输出路径
    from agentype.config import get_session_id_for_filename
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
    from agentype.dataagent.utils.path_manager import normalize_path, get_absolute_paths
except ImportError:
    # 简单的备用实现
    def normalize_path(file_path):
        return str(Path(file_path).resolve()) if file_path else ""
    def get_absolute_paths(**kwargs):
        return {k: normalize_path(v) for k, v in kwargs.items()}

# 初始化FastMCP服务器
mcp = FastMCP("celltype-data-processor", log_level="INFO")

# 缓存目录配置（在 __main__ 块中初始化）
CACHE_DIR = None

# 配置对象（在 __main__ 块中初始化）
_CONFIG = None

def ensure_cache_dir() -> str:
    """确保缓存目录存在"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    return CACHE_DIR

@mcp.tool()
async def run_r_findallmarkers(
    seurat_file: Optional[str] = None,
    pval_threshold: float = 0.05
) -> str:
    """运行R FindAllMarkers分析，获取各聚类的标记基因（自动化版本）

    此工具完全自动化处理marker基因分析流程：
    1. 自动从bundle读取Seurat数据文件路径（优先rds_file）
    2. 自动生成输出文件路径，使用session_id命名
    3. 自动更新bundle，保存marker_genes_json路径

    Args:
        seurat_file: Seurat RDS文件路径（可选，不指定则自动从bundle读取）
        output_file: 输出JSON文件路径（可选，已废弃，自动生成）
        pval_threshold: p值阈值，默认0.05

    Returns:
        JSON格式的分析结果
    """
    try:
        ensure_cache_dir()

        # 1. 使用智能fallback自动获取Seurat文件路径
        try:
            from agentype.mainagent.tools.file_paths_tools import auto_get_input_path
            seurat_file = auto_get_input_path(
                manual_path=seurat_file,
                bundle_keys=['rds_file', 'sce_h5', 'h5_file'],
                tool_name='run_r_findallmarkers'
            )
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"自动获取Seurat路径失败: {e}"
            }, ensure_ascii=False, indent=2)

        print(f"🔬 运行FindAllMarkers分析: {seurat_file}")

        # 在调用前生成输出文件路径
        session_id = get_session_id_for_filename()
        results_dir = _CONFIG.get_results_dir()
        actual_output_file = str(results_dir / f'cluster_markers_{session_id}.json')

        # 使用异步执行器调用处理函数，传递 output_file 参数
        # 注意：底层函数现在返回Dict或抛出RuntimeError
        from agentype.dataagent.tools.data_converters import run_r_findallmarkers as original_func

        try:
            result_dict = await asyncio.get_event_loop().run_in_executor(
                None, original_func, seurat_file, pval_threshold, "seurat_clusters", actual_output_file
            )

            # 从Dict中提取marker基因数据
            marker_genes = result_dict.get("marker_genes", {})

        except RuntimeError as e:
            return json.dumps({
                "success": False,
                "error": f"FindAllMarkers分析失败: {str(e)}"
            }, ensure_ascii=False, indent=2)

        # 为MCP传输创建精简版本（每个分簇只返回前10个基因）
        preview_marker_genes = {}
        for cluster, genes in marker_genes.items():
            preview_marker_genes[cluster] = genes[:10] if len(genes) > 10 else genes

        result = {
            "success": True,
            "input_file": seurat_file,
            "output_file": actual_output_file,
            "pval_threshold": pval_threshold,
            "marker_genes_preview": preview_marker_genes,
            "cluster_count": len(marker_genes),
            "total_genes": sum(len(genes) for genes in marker_genes.values()),
            "note": "完整的marker基因数据已保存到文件，这里只显示每个分簇的前10个基因预览"
        }

        # 2. 自动更新bundle，保存marker_genes_json路径
        try:
            from agentype.mainagent.tools.file_paths_tools import auto_update_bundle
            auto_update_bundle('marker_genes_json', actual_output_file)
        except Exception as e:
            print(f"⚠️ 更新bundle失败（不影响主流程）: {e}")

        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"运行FindAllMarkers分析时发生异常: {str(e)}"
        }, ensure_ascii=False, indent=2)

@mcp.tool()
async def run_r_sce_to_h5(
    seurat_file: Optional[str] = None
) -> str:
    """将R SCE对象转换为H5格式（自动化版本）

    此工具完全自动化处理SCE转H5流程：
    1. 自动从bundle读取Seurat数据文件路径（优先rds_file）
    2. 自动生成输出文件路径，使用session_id命名
    3. 自动更新bundle，保存sce_h5路径

    Args:
        seurat_file: Seurat RDS文件路径（可选，不指定则自动从bundle读取）
        output_file: 输出H5文件路径（可选，已废弃，自动生成）

    Returns:
        JSON格式的转换结果
    """
    try:
        ensure_cache_dir()

        # 1. 使用智能fallback自动获取Seurat文件路径
        try:
            from agentype.mainagent.tools.file_paths_tools import auto_get_input_path
            seurat_file = auto_get_input_path(
                manual_path=seurat_file,
                bundle_keys=['rds_file', 'h5_file'],
                tool_name='run_r_sce_to_h5'
            )
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"自动获取Seurat路径失败: {e}"
            }, ensure_ascii=False, indent=2)

        print(f"📁 转换SCE为H5格式: {seurat_file}")

        # 在调用前生成输出文件路径
        session_id = get_session_id_for_filename()
        results_dir = _CONFIG.get_results_dir()
        actual_output_file = str(results_dir / f'sce_{session_id}.h5')

        # 使用异步执行器调用处理函数，传递 output_file 参数
        # 注意：底层函数现在返回Dict或抛出RuntimeError
        from agentype.dataagent.tools.data_converters import run_r_sce_to_h5 as original_func

        try:
            h5_result = await asyncio.get_event_loop().run_in_executor(
                None, original_func, seurat_file, actual_output_file
            )

            # 从Dict中提取数据
            result = {
                "success": h5_result.get("success", True),
                "input_file": h5_result.get("input_file", seurat_file),
                "output_file": h5_result.get("output_file", actual_output_file),
                "file_size": h5_result.get("file_size", 0),
                "message": h5_result.get("message", "转换成功")
            }

            # 2. 自动更新bundle，保存sce_h5路径
            try:
                from agentype.mainagent.tools.file_paths_tools import auto_update_bundle
                auto_update_bundle('sce_h5', actual_output_file)
            except Exception as e:
                print(f"⚠️ 更新bundle失败（不影响主流程）: {e}")

        except RuntimeError as e:
            return json.dumps({
                "success": False,
                "error": f"SCE转H5格式失败: {str(e)}"
            }, ensure_ascii=False, indent=2)

        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"转换SCE为H5格式时发生异常: {str(e)}"
        }, ensure_ascii=False, indent=2)

@mcp.tool()
async def convert_r_markers_csv_to_json(
    csv_file: str,
    pval_threshold: float = 0.05
) -> str:
    """转换R FindAllMarkers CSV结果为JSON格式
    
    Args:
        csv_file: CSV文件路径
        output_file: 输出JSON文件路径（可选）
        pval_threshold: p值阈值，默认0.05
        
    Returns:
        JSON格式的转换结果
    """
    try:
        ensure_cache_dir()

        print(f"🔄 转换CSV为JSON格式: {csv_file}")

        # 在调用前生成输出文件路径
        session_id = get_session_id_for_filename()
        results_dir = _CONFIG.get_results_dir()
        actual_output_file = str(results_dir / f'cluster_marker_genes_{session_id}.json')

        # 使用异步执行器调用处理函数，传递 output_file 参数
        # 注意：底层函数现在返回Dict或抛出RuntimeError
        from agentype.dataagent.tools.data_converters import convert_r_markers_csv_to_json as original_func

        try:
            result_dict = await asyncio.get_event_loop().run_in_executor(
                None, original_func, csv_file, pval_threshold, actual_output_file
            )

            # 从Dict中提取marker基因数据
            marker_genes = result_dict.get("marker_genes", {})

        except RuntimeError as e:
            return json.dumps({
                "success": False,
                "error": f"CSV转JSON失败: {str(e)}"
            }, ensure_ascii=False, indent=2)

        # 为MCP传输创建精简版本（每个分簇只返回前10个基因）
        preview_marker_genes = {}
        for cluster, genes in marker_genes.items():
            preview_marker_genes[cluster] = genes[:10] if len(genes) > 10 else genes

        # 自动更新bundle，保存marker_genes_json路径
        try:
            from agentype.mainagent.tools.file_paths_tools import auto_update_bundle
            auto_update_bundle('marker_genes_json', actual_output_file)
        except Exception as e:
            print(f"⚠️ 更新bundle失败（不影响主流程）: {e}")

        result = {
            "success": True,
            "input_file": csv_file,
            "output_file": actual_output_file,
            "pval_threshold": pval_threshold,
            "marker_genes_preview": preview_marker_genes,
            "cluster_count": len(marker_genes),
            "total_genes": sum(len(genes) for genes in marker_genes.values()),
            "note": "完整的marker基因数据已保存到文件，这里只显示每个分簇的前10个基因预览"
        }

        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"转换CSV为JSON时发生异常: {str(e)}"
        }, ensure_ascii=False, indent=2)

@mcp.tool()
async def easyscfpy_h5_to_json(
    h5_file: Optional[str] = None,
    pval_threshold: float = 0.05
) -> str:
    """将easySCF H5文件转换为JSON格式（自动化版本）

    此工具完全自动化处理H5转JSON流程：
    1. 自动从bundle读取H5数据文件路径
    2. 自动生成输出文件路径，使用session_id命名
    3. 自动更新bundle，保存marker_genes_json路径

    Args:
        h5_file: H5文件路径（可选，不指定则自动从bundle读取）
        output_file: 输出JSON文件路径（可选，已废弃，自动生成）
        pval_threshold: p值阈值，默认0.05

    Returns:
        JSON格式的转换结果
    """
    try:
        ensure_cache_dir()

        # 1. 使用智能fallback自动获取H5文件路径
        try:
            from agentype.mainagent.tools.file_paths_tools import auto_get_input_path
            h5_file = auto_get_input_path(
                manual_path=h5_file,
                bundle_keys=['sce_h5', 'scanpy_h5', 'h5_file'],
                tool_name='easyscfpy_h5_to_json'
            )
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"自动获取H5路径失败: {e}"
            }, ensure_ascii=False, indent=2)

        print(f"🔄 转换easySCF H5为JSON格式: {h5_file}")

        # 在调用前生成输出文件路径
        session_id = get_session_id_for_filename()
        results_dir = _CONFIG.get_results_dir()
        actual_output_file = str(results_dir / f'cluster_marker_genes_{session_id}.json')

        # 使用异步执行器调用处理函数，传递 output_file 参数
        # 注意：底层函数现在返回Dict或抛出RuntimeError
        from agentype.dataagent.tools.data_converters import easyscfpy_h5_to_json as original_func

        try:
            result_dict = await asyncio.get_event_loop().run_in_executor(
                None, original_func, h5_file, pval_threshold, None, actual_output_file
            )

            # 从Dict中提取marker基因数据
            marker_genes = result_dict.get("marker_genes", {})

        except RuntimeError as e:
            return json.dumps({
                "success": False,
                "error": f"easySCF H5转JSON失败: {str(e)}"
            }, ensure_ascii=False, indent=2)

        # 为MCP传输创建精简版本（每个分簇只返回前10个基因）
        preview_marker_genes = {}
        for cluster, genes in marker_genes.items():
            preview_marker_genes[cluster] = genes[:10] if len(genes) > 10 else genes

        result = {
            "success": True,
            "input_file": h5_file,
            "output_file": actual_output_file,
            "pval_threshold": pval_threshold,
            "marker_genes_preview": preview_marker_genes,
            "cluster_count": len(marker_genes),
            "total_genes": sum(len(genes) for genes in marker_genes.values()),
            "note": "完整的marker基因数据已保存到文件，这里只显示每个分簇的前10个基因预览"
        }

        # 2. 自动更新bundle，保存marker_genes_json路径
        try:
            from agentype.mainagent.tools.file_paths_tools import auto_update_bundle
            auto_update_bundle('marker_genes_json', actual_output_file)
        except Exception as e:
            print(f"⚠️ 更新bundle失败（不影响主流程）: {e}")

        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"转换easySCF H5为JSON时发生异常: {str(e)}"
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def scanpy_path_to_json(
    scanpy_path: Optional[str] = None,
    pval_threshold: float = 0.05
) -> str:
    """将scanpy文件路径转换为JSON格式（自动化版本）

    此工具完全自动化处理scanpy转JSON流程：
    1. 自动从bundle读取scanpy数据文件路径（优先h5ad_file，降级h5_file）
    2. 自动生成输出文件路径，使用session_id命名
    3. 自动更新bundle，保存marker_genes_json路径

    Args:
        scanpy_path: scanpy文件路径（可选，不指定则自动从bundle读取）
        output_file: 输出JSON文件路径（可选，已废弃，自动生成）
        pval_threshold: p值阈值，默认0.05

    Returns:
        JSON格式的转换结果
    """
    try:
        ensure_cache_dir()

        # 1. 使用智能fallback自动获取scanpy文件路径
        try:
            from agentype.mainagent.tools.file_paths_tools import auto_get_input_path
            scanpy_path = auto_get_input_path(
                manual_path=scanpy_path,
                bundle_keys=['h5ad_file', 'scanpy_h5', 'sce_h5', 'h5_file'],
                tool_name='scanpy_path_to_json'
            )
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"自动获取scanpy路径失败: {e}"
            }, ensure_ascii=False, indent=2)

        print(f"🔬 转换scanpy文件为JSON格式: {scanpy_path}")

        # 在调用前生成输出文件路径
        session_id = get_session_id_for_filename()
        results_dir = _CONFIG.get_results_dir()
        actual_output_file = str(results_dir / f'cluster_marker_genes_{session_id}.json')

        # 使用异步执行器调用处理函数，传递 output_file 参数
        # 注意：底层函数现在返回Dict或抛出RuntimeError
        from agentype.dataagent.tools.data_converters import scanpy_path_to_json as original_func

        try:
            result_dict = await asyncio.get_event_loop().run_in_executor(
                None, original_func, scanpy_path, pval_threshold, None, actual_output_file
            )

            # 从Dict中提取marker基因数据
            marker_genes = result_dict.get("marker_genes", {})

        except RuntimeError as e:
            return json.dumps({
                "success": False,
                "error": f"scanpy文件转JSON失败: {str(e)}"
            }, ensure_ascii=False, indent=2)

        # 为MCP传输创建精简版本（每个分簇只返回前10个基因）
        preview_marker_genes = {}
        for cluster, genes in marker_genes.items():
            preview_marker_genes[cluster] = genes[:10] if len(genes) > 10 else genes

        result = {
            "success": True,
            "input_file": scanpy_path,
            "output_file": actual_output_file,
            "pval_threshold": pval_threshold,
            "marker_genes_preview": preview_marker_genes,
            "cluster_count": len(marker_genes),
            "total_genes": sum(len(genes) for genes in marker_genes.values()),
            "note": "完整的marker基因数据已保存到文件，这里只显示每个分簇的前10个基因预览"
        }

        # 2. 自动更新bundle，保存marker_genes_json路径
        try:
            from agentype.mainagent.tools.file_paths_tools import auto_update_bundle
            auto_update_bundle('marker_genes_json', actual_output_file)
        except Exception as e:
            print(f"⚠️ 更新bundle失败（不影响主流程）: {e}")

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"转换scanpy文件为JSON时发生异常: {str(e)}"
        }, ensure_ascii=False, indent=2)

@mcp.tool()
async def convert_scanpy_file_to_h5(
    input_file: Optional[str] = None
) -> str:
    """将scanpy数据文件转换为easySCF H5格式（自动化版本）

    此工具完全自动化处理scanpy转H5流程：
    1. 自动从bundle读取scanpy数据文件路径（优先h5ad_file，降级h5_file）
    2. 自动生成输出文件路径，使用session_id命名
    3. 自动更新bundle，保存scanpy_h5路径

    Args:
        input_file: 输入数据文件路径（可选，不指定则自动从bundle读取）
        h5_file: 输出H5文件路径（可选，已废弃，自动生成）

    Returns:
        JSON格式的转换结果
    """
    try:
        ensure_cache_dir()

        # 1. 使用智能fallback自动获取输入文件路径
        try:
            from agentype.mainagent.tools.file_paths_tools import auto_get_input_path
            input_file = auto_get_input_path(
                manual_path=input_file,
                bundle_keys=['h5ad_file', 'h5_file'],
                tool_name='convert_scanpy_file_to_h5'
            )
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"自动获取输入文件路径失败: {e}"
            }, ensure_ascii=False, indent=2)

        print(f"🔄 转换scanpy文件为H5格式: {input_file}")

        # 在调用前生成输出文件路径
        session_id = get_session_id_for_filename()
        results_dir = _CONFIG.get_results_dir()
        actual_output_file = str(results_dir / f'data_{session_id}.h5')

        # 使用异步执行器调用处理函数，传递 output_file 参数
        # 注意：底层函数现在返回Dict或抛出RuntimeError
        from agentype.dataagent.tools.data_converters import convert_scanpy_file_to_h5 as original_func

        try:
            result_dict = await asyncio.get_event_loop().run_in_executor(
                None, original_func, input_file, actual_output_file
            )

            # 从Dict中提取数据
            file_size = result_dict.get("file_size", 0)
            message = result_dict.get("message", "转换成功")

            result = {
                "success": True,
                "message": message,
                "input_file": input_file,
                "output_file": actual_output_file,
                "file_size": f"{file_size / 1024 / 1024:.1f} MB" if file_size > 1024*1024 else f"{file_size / 1024:.1f} KB" if file_size > 1024 else f"{file_size} bytes"
            }

        except RuntimeError as e:
            return json.dumps({
                "success": False,
                "error": f"scanpy文件转H5失败: {str(e)}"
            }, ensure_ascii=False, indent=2)

        # 2. 自动更新bundle，保存scanpy_h5路径
        try:
            from agentype.mainagent.tools.file_paths_tools import auto_update_bundle
            auto_update_bundle('scanpy_h5', actual_output_file)
        except Exception as e:
            print(f"⚠️ 更新bundle失败（不影响主流程）: {e}")

        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"转换scanpy文件为H5时发生异常: {str(e)}"
        }, ensure_ascii=False, indent=2)

@mcp.tool()
async def validate_json_only(marker_genes_json: str) -> str:
    """专门验证JSON文件格式和内容

    Args:
        marker_genes_json: Marker基因JSON文件路径

    Returns:
        JSON格式的验证结果
    """
    try:
        if not os.path.exists(marker_genes_json):
            return json.dumps({
                "success": False,
                "error": f"JSON文件不存在: {marker_genes_json}",
                "valid": False
            }, ensure_ascii=False, indent=2)

        file_path_obj = Path(marker_genes_json)

        # 检查文件扩展名
        if file_path_obj.suffix.lower() != '.json':
            return json.dumps({
                "success": False,
                "error": f"文件不是JSON格式: {marker_genes_json}",
                "valid": False,
                "file_extension": file_path_obj.suffix
            }, ensure_ascii=False, indent=2)

        # 读取并验证JSON内容
        try:
            with open(marker_genes_json, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
        except json.JSONDecodeError as e:
            return json.dumps({
                "success": False,
                "error": f"JSON格式错误: {str(e)}",
                "valid": False,
                "json_decode_error": str(e)
            }, ensure_ascii=False, indent=2)
        
        file_size = file_path_obj.stat().st_size
        
        # 分析JSON内容结构
        content_info = {
            "data_type": type(json_data).__name__,
            "size_bytes": file_size,
            "size_readable": f"{file_size / 1024:.1f} KB" if file_size > 1024 else f"{file_size} bytes"
        }
        
        # 如果是字典，分析键值
        if isinstance(json_data, dict):
            content_info.update({
                "keys": list(json_data.keys()),
                "key_count": len(json_data.keys()),
                "is_marker_genes": "cluster" in str(json_data).lower() or "gene" in str(json_data).lower()
            })
        # 如果是列表，分析元素
        elif isinstance(json_data, list):
            content_info.update({
                "list_length": len(json_data),
                "first_element_type": type(json_data[0]).__name__ if json_data else "empty",
                "is_marker_genes": len(json_data) > 0 and any("gene" in str(item).lower() for item in json_data[:3])
            })
        
        # 特殊检查：是否是marker基因文件
        marker_gene_indicators = [
            "cluster", "gene", "marker", "p_val", "avg_log", "pct"
        ]
        content_str = str(json_data).lower()
        marker_score = sum(1 for indicator in marker_gene_indicators if indicator in content_str)
        
        # 额外检查：如果有cluster键，很可能是marker基因
        cluster_pattern = any("cluster" in str(k).lower() for k in (json_data.keys() if isinstance(json_data, dict) else []))
        content_info["likely_marker_genes"] = marker_score >= 2 or cluster_pattern
        
        result = {
            "success": True,
            "valid": True,
            "file_path": str(file_path_obj),
            "file_name": file_path_obj.name,
            "json_validation": "passed",
            "content_analysis": content_info,
            "processing_recommendation": "ready_for_use" if content_info.get("likely_marker_genes", False) else "general_json"
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"JSON验证过程中发生异常: {str(e)}",
            "valid": False
        }, ensure_ascii=False, indent=2)

@mcp.tool()
async def validate_file_type(file_path: str) -> str:
    """识别和验证文件类型
    
    Args:
        file_path: 文件路径
        
    Returns:
        JSON格式的文件类型信息
    """
    try:
        # 使用当前会话的session_id保持一致性
        current_timestamp = get_session_id_for_filename()
        print(f"🕒 使用当前会话session_id: {current_timestamp}")
        
        if not os.path.exists(file_path):
            return json.dumps({
                "success": False,
                "error": f"文件不存在: {file_path}",
                "file_type": "unknown",
                "timestamp": current_timestamp
            }, ensure_ascii=False, indent=2)
        
        file_path_obj = Path(file_path)
        file_size = file_path_obj.stat().st_size
        file_extension = file_path_obj.suffix.lower()
        
        # 基于扩展名判断文件类型
        file_type_map = {
            '.rds': 'rds',
            '.h5': 'h5',
            '.h5ad': 'h5ad',
            '.csv': 'csv',
            '.json': 'json'
        }
        
        file_type = file_type_map.get(file_extension, 'unknown')
        
        result = {
            "success": True,
            "file_path": str(file_path_obj),
            "file_name": file_path_obj.name,
            "file_size": file_size,
            "file_extension": file_extension,
            "file_type": file_type,
            "valid": file_type != 'unknown',
            "timestamp": current_timestamp
        }
        
        # 对JSON文件进行额外验证和深度分析
        if file_type == 'json':
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                result["json_valid"] = True
                result["json_keys"] = list(json_data.keys()) if isinstance(json_data, dict) else None

                # 深度分析：检测是否为 marker 基因文件
                marker_gene_indicators = [
                    "cluster", "gene", "marker", "p_val", "avg_log", "pct"
                ]
                content_str = str(json_data).lower()
                marker_score = sum(1 for indicator in marker_gene_indicators if indicator in content_str)

                # 额外检查：如果有 cluster 键，很可能是 marker 基因
                cluster_pattern = any("cluster" in str(k).lower() for k in (json_data.keys() if isinstance(json_data, dict) else []))
                result["is_marker_genes"] = marker_score >= 2 or cluster_pattern
                result["marker_confidence"] = "high" if marker_score >= 3 or cluster_pattern else "medium" if marker_score >= 2 else "low"

            except json.JSONDecodeError as e:
                result["json_valid"] = False
                result["json_error"] = str(e)
                result["is_marker_genes"] = False

        # 对CSV文件进行内容分析
        if file_type == 'csv':
            try:
                import csv
                with open(file_path, 'r', encoding='utf-8') as f:
                    # 读取前几行来检测列名
                    reader = csv.reader(f)
                    header = next(reader, None)

                    if header:
                        # 转换为小写便于比较
                        header_lower = [col.lower() for col in header]

                        # FindAllMarkers 常见列名
                        marker_columns = ['cluster', 'gene', 'p_val', 'avg_log', 'pct.1', 'pct.2', 'p_val_adj']

                        # 检测匹配的列数
                        matches = sum(1 for col in marker_columns if any(col in h for h in header_lower))

                        result["csv_columns"] = header
                        result["csv_column_count"] = len(header)
                        result["is_marker_csv"] = matches >= 3  # 至少匹配3个特征列
                        result["marker_column_matches"] = matches
                        result["marker_confidence"] = "high" if matches >= 5 else "medium" if matches >= 3 else "low"
                    else:
                        result["csv_columns"] = []
                        result["is_marker_csv"] = False
                        result["csv_error"] = "CSV文件为空或无法读取头部"

            except Exception as e:
                result["csv_error"] = f"CSV分析失败: {str(e)}"
                result["is_marker_csv"] = False

        # 自动更新 Bundle
        try:
            from agentype.mainagent.tools.file_paths_tools import auto_update_bundle

            # 文件类型到 bundle 字段的映射
            file_type_to_bundle_key = {
                'rds': 'rds_file',
                'h5': 'h5_file',
                'h5ad': 'h5ad_file',
                'csv': 'marker_genes_csv',
                'json': 'marker_genes_json'
            }

            bundle_key = None
            should_update = False

            # 根据文件类型和内容分析决定是否更新
            if file_type == 'json':
                # JSON 需要内容分析，只有 marker 基因 JSON 才更新
                if result.get('is_marker_genes', False):
                    bundle_key = 'marker_genes_json'
                    should_update = True
            elif file_type == 'csv':
                # CSV 需要内容分析，只有 marker 基因 CSV 才更新
                if result.get('is_marker_csv', False):
                    bundle_key = 'marker_genes_csv'
                    should_update = True
            elif file_type in ['rds', 'h5', 'h5ad']:
                # 原始数据文件直接更新
                bundle_key = file_type_to_bundle_key[file_type]
                should_update = True

            # 执行更新
            if should_update and bundle_key:
                auto_update_bundle(bundle_key, str(file_path_obj))
                result['bundle_updated'] = True
                result['bundle_key'] = bundle_key
                result['bundle_update_message'] = f'✅ 已自动更新到 bundle.{bundle_key}'
                print(f"✅ 已将文件自动保存到 bundle.{bundle_key}: {file_path_obj}")
            else:
                result['bundle_updated'] = False
                result['bundle_update_message'] = '未更新 bundle（文件类型不匹配或内容分析未通过）'

        except Exception as e:
            print(f"⚠️ 更新bundle失败（不影响主流程）: {e}")
            result['bundle_updated'] = False
            result['bundle_error'] = str(e)

        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"文件类型验证失败: {str(e)}",
            "file_type": "unknown",
            "timestamp": get_session_id_for_filename()
        }, ensure_ascii=False, indent=2)

@mcp.tool()
async def get_token_stats() -> str:
    """获取DataAgent的token消耗统计信息

    Returns:
        str: JSON格式的token统计信息
    """
    try:
        # 由于MCP服务器是独立进程，这里返回默认的空统计
        # 实际的token统计需要通过agent实例获取
        from agentype.common.token_statistics import TokenStatistics

        # 创建一个空的统计对象作为占位符
        # 实际应该通过某种IPC机制或共享存储获取真实数据
        stats = TokenStatistics(agent_name="DataAgent")

        return json.dumps({
            "success": True,
            "data": stats.to_dict(),
            "message": "DataAgent token统计 (MCP服务器独立进程)"
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
    marker_genes_json: Optional[str] = None
) -> str:
    """保存数据文件路径到cache目录

    此工具用于在数据处理完成后保存所有关键文件路径，以便后续步骤使用。

    Args:
        rds_file: RDS文件路径
        h5ad_file: H5AD文件路径
        h5_file: H5文件路径（easySCF格式）
        marker_genes_json: Marker基因JSON文件路径

    Returns:
        JSON格式的保存结果，包含成功状态、session_id、保存路径等信息

    使用场景：
        - 在完成数据处理后立即调用，保存生成的文件路径
        - 确保路径格式正确（特别注意中文路径的分隔符）
        - 如果保存失败，检查错误信息并修正路径后重试
    """
    try:
        # marker_genes_json 是 DataAgent 的必需输出
        if not marker_genes_json or marker_genes_json.strip() == "":
            return json.dumps({
                "success": False,
                "error": "❌ marker_genes_json 是必需的！DataAgent 必须生成 marker 基因 JSON 文件。",
                "action_required": "请使用以下方法之一生成 JSON 文件：",
                "available_methods": [
                    "1. run_r_findallmarkers - 对 RDS/Seurat 对象进行标记基因分析",
                    "2. easyscfpy_h5_to_json - 从 easySCF H5 文件提取",
                    "3. scanpy_path_to_json - 从 scanpy/AnnData 文件转换",
                    "4. convert_r_markers_csv_to_json - 从 FindAllMarkers CSV 结果转换"
                ]
            }, ensure_ascii=False, indent=2)

        # 构建 metadata（自动添加 DataAgent 标记）
        metadata_dict = {
            "agent": "DataAgent",
            "stage": "data_processing"
        }

        # 调用核心函数（session_id 由底层函数自动获取，使用默认过期时间）
        result = _save_file_paths_bundle(
            rds_file=rds_file,
            h5ad_file=h5ad_file,
            h5_file=h5_file,
            marker_genes_json=marker_genes_json,
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

    此工具用于加载之前保存的文件路径信息。

    Returns:
        JSON格式的路径信息，包含 rds_file, h5ad_file, h5_file, marker_genes_json 等

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
    启动 DataAgent MCP 服务器

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
    parser = argparse.ArgumentParser(description='CellType DataAgent MCP Server')
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
        print("   DataAgent MCP Server 需要 API Key 才能运行", file=sys.stderr)
        sys.exit(1)

    # 3. 验证必需的命令行参数
    if not args.api_base:
        print("❌ 错误: 缺少必需参数 --api-base", file=sys.stderr)
        sys.exit(1)

    # 4. 创建输出目录
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # 4.5. 创建ConfigManager并设置为模块级配置对象
    from agentype.dataagent.config.settings import ConfigManager

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

    print(f"✅ DataAgent ConfigManager 已初始化:", file=sys.stderr)
    print(f"   Output Dir: {_CONFIG.output_dir}", file=sys.stderr)
    print(f"   Results Dir: {_CONFIG.results_dir}", file=sys.stderr)
    print(f"   Cache Dir: {_CONFIG.cache_dir}", file=sys.stderr)

    # 初始化缓存（使用 ConfigManager）
    from agentype.dataagent.config.cache_config import init_cache
    cache_dir = init_cache(config=_CONFIG)

    # 设置工具模块的全局配置（用于 file_paths_tools）
    from agentype.mainagent.tools.file_paths_tools import set_global_config
    set_global_config(_CONFIG)

    # 5. 设置 session_id
    if args.session_id:
        set_session_id(args.session_id)
        print(f"✅ DataAgent MCP Server 使用 session_id: {args.session_id}", file=sys.stderr)

    # 6. 打印配置信息
    print(f"✅ DataAgent MCP Server 配置:", file=sys.stderr)
    print(f"   API Base: {args.api_base}", file=sys.stderr)
    print(f"   Model: {args.model}", file=sys.stderr)

    # 启动MCP服务器 (标准stdio传输)
    print("🚀 启动CellType DataProcessor MCP服务器...")
    print("📋 协议: Model Context Protocol (MCP)")
    print("🔧 可用工具: 12个")
    print("📊 核心工具:")
    print("  1️⃣  run_r_findallmarkers - R FindAllMarkers分析")
    print("  2️⃣  run_r_sce_to_h5 - SCE转H5格式")
    print("  3️⃣  convert_r_markers_csv_to_json - CSV转JSON")
    print("  4️⃣  easyscfpy_h5_to_json - easySCF H5转JSON")
    print("  5️⃣  scanpy_to_json - scanpy对象转JSON")
    print("  6️⃣  scanpy_path_to_json - scanpy文件转JSON")
    print("  7️⃣  convert_scanpy_file_to_h5 - scanpy文件转H5格式")
    print("  8️⃣  validate_file_type - 文件类型验证")
    print("  9️⃣  validate_json_only - JSON文件专门验证")
    print("  🔟  get_token_stats - 获取token统计信息")
    print("  1️⃣1️⃣ save_file_paths_bundle - 保存文件路径到cache")
    print("  1️⃣2️⃣ load_file_paths_bundle - 从cache加载文件路径")
    print("=" * 60)
    mcp.run(transport='stdio')