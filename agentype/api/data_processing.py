#!/usr/bin/env python3
"""
agentype - DataAgent 数据处理和格式转换接口
Author: cuilei
Version: 1.0
"""

import asyncio
import gc
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, Union, List

# 导入依赖模块
try:
    from agentype.dataagent.config.cache_config import init_cache, get_cache_info
    from agentype.dataagent.config.settings import ConfigManager
    from agentype.dataagent.agent.data_processor_agent import DataProcessorReactAgent
except ImportError as e:
    raise ImportError(f"无法导入 DataAgent 依赖: {e}")


async def process_data(
    data_file: Union[str, Path],
    output_dir: Optional[Union[str, Path]] = None,
    target_format: Optional[str] = None,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    model: Optional[str] = None,
    language: str = "zh",
    enable_streaming: bool = True,
    **kwargs
) -> Dict[str, Any]:
    """
    处理和转换单细胞数据文件

    这是 DataAgent 的核心接口，支持处理 RDS、H5AD、H5、CSV、JSON 等多种数据格式，
    提供数据质量控制、格式转换和标准化功能。

    Args:
        data_file: 输入数据文件路径，支持的格式：
            - .rds: R数据格式
            - .h5ad: AnnData格式
            - .h5: HDF5格式
            - .csv: CSV格式
            - .json: JSON格式
        output_dir: 输出目录，默认使用配置的结果目录
        target_format: 目标转换格式 (h5ad, rds, csv, json)，默认自动推断
        api_key: OpenAI API密钥，默认从环境变量读取
        api_base: API基础URL，默认使用配置文件设置
        model: 使用的模型，默认使用配置文件设置
        language: 语言设置，默认为中文
        enable_streaming: 是否启用流式输出
        **kwargs: 其他参数

    Returns:
        Dict[str, Any]: 处理结果，包含：
            - success: 是否成功
            - total_iterations: 总迭代次数
            - output_file_paths: 输出文件路径字典
            - analysis_log: 处理日志
            - input_file_info: 输入文件信息

    Raises:
        ImportError: 当无法导入必要依赖时
        FileNotFoundError: 当输入文件不存在时
        Exception: 当处理过程中发生错误时
    """

    agent = None
    data_file_path = Path(data_file)

    try:
        # 检查输入文件
        if not data_file_path.exists():
            return {
                "success": False,
                "error": f"输入文件不存在: {data_file_path}",
                "total_iterations": 0,
                "output_file_paths": {},
                "analysis_log": [],
                "input_file_info": {"path": str(data_file_path), "exists": False}
            }

        # 获取文件信息
        file_size = data_file_path.stat().st_size
        file_suffix = data_file_path.suffix.lower()

        # 验证文件格式
        supported_formats = ['.rds', '.h5ad', '.h5', '.csv', '.json']
        if file_suffix not in supported_formats:
            return {
                "success": False,
                "error": f"不支持的文件格式: {file_suffix}. 支持的格式: {supported_formats}",
                "total_iterations": 0,
                "output_file_paths": {},
                "analysis_log": [],
                "input_file_info": {
                    "path": str(data_file_path),
                    "exists": True,
                    "size": file_size,
                    "format": file_suffix
                }
            }

        # 初始化缓存
        cache_dir = init_cache()

        # 创建配置管理器（从参数或环境变量获取配置）
        config = ConfigManager(
            openai_api_base=api_base or os.getenv("OPENAI_API_BASE", "https://api.siliconflow.cn/v1"),
            openai_api_key=api_key or os.getenv("OPENAI_API_KEY"),
            openai_model=model or os.getenv("OPENAI_MODEL", "gpt-4"),
        )

        # 创建 DataProcessorReactAgent 实例
        agent = DataProcessorReactAgent(
            config=config,
            language=language,
            enable_streaming=enable_streaming,
        )

        # 初始化 Agent
        if not await agent.initialize():
            return {
                "success": False,
                "error": "DataAgent 初始化失败",
                "total_iterations": 0,
                "output_file_paths": {},
                "analysis_log": [],
                "input_file_info": {
                    "path": str(data_file_path),
                    "exists": True,
                    "size": file_size,
                    "format": file_suffix
                }
            }

        # 执行数据处理
        result = await agent.process_data(str(data_file_path))

        # 确保返回标准格式
        return {
            "success": result.get('success', False),
            "total_iterations": result.get('total_iterations', 0),
            "output_file_paths": result.get('output_file_paths', {}),
            "analysis_log": result.get('analysis_log', []),
            "input_file_info": {
                "path": str(data_file_path),
                "exists": True,
                "size": file_size,
                "format": file_suffix
            },
            "target_format": target_format,
            "output_dir": str(output_dir) if output_dir else None
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "total_iterations": 0,
            "output_file_paths": {},
            "analysis_log": [],
            "input_file_info": {
                "path": str(data_file_path),
                "exists": data_file_path.exists(),
                "size": data_file_path.stat().st_size if data_file_path.exists() else 0,
                "format": data_file_path.suffix.lower() if data_file_path.exists() else None
            }
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


def process_data_sync(
    data_file: Union[str, Path],
    **kwargs
) -> Dict[str, Any]:
    """
    同步版本的数据处理函数

    为不使用 async/await 的用户提供的便利接口。

    Args:
        data_file: 输入数据文件路径
        **kwargs: 其他参数，传递给 process_data

    Returns:
        Dict[str, Any]: 处理结果
    """
    return asyncio.run(process_data(data_file, **kwargs))


async def convert_format(
    input_file: Union[str, Path],
    target_format: str,
    output_file: Optional[Union[str, Path]] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    数据格式转换的便利函数

    Args:
        input_file: 输入文件路径
        target_format: 目标格式 (h5ad, rds, csv, json)
        output_file: 输出文件路径，默认自动生成
        **kwargs: 其他参数，传递给 process_data

    Returns:
        Dict[str, Any]: 转换结果
    """
    return await process_data(
        data_file=input_file,
        target_format=target_format,
        output_file=output_file,
        **kwargs
    )


def convert_format_sync(
    input_file: Union[str, Path],
    target_format: str,
    **kwargs
) -> Dict[str, Any]:
    """
    同步版本的格式转换函数

    Args:
        input_file: 输入文件路径
        target_format: 目标格式
        **kwargs: 其他参数

    Returns:
        Dict[str, Any]: 转换结果
    """
    return asyncio.run(convert_format(input_file, target_format, **kwargs))


async def get_supported_formats() -> List[str]:
    """
    获取支持的数据格式列表

    Returns:
        List[str]: 支持的文件格式列表
    """
    return ['.rds', '.h5ad', '.h5', '.csv', '.json']


async def validate_data_file(data_file: Union[str, Path]) -> Dict[str, Any]:
    """
    验证数据文件

    Args:
        data_file: 数据文件路径

    Returns:
        Dict[str, Any]: 验证结果
    """
    data_file_path = Path(data_file)
    supported_formats = await get_supported_formats()

    result = {
        "path": str(data_file_path),
        "exists": data_file_path.exists(),
        "valid": False,
        "format": None,
        "size": 0,
        "error": None
    }

    try:
        if not data_file_path.exists():
            result["error"] = "文件不存在"
            return result

        result["size"] = data_file_path.stat().st_size
        result["format"] = data_file_path.suffix.lower()

        if result["format"] not in supported_formats:
            result["error"] = f"不支持的文件格式: {result['format']}"
            return result

        result["valid"] = True

    except Exception as e:
        result["error"] = str(e)

    return result


# 为向后兼容保留的别名
data_processing = process_data
data_processing_sync = process_data_sync