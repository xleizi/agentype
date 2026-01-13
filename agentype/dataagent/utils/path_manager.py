#!/usr/bin/env python3
"""
agentype - 路径管理器模块
Author: cuilei
Version: 1.0
"""

from pathlib import Path
from typing import Optional, Dict, Union
import os
import logging

# 设置日志
logger = logging.getLogger(__name__)

class PathManager:
    """统一的路径管理器 - 专为打包环境优化"""

    def __init__(self):
        # 不再依赖文件系统路径，使用包内机制
        self.package_name = "agentype.dataagent"
        self.agent_name = "dataagent"

        # 为了兼容性，保留这些属性（但不再用于路径计算）
        self.package_root = self._get_package_root()
        self.package_dir = self.package_root / self.agent_name if self.package_root else None

    def _get_package_root(self) -> Optional[Path]:
        """获取包根目录（仅用于兼容性，不用于关键路径计算）"""
        try:
            import agentype
            return Path(agentype.__file__).parent
        except (ImportError, AttributeError):
            # 如果无法通过导入获取，回退到相对路径
            try:
                return Path(__file__).resolve().parent.parent.parent
            except:
                return None
        
    def get_mcp_server_path(self) -> Path:
        """获取MCP服务器脚本的路径 - 优先使用包内资源"""

        # 方法1：使用 importlib.resources (Python 3.9+)
        try:
            from importlib.resources import files
            package_path = files('agentype.dataagent.services')
            mcp_server_file = package_path / 'mcp_server.py'
            if mcp_server_file.is_file():
                logger.info(f"使用 importlib.resources 找到 MCP 服务器: {mcp_server_file}")
                return Path(str(mcp_server_file))
        except (ImportError, AttributeError, Exception) as e:
            logger.debug(f"importlib.resources 方法失败: {e}")

        # 方法2：使用 pkg_resources (向后兼容)
        try:
            import pkg_resources
            resource_path = pkg_resources.resource_filename(
                'agentype.dataagent.services', 'mcp_server.py'
            )
            if Path(resource_path).exists():
                logger.info(f"使用 pkg_resources 找到 MCP 服务器: {resource_path}")
                return Path(resource_path)
        except (ImportError, pkg_resources.DistributionNotFound, Exception) as e:
            logger.debug(f"pkg_resources 方法失败: {e}")

        # 方法3：基于模块导入的路径查找（开发环境兼容）
        try:
            import agentype.dataagent.services.mcp_server as mcp_module
            module_path = Path(mcp_module.__file__)
            if module_path.exists():
                logger.info(f"使用模块导入找到 MCP 服务器: {module_path}")
                return module_path
        except (ImportError, AttributeError, Exception) as e:
            logger.debug(f"模块导入方法失败: {e}")

        # 方法4：回退到相对路径查找（最后手段）
        try:
            # 基于当前模块计算相对路径
            current_module_path = Path(__file__).resolve()
            relative_server_path = current_module_path.parent.parent / "services" / "mcp_server.py"
            if relative_server_path.exists():
                logger.warning(f"使用相对路径找到 MCP 服务器: {relative_server_path}")
                return relative_server_path
        except Exception as e:
            logger.debug(f"相对路径方法失败: {e}")

        # 所有方法都失败，抛出详细错误
        raise FileNotFoundError(
            f"无法找到 {self.agent_name} 的 MCP 服务器脚本。\n"
            f"包名: {self.package_name}\n"
            f"请确保包已正确安装，并且 mcp_server.py 存在于 services 目录中。"
        )
    
    def get_cache_dir(self, custom_dir: Optional[str] = None) -> Path:
        """获取缓存目录"""
        if custom_dir:
            return Path(custom_dir).resolve()
        
        # 默认使用当前工作目录下的缓存
        cache_dir = Path.cwd() / ".agentype_cache"
        cache_dir.mkdir(exist_ok=True)
        return cache_dir
    
    def get_log_dir(self, log_dir: str = "logs") -> Path:
        """获取日志目录"""
        # 基于当前工作目录
        log_path = Path.cwd() / log_dir
        log_path.mkdir(exist_ok=True)
        return log_path
    
    def get_llm_log_dir(self, log_dir: str = "llm_logs") -> Path:
        """获取LLM日志目录"""
        # 基于当前工作目录
        log_path = Path.cwd() / log_dir  
        log_path.mkdir(exist_ok=True)
        return log_path
    
    def get_locales_dir(self) -> Path:
        """获取语言配置文件目录"""
        return self.package_dir / "locales"
    
    def get_config_dir(self) -> Path:
        """获取配置文件目录"""
        return self.package_dir / "config"
    
    def get_tools_dir(self) -> Path:
        """获取工具目录"""
        return self.package_dir / "tools"
    
    def get_utils_dir(self) -> Path:
        """获取工具类目录"""
        return self.package_dir / "utils"
    
    def normalize_to_absolute_path(self, file_path: Union[str, Path]) -> str:
        """
        将相对路径转换为绝对路径
        
        Args:
            file_path: 输入的文件路径（相对或绝对）
            
        Returns:
            str: 标准化的绝对路径
        """
        if not file_path:
            return ""
        
        try:
            path_obj = Path(file_path)
            
            # 如果已经是绝对路径，直接resolve
            if path_obj.is_absolute():
                return str(path_obj.resolve())
            
            # 相对路径，基于当前工作目录转换
            absolute_path = (Path.cwd() / path_obj).resolve()
            return str(absolute_path)
            
        except Exception:
            return str(file_path)
    
    def get_all_output_file_paths(self,
                                  rds_file: Optional[str] = None,
                                  h5ad_file: Optional[str] = None,
                                  h5_file: Optional[str] = None,
                                  marker_genes_json: Optional[str] = None) -> Dict[str, str]:
        """
        获取所有输出文件的标准化绝对路径

        Args:
            rds_file: RDS文件路径
            h5ad_file: H5AD文件路径
            h5_file: H5文件路径
            marker_genes_json: Marker基因JSON文件路径

        Returns:
            Dict[str, str]: 所有文件的绝对路径，空文件返回空字符串
        """
        return {
            'rds_file': self.normalize_to_absolute_path(rds_file) if rds_file else "",
            'h5ad_file': self.normalize_to_absolute_path(h5ad_file) if h5ad_file else "",
            'h5_file': self.normalize_to_absolute_path(h5_file) if h5_file else "",
            'marker_genes_json': self.normalize_to_absolute_path(marker_genes_json) if marker_genes_json else ""
        }
    
    def get_platform_info(self) -> str:
        """获取当前平台信息"""
        if os.name == 'nt':  # Windows
            return "Windows"
        elif os.name == 'posix':
            if 'darwin' in os.sys.platform.lower():  # macOS
                return "macOS" 
            else:  # Linux and others
                return "Linux"
        return "Unknown"

# 全局路径管理器实例
path_manager = PathManager()

# 便捷函数
def get_absolute_paths(**file_paths) -> Dict[str, str]:
    """
    便捷函数：获取所有文件的绝对路径
    
    Returns:
        Dict[str, str]: 标准化后的绝对路径字典
    """
    return path_manager.get_all_output_file_paths(**file_paths)

def normalize_path(file_path: Union[str, Path]) -> str:
    """
    便捷函数：标准化单个文件路径
    
    Args:
        file_path: 文件路径
        
    Returns:
        str: 绝对路径
    """
    return path_manager.normalize_to_absolute_path(file_path)
