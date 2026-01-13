#!/usr/bin/env python3
"""
agentype - 批量分析CSV中簇的细胞亚型
Author: cuilei
Version: 1.0
"""

import asyncio
import csv
import gc
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional


# 导入依赖模块


# 初始化统一缓存系统（必须在其他导入之前）
from agentype.subagent import init_cache

from agentype.subagent.agent.celltype_react_agent import CellTypeReactAgent
from agentype.subagent.config.settings import ConfigManager
from agentype.subagent.utils.i18n import _


async def analyze_clusters_from_csv(
    csv_path: str,
    tissue_type: str = None,
    max_genes_per_cluster: int = 20,
    unique_genes: bool = True,
    output_dir: Optional[str] = None,
) -> Dict[str, Dict]:
    """批量分析CSV文件中每个簇的细胞亚型"""

    print("🧬 准备批量分析簇细胞亚型")
    csv_path = Path(csv_path).expanduser().resolve()
    if not csv_path.exists():
        raise FileNotFoundError(f"未找到CSV文件: {csv_path}")

    cluster_genes: Dict[str, List[tuple]] = defaultdict(list)
    with csv_path.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required_columns = {"cluster", "gene", "avg_log2FC"}
        missing_columns = required_columns - set(reader.fieldnames or [])
        if missing_columns:
            raise ValueError(f"CSV缺少必要列: {', '.join(sorted(missing_columns))}")

        for row in reader:
            cluster_id = (row.get("cluster") or "").strip().strip('"')
            gene_name = (row.get("gene") or "").strip()
            if not cluster_id or not gene_name:
                continue
            try:
                avg_log2fc = float(row.get("avg_log2FC") or 0.0)
            except ValueError:
                avg_log2fc = 0.0

            cluster_genes[cluster_id].append((avg_log2fc, gene_name))

    if not cluster_genes:
        raise ValueError(f"未在CSV中解析到任何簇的marker基因: {csv_path}")

    if output_dir:
        output_dir = Path(output_dir).expanduser().resolve()
    else:
        output_dir = csv_path.with_name(f"{csv_path.stem}_celltype_results")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"📄 数据文件: {csv_path}")
    print(f"📊 检测到 {len(cluster_genes)} 个簇")
    if tissue_type:
        print(f"🏥 组织类型提示: {tissue_type}")

    cache_dir = init_cache()
    print(f"📂 缓存目录已初始化: {cache_dir}")

    # config = ConfigManager(
    #     openai_api_base="https://api.siliconflow.cn/v1",
    #     openai_api_key="sk-paypkckrtunjtcmrfagtmpqotnjrhcrhsmtpnsmwquxxvokd",
    #     openai_model="Pro/deepseek-ai/DeepSeek-V3",
    # )
    # config = ConfigManager(
    #     openai_api_base="https://api.siliconflow.cn/v1",
    #     openai_api_key="sk-paypkckrtunjtcmrfagtmpqotnjrhcrhsmtpnsmwquxxvokd",
    #     openai_model="Pro/deepseek-ai/DeepSeek-R1",
    # )

    config = ConfigManager(
        openai_api_base="https://40-3.chatgptsb.net/v1",
        openai_api_key="sk-jJ9HlkirHejAw8OA787c7295179a464fBf41D827CeE9Ae84",
        openai_model="gpt-5",
    )
    

    agent = CellTypeReactAgent(
        config=config,
        language="zh",
        enable_streaming=False,
    )

    results: Dict[str, Dict] = {}

    try:
        print("🚀 初始化 Agent...")
        if not await agent.initialize():
            print(_("agent.init_failed"))
            return results

        for cluster_id in sorted(cluster_genes, key=lambda x: (int(x) if x.isdigit() else x)):
            gene_records = sorted(cluster_genes[cluster_id], key=lambda item: item[0], reverse=True)

            ordered_genes: List[str] = []
            seen = set()
            for _, gene_name in gene_records:
                if unique_genes and gene_name in seen:
                    continue
                ordered_genes.append(gene_name)
                seen.add(gene_name)
                if len(ordered_genes) >= max_genes_per_cluster:
                    break

            if not ordered_genes:
                print(f"⚠️ 簇 {cluster_id} 未找到有效基因，跳过")
                continue

            gene_list = ",".join(ordered_genes)
            print("\n" + "-" * 40)
            print(f"🧾 正在分析簇 {cluster_id}")
            print(f"🧬 使用基因({len(ordered_genes)}): {gene_list}")

            result = await agent.analyze_celltype(gene_list, tissue_type=tissue_type, cell_type="Monocyte或Neutrophil")

            cluster_payload = {
                "cluster_id": cluster_id,
                "genes": ordered_genes,
                "result": result,
            }
            results[cluster_id] = cluster_payload

            safe_cluster_id = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in cluster_id)
            cluster_file = output_dir / f"cluster_{safe_cluster_id}.json"
            with cluster_file.open("w", encoding="utf-8") as f:
                json.dump(cluster_payload, f, ensure_ascii=False, indent=2)
            print(f"💾 簇 {cluster_id} 结果已保存至: {cluster_file}")

            final_celltype = result.get("final_celltype")
            if final_celltype:
                print(f"✅ 簇 {cluster_id} 推断细胞亚型: {final_celltype}")
            else:
                print(f"❔ 簇 {cluster_id} 未能确定最终细胞亚型")

    finally:
        await agent.cleanup()
        await asyncio.sleep(0.5)
        gc.collect()
        await asyncio.sleep(0.2)

    summary_path = output_dir / "summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n💾 汇总结果已保存至: {summary_path}")
    print("🎉 所有簇分析完成！")
    return results


async def main():
    csv_path = "/root/code/gitpackage/agentype/utils/alm.csv"
    tissue_type = "骨髓"
    await analyze_clusters_from_csv(csv_path, tissue_type=tissue_type)


if __name__ == "__main__":
    asyncio.run(main())
