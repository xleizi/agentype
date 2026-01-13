"""
agentype - MainAgent工具模块
Author: cuilei
Version: 1.0
"""

# 簇相关工具
from .cluster_tools import (
    # 簇注释保存/加载
    save_cluster_type,
    load_cluster_types,
    # 簇结果读取
    read_cluster_results,
    # 基因提取
    extract_cluster_genes,
    get_all_cluster_ids,
    get_cluster_info,
    # 会话管理
    list_all_sessions,
    load_cluster_types_by_session,
    get_session_summary
)

# 映射工具
from .mapping_tools import map_cluster_types

# 文件路径管理工具
from .file_paths_tools import (
    save_file_paths_bundle,
    load_file_paths_bundle,
    list_saved_bundles,
    delete_bundle,
    FilePathsInfo,
    FilePathsManager
)

# 保持向后兼容
try:
    from .subagent_tools import (
        process_data_via_subagent,
        run_annotation_via_subagent,
        analyze_gene_list_via_subagent,
        # 简化的函数名
        process_data,
        run_annotation_pipeline,
        analyze_gene_list
    )
except ImportError:
    # 如果旧的工具模块不存在，提供兼容性函数
    def process_data_via_subagent(input_data):
        """兼容性函数 - 暂时返回错误"""
        return {"success": False, "error": "workflow_tools 模块未可用"}

    def run_annotation_via_subagent(rds_path=None, h5ad_path=None, tissue_description=None,
                                   marker_json_path=None, species=None, h5_path=None,
                                   cluster_column=None):
        """兼容性函数 - 暂时返回错误"""
        return {"success": False, "error": "workflow_tools 模块未可用"}

    def analyze_gene_list_via_subagent(gene_list, tissue_type=None):
        """兼容性函数 - 暂时返回错误"""
        return {"success": False, "error": "workflow_tools 模块未可用"}

__all__ = [
    'process_data_via_subagent',
    'run_annotation_via_subagent',
    'analyze_gene_list_via_subagent',
    'process_data',
    'run_annotation_pipeline',
    'analyze_gene_list',
    # 簇相关工具
    'save_cluster_type',
    'load_cluster_types',
    'read_cluster_results',
    'extract_cluster_genes',
    'get_all_cluster_ids',
    'get_cluster_info',
    # 会话管理
    'list_all_sessions',
    'load_cluster_types_by_session',
    'get_session_summary',
    # 映射工具
    'map_cluster_types',
    # 文件路径管理工具
    'save_file_paths_bundle',
    'load_file_paths_bundle',
    'list_saved_bundles',
    'delete_bundle',
    'FilePathsInfo',
    'FilePathsManager'
]
