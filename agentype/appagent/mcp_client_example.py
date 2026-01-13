#!/usr/bin/env python3
"""
agentype - App Agent 使用示例（统一查询模板 + 指定组织/物种）
Author: cuilei
Version: 1.0
"""

import asyncio
import gc
import sys
from pathlib import Path

# 将项目根目录加入 Python 路径
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

from agentype.appagent.config import init_cache
from agentype.appagent.config.settings import ConfigManager
from agentype.appagent.agent.celltype_annotation_agent import CelltypeAnnotationAgent
from agentype.appagent.config.prompts import build_unified_user_query


async def example_usage():
    # 初始化缓存
    cache_dir = init_cache()

    print("🧬 CellType App Agent 使用示例")
    print(f"📂 缓存目录: {cache_dir}")

    # OpenAI/兼容 API 配置（示例）
    config = ConfigManager(
        openai_api_base="https://api.siliconflow.cn/v1",
        openai_api_key="sk-paypkckrtunjtcmrfagtmpqotnjrhcrhsmtpnsmwquxxvokd",
        openai_model="Pro/deepseek-ai/DeepSeek-V3",
    )

    agent = CelltypeAnnotationAgent(
        config=config,
        language="zh",
        enable_streaming=True,
    )

    # 测试输入（来自用户提供）
    file_paths = {
        'rds_file': None,
        'h5ad_file': '/root/code/gitpackage/agentype/utils/data.h5ad',
        'h5_file': '/root/code/gitpackage/agentype/utils/.agentype_cache/data_20250915_013359.h5',
        'marker_genes_json': '/root/code/gitpackage/agentype/utils/.agentype_cache/cluster_marker_genes_20250915_013359.json',
    }
    tissue = '骨髓'   # 默认可为空，业务默认"免疫系统"
    species = 'Mouse'  # 可为空，业务默认 Human
    cluster_column = 'seurat_clusters'

    # 展示统一查询（便于确认 prompt 内容）
    unified_query = build_unified_user_query(
        file_paths=file_paths,
        tissue_description=tissue,
        species=species,
        language='zh',
        cluster_column=cluster_column,
    )
    print("📝 统一查询预览：")
    print(unified_query)

    try:
        print("🚀 初始化 MCP/Agent...")
        if not await agent.initialize():
            print("Agent 初始化失败")
            return

        # 使用统一模板字段调用注释（React 循环）
        result = await agent.annotate(
            rds_path=file_paths['rds_file'],
            h5ad_path=file_paths['h5ad_file'],
            h5_path=file_paths['h5_file'],
            marker_json_path=file_paths['marker_genes_json'],
            tissue_description=tissue,
            species=species,
            cluster_column=cluster_column,
        )

        # 输出摘要
        print(f"✅ 执行完成，是否成功: {result.get('success')}")
        print(f"   - 迭代次数: {result.get('total_iterations')}")
        print(f"   - 工具调用次数: {len([x for x in result.get('analysis_log', []) if x.get('type')=='tool_call'])}")

        # 解析的输出文件路径（若 LLM 在 <final_answer> 之后提供了 <file_paths>）
        out_paths = result.get('output_file_paths') or {}
        if out_paths:
            print("📁 解析出的文件路径：")
            for k, v in out_paths.items():
                print(f"- {k}: {v}")

    finally:
        await agent.cleanup()
        await asyncio.sleep(0.3)
        gc.collect()
        await asyncio.sleep(0.1)

    print("🎉 示例运行完成！")


if __name__ == "__main__":
    asyncio.run(example_usage())
