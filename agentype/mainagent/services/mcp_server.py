#!/usr/bin/env python3
"""
agentype - MainAgent MCP Server
Author: cuilei
Version: 1.0
"""

from __future__ import annotations

import os
import json
import asyncio
from pathlib import Path
from typing import Any, Dict, Optional, Union

# 导入项目模块
import sys

# 依赖导入
try:
    from mcp.server.fastmcp import FastMCP
except Exception as e:
    print(f"导入FastMCP失败: {e}\n请先安装依赖：pip install mcp")
    sys.exit(1)

# 本项目内部依赖
from agentype.mainagent.config.settings import ConfigManager
from agentype.mainagent.config.cache_config import CacheManager, init_cache
from agentype.prompts import get_prompt_manager

# 国际化占位（与DataAgent风格保持一致）
try:
    from agentype.mainagent.utils.i18n import _  # 若存在 _(key, **kwargs)
except Exception:
    def _(key: str, **kwargs):
        return key.format(**kwargs) if kwargs else key

# 导入工具函数
from agentype.mainagent.tools.subagent_tools import process_data, run_annotation_pipeline, analyze_gene_list
from agentype.mainagent.tools.file_paths_tools import (
    save_file_paths_bundle as _save_file_paths_bundle,
    load_file_paths_bundle as _load_file_paths_bundle,
    load_and_validate_bundle as _load_and_validate_bundle,
    list_saved_bundles as _list_saved_bundles,
    delete_bundle as _delete_bundle
)

# 导入会话配置
from agentype.mainagent.config.session_config import (
    create_session_id,
    set_session_id,
    get_session_id,
    get_session_info
)

# 为避免启动时硬依赖不可用模块，改为在对应工具内惰性导入。
# 如模块缺失，工具将返回结构化的错误信息，而不影响服务器启动。


# ========== 全局对象 ==========
mcp = FastMCP("celltype-main-agent", log_level="INFO")

# 配置对象（在 __main__ 块中初始化）
_CONFIG = None

# ========== 会话管理 ==========
# 🌟 会话ID将在 __main__ 块中设置（通过命令行参数或自动生成）
SESSION_ID = None  # 将在启动时初始化

# ========== 注意 ==========
# MainAgent MCP Server 的配置通过命令行参数传递
# 配置由 MCPClient 在启动时通过混合方案传递：
#   - 敏感信息（API Key）→ 环境变量 OPENAI_API_KEY
#   - 非敏感配置 → 命令行参数 (--api-base, --model, --output-dir, etc.)
# 配置的验证和初始化在 if __name__ == "__main__": 块中完成

# 全局配置对象（将在 __main__ 块中初始化）
config = None

# 缓存管理器（将在 __main__ 块中初始化，使用 ConfigManager 提供的路径）
cache_manager = None

# 缓存目录（将在 __main__ 块中设置）
CACHE_DIR = None

def ensure_cache_dir() -> str:
    """确保缓存目录存在"""
    if CACHE_DIR is None:
        raise RuntimeError(
            "缓存目录未初始化。请确保在 __main__ 块中正确初始化了 cache_manager"
        )
    os.makedirs(CACHE_DIR, exist_ok=True)
    return CACHE_DIR

def _ensure_abs(path: Optional[str]) -> Optional[str]:
    return str(Path(path).resolve()) if path else None



# ========== 数据预处理 ==========
@mcp.tool()
async def enhanced_data_processing(input_data: str, species: Optional[str] = None) -> str:
    """根据输入数据类型自动选择 DataAgent 的合适工具完成预处理与标准输出。

    支持 .rds / .h5ad / .h5 / .csv / .json

    Args:
        input_data: 输入数据路径
        species: 可选的物种参数 (如 "Human", "Mouse")，如果不提供则自动检测
    """
    try:
        ensure_cache_dir()
        abs_input = _ensure_abs(input_data)
        if not abs_input:
            return json.dumps({"success": False, "error": "缺少必要的输入数据参数"}, ensure_ascii=False, indent=2)

        # 直接调用子Agent封装函数，传递species参数
        result = process_data(abs_input, species=species, config=_CONFIG)

        # ✅ 验证marker_genes_json是否成功生成
        output_paths = result.get("output_file_paths", {})
        marker_json = output_paths.get("marker_genes_json")

        if not marker_json:
            # marker_genes_json未在返回结果中
            return json.dumps({
                "success": False,
                "error": "数据预处理完成，但marker基因JSON文件未生成。请重新运行 enhanced_data_processing 进行重试。",
                "retry_hint": "建议使用相同参数重新调用此工具",
                "final_result": result.get("final_result"),
                "output_file_paths": output_paths
            }, ensure_ascii=False, indent=2)

        # 验证文件是否实际存在
        if not os.path.exists(marker_json):
            return json.dumps({
                "success": False,
                "error": f"marker基因JSON路径已返回但文件不存在: {marker_json}。请重新运行 enhanced_data_processing 进行重试。",
                "retry_hint": "建议使用相同参数重新调用此工具",
                "final_result": result.get("final_result"),
                "output_file_paths": output_paths
            }, ensure_ascii=False, indent=2)

        # ✅ 验证通过，返回成功结果
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({"success": False, "error": f"数据预处理异常: {e}"}, ensure_ascii=False, indent=2)


# ========== 细胞注释 ==========
@mcp.tool()
async def enhanced_cell_annotation(
    rds_path: Optional[str] = None,
    h5ad_path: Optional[str] = None,
    h5_path: Optional[str] = None,
    marker_json_path: Optional[str] = None,
    tissue_description: Optional[str] = None,
    species: Optional[str] = None,
    cluster_column: Optional[str] = None,
) -> str:
    """调用 AppAgent 的多种注释工具（SingleR / scType / CellTypist）。

    目标：尽量根据可用输入运行更多方法，返回汇总结构。
    """
    try:
        ensure_cache_dir()
        result = run_annotation_pipeline(
            rds_path=_ensure_abs(rds_path) if rds_path else None,
            h5ad_path=_ensure_abs(h5ad_path) if h5ad_path else None,
            tissue_description=tissue_description,
            marker_json_path=_ensure_abs(marker_json_path) if marker_json_path else None,
            species=species,
            h5_path=_ensure_abs(h5_path) if h5_path else None,
            cluster_column=cluster_column,
            config=_CONFIG,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({"success": False, "error": f"细胞注释异常: {e}"}, ensure_ascii=False, indent=2)


# ========== 基因分析 ==========
@mcp.tool()
async def enhanced_gene_analysis(
    gene_list: str,
    tissue_type: Optional[str] = None,
    species: str = "HUMAN"
) -> str:
    """调用 Subagent 的基因相关工具（基因信息、CellMarker/PanglaoDB富集、GO/KEGG）。

    🔄 自动路径echo机制：
    在第四阶段循环处理cluster时，此函数会自动从最新保存的路径包中读取路径信息：
    - marker_genes_json: 用于 extract_cluster_genes 提取基因
    - singler_result, sctype_result, celltypist_result: 用于 read_cluster_results 读取注释

    这些路径会在返回值的 remember_paths 中自动echo回来，防止长循环（30+次）中路径丢失。
    无需手动传递路径参数，函数内部会自动加载！

    Args:
        gene_list: 基因列表（逗号分隔， 建议50个）
        tissue_type: 组织类型
        species: 物种，默认HUMAN
    """
    try:
        ensure_cache_dir()
        # 注意：species 参数目前在 analyze_gene_list 中未使用，但保留以便兼容
        if not gene_list:
            return json.dumps({"success": False, "error": "缺少基因列表参数"}, ensure_ascii=False, indent=2)

        # 导入 analyze_gene_list_via_subagent（自动从路径包读取路径）
        from agentype.mainagent.tools.subagent_tools import analyze_gene_list_via_subagent

        result = analyze_gene_list_via_subagent(
            gene_list=gene_list,
            tissue_type=tissue_type,
            config=_CONFIG
        )

        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": f"基因分析异常: {e}"}, ensure_ascii=False, indent=2)


# ========== 簇级结果读写 ==========
@mcp.tool()
async def read_cluster_results(
    cluster: str,
    singler_result: Optional[str] = None,
    sctype_result: Optional[str] = None,
    celltypist_result: Optional[str] = None
) -> str:
    """从常用方法的结果 JSON 中读取指定簇的合并结果。

    Args:
        cluster: 簇ID，例如 "cluster0" 或 "0"
        singler_result: SingleR 结果 JSON 路径（可选，默认自动读取当前 session 的结果文件）
        sctype_result: scType 结果 JSON 路径（可选，默认自动读取当前 session 的结果文件）
        celltypist_result: CellTypist 结果 JSON 路径（可选，默认自动读取当前 session 的结果文件）

    Returns:
        包含各方法结果的合并字典的 JSON 字符串
    """
    try:
        try:
            from agentype.mainagent.tools.cluster_tools import read_cluster_results as _read_cluster_results  # type: ignore
        except Exception as e:
            return json.dumps({"success": False, "error": f"依赖缺失: cluster_tools.read_cluster_results: {e}"}, ensure_ascii=False, indent=2)

        # 直接传递参数，让底层函数处理 None 值和自动加载
        out = _read_cluster_results(
            cluster=cluster,
            singler_result=_ensure_abs(singler_result) if singler_result else None,
            sctype_result=_ensure_abs(sctype_result) if sctype_result else None,
            celltypist_result=_ensure_abs(celltypist_result) if celltypist_result else None
        )
        return json.dumps(out, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": f"读取簇结果异常: {e}"}, ensure_ascii=False, indent=2)


@mcp.tool()
async def save_cluster_type(cluster_id: str, cell_type: str) -> str:
    """保存单个簇的注释类型，并自动检测完成度。

    保存后会自动检测所有簇的完成情况，返回包含完成度信息的详细结果。
    """
    try:
        try:
            from agentype.mainagent.tools.cluster_tools import save_cluster_type as _save_cluster_type  # type: ignore
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"依赖缺失: cluster_tools.save_cluster_type: {e}",
                "cluster_id": cluster_id,
                "error_type": "ImportError"
            }, ensure_ascii=False, indent=2)

        # 调用底层函数保存（自动检测完成度）
        result = _save_cluster_type(cluster_id, cell_type)

        # 直接返回包含完成度信息的结果
        return json.dumps(result, ensure_ascii=False, indent=2)

    except IOError as e:
        # 文件IO错误(写入失败、验证失败等)
        return json.dumps({
            "success": False,
            "error": str(e),
            "cluster_id": cluster_id,
            "cell_type": cell_type,
            "error_type": "IOError",
            "message": "文件保存或验证失败,请检查磁盘空间和权限"
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        # 其他未预期的错误
        return json.dumps({
            "success": False,
            "error": f"保存异常: {e}",
            "cluster_id": cluster_id,
            "cell_type": cell_type,
            "error_type": type(e).__name__
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def load_cluster_types() -> str:
    """读取所有已保存的簇→类型映射。"""
    try:
        try:
            from agentype.mainagent.tools.cluster_tools import load_cluster_types as _load_cluster_types  # type: ignore
        except Exception as e:
            return json.dumps({"success": False, "error": f"依赖缺失: cluster_tools.load_cluster_types: {e}"}, ensure_ascii=False, indent=2)

        mapping = _load_cluster_types()
        return json.dumps({"success": True, "mapping": mapping}, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": f"读取异常: {e}"}, ensure_ascii=False, indent=2)


# @mcp.tool()
# async def unify_cell_type_names(cluster_mapping_data: Union[str, Dict], output_json_path: str) -> str:
#     """将细胞类型映射保存为JSON文件。

#     Args:
#         cluster_mapping_data: 映射数据，可以是JSON字符串或字典
#         output_json_path: 输出json文件路径

#     Returns:
#         包含成功状态的JSON字符串，失败时包含错误信息
#     """
#     try:
#         try:
#             from agentype.mainagent.tools.cluster_tools import unify_cell_type_names as _unify_cell_type_names  # type: ignore
#         except Exception as e:
#             return json.dumps({"success": False, "error": f"依赖缺失: cluster_tools.unify_cell_type_names: {e}"}, ensure_ascii=False, indent=2)

#         abs_output_path = _ensure_abs(output_json_path)
#         if not abs_output_path:
#             return json.dumps({"success": False, "error": "无效的输出文件路径"}, ensure_ascii=False, indent=2)

#         # 处理cluster_mapping_data参数 - 支持字典和字符串格式
#         if isinstance(cluster_mapping_data, dict):
#             # 如果传入的是字典，转换为JSON字符串
#             json_string = json.dumps(cluster_mapping_data, ensure_ascii=False)
#         elif isinstance(cluster_mapping_data, str):
#             # 如果传入的是字符串，直接使用
#             json_string = cluster_mapping_data
#         else:
#             return json.dumps({"success": False, "error": f"不支持的cluster_mapping_data类型: {type(cluster_mapping_data)}"}, ensure_ascii=False, indent=2)

#         result = _unify_cell_type_names(json_string, abs_output_path)
#         return json.dumps(result, ensure_ascii=False, indent=2)
#     except Exception as e:
#         return json.dumps({"success": False, "error": f"统一化处理异常: {e}"}, ensure_ascii=False, indent=2)


# ========== 基因提取工具 ==========
@mcp.tool()
async def get_all_cluster_ids(marker_genes_json_path: Optional[str] = None) -> str:
    """获取 JSON 文件中所有簇的编号。

    Args:
        marker_genes_json_path: 包含簇基因信息的 JSON 文件路径（可选，默认自动读取当前 session 的 marker genes 文件）

    Returns:
        包含所有簇编号列表的 JSON 字符串
    """
    try:
        from agentype.mainagent.tools.cluster_tools import get_all_cluster_ids as _get_all_cluster_ids

        # 直接传递参数，让底层函数处理 None 值和自动加载
        abs_path = _ensure_abs(marker_genes_json_path) if marker_genes_json_path else None
        cluster_ids = _get_all_cluster_ids(marker_genes_json_path=abs_path)

        return json.dumps({
            "success": True,
            "cluster_ids": cluster_ids,
            "total_clusters": len(cluster_ids)
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": f"获取簇编号异常: {e}"}, ensure_ascii=False, indent=2)


@mcp.tool()
async def extract_cluster_genes(cluster_name: str, gene_count: int = 50, marker_genes_json_path: Optional[str] = None) -> str:
    """从 JSON 文件中提取指定簇的基因。

    Args:
        cluster_name: 簇名称（支持 "cluster0", "0" 等格式）
        gene_count: 要提取的基因数量，默认50
        marker_genes_json_path: 包含簇基因信息的 JSON 文件路径（可选，默认自动读取当前 session 的 marker genes 文件）

    Returns:
        包含基因列表的 JSON 字符串
    """
    try:
        from agentype.mainagent.tools.cluster_tools import extract_cluster_genes as _extract_cluster_genes

        # 参数验证
        if gene_count <= 0:
            return json.dumps({"success": False, "error": "基因数量必须大于 0"}, ensure_ascii=False, indent=2)

        # 直接传递参数，让底层函数处理 None 值和自动加载
        abs_path = _ensure_abs(marker_genes_json_path) if marker_genes_json_path else None
        result = _extract_cluster_genes(
            cluster_name=cluster_name,
            gene_count=gene_count,
            marker_genes_json_path=abs_path
        )

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({"success": False, "error": f"提取基因异常: {e}"}, ensure_ascii=False, indent=2)


# ========== 写回 Seurat/AnnData ==========
@mcp.tool()
async def map_cluster_types_to_seurat(
    cluster_col: str = "seurat_clusters",
    output_col: str = "agentype"
) -> str:
    """将簇注释映射写回Seurat对象（RDS/H5格式），自动从缓存读取所有必要信息。

    此工具完全自动化处理簇注释写回流程：
    1. 自动从缓存读取已保存的簇类型映射（无需手动传入JSON）
    2. 自动从路径包读取输入数据文件路径（优先rds_file，降级到h5_file）
    3. 自动生成输出文件路径，使用session_id命名（annotated_seurat_{session_id}.rds）

    Args:
        cluster_col: Seurat对象中的簇列名，默认"seurat_clusters"
        output_col: 写入的细胞类型列名，默认"agentype"

    Returns:
        JSON格式的写回结果，包含输出文件路径和摘要信息
    """
    try:
        ensure_cache_dir()

        # 1. 加载已保存的簇映射
        try:
            from agentype.mainagent.tools.cluster_tools import load_cluster_types as _load_cluster_types  # type: ignore
            from agentype.mainagent.tools.cluster_tools import check_cluster_completion
        except Exception as e:
            return json.dumps({"success": False, "error": f"依赖缺失: {e}"}, ensure_ascii=False, indent=2)

        mapping = _load_cluster_types()

        if not mapping:
            return json.dumps({
                "success": False,
                "error": "未找到已保存的簇映射，请先完成簇注释并使用save_cluster_type保存所有簇的注释结果"
            }, ensure_ascii=False, indent=2)

        # 2. 检查所有簇是否已完成注释（参考 save_cluster_type 的 reminder 机制）
        try:
            completion_status = check_cluster_completion()
            manager = get_prompt_manager()

            # 生成 reminder（与 save_cluster_type 风格一致）
            if completion_status.get("all_completed"):
                reminder_template = manager.get_agent_specific_prompt('mainagent', 'CLUSTER_PROGRESS_COMPLETE_MESSAGE')
                next_action = manager.get_agent_specific_prompt('mainagent', 'CLUSTER_PROGRESS_ACTION_WRITEBACK_SEURAT')
                reminder = reminder_template.format(
                    total_clusters=completion_status['total_clusters'],
                    next_action=next_action
                )
                print(f"📊 {reminder}")
            else:
                # 未完成的情况：返回错误，阻止写回
                completed = completion_status["completed_clusters"]
                total = completion_status["total_clusters"]
                incomplete = completion_status["incomplete_clusters"]
                incomplete_preview = ", ".join(incomplete[:5])
                if len(incomplete) > 5:
                    incomplete_preview += f" 等共{len(incomplete)}个"

                reminder_template = manager.get_agent_specific_prompt('mainagent', 'CLUSTER_PROGRESS_INCOMPLETE_MESSAGE')
                next_action = manager.get_agent_specific_prompt('mainagent', 'CLUSTER_PROGRESS_ACTION_BLOCKER')
                reminder = reminder_template.format(
                    completed=completed,
                    total=total,
                    completion_rate=completion_status["completion_rate"],
                    incomplete_preview=incomplete_preview,
                    next_action=next_action
                )

                return json.dumps({
                    "success": False,
                    "error": "簇注释未完成，不能执行写回操作",
                    "completion_status": completion_status,
                    "reminder": reminder
                }, ensure_ascii=False, indent=2)

        except Exception as e:
            # 检查失败不阻止流程，但记录警告
            print(f"⚠️ 完成度检查失败（不影响写回）: {e}")

        # 3. 使用智能fallback自动获取Seurat数据文件路径（优先已注释的RDS，然后原始RDS，最后是转换格式）
        try:
            from agentype.mainagent.tools.file_paths_tools import auto_get_input_path
            seurat_path = auto_get_input_path(
                manual_path=None,
                bundle_keys=['annotated_rds', 'rds_file', 'sce_h5', 'h5_file'],
                tool_name='map_cluster_types_to_seurat'
            )
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"自动获取Seurat路径失败: {e}"
            }, ensure_ascii=False, indent=2)

        # 3. 自动生成输出文件路径，使用session_id命名
        session_id = get_session_id()
        results_dir = _CONFIG.get_results_dir()
        output_rds = str(Path(results_dir) / f"annotated_seurat_{session_id}.rds")
        print(f"📁 输出文件将保存到: {output_rds}")

        # 4. 调用底层map_cluster_types函数执行写回
        try:
            from agentype.mainagent.tools.mapping_tools import map_cluster_types as _map_cluster_types  # type: ignore
        except Exception as e:
            return json.dumps({"success": False, "error": f"依赖缺失: mapping_tools.map_cluster_types: {e}"}, ensure_ascii=False, indent=2)

        summary = await asyncio.get_event_loop().run_in_executor(
            None,
            _map_cluster_types,
            _ensure_abs(seurat_path),
            mapping,  # 直接传入字典
            cluster_col,
            output_col,
            output_rds
        )

        # 5. 自动更新bundle，保存annotated_rds路径
        try:
            from agentype.mainagent.tools.file_paths_tools import auto_update_bundle
            auto_update_bundle('annotated_rds', output_rds)
        except Exception as e:
            print(f"⚠️ 更新bundle失败（不影响主流程）: {e}")

        return json.dumps({"success": True, **summary}, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": f"写回Seurat对象异常: {e}"}, ensure_ascii=False, indent=2)


@mcp.tool()
async def apply_cluster_mapping_to_adata(
    cluster_col: str = "seurat_clusters",
    output_col: str = "agentype"
) -> str:
    """将簇注释映射写回AnnData对象（H5AD格式），自动从缓存读取所有必要信息。

    此工具完全自动化处理簇注释写回流程：
    1. 自动从缓存读取已保存的簇类型映射（无需手动传入JSON）
    2. 自动从路径包读取输入数据文件路径（优先h5ad_file，降级到h5_file）
    3. 自动生成输出文件路径，使用session_id命名（annotated_adata_{session_id}.h5ad）

    Args:
        cluster_col: AnnData.obs中的簇列名，默认"seurat_clusters"
        output_col: 写入的细胞类型列名，默认"agentype"

    Returns:
        JSON格式的写回结果，包含输出文件路径和摘要信息
    """
    try:
        ensure_cache_dir()

        # 1. 加载已保存的簇映射
        try:
            from agentype.mainagent.tools.cluster_tools import load_cluster_types as _load_cluster_types  # type: ignore
            from agentype.mainagent.tools.cluster_tools import check_cluster_completion
        except Exception as e:
            return json.dumps({"success": False, "error": f"依赖缺失: {e}"}, ensure_ascii=False, indent=2)

        mapping = _load_cluster_types()

        if not mapping:
            return json.dumps({
                "success": False,
                "error": "未找到已保存的簇映射，请先完成簇注释并使用save_cluster_type保存所有簇的注释结果"
            }, ensure_ascii=False, indent=2)

        # 2. 检查所有簇是否已完成注释（参考 save_cluster_type 的 reminder 机制）
        try:
            completion_status = check_cluster_completion()
            manager = get_prompt_manager()

            # 生成 reminder（与 save_cluster_type 风格一致）
            if completion_status.get("all_completed"):
                reminder_template = manager.get_agent_specific_prompt('mainagent', 'CLUSTER_PROGRESS_COMPLETE_MESSAGE')
                next_action = manager.get_agent_specific_prompt('mainagent', 'CLUSTER_PROGRESS_ACTION_WRITEBACK_ADATA')
                reminder = reminder_template.format(
                    total_clusters=completion_status['total_clusters'],
                    next_action=next_action
                )
                print(f"📊 {reminder}")
            else:
                # 未完成的情况：返回错误，阻止写回
                completed = completion_status["completed_clusters"]
                total = completion_status["total_clusters"]
                incomplete = completion_status["incomplete_clusters"]
                incomplete_preview = ", ".join(incomplete[:5])
                if len(incomplete) > 5:
                    incomplete_preview += f" 等共{len(incomplete)}个"

                reminder_template = manager.get_agent_specific_prompt('mainagent', 'CLUSTER_PROGRESS_INCOMPLETE_MESSAGE')
                next_action = manager.get_agent_specific_prompt('mainagent', 'CLUSTER_PROGRESS_ACTION_BLOCKER')
                reminder = reminder_template.format(
                    completed=completed,
                    total=total,
                    completion_rate=completion_status["completion_rate"],
                    incomplete_preview=incomplete_preview,
                    next_action=next_action
                )

                return json.dumps({
                    "success": False,
                    "error": "簇注释未完成，不能执行写回操作",
                    "completion_status": completion_status,
                    "reminder": reminder
                }, ensure_ascii=False, indent=2)

        except Exception as e:
            # 检查失败不阻止流程，但记录警告
            print(f"⚠️ 完成度检查失败（不影响写回）: {e}")

        # 3. 使用智能fallback自动获取AnnData数据文件路径（优先已注释的H5AD，然后原始H5AD，最后是转换格式）
        try:
            from agentype.mainagent.tools.file_paths_tools import auto_get_input_path
            h5ad_path = auto_get_input_path(
                manual_path=None,
                bundle_keys=['annotated_h5ad', 'h5ad_file', 'scanpy_h5', 'sce_h5', 'h5_file'],
                tool_name='apply_cluster_mapping_to_adata'
            )
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"自动获取AnnData路径失败: {e}"
            }, ensure_ascii=False, indent=2)

        # 3. 自动生成输出文件路径，使用session_id命名
        session_id = get_session_id()
        results_dir = _CONFIG.get_results_dir()
        output_file = str(Path(results_dir) / f"annotated_adata_{session_id}.h5ad")
        print(f"📁 输出文件将保存到: {output_file}")

        # 4. 调用底层map_cluster_types_to_adata函数执行写回
        try:
            from agentype.mainagent.tools.adata_mapping import map_cluster_types_to_adata  # type: ignore
        except Exception as e:
            return json.dumps({"success": False, "error": f"依赖缺失: adata_mapping.map_cluster_types_to_adata: {e}"}, ensure_ascii=False, indent=2)

        in_path = _ensure_abs(h5ad_path)
        out_path = _ensure_abs(output_file)

        # 使用新的主函数，在 executor 中运行以避免阻塞
        def _process():
            return map_cluster_types_to_adata(
                h5ad_path=in_path,
                mapping_json_or_path=mapping,  # 直接传入字典
                cluster_col=cluster_col,
                output_col=output_col,
                output_h5ad=out_path
            )

        summary = await asyncio.get_event_loop().run_in_executor(None, _process)

        # 5. 自动更新bundle，保存annotated_h5ad路径
        try:
            from agentype.mainagent.tools.file_paths_tools import auto_update_bundle
            auto_update_bundle('annotated_h5ad', output_file)
        except Exception as e:
            print(f"⚠️ 更新bundle失败（不影响主流程）: {e}")

        return json.dumps(summary, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": f"写回AnnData对象异常: {e}"}, ensure_ascii=False, indent=2)


# # ========== 文件路径管理工具 ==========
# @mcp.tool()
# async def save_file_paths_bundle(
#     rds_file: Optional[str] = None,
#     h5ad_file: Optional[str] = None,
#     h5_file: Optional[str] = None,
#     marker_genes_json: Optional[str] = None,
#     singler_result: Optional[str] = None,
#     sctype_result: Optional[str] = None,
#     celltypist_result: Optional[str] = None,
#     annotated_rds: Optional[str] = None,
#     annotated_h5ad: Optional[str] = None,
#     cluster_mapping_json: Optional[str] = None,
#     sce_h5: Optional[str] = None,
#     scanpy_h5: Optional[str] = None
# ) -> str:
#     """保存文件路径信息包到系统临时目录。

#     将包含12个核心文件路径的信息保存到跨平台兼容的临时目录中，
#     支持自动增量更新和会话管理。适用于保存分析流程中的文件路径组合。

#     Args:
#         rds_file: RDS文件路径
#         h5ad_file: H5AD文件路径
#         h5_file: H5文件路径
#         marker_genes_json: Marker基因JSON文件路径
#         singler_result: SingleR结果文件路径
#         sctype_result: scType结果文件路径
#         celltypist_result: CellTypist结果文件路径
#         annotated_rds: Seurat写回结果文件路径
#         annotated_h5ad: AnnData写回结果文件路径
#         cluster_mapping_json: 细胞类型映射JSON文件路径
#         sce_h5: SCE转H5结果文件路径
#         scanpy_h5: Scanpy转H5结果文件路径

#     Returns:
#         JSON格式的保存结果
#     """
#     try:
#         # 调用核心函数（session_id 由底层函数自动获取，自动增量更新）
#         result = _save_file_paths_bundle(
#             rds_file=rds_file,
#             h5ad_file=h5ad_file,
#             h5_file=h5_file,
#             marker_genes_json=marker_genes_json,
#             singler_result=singler_result,
#             sctype_result=sctype_result,
#             celltypist_result=celltypist_result,
#             annotated_rds=annotated_rds,
#             annotated_h5ad=annotated_h5ad,
#             cluster_mapping_json=cluster_mapping_json,
#             sce_h5=sce_h5,
#             scanpy_h5=scanpy_h5,
#             metadata=None
#         )

#         return json.dumps(result, ensure_ascii=False, indent=2)
#     except Exception as e:
#         return json.dumps({"success": False, "error": f"保存文件路径包异常: {e}"}, ensure_ascii=False, indent=2)


@mcp.tool()
async def load_file_paths_bundle() -> str:
    """从临时目录加载当前会话的文件路径信息包。

    自动使用当前会话ID从临时目录加载文件路径信息,
    自动检查过期时间并清理过期文件。

    Returns:
        JSON格式的文件路径信息
    """
    try:
        result = _load_file_paths_bundle()
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": f"加载文件路径包异常: {e}"}, ensure_ascii=False, indent=2)


@mcp.tool()
async def load_and_validate_file_paths_bundle() -> str:
    """加载当前会话的文件路径包并验证关键文件是否存在。

    这是一个安全的加载方法，会在加载后验证marker_genes_json等关键文件是否存在。
    推荐使用此方法而非 load_file_paths_bundle，可以避免使用指向已删除文件的过时路径包。

    Returns:
        JSON格式的文件路径信息及验证结果：
        - validated: 是否完成验证
        - missing_files: 缺失的文件列表
        - existing_files: 存在的文件列表
        - all_files_exist: 是否所有文件都存在
        - validation_failed: 如果关键文件不存在则为True
    """
    try:
        result = _load_and_validate_bundle()
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": f"加载并验证文件路径包异常: {e}"}, ensure_ascii=False, indent=2)


# @mcp.tool()
# async def list_saved_file_paths_bundles(validate_files: bool = True) -> str:
#     """列出所有已保存的文件路径包。

#     查看cache目录中所有已保存的文件路径包信息,
#     包括会话ID、创建时间、文件数量等。

#     **重要**：默认会验证文件存在性，过滤掉指向已删除文件的路径包。

#     Args:
#         validate_files: 是否验证文件存在性（默认True，强烈推荐保持开启）

#     Returns:
#         JSON格式的文件路径包列表，每个包含marker_genes_json路径和files_exist状态
#     """
#     try:
#         result = _list_saved_bundles(validate_files)
#         return json.dumps(result, ensure_ascii=False, indent=2)
#     except Exception as e:
#         return json.dumps({"success": False, "error": f"列出文件路径包异常: {e}"}, ensure_ascii=False, indent=2)


# @mcp.tool()
# async def delete_file_paths_bundle(session_id: str) -> str:
#     """删除指定的文件路径包。

#     根据会话ID删除对应的文件路径包文件。

#     Args:
#         session_id: 会话ID

#     Returns:
#         JSON格式的删除结果
#     """
#     try:
#         result = _delete_bundle(session_id)
#         return json.dumps(result, ensure_ascii=False, indent=2)
#     except Exception as e:
#         return json.dumps({"success": False, "error": f"删除文件路径包异常: {e}"}, ensure_ascii=False, indent=2)


# ========== 会话管理工具 ==========

@mcp.tool()
async def get_current_session() -> str:
    """获取当前进程的会话ID和详细信息。

    每个MainAgent进程都有唯一的会话ID，用于隔离不同进程的数据。

    Returns:
        JSON格式的会话信息
    """
    try:
        session_info = get_session_info()
        return json.dumps(session_info, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": f"获取会话信息异常: {e}"}, ensure_ascii=False, indent=2)


@mcp.tool()
async def list_all_sessions() -> str:
    """列出所有历史会话。

    返回所有已保存的会话ID列表，按时间倒序排列（最新的在前）。

    Returns:
        JSON格式的会话列表
    """
    try:
        from agentype.mainagent.tools.cluster_tools import list_all_sessions as _list_all_sessions  # type: ignore
    except Exception as e:
        return json.dumps({"success": False, "error": f"依赖缺失: cluster_tools.list_all_sessions: {e}"}, ensure_ascii=False, indent=2)

    try:
        sessions = _list_all_sessions()
        current = get_session_id()
        return json.dumps({
            "success": True,
            "current_session": current,
            "total_sessions": len(sessions),
            "sessions": sessions
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": f"列出会话异常: {e}"}, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_session_summary() -> str:
    """获取所有会话的摘要信息。

    返回每个会话的详细信息，包括创建时间、簇数量等。

    Returns:
        JSON格式的会话摘要
    """
    try:
        from agentype.mainagent.tools.cluster_tools import get_session_summary as _get_session_summary  # type: ignore
    except Exception as e:
        return json.dumps({"success": False, "error": f"依赖缺失: cluster_tools.get_session_summary: {e}"}, ensure_ascii=False, indent=2)

    try:
        summary = _get_session_summary()
        return json.dumps(summary, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": f"获取会话摘要异常: {e}"}, ensure_ascii=False, indent=2)


@mcp.tool()
async def load_session_cluster_types(session_id: str) -> str:
    """加载指定会话的簇注释结果。

    用于查看历史会话的注释结果。

    Args:
        session_id: 会话ID

    Returns:
        JSON格式的簇映射
    """
    try:
        from agentype.mainagent.tools.cluster_tools import load_cluster_types_by_session as _load_by_session  # type: ignore
    except Exception as e:
        return json.dumps({"success": False, "error": f"依赖缺失: cluster_tools.load_cluster_types_by_session: {e}"}, ensure_ascii=False, indent=2)

    try:
        mapping = _load_by_session(session_id)
        if not mapping:
            return json.dumps({
                "success": False,
                "error": f"会话 {session_id} 不存在或无注释数据"
            }, ensure_ascii=False, indent=2)

        return json.dumps({
            "success": True,
            "session_id": session_id,
            "mapping": mapping
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": f"加载会话注释异常: {e}"}, ensure_ascii=False, indent=2)


# ========== 服务器启动 ==========
if __name__ == "__main__":
    """
    启动 MCP 服务器，等待客户端连接并处理工具调用请求

    配置通过混合方案传递：
    - 敏感信息（API Key）通过环境变量 OPENAI_API_KEY
    - 非敏感配置通过命令行参数
    """
    import argparse
    from agentype.mainagent.config.session_config import set_session_id

    # 1. 解析命令行参数
    parser = argparse.ArgumentParser(description='CellType MainAgent MCP Server')
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
        print("   MainAgent MCP Server 需要 API Key 才能运行", file=sys.stderr)
        sys.exit(1)

    # 3. 验证必需的命令行参数
    if not args.api_base:
        print("❌ 错误: 缺少必需参数 --api-base", file=sys.stderr)
        print("   用法: python mcp_server.py --api-base <URL> [其他选项]", file=sys.stderr)
        sys.exit(1)

    # 4. 创建输出目录
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # 5. 创建全局配置对象（供工具函数使用）
    enable_streaming = args.enable_streaming.lower() in ('true', '1', 'yes')
    enable_thinking = args.enable_thinking.lower() in ('true', '1', 'yes')

    config = ConfigManager(
        openai_api_base=args.api_base,
        openai_api_key=api_key,
        openai_model=args.model,
        language=args.language,
        enable_streaming=enable_streaming,
        enable_thinking=enable_thinking,
        output_dir=str(output_dir)
    )

    # 设置为模块级配置对象
    _CONFIG = config

    # 更新全局CACHE_DIR（从 _CONFIG 获取）
    CACHE_DIR = _CONFIG.cache_dir

    # 初始化缓存管理器（使用 ConfigManager）
    cache_manager = CacheManager(config=_CONFIG)

    # 设置工具模块的全局配置（用于 file_paths_tools 和 cluster_tools）
    from agentype.mainagent.tools.file_paths_tools import set_global_config
    set_global_config(_CONFIG)

    print(f"✅ MainAgent ConfigManager 已初始化:", file=sys.stderr)
    print(f"   Output Dir: {_CONFIG.output_dir}", file=sys.stderr)
    print(f"   Results Dir: {_CONFIG.results_dir}", file=sys.stderr)
    print(f"   Cache Dir: {_CONFIG.cache_dir}", file=sys.stderr)

    # 6. 设置 session_id（必须设置，如果没有提供则自动生成）
    if args.session_id:
        set_session_id(args.session_id)
        print(f"✅ MainAgent MCP Server 使用传入的 session_id: {args.session_id}", file=sys.stderr)
    else:
        # 如果没有提供session_id，自动生成一个（用于顶层MainAgent）
        from agentype.mainagent.config.session_config import create_session_id
        new_session_id = create_session_id()
        set_session_id(new_session_id)
        print(f"✅ MainAgent MCP Server 生成新 session_id: {new_session_id}", file=sys.stderr)

    # 7. 打印配置信息（不包含敏感信息）
    print(f"✅ MainAgent MCP Server 配置:", file=sys.stderr)
    print(f"   API Base: {args.api_base}", file=sys.stderr)
    print(f"   Model: {args.model}", file=sys.stderr)
    print(f"   Output Dir: {output_dir}", file=sys.stderr)
    print(f"   Language: {args.language}", file=sys.stderr)
    print(f"   Streaming: {enable_streaming}", file=sys.stderr)

    try:
        # 8. 运行 FastMCP 服务器（stdio 模式）
        mcp.run()
    except KeyboardInterrupt:
        print("\n🛑 MainAgent MCP 服务器已停止", file=sys.stderr)
    except Exception as e:
        print(f"❌ MainAgent MCP 服务器启动失败: {e}", file=sys.stderr)
        sys.exit(1)
