"""
agentype - MCP Server 统一配置模块
Author: cuilei
Version: 3.0 - 移除GlobalConfigManager，统一使用Agent级ConfigManager

注意：PathManager 已在 v3.0 中废弃，请使用各 Agent 的 ConfigManager
"""

# paths_config 已废弃，移除导入
# from .paths_config import (
#     PathManager,
#     path_manager,
#     get_path_manager
# )

from ..mainagent.config.session_config import (
    get_session_id,
    get_session_id_for_filename,
    set_session_id,
    create_session_id,
    reset_session_id,
    get_session_info
)

__all__ = [
    # PathManager 已废弃，已移除
    # 'PathManager',
    # 'path_manager',
    # 'get_path_manager',

    # Session 管理函数
    'get_session_id',
    'get_session_id_for_filename',
    'set_session_id',
    'create_session_id',
    'reset_session_id',
    'get_session_info',
]