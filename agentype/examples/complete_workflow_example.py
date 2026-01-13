#!/usr/bin/env python3
"""
AgentType 完整工作流示例

展示最简单的使用方式 - 使用 process_workflow_sync 处理单个文件
"""

import json
from pathlib import Path
from agentype.api.main_workflow import process_workflow_sync


def load_config(config_path="./agentype_config.json"):
    """从配置文件加载配置

    如果不存在，请复制 agentype_config.example.json 并修改
    """
    config_file = Path(config_path)

    if not config_file.exists():
        print(f"❌ 配置文件不存在: {config_path}")
        print("请复制 agentype_config.example.json 为 agentype_config.json")
        print("并填入您的 API key")
        return None

    with open(config_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    """主函数"""
    print("="*60)
    print("AgentType 完整工作流示例")
    print("="*60)

    # 1. 加载配置
    config = load_config()
    if not config:
        return

    # 2. 准备数据文件路径（请修改为您的实际路径）
    input_file = "your_data.rds"  # 支持 RDS, H5AD, H5 等
    tissue_type = "PBMC"
    cluster_column = "seurat_clusters"

    print(f"\n处理文件: {input_file}")
    print(f"组织类型: {tissue_type}")
    print(f"聚类列: {cluster_column}\n")

    # 3. 调用完整工作流
    result = process_workflow_sync(
        input_data=input_file,
        tissue_type=tissue_type,
        cluster_column=cluster_column,
        # LLM 配置
        api_key=config["llm"]["api_key"],
        api_base=config["llm"]["api_base"],
        model=config["llm"]["model"],
        # 项目配置
        output_dir="./outputs",
        language=config["project"]["language"],
        enable_streaming=config["project"]["enable_streaming"],
        enable_llm_logging=config["project"]["enable_logging"]
    )

    # 4. 处理结果
    if result['success']:
        print("\n✅ 处理成功！")
        print(f"Session ID: {result['session_id']}")
        print(f"总迭代次数: {result.get('total_iterations', 0)}")
        print(f"结果文件: {result['result_file']}")

        # 输出文件路径
        output_files = result.get('output_file_paths', {})
        if output_files:
            print("\n📁 生成的文件：")
            for key, path in output_files.items():
                print(f"  • {key}: {path}")

        # Token 统计
        token_stats = result.get('token_stats', {})
        if token_stats and 'total' in token_stats:
            total_tokens = token_stats['total'].get('total_tokens', 0)
            print(f"\n💰 Token 使用: {total_tokens:,}")
    else:
        print("\n❌ 处理失败")
        print(f"错误: {result.get('error', '未知错误')}")


if __name__ == "__main__":
    main()
