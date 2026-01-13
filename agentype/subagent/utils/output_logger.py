#!/usr/bin/env python3
"""
agentype - 输出日志工具模块 - SubAgent版本
Author: cuilei
Version: 1.0
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
from contextlib import contextmanager

# 尝试导入统一日志管理器
try:
    from agentype.config.unified_logger import UnifiedOutputLogger, create_agent_logger
    UNIFIED_LOGGER_AVAILABLE = True
except ImportError:
    UNIFIED_LOGGER_AVAILABLE = False

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


class OutputLogger:
    """输出日志工具类 - SubAgent兼容版本

    基于统一配置系统，支持同时输出到控制台和文件，保持格式一致性
    如果统一日志管理器可用，则使用统一配置；否则回退到原始实现
    """

    def __init__(self,
                 log_prefix: str = "celltypeSubagent",
                 console_output: bool = True,
                 file_output: bool = True,
                 log_dir: Optional[str] = None):
        """初始化输出日志器

        Args:
            log_prefix: 日志文件名前缀（用作agent_name）
            console_output: 是否输出到控制台
            file_output: 是否输出到文件
            log_dir: 日志文件保存目录（可选，默认使用统一配置）
        """
        self.log_prefix = log_prefix
        self.console_output = console_output
        self.file_output = file_output

        # 优先使用统一日志管理器
        if UNIFIED_LOGGER_AVAILABLE:
            try:
                self._unified_logger = create_agent_logger(
                    agent_name=log_prefix,
                    console_output=console_output,
                    file_output=file_output,
                    log_dir=log_dir
                )
                self._use_unified = True
                # 兼容性属性
                self.log_dir = self._unified_logger.get_log_dir()
                self.log_file = self._unified_logger.get_log_file_path()
                return
            except Exception as e:
                print(f"警告: 无法使用统一日志管理器，回退到原始实现: {e}")

        # 回退到原始实现
        self._use_unified = False

        # 如果没有提供 log_dir，不再回退到 .output，直接报错
        if log_dir is None:
            raise ValueError(
                f"log_dir 参数为 None！OutputLogger 需要有效的日志目录。\n"
                f"Agent: {log_prefix}\n"
                f"请在创建 Agent 时传入 config.log_dir"
            )
        else:
            self.log_dir = Path(log_dir)

        # 创建日志目录
        if self.file_output:
            self.log_dir.mkdir(parents=True, exist_ok=True)

            # 获取 session_id（完整格式：session_20251023_142530）
            try:
                from agentype.mainagent.config.session_config import get_session_id
                session_id = get_session_id()
            except ImportError:
                # 如果导入失败，回退到时间戳格式
                session_id = "session_" + datetime.now().strftime("%Y%m%d_%H%M%S")

            # 使用 session_id 生成日志文件名
            self.log_file = self.log_dir / f"{self.log_prefix}_{session_id}.log"

            # 初始化日志文件
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write(f"# {self.log_prefix} 日志文件 (备用模式)\n")
                f.write(f"# Session ID: {session_id}\n")
                f.write(f"# 创建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("# " + "="*60 + "\n\n")
        else:
            self.log_file = None

    def _write_to_file(self, message: str) -> None:
        """写入日志文件

        Args:
            message: 要写入的消息
        """
        if not self._use_unified and self.file_output and self.log_file:
            timestamp = datetime.now().strftime("%H:%M:%S")
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {message}\n")

    def _write_to_console(self, message: str, color: str = None) -> None:
        """写入控制台

        Args:
            message: 要输出的消息
            color: 颜色代码
        """
        if not self._use_unified and self.console_output:
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
        if self._use_unified:
            self._unified_logger.info(message, color)
        else:
            self._write_to_console(message, color)
            self._write_to_file(message)

    def success(self, message: str) -> None:
        """输出成功信息（绿色）

        Args:
            message: 消息内容
        """
        if self._use_unified:
            self._unified_logger.success(message)
        else:
            self.info(message, Fore.GREEN)

    def warning(self, message: str) -> None:
        """输出警告信息（黄色）

        Args:
            message: 消息内容
        """
        if self._use_unified:
            self._unified_logger.warning(message)
        else:
            self.info(message, Fore.YELLOW)

    def error(self, message: str) -> None:
        """输出错误信息（红色）

        Args:
            message: 消息内容
        """
        if self._use_unified:
            self._unified_logger.error(message)
        else:
            self.info(message, Fore.RED)

    def header(self, message: str) -> None:
        """输出标题信息（蓝色加粗）

        Args:
            message: 消息内容
        """
        if self._use_unified:
            self._unified_logger.header(message)
        else:
            self.info(message, Fore.BLUE + Style.BRIGHT)

    def separator(self, char: str = "=", length: int = 60) -> None:
        """输出分隔线

        Args:
            char: 分隔符字符
            length: 分隔线长度
        """
        if self._use_unified:
            self._unified_logger.separator(char, length)
        else:
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
        if self._use_unified:
            self._unified_logger.print(*args, sep=sep, end=end, **kwargs)
        else:
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
        if self._use_unified:
            # 使用统一日志管理器的capture_stdout
            with self._unified_logger.capture_stdout():
                yield
            return

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
        if self._use_unified:
            return self._unified_logger.get_log_file_path()
        return self.log_file

    def close(self) -> None:
        """关闭日志器（添加结束标记）"""
        if self._use_unified:
            self._unified_logger.close()
        elif self.file_output and self.log_file:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n# 日志结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("# " + "="*60 + "\n")


# 创建默认的输出日志器实例
default_output_logger = None


def create_logger(log_dir: str = "./logs",
                 log_prefix: str = "celltypeSubagent",
                 console_output: bool = True,
                 file_output: bool = True) -> OutputLogger:
    """创建输出日志器实例

    Args:
        log_dir: 日志文件保存目录（统一配置下会被忽略）
        log_prefix: 日志文件名前缀（用作agent_name）
        console_output: 是否输出到控制台
        file_output: 是否输出到文件

    Returns:
        OutputLogger实例
    """
    global default_output_logger
    default_output_logger = OutputLogger(log_dir, log_prefix, console_output, file_output)
    return default_output_logger


def get_default_logger() -> OutputLogger:
    """获取默认的输出日志器

    Returns:
        默认的OutputLogger实例
    """
    global default_output_logger
    if default_output_logger is None:
        default_output_logger = create_logger()
    return default_output_logger


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
