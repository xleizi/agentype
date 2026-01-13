#!/usr/bin/env python3
"""
agentype - React Agent 使用示例
Author: cuilei
Version: 1.0
"""

import asyncio
import gc
import sys
from pathlib import Path

# 获取项目目录
current_dir = Path(__file__).resolve().parent
parent_dir = current_dir.parent


# 初始化统一缓存系统（必须在其他导入之前）
from agentype.subagent import init_cache

from agentype.subagent.config.settings import ConfigManager
from agentype.subagent.agent.celltype_react_agent import CellTypeReactAgent
from agentype.subagent.utils.file_utils import load_gene_list_from_file
from agentype.subagent.utils.i18n import _

async def example_usage():
    """使用示例"""
    # 初始化统一缓存系统
    cache_dir = init_cache()

    print("🧬 CellType React Agent 使用示例")
    print(f"📂 缓存目录已初始化: {cache_dir}")
    
    config = ConfigManager(
        openai_api_base="https://api.siliconflow.cn/v1",
        openai_api_key="sk-paypkckrtunjtcmrfagtmpqotnjrhcrhsmtpnsmwquxxvokd",
        openai_model="Pro/deepseek-ai/DeepSeek-V3",
    )
    
    agent = CellTypeReactAgent(
        config=config,
        # 移除硬编码路径，让Agent使用路径管理器的默认值
        # language="en",
        language="zh",
        enable_streaming=True,
    )
    
    try:
        print("🚀 初始化 Agent...")

        if not await agent.initialize():
            print(_("agent.init_failed"))
            return

        print(_("agent.analysis_start"))
        genes_file = "/root/code/gitpackage/agentype/utils/genes.txt"
        gene_list = load_gene_list_from_file(str(genes_file), max_genes=100)

        result = await agent.analyze_celltype(gene_list, tissue_type="骨髓")

        print(f"✅ 分析结果: {result.get('final_celltype')}")
        print("")
        print("📊 分析统计信息:")
        print(f"   - 总迭代数: {result.get('total_iterations')}")
        print(f"   - 工具调用次数: {len([log for log in result.get('analysis_log', []) if log.get('type') == 'tool_call'])}")
        print(f"   - 分析成功: {result.get('success')}")

    finally:
        await agent.cleanup()

        # 给异步清理过程额外时间以完成所有资源释放
        await asyncio.sleep(0.5)

        # 强制垃圾回收，清理所有未引用的对象
        gc.collect()

        # 最后一次延迟确保垃圾回收完全完成
        await asyncio.sleep(0.2)

    print("")
    print("🎉 分析完成！")

if __name__ == "__main__":
    asyncio.run(example_usage())
