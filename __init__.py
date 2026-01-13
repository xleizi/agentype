"""
agentype - - 统一细胞类型分析工具包
Author: cuilei
Version: 1.0
"""

__version__ = "1.0.0"
__author__ = "CellType Agent Team"
__email__ = "contact@agentype.com"
__description__ = "统一的细胞类型分析工具包，集成四个专业Agent提供完整的细胞类型注释流程"

# 导入核心功能
try:
    from agentype import (
        get_main_agent,
        get_sub_agent,
        get_data_agent,
        get_app_agent,
        get_global_config,
        start_all_servers,
        start_single_server,
    )

    _CORE_AVAILABLE = True
except ImportError:
    _CORE_AVAILABLE = False

# 直接从各模块导入主要类（可选）
_AGENTS_AVAILABLE = {}

try:
    from agentype.mainagent.agent.main_react_agent import MainReactAgent
    _AGENTS_AVAILABLE['MainReactAgent'] = MainReactAgent
except ImportError:
    pass

try:
    from agentype.subagent.agent.celltype_react_agent import CelltypeReactAgent
    _AGENTS_AVAILABLE['CelltypeReactAgent'] = CelltypeReactAgent
except ImportError:
    pass

try:
    from agentype.dataagent.agent.data_processor_agent import DataProcessorAgent
    _AGENTS_AVAILABLE['DataProcessorAgent'] = DataProcessorAgent
except ImportError:
    pass

try:
    from agentype.appagent.agent.celltype_annotation_agent import CelltypeAnnotationAgent
    _AGENTS_AVAILABLE['CelltypeAnnotationAgent'] = CelltypeAnnotationAgent
except ImportError:
    pass

# 定义公开接口
__all__ = [
    # 版本信息
    "__version__",
    "__author__",
    "__email__",
    "__description__",
]

# 添加可用的功能到公开接口
if _CORE_AVAILABLE:
    __all__.extend([
        "get_main_agent",
        "get_sub_agent",
        "get_data_agent",
        "get_app_agent",
        "get_global_config",
        "start_all_servers",
        "start_single_server",
    ])

# 添加可用的Agent类到公开接口
__all__.extend(_AGENTS_AVAILABLE.keys())

# 动态添加Agent类到当前命名空间
for name, cls in _AGENTS_AVAILABLE.items():
    globals()[name] = cls

# 便捷函数
def check_installation():
    """检查安装状态和依赖"""
    print(f"CellType Agent v{__version__}")
    print("=" * 50)

    # 检查核心功能
    if _CORE_AVAILABLE:
        print("✅ 核心功能可用")
    else:
        print("❌ 核心功能不可用")

    # 检查各Agent
    agents_status = {
        "MainAgent": "MainReactAgent" in _AGENTS_AVAILABLE,
        "SubAgent": "CelltypeReactAgent" in _AGENTS_AVAILABLE,
        "DataAgent": "DataProcessorAgent" in _AGENTS_AVAILABLE,
        "AppAgent": "CelltypeAnnotationAgent" in _AGENTS_AVAILABLE,
    }

    for agent_name, available in agents_status.items():
        status = "✅" if available else "❌"
        print(f"{status} {agent_name}")

    # 检查可选依赖
    optional_deps = {
        "CellTypist": "celltypist",
        "R Interface": "rpy2",
        "Scanpy": "scanpy",
        "Visualization": "matplotlib",
    }

    print("\n可选依赖:")
    for dep_name, module_name in optional_deps.items():
        try:
            __import__(module_name)
            print(f"✅ {dep_name}")
        except ImportError:
            print(f"❌ {dep_name}")

    print(f"\n总计可用Agent: {sum(agents_status.values())}/{len(agents_status)}")

def info():
    """显示包信息"""
    print(__doc__)

# 导入时的自检（仅在调试模式下）
import os
if os.environ.get('CELLTYPE_DEBUG', '').lower() in ['1', 'true', 'yes']:
    check_installation()