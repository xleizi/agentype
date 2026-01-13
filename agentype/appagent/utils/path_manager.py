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
    """统一的路径管理器"""

    def __init__(self):
        # 不再依赖文件系统路径，使用包内机制
        self.package_name = "agentype.appagent"
        self.agent_name = "appagent"

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
            package_path = files('agentype.appagent.services')
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
                'agentype.appagent.services', 'mcp_server.py'
            )
            if Path(resource_path).exists():
                logger.info(f"使用 pkg_resources 找到 MCP 服务器: {resource_path}")
                return Path(resource_path)
        except (ImportError, pkg_resources.DistributionNotFound, Exception) as e:
            logger.debug(f"pkg_resources 方法失败: {e}")

        # 方法3：基于模块导入的路径查找（开发环境兼容）
        try:
            import agentype.appagent.services.mcp_server as mcp_module
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

def normalize_path(file_path: Union[str, Path, None]) -> str:
    """
    便捷函数：标准化单个文件路径

    Args:
        file_path: 输入的文件路径

    Returns:
        标准化后的绝对路径字符串，如果输入为空则返回空字符串
    """
    if not file_path:
        return ""

    try:
        # 转换为Path对象
        path = Path(file_path)

        # 展开用户目录（~）
        if str(path).startswith('~'):
            path = path.expanduser()

        # 转换为绝对路径并解析所有符号链接
        absolute_path = path.resolve()

        return str(absolute_path)

    except Exception as e:
        logger.warning(f"标准化路径失败 {file_path}: {e}")
        return str(file_path) if file_path else ""

def validate_path_exists(file_path: str) -> bool:
    """
    验证路径是否存在

    Args:
        file_path: 文件路径

    Returns:
        路径是否存在
    """
    if not file_path:
        return False

    try:
        return Path(file_path).exists()
    except Exception:
        return False

def get_file_extension(file_path: str) -> str:
    """
    获取文件扩展名

    Args:
        file_path: 文件路径

    Returns:
        文件扩展名（包含点，如'.json'），如果无扩展名则返回空字符串
    """
    if not file_path:
        return ""

    try:
        return Path(file_path).suffix.lower()
    except Exception:
        return ""

def get_parent_directory(file_path: str) -> str:
    """
    获取文件的父目录

    Args:
        file_path: 文件路径

    Returns:
        父目录的绝对路径
    """
    if not file_path:
        return ""

    try:
        normalized_path = normalize_path(file_path)
        return str(Path(normalized_path).parent)
    except Exception as e:
        logger.warning(f"获取父目录失败 {file_path}: {e}")
        return ""

def ensure_directory_exists(directory_path: str) -> bool:
    """
    确保目录存在，如果不存在则创建

    Args:
        directory_path: 目录路径

    Returns:
        目录是否存在或创建成功
    """
    if not directory_path:
        return False

    try:
        Path(directory_path).mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"创建目录失败 {directory_path}: {e}")
        return False

def get_relative_path(file_path: str, base_path: str = None) -> str:
    """
    获取相对于基准路径的相对路径

    Args:
        file_path: 文件路径
        base_path: 基准路径，默认为当前工作目录

    Returns:
        相对路径字符串
    """
    if not file_path:
        return ""

    try:
        file_path = normalize_path(file_path)

        if base_path:
            base_path = normalize_path(base_path)
        else:
            base_path = str(Path.cwd())

        return str(Path(file_path).relative_to(base_path))

    except ValueError:
        # 如果无法计算相对路径，返回绝对路径
        return file_path
    except Exception as e:
        logger.warning(f"计算相对路径失败 {file_path}: {e}")
        return file_path

def is_file_type(file_path: str, expected_extensions: list) -> bool:
    """
    检查文件是否为指定类型

    Args:
        file_path: 文件路径
        expected_extensions: 预期的扩展名列表（如['.json', '.txt']）

    Returns:
        文件是否为指定类型
    """
    if not file_path or not expected_extensions:
        return False

    file_ext = get_file_extension(file_path)
    return file_ext in [ext.lower() for ext in expected_extensions]

def get_safe_filename(filename: str, max_length: int = 255) -> str:
    """
    生成安全的文件名，移除非法字符并限制长度

    Args:
        filename: 原始文件名
        max_length: 最大长度

    Returns:
        安全的文件名
    """
    if not filename:
        return "unnamed_file"

    # 移除或替换非法字符
    illegal_chars = '<>:"/\\|?*'
    safe_name = filename

    for char in illegal_chars:
        safe_name = safe_name.replace(char, '_')

    # 移除控制字符
    safe_name = ''.join(char for char in safe_name if ord(char) >= 32)

    # 移除首尾空格和点
    safe_name = safe_name.strip(' .')

    # 限制长度
    if len(safe_name) > max_length:
        # 保留扩展名
        path = Path(safe_name)
        stem = path.stem
        suffix = path.suffix

        max_stem_length = max_length - len(suffix)
        if max_stem_length > 0:
            safe_name = stem[:max_stem_length] + suffix
        else:
            safe_name = safe_name[:max_length]

    # 确保不为空
    if not safe_name:
        safe_name = "unnamed_file"

    return safe_name

def join_paths(*paths) -> str:
    """
    安全地连接多个路径

    Args:
        *paths: 要连接的路径组件

    Returns:
        连接后的标准化绝对路径
    """
    if not paths:
        return ""

    try:
        # 过滤掉空路径
        valid_paths = [p for p in paths if p]

        if not valid_paths:
            return ""

        # 使用Path对象连接路径
        result_path = Path(valid_paths[0])
        for path in valid_paths[1:]:
            result_path = result_path / path

        return normalize_path(result_path)

    except Exception as e:
        logger.error(f"连接路径失败 {paths}: {e}")
        return ""
