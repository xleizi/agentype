"""
agentype - 统一细胞类型分析工具包
Author: cuilei
Version: 1.0
"""

__version__ = "1.0.1"
__author__ = "CellType Agent Team"
__email__ = "contact@agentype.com"
__description__ = "统一的细胞类型分析工具包，集成四个专业Agent提供完整的细胞类型注释流程"

# 导入核心API - 基于examples接口提取的简化函数
from .api import (
    process_workflow,
    analyze_genes,
    process_data,
    annotate_cells
)

# 导入同步版本
from .api.main_workflow import process_workflow_sync, main_workflow, main_workflow_sync
from .api.celltype_analysis import analyze_genes_sync, celltype_analysis, celltype_analysis_sync
from .api.data_processing import process_data_sync, data_processing, data_processing_sync
from .api.annotation import annotate_cells_sync, celltype_annotation, celltype_annotation_sync

# 导入服务器启动功能
from .servers import start_all_servers, start_single_server

# 便捷函数：获取各Agent实例（保持向后兼容）
def get_main_agent():
    """获取MainAgent实例"""
    try:
        from agentype.mainagent.agent.main_react_agent import MainReactAgent
        return MainReactAgent()
    except ImportError as e:
        raise ImportError(f"无法导入MainAgent: {e}")


def get_sub_agent():
    """获取SubAgent实例"""
    try:
        from agentype.subagent.agent.celltype_react_agent import CelltypeReactAgent
        return CelltypeReactAgent()
    except ImportError as e:
        raise ImportError(f"无法导入SubAgent: {e}")


def get_data_agent():
    """获取DataAgent实例"""
    try:
        from agentype.dataagent.agent.data_processor_agent import DataProcessorAgent
        return DataProcessorAgent()
    except ImportError as e:
        raise ImportError(f"无法导入DataAgent: {e}")


def get_app_agent():
    """获取AppAgent实例"""
    try:
        from agentype.appagent.agent.celltype_annotation_agent import CelltypeAnnotationAgent
        return CelltypeAnnotationAgent()
    except ImportError as e:
        raise ImportError(f"无法导入AppAgent: {e}")


# 统一配置管理（已废弃）
def get_global_config():
    """获取全局配置（已废弃）

    ⚠️ 此函数已废弃！GlobalConfig 配置系统已在 v2.0 中移除。

    新的配置方式：
    1. 使用 ConfigManager 直接创建配置：
       from agentype.config import ConfigManager
       config = ConfigManager(
           api_base='https://api.example.com',
           api_key='your-key',
           model='gpt-4o',
           output_dir='./outputs'
       )

    2. 或从环境变量加载：
       config = ConfigManager.from_env()

    详情请参阅文档: docs/CONFIGURATION.md
    """
    raise RuntimeError(
        "❌ get_global_config() 已废弃！\n\n"
        "GlobalConfig 配置系统已在 v2.0 中移除。\n\n"
        "请使用新的 ConfigManager：\n"
        "  from agentype.config import ConfigManager\n"
        "  config = ConfigManager(\n"
        "      api_base='https://api.example.com',\n"
        "      api_key='your-key',\n"
        "      model='gpt-4o',\n"
        "      output_dir='./outputs'\n"
        "  )\n\n"
        "详情请参阅: 配置传递流程详解.md"
    )


# Agent类别名（为了方便导入）
MainAgent = get_main_agent
SubAgent = get_sub_agent
DataAgent = get_data_agent
AppAgent = get_app_agent

# 定义包的公开接口
__all__ = [
    # 版本信息
    "__version__",
    "__author__",
    "__email__",
    "__description__",

    # 核心API - 简化接口
    "process_workflow",          # MainAgent核心功能
    "analyze_genes",             # SubAgent核心功能
    "process_data",              # DataAgent核心功能
    "annotate_cells",            # AppAgent核心功能

    # 同步版本
    "process_workflow_sync",
    "analyze_genes_sync",
    "process_data_sync",
    "annotate_cells_sync",

    # 向后兼容别名
    "main_workflow",
    "main_workflow_sync",
    "celltype_analysis",
    "celltype_analysis_sync",
    "data_processing",
    "data_processing_sync",
    "celltype_annotation",
    "celltype_annotation_sync",

    # 服务器功能
    "start_all_servers",
    "start_single_server",

    # Agent获取函数
    "get_main_agent",
    "get_sub_agent",
    "get_data_agent",
    "get_app_agent",

    # Agent类别名
    "MainAgent",
    "SubAgent",
    "DataAgent",
    "AppAgent",

    # 配置管理
    "get_global_config",
]

# 包级别的初始化检查
def _check_environment():
    """检查运行环境"""
    import sys
    import warnings

    # 检查Python版本
    if sys.version_info < (3, 8):
        raise RuntimeError("CellType Agent需要Python 3.8或更高版本")

    # 检查关键依赖
    missing_deps = []

    try:
        import pandas
        import numpy
    except ImportError:
        missing_deps.append("pandas, numpy")

    try:
        import fastapi
        import uvicorn
    except ImportError:
        missing_deps.append("fastapi, uvicorn")

    try:
        import mcp
    except ImportError:
        missing_deps.append("mcp")

    if missing_deps:
        warnings.warn(
            f"缺少关键依赖: {', '.join(missing_deps)}。"
            f"请运行: pip install celltype-agent",
            ImportWarning
        )

# 执行环境检查（可以通过环境变量禁用）
import os
if os.environ.get('CELLTYPE_SKIP_ENV_CHECK', '').lower() not in ['1', 'true', 'yes']:
    try:
        _check_environment()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"环境检查时发生异常: {e}")

# 打印欢迎信息（仅在调试模式下）
if os.environ.get('CELLTYPE_DEBUG', '').lower() in ['1', 'true', 'yes']:
    print(f"CellType Agent v{__version__} 已加载")
    print("集成四个专业Agent提供完整的细胞类型注释流程")
    print("核心API: process_workflow, analyze_genes, process_data, annotate_cells")
    print("使用 help(celltype_agent) 获取更多信息")