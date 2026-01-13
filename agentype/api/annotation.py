#!/usr/bin/env python3
"""
agentype - AppAgent 细胞类型注释接口
Author: cuilei
Version: 1.0
"""

import asyncio
import gc
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, Union

# 导入依赖模块
try:
    from agentype.appagent.config.cache_config import init_cache, get_cache_info
    from agentype.appagent.config.settings import ConfigManager
    from agentype.appagent.agent.celltype_annotation_agent import CelltypeAnnotationAgent
    from agentype.appagent.config.prompts import build_unified_user_query
except ImportError as e:
    raise ImportError(f"无法导入 AppAgent 依赖: {e}")


async def annotate_cells(
    files: Dict[str, Optional[Union[str, Path]]] = None,
    tissue_description: str = "骨髓",
    species: str = "Mouse",
    rds_path: Optional[Union[str, Path]] = None,
    h5ad_path: Optional[Union[str, Path]] = None,
    h5_path: Optional[Union[str, Path]] = None,
    marker_json_path: Optional[Union[str, Path]] = None,
    cluster_column: Optional[str] = None,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    model: Optional[str] = None,
    language: str = "zh",
    enable_streaming: bool = True,
    **kwargs
) -> Dict[str, Any]:
    """
    执行细胞类型注释

    这是 AppAgent 的核心接口，集成 SingleR、scType、CellTypist 三种注释方法，
    提供智能的细胞类型注释功能。

    Args:
        files: 输入文件字典，包含：
            - 'rds_file': RDS文件路径
            - 'h5ad_file': H5AD文件路径
            - 'h5_file': H5文件路径
            - 'marker_genes_json': 标记基因JSON文件路径
        tissue_description: 组织类型描述，默认为"骨髓"
        species: 物种，Human 或 Mouse，默认为"Mouse"
        rds_path: RDS文件路径（替代files参数的便利方式）
        h5ad_path: H5AD文件路径（替代files参数的便利方式）
        h5_path: H5文件路径（替代files参数的便利方式）
        marker_json_path: 标记基因JSON文件路径（替代files参数的便利方式）
        cluster_column: 聚类列名，默认使用方法内部推断
        api_key: OpenAI API密钥，默认从环境变量读取
        api_base: API基础URL，默认使用配置文件设置
        model: 使用的模型，默认使用配置文件设置
        language: 语言设置，默认为中文
        enable_streaming: 是否启用流式输出
        **kwargs: 其他参数

    Returns:
        Dict[str, Any]: 注释结果，包含：
            - success: 是否成功
            - total_iterations: 总迭代次数
            - output_file_paths: 输出文件路径字典
            - analysis_log: 分析日志
            - annotation_methods: 使用的注释方法
            - input_files: 输入文件信息

    Raises:
        ImportError: 当无法导入必要依赖时
        Exception: 当注释过程中发生错误时
    """

    agent = None

    try:
        # 处理输入文件参数
        if files is None:
            files = {}

        # 便利参数转换为files字典
        if rds_path:
            files['rds_file'] = rds_path
        if h5ad_path:
            files['h5ad_file'] = h5ad_path
        if h5_path:
            files['h5_file'] = h5_path
        if marker_json_path:
            files['marker_genes_json'] = marker_json_path

        # 标准化文件路径字典
        test_files = {
            'rds_file': str(files.get('rds_file')) if files.get('rds_file') else None,
            'h5ad_file': str(files.get('h5ad_file')) if files.get('h5ad_file') else None,
            'h5_file': str(files.get('h5_file')) if files.get('h5_file') else None,
            'marker_genes_json': str(files.get('marker_genes_json')) if files.get('marker_genes_json') else None,
        }

        # 验证至少有一个输入文件
        available_files = [path for path in test_files.values() if path and Path(path).exists()]
        if not available_files:
            return {
                "success": False,
                "error": "未提供有效的输入文件或文件不存在",
                "total_iterations": 0,
                "output_file_paths": {},
                "analysis_log": [],
                "annotation_methods": [],
                "input_files": test_files,
                "cluster_column": cluster_column,
            }

        # 验证物种参数
        if species not in ["Human", "Mouse"]:
            return {
                "success": False,
                "error": "species 参数必须是 'Human' 或 'Mouse'",
                "total_iterations": 0,
                "output_file_paths": {},
                "analysis_log": [],
                "annotation_methods": [],
                "input_files": test_files,
                "cluster_column": cluster_column,
            }

        # 初始化缓存
        cache_dir = init_cache()

        # 创建配置管理器（从参数或环境变量获取配置）
        config = ConfigManager(
            openai_api_base=api_base or os.getenv("OPENAI_API_BASE", "https://api.siliconflow.cn/v1"),
            openai_api_key=api_key or os.getenv("OPENAI_API_KEY"),
            openai_model=model or os.getenv("OPENAI_MODEL", "gpt-4"),
        )

        # 创建 CelltypeAnnotationAgent 实例
        agent = CelltypeAnnotationAgent(
            config=config,
            language=language,
            enable_streaming=enable_streaming,
        )

        # 初始化 Agent
        if not await agent.initialize():
            return {
                "success": False,
                "error": "AppAgent 初始化失败",
                "total_iterations": 0,
                "output_file_paths": {},
                "analysis_log": [],
                "annotation_methods": [],
                "input_files": test_files,
                "cluster_column": cluster_column,
            }

        # 执行细胞类型注释
        result = await agent.annotate(
            rds_path=test_files['rds_file'],
            h5ad_path=test_files['h5ad_file'],
            h5_path=test_files['h5_file'],
            marker_json_path=test_files['marker_genes_json'],
            tissue_description=tissue_description,
            species=species,
            cluster_column=cluster_column,
        )

        # 确保返回标准格式
        return {
            "success": result.get('success', False),
            "total_iterations": result.get('total_iterations', 0),
            "output_file_paths": result.get('output_file_paths', {}),
            "analysis_log": result.get('analysis_log', []),
            "annotation_methods": _extract_annotation_methods(result.get('analysis_log', [])),
            "input_files": test_files,
            "tissue_description": tissue_description,
            "species": species,
            "cluster_column": cluster_column,
            "available_files_count": len(available_files)
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "total_iterations": 0,
            "output_file_paths": {},
            "analysis_log": [],
            "annotation_methods": [],
            "input_files": test_files if 'test_files' in locals() else {},
            "tissue_description": tissue_description,
            "species": species,
            "cluster_column": cluster_column,
        }

    finally:
        # 清理资源
        if agent:
            try:
                await agent.cleanup()
                await asyncio.sleep(0.3)
                gc.collect()
                await asyncio.sleep(0.1)
            except Exception:
                pass  # 静默处理清理错误


def annotate_cells_sync(
    files: Dict[str, Optional[Union[str, Path]]] = None,
    tissue_description: str = "骨髓",
    species: str = "Mouse",
    cluster_column: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    同步版本的细胞类型注释函数

    为不使用 async/await 的用户提供的便利接口。

    Args:
        files: 输入文件字典
        tissue_description: 组织类型描述
        species: 物种
        **kwargs: 其他参数，传递给 annotate_cells

    Returns:
        Dict[str, Any]: 注释结果
    """
    return asyncio.run(
        annotate_cells(
            files,
            tissue_description,
            species,
            cluster_column=cluster_column,
            **kwargs,
        )
    )


async def annotate_with_singleR(
    rds_path: Union[str, Path],
    tissue_description: str = "骨髓",
    species: str = "Mouse",
    **kwargs
) -> Dict[str, Any]:
    """
    使用 SingleR 方法进行注释的便利函数

    Args:
        rds_path: RDS文件路径
        tissue_description: 组织类型描述
        species: 物种
        **kwargs: 其他参数

    Returns:
        Dict[str, Any]: 注释结果
    """
    return await annotate_cells(
        files={'rds_file': rds_path},
        tissue_description=tissue_description,
        species=species,
        **kwargs
    )


async def annotate_with_celltypist(
    h5ad_path: Union[str, Path],
    tissue_description: str = "骨髓",
    species: str = "Mouse",
    **kwargs
) -> Dict[str, Any]:
    """
    使用 CellTypist 方法进行注释的便利函数

    Args:
        h5ad_path: H5AD文件路径
        tissue_description: 组织类型描述
        species: 物种
        **kwargs: 其他参数

    Returns:
        Dict[str, Any]: 注释结果
    """
    return await annotate_cells(
        files={'h5ad_file': h5ad_path},
        tissue_description=tissue_description,
        species=species,
        **kwargs
    )


def _extract_annotation_methods(analysis_log: list) -> list:
    """
    从分析日志中提取使用的注释方法

    Args:
        analysis_log: 分析日志列表

    Returns:
        list: 使用的注释方法列表
    """
    methods = []
    for log_entry in analysis_log:
        if log_entry.get('type') == 'tool_call':
            tool_name = log_entry.get('tool_name', '')
            if 'singleR' in tool_name.lower():
                methods.append('SingleR')
            elif 'sctype' in tool_name.lower():
                methods.append('scType')
            elif 'celltypist' in tool_name.lower():
                methods.append('CellTypist')

    return list(set(methods))  # 去重


async def get_supported_species() -> list:
    """
    获取支持的物种列表

    Returns:
        list: 支持的物种列表
    """
    return ["Human", "Mouse"]


async def get_available_annotation_methods() -> list:
    """
    获取可用的注释方法列表

    Returns:
        list: 可用的注释方法列表
    """
    return ["SingleR", "scType", "CellTypist"]


# 为向后兼容保留的别名
celltype_annotation = annotate_cells
celltype_annotation_sync = annotate_cells_sync
