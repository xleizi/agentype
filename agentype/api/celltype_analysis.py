#!/usr/bin/env python3
"""
agentype - SubAgent 基因分析和细胞类型推断接口
Author: cuilei
Version: 1.0
"""

import asyncio
import gc
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List, Union

# 导入依赖模块
try:
    from agentype.subagent.config.cache_config import init_cache, get_cache_info
    from agentype.subagent.config.settings import ConfigManager
    from agentype.subagent.agent.celltype_react_agent import CellTypeReactAgent
    from agentype.subagent.utils.file_utils import load_gene_list_from_file
except ImportError as e:
    raise ImportError(f"无法导入 SubAgent 依赖: {e}")


async def analyze_genes(
    gene_list: Union[List[str], str, Path],
    tissue_type: str = "骨髓",
    max_genes: int = 100,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    model: Optional[str] = None,
    language: str = "zh",
    enable_streaming: bool = True,
    **kwargs
) -> Dict[str, Any]:
    """
    分析基因列表并推断细胞类型

    这是 SubAgent 的核心接口，提供基因信息查询、CellMarker/PanglaoDB 数据库查询、
    基因富集分析等功能。

    Args:
        gene_list: 基因列表，可以是：
            - List[str]: 基因符号列表
            - str: 基因文件路径，或逗号分隔的基因字符串
            - Path: 基因文件路径
        tissue_type: 目标组织类型，默认为"骨髓"
        max_genes: 最大基因数量限制，默认100
        api_key: OpenAI API密钥，默认从环境变量读取
        api_base: API基础URL，默认使用配置文件设置
        model: 使用的模型，默认使用配置文件设置
        language: 语言设置，默认为中文
        enable_streaming: 是否启用流式输出
        **kwargs: 其他参数

    Returns:
        Dict[str, Any]: 分析结果，包含：
            - success: 是否成功
            - final_celltype: 推断的细胞类型
            - total_iterations: 总迭代次数
            - analysis_log: 分析日志
            - gene_count: 分析的基因数量

    Raises:
        ImportError: 当无法导入必要依赖时
        Exception: 当分析过程中发生错误时
    """

    agent = None
    processed_genes = []

    try:
        # 处理基因列表输入
        if isinstance(gene_list, (str, Path)):
            file_path = Path(gene_list)
            if file_path.exists():
                # 从文件加载基因列表
                processed_genes = load_gene_list_from_file(str(file_path), max_genes=max_genes)
            else:
                # 尝试解析为逗号分隔的字符串
                processed_genes = [gene.strip() for gene in str(gene_list).split(',') if gene.strip()]
        elif isinstance(gene_list, list):
            processed_genes = gene_list[:max_genes] if len(gene_list) > max_genes else gene_list
        else:
            raise ValueError("gene_list 必须是列表、文件路径或逗号分隔的字符串")

        if not processed_genes:
            return {
                "success": False,
                "error": "基因列表为空",
                "final_celltype": "未确定",
                "total_iterations": 0,
                "analysis_log": [],
                "gene_count": 0
            }

        # 初始化缓存
        cache_dir = init_cache()

        # 创建配置管理器（从参数或环境变量获取配置）
        config = ConfigManager(
            openai_api_base=api_base or os.getenv("OPENAI_API_BASE", "https://api.siliconflow.cn/v1"),
            openai_api_key=api_key or os.getenv("OPENAI_API_KEY"),
            openai_model=model or os.getenv("OPENAI_MODEL", "gpt-4"),
        )

        # 创建 CellTypeReactAgent 实例
        agent = CellTypeReactAgent(
            config=config,
            language=language,
            enable_streaming=enable_streaming,
        )

        # 初始化 Agent
        if not await agent.initialize():
            return {
                "success": False,
                "error": "SubAgent 初始化失败",
                "final_celltype": "未确定",
                "total_iterations": 0,
                "analysis_log": [],
                "gene_count": len(processed_genes)
            }

        # 执行细胞类型分析
        result = await agent.analyze_celltype(processed_genes, tissue_type=tissue_type)

        # 确保返回标准格式
        return {
            "success": result.get('success', False),
            "final_celltype": result.get('final_celltype', '未确定'),
            "total_iterations": result.get('total_iterations', 0),
            "analysis_log": result.get('analysis_log', []),
            "gene_count": len(processed_genes),
            "tissue_type": tissue_type,
            "input_genes": processed_genes[:10] if len(processed_genes) > 10 else processed_genes  # 只保留前10个用于日志
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "final_celltype": "未确定",
            "total_iterations": 0,
            "analysis_log": [],
            "gene_count": len(processed_genes),
            "tissue_type": tissue_type
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


def analyze_genes_sync(
    gene_list: Union[List[str], str, Path],
    tissue_type: str = "骨髓",
    **kwargs
) -> Dict[str, Any]:
    """
    同步版本的基因分析函数

    为不使用 async/await 的用户提供的便利接口。

    Args:
        gene_list: 基因列表
        tissue_type: 目标组织类型
        **kwargs: 其他参数，传递给 analyze_genes

    Returns:
        Dict[str, Any]: 分析结果
    """
    return asyncio.run(analyze_genes(gene_list, tissue_type, **kwargs))


async def get_cache_status() -> Dict[str, Any]:
    """
    获取 SubAgent 缓存状态

    Returns:
        Dict[str, Any]: 缓存状态信息
    """
    try:
        cache_dir = init_cache()
        cache_info = get_cache_info()

        return {
            "cache_dir": str(cache_dir),
            "cache_info": cache_info,
            "success": True
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "cache_dir": None,
            "cache_info": {}
        }


# 为向后兼容保留的别名
celltype_analysis = analyze_genes
celltype_analysis_sync = analyze_genes_sync