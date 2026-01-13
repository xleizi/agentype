#!/usr/bin/env python3
"""
agentype - DataProcessor Agent 使用示例
Author: cuilei
Version: 1.0
"""

import asyncio
import gc
import sys
import os
from pathlib import Path

# 添加项目路径
current_dir = Path(__file__).resolve().parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

# 初始化统一缓存系统（必须在其他导入之前）
from agentype.dataagent.config.cache_config import init_cache

from agentype.dataagent.config.settings import ConfigManager
from agentype.dataagent.agent.data_processor_agent import DataProcessorReactAgent
from agentype.dataagent.utils.i18n import _

async def example_usage():
    """使用示例"""
    # 初始化统一缓存系统
    cache_dir = init_cache()
    print(f"📂 缓存目录已初始化: {cache_dir}")

    print("🧬 CellType DataProcessor Agent 使用示例")
    print("=" * 60)
    print(f"📂 统一缓存目录: {cache_dir}")
    print("-" * 60)
    
    config = ConfigManager(
        openai_api_base="https://api.siliconflow.cn/v1",
        openai_api_key="sk-paypkckrtunjtcmrfagtmpqotnjrhcrhsmtpnsmwquxxvokd",
        openai_model="Pro/deepseek-ai/DeepSeek-V3",
    )
    
    agent = DataProcessorReactAgent(
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

        # 测试数据处理 - 使用示例数据文件路径
        # test_data_file = "/root/code/gitpackage/agentype/utils/sce.rds"  # 示例RDS文件，成功
        # test_data_file = "/root/code/gitpackage/agentype/utils/data.h5"  # 示例H5文件，成功
        test_data_file = "/root/code/gitpackage/agentype/utils/data.h5ad"  # 示例H5AD文件，成功
        # test_data_file = "/root/code/gitpackage/agentype/utils/.agentype_cache/cluster_marker_genes.json"  # 示例json文件
        # test_data_file = ["/root/code/gitpackage/agentype/utils/.agentype_cache/cluster_marker_genes.json", "/root/code/gitpackage/agentype/utils/sce.rds"] # 示例json文件和RDS文件
        # test_data_file = "/root/code/gitpackage/agentype/utils/alm.csv"
        # import scanpy as sc
        # test_data_file = sc.read_h5ad("/root/code/gitpackage/agentype/utils/data.h5ad") # 示例adata

        result = await agent.process_data(test_data_file)

        print(f"✅ 处理文件路径: {result.get('output_file_paths')}")

        print("")
        print("📊 处理统计信息:")
        print(f"   - 总迭代数: {result.get('total_iterations')}")
        print(f"   - 工具调用次数: {len([log for log in result.get('analysis_log', []) if log.get('type') == 'tool_call'])}")
        print(f"   - 处理成功: {result.get('success')}")
        
    finally:
        await agent.cleanup()

        # 给异步清理过程额外时间以完成所有资源释放
        await asyncio.sleep(0.5)

        # 强制垃圾回收，清理所有未引用的对象
        gc.collect()

        # 最后一次延迟确保垃圾回收完全完成
        await asyncio.sleep(0.2)

    print("")
    print("🎉 处理完成！")

if __name__ == "__main__":
    asyncio.run(example_usage())