#!/usr/bin/env python3
"""
agentype - MainAgent 主工作流处理接口
Author: cuilei
Version: 1.0
"""

import asyncio
import gc
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, Union

# 导入依赖模块
try:
    from agentype.mainagent.config.settings import ConfigManager
    from agentype.mainagent.agent.main_react_agent import MainReactAgent
except ImportError as e:
    raise ImportError(f"无法导入 MainAgent 依赖: {e}")


async def process_workflow(
    input_data: Union[str, Path],
    tissue_type: str = "骨髓",
    cluster_column: str = "seurat_clusters",
    species: Optional[str] = None,
    # 必需的配置参数
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    model: str = "gpt-4o",
    # 可选的配置参数
    output_dir: Union[str, Path] = "./outputs",
    language: str = "zh",
    enable_streaming: bool = True,
    enable_thinking: bool = False,
    enable_llm_logging: bool = True,
    **kwargs
) -> Dict[str, Any]:
    """
    执行主工作流处理

    这是 MainAgent 的核心接口，负责统一工作流编排和多Agent协调。

    Args:
        input_data: 输入数据文件路径 (RDS/H5AD等格式)
        tissue_type: 目标组织类型，默认为"骨髓"
        cluster_column: 聚类列名，用于细胞类型注释，默认为"seurat_clusters"
        species: 可选的物种参数 (如 "Human", "Mouse")，如果不提供则自动检测
        api_key: LLM API 密钥（必需，或从环境变量 OPENAI_API_KEY 读取）
        api_base: LLM API 基础URL（必需，或从环境变量 OPENAI_API_BASE 读取）
        model: LLM 模型名称，默认为 "gpt-4o"
        output_dir: 输出目录，默认为 "./outputs"
        language: 语言设置 (zh/en)，默认为中文
        enable_streaming: 是否启用流式输出，默认为 True
        enable_thinking: 是否启用思考输出，默认为 False
        enable_llm_logging: 是否启用 LLM 日志记录，默认为 True
        **kwargs: 其他参数

    Returns:
        Dict[str, Any]: 处理结果，包含：
            - success: 是否成功
            - total_iterations: 总迭代次数
            - output_file_paths: 输出文件路径
            - analysis_log: 分析日志

    Raises:
        ValueError: 当必需参数缺失时
        ImportError: 当无法导入必要依赖时
        Exception: 当处理过程中发生错误时
    """

    agent = None
    try:
        # 1. 从环境变量或参数获取配置
        api_key = api_key or os.getenv('OPENAI_API_KEY')
        api_base = api_base or os.getenv('OPENAI_API_BASE')

        # 2. 验证必需参数
        if not api_key:
            raise ValueError(
                "缺少必需参数: api_key\n"
                "请通过以下方式之一提供 API 密钥:\n"
                "  1. 传入参数: process_workflow(..., api_key='sk-xxx')\n"
                "  2. 设置环境变量: export OPENAI_API_KEY='sk-xxx'"
            )

        if not api_base:
            raise ValueError(
                "缺少必需参数: api_base\n"
                "请通过以下方式之一提供 API 基础URL:\n"
                "  1. 传入参数: process_workflow(..., api_base='https://api.example.com')\n"
                "  2. 设置环境变量: export OPENAI_API_BASE='https://api.example.com'"
            )

        # 3. 创建输出目录
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        # 4. 创建配置管理器（只传递 output_dir，让 ConfigManager 自动派生其他路径）
        config = ConfigManager(
            openai_api_base=api_base,
            openai_api_key=api_key,
            openai_model=model,
            language=language,
            enable_streaming=enable_streaming,
            enable_thinking=enable_thinking,
            output_dir=str(output_dir)
            # 不再传递 cache_dir 和 log_dir，让 ConfigManager 根据 output_dir 自动派生
        )

        # 5. 创建 MainReactAgent 实例
        agent = MainReactAgent(
            config=config,
            language=language,
            enable_streaming=enable_streaming,
            enable_llm_logging=enable_llm_logging
        )

        # 初始化 Agent
        if not await agent.initialize():
            return {
                "success": False,
                "error": "MainAgent 初始化失败",
                "total_iterations": 0,
                "output_file_paths": {},
                "analysis_log": []
            }

        # 执行主工作流
        result = await agent.process_with_llm_react(
            input_data=str(input_data),
            tissue_type=tissue_type,
            cluster_column=cluster_column,
            species=species
        )

        # 确保返回标准格式
        return {
            "session_id": result.get('session_id', 'unknown'),  # 会话ID
            "api_base": result.get('api_base', 'unknown'),  # API URL
            "model": result.get('model', 'unknown'),  # 使用的模型
            "result_file": result.get('result_file'),  # 保存的文件路径
            "result_saved_at": result.get('result_saved_at'),  # 保存时间
            "success": result.get('success', False),
            "total_iterations": result.get('total_iterations', 0),
            "output_file_paths": result.get('output_file_paths', {}),
            "analysis_log": result.get('analysis_log', []),
            "final_result": result.get('final_result', ''),  # LLM生成的最终分析结果
            "token_stats": result.get('token_stats', {}),  # Token统计信息
            "tissue_type": tissue_type,
            "input_data": str(input_data)
        }

    except Exception as e:
        # 即使异常也尝试获取 session_id
        try:
            from agentype.mainagent.config.session_config import get_session_id
            session_id = get_session_id()
        except:
            session_id = 'unknown'

        return {
            "session_id": session_id,
            "success": False,
            "error": str(e),
            "total_iterations": 0,
            "output_file_paths": {},
            "analysis_log": [],
            "tissue_type": tissue_type,
            "input_data": str(input_data)
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


def process_workflow_sync(
    input_data: Union[str, Path],
    tissue_type: str = "骨髓",
    cluster_column: str = "seurat_clusters",
    species: Optional[str] = None,
    # 必需的配置参数
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    model: str = "gpt-4o",
    # 可选的配置参数
    output_dir: Union[str, Path] = "./outputs",
    language: str = "zh",
    enable_streaming: bool = True,
    enable_thinking: bool = False,
    enable_llm_logging: bool = True,
    **kwargs
) -> Dict[str, Any]:
    """
    同步版本的工作流处理函数

    为不使用 async/await 的用户提供的便利接口。

    Args:
        input_data: 输入数据文件路径
        tissue_type: 目标组织类型
        cluster_column: 聚类列名，用于细胞类型注释，默认为"seurat_clusters"
        species: 可选的物种参数 (如 "Human", "Mouse")，如果不提供则自动检测
        api_key: LLM API 密钥（必需，或从环境变量读取）
        api_base: LLM API 基础URL（必需，或从环境变量读取）
        model: LLM 模型名称，默认为 "gpt-4o"
        output_dir: 输出目录，默认为 "./outputs"
        language: 语言设置，默认为中文
        enable_streaming: 是否启用流式输出
        enable_thinking: 是否启用思考输出
        enable_llm_logging: 是否启用LLM日志
        **kwargs: 其他参数，传递给 process_workflow

    Returns:
        Dict[str, Any]: 处理结果
    """
    return asyncio.run(process_workflow(
        input_data=input_data,
        tissue_type=tissue_type,
        cluster_column=cluster_column,
        species=species,
        api_key=api_key,
        api_base=api_base,
        model=model,
        output_dir=output_dir,
        language=language,
        enable_streaming=enable_streaming,
        enable_thinking=enable_thinking,
        enable_llm_logging=enable_llm_logging,
        **kwargs
    ))


# 为向后兼容保留的别名
main_workflow = process_workflow
main_workflow_sync = process_workflow_sync