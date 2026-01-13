#!/usr/bin/env python3
"""
agentype - SubAgent内容处理器
Author: cuilei
Version: 2.0

SubAgent的内容处理器，继承基类并添加基因信息减少逻辑。
"""

import json
from typing import Optional
from agentype.common.base_content_processor import BaseContentProcessor
from agentype.subagent.config.prompts import DEFAULT_LANGUAGE


class ContentProcessor(BaseContentProcessor):
    """SubAgent内容处理器

    继承BaseContentProcessor并添加：
    1. JSON清理逻辑（重写truncate_content）
    2. get_gene_info工具的基因数量减少策略
    """

    def truncate_content(self, content: str) -> str:
        """智能清理内容，优先处理JSON数据（重写基类方法）

        Args:
            content: 原始内容

        Returns:
            清理后的内容
        """
        # 优先处理 JSON 数据，删除无用的空字段
        if content.strip().startswith('{') or content.strip().startswith('['):
            try:
                parsed = json.loads(content)
                cleaned = self._clean_json_data(parsed)
                return json.dumps(cleaned, separators=(',', ':'), ensure_ascii=False)
            except:
                pass

        # 非JSON数据直接返回原内容
        return content

    def _should_reduce_content(self, tool_name: str, content_length: int,
                              tool_params: dict, mcp_client) -> bool:
        """判断是否应该减少内容（SubAgent特有逻辑）

        SubAgent特殊处理get_gene_info工具。

        Args:
            tool_name: 工具名称
            content_length: 内容长度
            tool_params: 工具参数
            mcp_client: MCP客户端

        Returns:
            是否应该尝试减少内容
        """
        return (tool_name == "get_gene_info" and
                content_length > 20000 and
                mcp_client and
                tool_params)

    async def _reduce_data_content(self, content: str, tool_params: dict,
                                  mcp_client, tool_name: str) -> Optional[str]:
        """减少数据内容（SubAgent特有逻辑）

        对于get_gene_info工具，减少基因数量并重新调用。

        Args:
            content: 原始内容
            tool_params: 工具参数
            mcp_client: MCP客户端
            tool_name: 工具名称

        Returns:
            减少后的内容，失败返回None
        """
        if tool_name == "get_gene_info":
            return await self._reduce_gene_info_content(content, tool_params, mcp_client)
        return None

    async def _reduce_gene_info_content(self, content: str, tool_params: dict,
                                       mcp_client) -> Optional[str]:
        """减少get_gene_info的基因数量并重新调用（SubAgent特有方法）

        Args:
            content: 原始内容
            tool_params: 工具参数
            mcp_client: MCP客户端

        Returns:
            减少后的内容，失败返回None
        """
        try:
            # 从工具参数中获取基因列表
            gene_ids = tool_params.get('gene_ids', '')

            if not gene_ids:
                return None

            # 解析基因列表
            if isinstance(gene_ids, str):
                gene_list = [g.strip() for g in gene_ids.split(',') if g.strip()]
            else:
                gene_list = list(gene_ids)

            if len(gene_list) <= 3:  # 如果已经很少了，不再减少
                print("🚫 基因数量已经很少，无法进一步减少")
                return None

            # 减少到原来的一半，但至少保留3个
            new_count = max(3, len(gene_list) // 2)
            reduced_gene_list = gene_list[:new_count]
            reduced_gene_ids = ','.join(reduced_gene_list)

            print(f"🔄 减少基因数量: {len(gene_list)} -> {new_count}")
            print(f"📋 保留的基因: {reduced_gene_ids}")

            # 构造新的参数
            new_params = tool_params.copy()
            new_params['gene_ids'] = reduced_gene_ids
            new_params['max_genes'] = new_count

            # 重新调用工具
            tool_result = await mcp_client.call_tool("get_gene_info", new_params)

            if tool_result and tool_result.get("success"):
                new_content = tool_result.get("content", "")
                print(f"✅ 重新调用成功，新内容长度: {len(new_content)}")

                # 添加说明信息
                try:
                    result_data = json.loads(new_content)
                    if isinstance(result_data, dict) and result_data.get("success"):
                        result_data["_note"] = f"由于原始结果过长，已自动减少基因数量从 {len(gene_list)} 个到 {new_count} 个"
                        result_data["_original_gene_count"] = len(gene_list)
                        result_data["_reduced_gene_count"] = new_count
                        return json.dumps(result_data, ensure_ascii=False, indent=2)
                except:
                    # 如果JSON解析失败，直接添加文本说明
                    note = f"\n\n注意: 由于原始结果过长，已自动减少基因数量从 {len(gene_list)} 个到 {new_count} 个"
                    return new_content + note

                return new_content
            else:
                print("❌ 重新调用失败")
                return None

        except Exception as e:
            print(f"❌ 减少基因数量时出错: {e}")
            return None
