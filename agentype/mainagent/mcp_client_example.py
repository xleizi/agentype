#!/usr/bin/env python3
"""
agentype - MainAgent 使用示例
Author: cuilei
Version: 1.0
"""

import asyncio
import gc
import sys
from pathlib import Path


# 获取项目目录
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent  # celltype-mcp-server


# MainAgent 依赖
from agentype.mainagent.config.cache_config import init_cache
from agentype.mainagent.config.settings import ConfigManager
from agentype.mainagent.agent.main_react_agent import MainReactAgent


async def example_usage():
    # 初始化统一缓存系统
    cache = init_cache()
    print(f"📂 缓存目录已初始化: {cache.cache_dir}")

    # 简单的输出（与其它示例保持相同风格）
    print("🧬 CellType MainAgent 使用示例")

    # OpenAI/兼容 API 配置（示例）
    config = ConfigManager(
        openai_api_base="https://api.siliconflow.cn/v1",
        openai_api_key="sk-paypkckrtunjtcmrfagtmpqotnjrhcrhsmtpnsmwquxxvokd",
        openai_model="Pro/deepseek-ai/DeepSeek-V3",
    )


    agent = MainReactAgent(
        config=config,
        language="zh",
        enable_streaming=True,
    )

    # 使用指定测试文件与组织类型（示例）
    test_data_file = "/root/code/gitpackage/agentype/utils/sce.rds"
    test_tissue = "骨髓"

    try:
        print("🚀 初始化 Agent…")
        if not await agent.initialize():
            print("初始化失败")
            return

        # 调用主工作流（传入RDS路径与组织类型）
        result = await agent.process_with_llm_react(input_data=test_data_file, tissue_type=test_tissue)

        # 输出摘要
        print(f"✅ 执行完成，是否成功: {result.get('success')}")
        # 打印关键摘要
        print(f"🧬 输入组织: {test_tissue}")
        print(f"📏 迭代次数: {result.get('total_iterations')}")
        if result.get("output_file_paths"):
            print(f"📁 输出路径键: {', '.join([k for k, v in result['output_file_paths'].items() if v])}")

    finally:
        # 清理资源
        await agent.cleanup()
        await asyncio.sleep(0.5)
        gc.collect()
        await asyncio.sleep(0.2)

        # 导出日志文件位置（若可用）
        try:
            export_path = logger.export_logs()
            if export_path:
                print(f"📄 完整日志: {export_path}")
        except Exception:
            pass

    print("🎉 示例运行完成！")


if __name__ == "__main__":
    asyncio.run(example_usage())
