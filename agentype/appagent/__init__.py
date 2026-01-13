"""
agentype - App Agent
Author: cuilei
Version: 1.0
"""

__version__ = "1.0.0"
__author__ = "CellType Agent Team"
__email__ = "contact@agentype.com"
__description__ = "智能细胞类型注释代理 - 集成SingleR、scType和CellTypist"

# 导入主要功能
from .agent.celltype_annotation_agent import CelltypeAnnotationAgent
from .clients.mcp_client import MCPClient

# 导入配置管理
from .config import (
    init_cache,
    set_cache_dir,
    get_cache_dir,
    get_cache_info,
    clear_cache
)

# 导入工具函数
from .utils import (
    GlobalTimestampManager,
    setup_logging,
    _,
    set_language,
    get_language
)

# 定义包的公开接口
__all__ = [
    # 主要功能
    'CelltypeAnnotationAgent',
    'MCPClient',
    
    # 缓存管理
    'init_cache',
    'set_cache_dir',
    'get_cache_dir',
    'get_cache_info',
    'clear_cache',
    
    # 工具函数
    'GlobalTimestampManager',
    'setup_logging',
    '_',
    'set_language',
    'get_language',
    
    # 元数据
    '__version__',
    '__author__',
    '__email__',
    '__description__'
]

# 配置日志
import logging

# 创建包级别的日志记录器
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())  # 防止没有配置日志时的警告

# 包初始化时的检查
def _check_environment():
    """检查环境配置"""
    import shutil
    import warnings
    
    # 检查Python版本
    import sys
    if sys.version_info < (3, 7):
        raise RuntimeError("此包需要Python 3.7或更高版本")
    
    # 检查R是否安装（SingleR和scType需要）
    if not shutil.which('Rscript'):
        warnings.warn(
            "未找到Rscript命令。SingleR和scType功能需要R环境支持。",
            ImportWarning
        )
    
    # 检查Python依赖（CellTypist需要）
    try:
        import scanpy
        import celltypist
    except ImportError:
        warnings.warn(
            "未找到scanpy或celltypist包。CellTypist功能需要这些依赖。\n"
            "请运行: pip install scanpy celltypist",
            ImportWarning
        )

# 执行环境检查（可以通过环境变量禁用）
import os
if os.environ.get('CELLTYPE_SKIP_ENV_CHECK', '').lower() not in ['1', 'true', 'yes']:
    try:
        _check_environment()
    except Exception as e:
        logger.warning(f"环境检查时发生异常: {e}")

# 打印欢迎信息（仅在调试模式下）
if os.environ.get('CELLTYPE_DEBUG', '').lower() in ['1', 'true', 'yes']:
    print(f"CellType App Agent v{__version__} 已加载")
    print("支持SingleR、scType和CellTypist三种注释方法")
    print("使用 help(celltypeAppAgent) 获取更多信息")