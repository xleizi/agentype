#!/usr/bin/env python3
"""
agentype - MainAgent内容处理器
Author: cuilei
Version: 2.0

MainAgent的内容处理器，继承基类并添加数据处理工具减少逻辑。
"""

import json
from typing import Optional
from agentype.common.base_content_processor import BaseContentProcessor


class ContentProcessor(BaseContentProcessor):
    """MainAgent内容处理器

    继承BaseContentProcessor并添加：
    1. 数据处理工具的减少策略
    """

    def _should_reduce_content(self, tool_name: str, content_length: int,
                              tool_params: dict, mcp_client) -> bool:
        """判断是否应该减少内容（MainAgent特有逻辑）

        MainAgent特殊处理数据处理相关工具。

        Args:
            tool_name: 工具名称
            content_length: 内容长度
            tool_params: 工具参数
            mcp_client: MCP客户端

        Returns:
            是否应该尝试减少内容
        """
        reduction_tools = [
            "process_rds_file",
            "convert_csv_to_json",
            "process_h5_file",
            "process_adata_path",
            "enhanced_data_processing",
            "main_process_data_tool"
        ]
        return (tool_name in reduction_tools and
                content_length > 20000 and
                mcp_client and
                tool_params)

    async def _reduce_data_content(self, content: str, tool_params: dict,
                                  mcp_client, tool_name: str) -> Optional[str]:
        """减少数据处理的内容量并重新调用（MainAgent特有逻辑）

        Args:
            content: 原始内容
            tool_params: 工具参数
            mcp_client: MCP客户端
            tool_name: 工具名称

        Returns:
            减少后的内容，失败返回None
        """
        try:
            # 根据不同工具类型采用不同的减少策略
            if tool_name in ["process_rds_file", "process_h5_file", "process_adata_path",
                           "enhanced_data_processing", "main_process_data_tool"]:
                return await self._reduce_gene_processing_output(content, tool_params, mcp_client, tool_name)
            elif tool_name == "convert_csv_to_json":
                return await self._reduce_csv_processing_output(content, tool_params, mcp_client, tool_name)

            return None

        except Exception as e:
            print(f"内容减少出错: {e}")
            return None

    async def _reduce_gene_processing_output(self, content: str, tool_params: dict,
                                           mcp_client, tool_name: str) -> Optional[str]:
        """减少基因处理输出的内容量（MainAgent特有方法）

        Args:
            content: 原始内容
            tool_params: 工具参数
            mcp_client: MCP客户端
            tool_name: 工具名称

        Returns:
            减少后的内容，失败返回None
        """
        try:
            # 尝试从内容中解析结果，并减少基因数量
            result_data = json.loads(content)

            if not isinstance(result_data, dict) or not result_data.get("success"):
                return None

            # 检查是否有基因相关的数据可以减少
            genes_data = result_data.get("genes", [])
            marker_genes = result_data.get("marker_genes", [])

            if len(genes_data) > 10:
                # 减少基因数量到前10个
                result_data["genes"] = genes_data[:10]
                result_data["_note"] = f"基因数据已减少（原始: {len(genes_data)}，减少到: 10）"
                return json.dumps(result_data, ensure_ascii=False, indent=2)

            if len(marker_genes) > 5:
                # 减少标记基因到前5个
                result_data["marker_genes"] = marker_genes[:5]
                result_data["_note"] = f"Marker基因数据已减少（原始: {len(marker_genes)}，减少到: 5）"
                return json.dumps(result_data, ensure_ascii=False, indent=2)

            return None

        except Exception as e:
            print(f"基因处理输出减少失败: {e}")
            return None

    async def _reduce_csv_processing_output(self, content: str, tool_params: dict,
                                          mcp_client, tool_name: str) -> Optional[str]:
        """减少CSV处理输出的内容量（MainAgent特有方法）

        Args:
            content: 原始内容
            tool_params: 工具参数
            mcp_client: MCP客户端
            tool_name: 工具名称

        Returns:
            减少后的内容，失败返回None
        """
        try:
            # 解析CSV转换结果，减少行数
            result_data = json.loads(content)

            if not isinstance(result_data, dict) or not result_data.get("success"):
                return None

            # 检查是否有可以减少的数据行
            data = result_data.get("data", [])
            if len(data) > 100:
                result_data["data"] = data[:100]
                result_data["_note"] = f"CSV数据已减少（原始: {len(data)}行，减少到: 100行）"
                return json.dumps(result_data, ensure_ascii=False, indent=2)

            return None

        except Exception as e:
            print(f"CSV减少处理失败: {e}")
            return None
