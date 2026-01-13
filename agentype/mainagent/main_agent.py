#!/usr/bin/env python3
"""
agentype - Project directory definitions
Author: cuilei
Version: 1.0
"""

import asyncio
import json
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
import sys


_CUR_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _CUR_DIR.parent

# 导入Main Agent的配置管理
from agentype.mainagent.config.settings import ConfigManager as MainConfigManager
    
def _run_async(coro):
    """Run an async coroutine in a safe way from sync code.

    Prefer asyncio.run when no loop is running; fallback to existing loop.
    """
    try:
        loop = asyncio.get_running_loop()
        # If we're already in an async context, we can't call run_until_complete
        # This indicates the function should be called differently
        import warnings
        warnings.warn(
            "celltypeMainagent functions are being called from within an async context. "
            "Consider using the async MainAgentOrchestrator methods instead.",
            RuntimeWarning,
            stacklevel=2
        )
        # In this case, we'll create a new thread to run the event loop
        import concurrent.futures

        def run_in_thread():
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                return new_loop.run_until_complete(coro)
            finally:
                new_loop.close()

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_in_thread)
            return future.result()

    except RuntimeError:
        # No event loop running
        return asyncio.run(coro)


def process_data(input_data: Union[str, List[str], Any], species: Optional[str] = None, config: Optional[MainConfigManager] = None) -> Dict:
    """调用 celltypeDataAgent 的数据处理 Agent。

    Args:
        input_data: 入参可为文件路径、路径列表，或 AnnData 对象（若环境安装了 scanpy/anndata）
        species: 可选的物种参数，如果不提供则由 DataAgent 自动检测
        config: 可选的配置管理器，如未提供则使用默认配置

    Returns: 处理结果字典。
    """
    # 使用修复后的统一处理函数
    from agentype.mainagent.tools.subagent_tools import process_data_via_subagent

    return process_data_via_subagent(input_data, species=species, config=config)

def run_annotation_pipeline(
    rds_path: Optional[str],
    h5ad_path: Optional[str],
    tissue_description: Optional[str] = None,
    marker_json_path: Optional[str] = None,
    species: Optional[str] = None,
    h5_path: Optional[str] = None,
    cluster_column: Optional[str] = None,
    config: Optional[MainConfigManager] = None,
) -> Dict:
    """调用 celltypeAppAgent 的应用级注释 Agent（整合 SingleR/scType/CellTypist）。

    Args:
        rds_path: RDS文件路径
        h5ad_path: H5AD文件路径
        tissue_description: 组织描述
        marker_json_path: 标记基因JSON文件路径
        species: 物种
        h5_path: H5文件路径
        cluster_column: 聚类列名
        config: 可选的配置管理器

    Returns: 综合注释结果与各方法输出路径。
    """
    from agentype.appagent.config.settings import ConfigManager
    from agentype.appagent.agent.celltype_annotation_agent import CelltypeAnnotationAgent
    from agentype.common.language_manager import get_current_language

    async def _run() -> Dict:
        try:
            # 使用传入的配置或创建默认配置
            if config:
                sub_config = ConfigManager(
                    openai_api_base=config.openai_api_base,
                    openai_api_key=config.openai_api_key,
                    openai_model=config.openai_model
                )
            else:
                sub_config = ConfigManager()

            agent = CelltypeAnnotationAgent(
                config=sub_config,
                language=get_current_language(),
                enable_streaming=True,
            )

            ok = await agent.initialize()
            if not ok:
                return {"success": False, "error": "Failed to start MCP server (AppAgent)"}

            result = await agent.annotate(
                rds_path=rds_path,
                h5ad_path=h5ad_path,
                tissue_description=tissue_description,
                marker_json_path=marker_json_path,
                species=species,
                h5_path=h5_path,
                cluster_column=cluster_column,
            )
            return {
                "success": result.get("success", True),
                "final_answer": result.get("final_answer"),
                "output_file_paths": result.get("output_file_paths", {}),
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"细胞类型注释失败: {str(e)}"
            }
        finally:
            try:
                await agent.cleanup()
            except:
                pass

    return _run_async(_run())


def analyze_gene_list(gene_list: str, tissue_type: Optional[str] = None, config: Optional[MainConfigManager] = None) -> Dict:
    """调用 celltypeSubagent 的基因列表分析 Agent（细胞类型推断）。

    Args:
        gene_list: 基因列表（逗号分隔）
        tissue_type: 组织类型
        config: 可选的配置管理器

    Returns: 细胞类型推断报告和最终标准英文细胞类型名。
    """
    from agentype.subagent.config.settings import ConfigManager
    from agentype.subagent.agent.celltype_react_agent import CellTypeReactAgent

    async def _run() -> Dict:
        try:
            # 使用传入的配置或创建默认配置
            if config:
                sub_config = ConfigManager(
                    openai_api_base=config.openai_api_base,
                    openai_api_key=config.openai_api_key,
                    openai_model=config.openai_model
                )
            else:
                sub_config = ConfigManager()

            # 🌟 获取 MainAgent 的 session_id 准备传递
            from agentype.mainagent.config.session_config import get_session_id
            main_session_id = get_session_id()

            agent = CellTypeReactAgent(
                config=sub_config,
                language="zh",
                enable_streaming=True,
                session_id=main_session_id
            )

            ok = await agent.initialize()
            if not ok:
                return {"success": False, "error": "Failed to start MCP server (Subagent)"}

            result = await agent.analyze_celltype(gene_list=gene_list, tissue_type=tissue_type)
            return result
        except Exception as e:
            return {
                "success": False,
                "error": f"基因列表分析失败: {str(e)}"
            }
        finally:
            try:
                await agent.cleanup()
            except:
                pass

    return _run_async(_run())

# 注意：此模块提供统一的子 Agent 调度函数。
# 不在导入时执行任何重处理逻辑，避免副作用。
