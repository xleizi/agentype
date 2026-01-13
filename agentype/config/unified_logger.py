#!/usr/bin/env python3
"""
agentype - 统一日志管理器
Author: cuilei
Version: 2.0 - 移除对 GlobalConfig 的依赖
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Union
from contextlib import contextmanager

# 尝试导入colorama，如果没有安装则使用空的颜色代码
try:
    import colorama
    from colorama import Fore, Style
    colorama.init()
    COLORAMA_AVAILABLE = True
except ImportError:
    # 如果colorama不可用，定义空的颜色代码
    class Fore:
        GREEN = ""
        YELLOW = ""
        RED = ""
        BLUE = ""

    class Style:
        RESET_ALL = ""
        BRIGHT = ""

    COLORAMA_AVAILABLE = False


class UnifiedOutputLogger:
    """统一输出日志工具类

    集成全局配置系统，支持同时输出到控制台和文件，保持格式一致性
    """

    def __init__(self,
                 agent_name: str = "celltype_analysis",
                 console_output: bool = True,
                 file_output: bool = True,
                 log_dir: Optional[Union[str, Path]] = None,
                 fallback_log_dir: str = "./logs"):
        """初始化统一输出日志器

        Args:
            agent_name: Agent名称，用于确定日志文件前缀
            console_output: 是否输出到控制台
            file_output: 是否输出到文件
            log_dir: 日志目录（优先使用此参数）
            fallback_log_dir: 当 log_dir 未提供时的备用日志目录
        """
        self.agent_name = agent_name
        self.console_output = console_output
        self.file_output = file_output

        # 确定日志目录（统一在基础日志目录下创建 agent_name 子目录）
        if log_dir:
            self.log_dir = Path(log_dir) / agent_name
        else:
            self.log_dir = Path(fallback_log_dir) / agent_name

        # 创建日志目录
        if self.file_output:
            self.log_dir.mkdir(parents=True, exist_ok=True)

            # 获取 session_id（完整格式：session_20251023_142530）
            from ..mainagent.config.session_config import get_session_id
            session_id = get_session_id()

            # 使用 session_id 生成日志文件名
            self.log_file = self.log_dir / f"{self.agent_name}_{session_id}.log"

            # 初始化日志文件
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write(f"# {self.agent_name} 日志文件\n")
                f.write(f"# Session ID: {session_id}\n")
                f.write(f"# 创建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# 日志目录: {self.log_dir}\n")
                f.write(f"# 统一配置: 启用\n")
                f.write("# " + "="*60 + "\n\n")
        else:
            self.log_file = None

    def _write_to_file(self, message: str) -> None:
        """写入日志文件

        Args:
            message: 要写入的消息
        """
        if self.file_output and self.log_file:
            timestamp = datetime.now().strftime("%H:%M:%S")
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {message}\n")

    def _write_to_console(self, message: str, color: str = None) -> None:
        """写入控制台

        Args:
            message: 要输出的消息
            color: 颜色代码
        """
        if self.console_output:
            if color:
                print(f"{color}{message}{Style.RESET_ALL}")
            else:
                print(message)

    def info(self, message: str, color: str = None) -> None:
        """输出信息级别的日志

        Args:
            message: 消息内容
            color: 控制台颜色（可选）
        """
        self._write_to_console(message, color)
        self._write_to_file(message)

    def success(self, message: str) -> None:
        """输出成功信息（绿色）

        Args:
            message: 消息内容
        """
        self.info(message, Fore.GREEN)

    def warning(self, message: str) -> None:
        """输出警告信息（黄色）

        Args:
            message: 消息内容
        """
        self.info(message, Fore.YELLOW)

    def error(self, message: str) -> None:
        """输出错误信息（红色）

        Args:
            message: 消息内容
        """
        self.info(message, Fore.RED)

    def header(self, message: str) -> None:
        """输出标题信息（蓝色加粗）

        Args:
            message: 消息内容
        """
        self.info(message, Fore.BLUE + Style.BRIGHT)

    def separator(self, char: str = "=", length: int = 60) -> None:
        """输出分隔线

        Args:
            char: 分隔符字符
            length: 分隔线长度
        """
        line = char * length
        self.info(line)

    def print(self, *args, sep: str = " ", end: str = "\n", **kwargs) -> None:
        """兼容原生print函数的接口

        Args:
            *args: 要打印的参数
            sep: 参数之间的分隔符
            end: 结尾字符
            **kwargs: 其他参数（为了兼容性，实际不使用）
        """
        message = sep.join(str(arg) for arg in args) + end.rstrip('\n')
        self.info(message)

    @contextmanager
    def capture_stdout(self):
        """上下文管理器，用于捕获stdout输出到日志文件

        使用方式:
        with logger.capture_stdout():
            # 在这里的所有print()输出都会被捕获到日志文件
            print("这会被记录到日志文件")
            some_function_that_prints()
        """
        if not self.file_output:
            # 如果没有启用文件输出，直接执行原始代码
            yield
            return

        # 创建一个自定义的输出类来同时处理控制台和文件输出
        class TeeOutput:
            def __init__(self, original_stdout, logger_instance):
                self.original_stdout = original_stdout
                self.logger = logger_instance
                self.buffer = ""

            def write(self, text):
                # 输出到控制台
                self.original_stdout.write(text)
                self.original_stdout.flush()

                # 处理日志文件写入
                if text:
                    self.buffer += text

                    # 处理换行符分割的内容
                    while '\n' in self.buffer:
                        line, self.buffer = self.buffer.split('\n', 1)
                        if line.strip():  # 只记录非空行
                            self.logger._write_to_file(line.rstrip())

            def flush(self):
                self.original_stdout.flush()
                # 刷新时如果缓冲区还有内容，也写入日志
                if self.buffer.strip():
                    self.logger._write_to_file(self.buffer.rstrip())
                    self.buffer = ""

            def __getattr__(self, name):
                return getattr(self.original_stdout, name)

        # 保存原始stdout
        original_stdout = sys.stdout

        try:
            # 替换stdout为我们的TeeOutput
            tee_output = TeeOutput(original_stdout, self)
            sys.stdout = tee_output
            yield
        finally:
            # 刷新缓冲区
            if hasattr(sys.stdout, 'flush'):
                sys.stdout.flush()
            # 恢复原始stdout
            sys.stdout = original_stdout

    def get_log_file_path(self) -> Optional[Path]:
        """获取日志文件路径

        Returns:
            日志文件路径，如果未启用文件输出则返回None
        """
        return self.log_file

    def get_log_dir(self) -> Path:
        """获取日志目录路径

        Returns:
            日志目录路径
        """
        return self.log_dir

    def close(self) -> None:
        """关闭日志器（添加结束标记）"""
        if self.file_output and self.log_file:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n# 日志结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("# " + "="*60 + "\n")


# 为了向后兼容，提供原始的OutputLogger接口
OutputLogger = UnifiedOutputLogger

# 全局日志器实例管理
_global_loggers = {}


def create_logger(log_dir: str = "./logs",
                 log_prefix: str = "celltype_analysis",
                 console_output: bool = True,
                 file_output: bool = True) -> UnifiedOutputLogger:
    """创建输出日志器实例（兼容原始接口）

    Args:
        log_dir: 日志文件保存目录（在统一配置下会被忽略）
        log_prefix: 日志文件名前缀（用作agent_name）
        console_output: 是否输出到控制台
        file_output: 是否输出到文件

    Returns:
        UnifiedOutputLogger实例
    """
    global _global_loggers

    # 使用log_prefix作为agent_name
    agent_name = log_prefix

    # 如果已存在相同配置的logger，直接返回
    logger_key = (agent_name, console_output, file_output)
    if logger_key in _global_loggers:
        return _global_loggers[logger_key]

    # 创建新的logger
    logger = UnifiedOutputLogger(
        agent_name=agent_name,
        console_output=console_output,
        file_output=file_output,
        fallback_log_dir=log_dir
    )

    _global_loggers[logger_key] = logger
    return logger


def create_agent_logger(agent_name: str,
                       console_output: bool = True,
                       file_output: bool = True,
                       log_dir: Optional[str] = None) -> UnifiedOutputLogger:
    """为特定Agent创建日志器（推荐使用）

    Args:
        agent_name: Agent名称
        console_output: 是否输出到控制台
        file_output: 是否输出到文件
        log_dir: 日志根目录（可选，会自动在此目录下创建 agent_name 子目录）

    Returns:
        UnifiedOutputLogger实例
    """
    return UnifiedOutputLogger(
        agent_name=agent_name,
        console_output=console_output,
        file_output=file_output,
        log_dir=log_dir
    )


def get_default_logger() -> UnifiedOutputLogger:
    """获取默认的输出日志器

    Returns:
        默认的UnifiedOutputLogger实例
    """
    return create_logger()


# 提供便捷的全局函数
def log_info(message: str, color: str = None) -> None:
    """便捷的信息输出函数"""
    get_default_logger().info(message, color)


def log_success(message: str) -> None:
    """便捷的成功信息输出函数"""
    get_default_logger().success(message)


def log_warning(message: str) -> None:
    """便捷的警告信息输出函数"""
    get_default_logger().warning(message)


def log_error(message: str) -> None:
    """便捷的错误信息输出函数"""
    get_default_logger().error(message)


def log_header(message: str) -> None:
    """便捷的标题输出函数"""
    get_default_logger().header(message)


def log_separator(char: str = "=", length: int = 60) -> None:
    """便捷的分隔线输出函数"""
    get_default_logger().separator(char, length)