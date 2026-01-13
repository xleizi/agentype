#!/usr/bin/env python3
"""
agentype - Content Processor模块
Author: cuilei
Version: 1.0
"""

import json
from typing import Optional, Callable, Dict, Any
from agentype.dataagent.utils.i18n import _

class ContentProcessor:
    """内容处理和优化工具类
    
    用于处理工具返回的大量内容，提供智能截断、摘要等功能
    """
    
    def __init__(self, max_content_length: int = 30000, enable_summarization: bool = True):
        self.max_content_length = max_content_length
        self.enable_summarization = enable_summarization
    
    def truncate_content(self, content: str) -> str:
        """智能清理内容，删除无用字符，保持完整性"""
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
    
    def _clean_json_data(self, data):
        """递归清理JSON数据，删除无用的空字符串字段"""
        if isinstance(data, dict):
            cleaned = {}
            for key, value in data.items():
                cleaned_value = self._clean_json_data(value)
                # 只保留有意义的字段
                if not self._is_empty_field(cleaned_value):
                    cleaned[key] = cleaned_value
            return cleaned
        elif isinstance(data, list):
            # 清理列表，删除空字符串
            cleaned_list = []
            for item in data:
                cleaned_item = self._clean_json_data(item)
                if not self._is_empty_field(cleaned_item):
                    cleaned_list.append(cleaned_item)
            return cleaned_list
        else:
            return data
    
    def _is_empty_field(self, value):
        """判断字段是否为无用的空字段"""
        if value == "" or value == []:
            return True
        if isinstance(value, list) and all(item == "" for item in value):
            return True
        if isinstance(value, dict) and len(value) == 0:
            return True
        return False
    
    async def process_tool_result_content(self,
                                        content: str,
                                        openai_client: Optional[Callable] = None,
                                        language: str = "zh_CN",
                                        tool_name: str = None,
                                        tool_params: dict = None,
                                        mcp_client=None) -> str:
        """处理工具返回内容，根据长度选择不同策略"""
        # 只做JSON清理，不截断长度
        content = self.truncate_content(content)
        content_length = len(content)

        if content_length <= self.max_content_length:
            print(_("content.length_ok", length=content_length))
            return content
        else:
            print(_("content.length_too_long", length=content_length))

            # 特殊处理数据处理工具的结果过长情况
            if self._should_reduce_content(tool_name, content_length, tool_params, mcp_client):
                print(_("content.reducing_data"))
                reduced_content = await self._reduce_data_content(content, tool_params, mcp_client, tool_name)
                if reduced_content:
                    print(_("content.reduction_success", length=len(reduced_content)))
                    return reduced_content
                else:
                    print(_("content.reduction_failed"))

            # 如果数据减少失败或不适用，尝试摘要或保持原内容
            if self.enable_summarization and content_length > 30000 and openai_client:
                print(_("content.generating_summary"))
                return await self._summarize_content(content, openai_client, language=language)
            else:
                print(_("content.keeping_integrity"))
                return content
    
    def _should_reduce_content(self, tool_name: str, content_length: int, tool_params: dict, mcp_client) -> bool:
        """判断是否应该减少内容"""
        # 针对数据处理相关的工具，如果内容过长，尝试减少处理的数据量
        reduction_tools = ["process_rds_file", "convert_csv_to_json", "process_h5_file", "process_adata_path"]
        return (tool_name in reduction_tools and 
                content_length > 20000 and 
                mcp_client and 
                tool_params)
    
    async def _reduce_data_content(self, content: str, tool_params: dict, mcp_client, tool_name: str) -> Optional[str]:
        """减少数据处理的内容量并重新调用"""
        try:
            # 根据不同工具类型采用不同的减少策略
            if tool_name in ["process_rds_file", "process_h5_file", "process_adata_path"]:
                # 这些工具通常处理基因数据，可以尝试限制输出的基因数量
                return await self._reduce_gene_processing_output(content, tool_params, mcp_client, tool_name)
            elif tool_name == "convert_csv_to_json":
                # CSV转换可以尝试限制处理的行数
                return await self._reduce_csv_processing_output(content, tool_params, mcp_client, tool_name)
            
            return None
                
        except Exception as e:
            print(_("content.reduction_error", error=str(e)))
            return None
    
    async def _reduce_gene_processing_output(self, content: str, tool_params: dict, mcp_client, tool_name: str) -> Optional[str]:
        """减少基因处理输出的内容量"""
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
                result_data["_note"] = _("content.gene_data_reduced", original=len(genes_data), reduced=10)
                return json.dumps(result_data, ensure_ascii=False, indent=2)
            
            if len(marker_genes) > 100:
                # 减少标记基因到前100个
                result_data["marker_genes"] = marker_genes[:100]
                result_data["_note"] = _("content.marker_genes_reduced", original=len(marker_genes), reduced=100)
                return json.dumps(result_data, ensure_ascii=False, indent=2)
            
            return None
                
        except Exception as e:
            print(_("content.gene_reduction_error", error=str(e)))
            return None
    
    async def _reduce_csv_processing_output(self, content: str, tool_params: dict, mcp_client, tool_name: str) -> Optional[str]:
        """减少CSV处理输出的内容量"""
        try:
            # 解析CSV转换结果，减少行数
            result_data = json.loads(content)
            
            if not isinstance(result_data, dict) or not result_data.get("success"):
                return None
            
            # 检查是否有可以减少的数据行
            marker_data = result_data.get("marker_genes", {})
            if isinstance(marker_data, dict):
                for cell_type, genes in marker_data.items():
                    if isinstance(genes, list) and len(genes) > 50:
                        # 每个细胞类型最多保留50个基因
                        marker_data[cell_type] = genes[:50]
                
                result_data["marker_genes"] = marker_data
                result_data["_note"] = _("content.csv_data_reduced")
                return json.dumps(result_data, ensure_ascii=False, indent=2)
            
            return None
                
        except Exception as e:
            print(_("content.csv_reduction_error", error=str(e)))
            return None
    
    async def _summarize_content(self, content: str, openai_client: Callable, max_summary_length: int = 2000, language: str = "zh_CN") -> str:
        """使用 LLM 对内容进行摘要，带重试和验证机制"""
        import asyncio
        max_retries = 3

        for attempt in range(max_retries):
            try:
                # 构建摘要prompt（简化版本，不依赖Sub项目的prompt系统）
                if language == "en_US":
                    summarization_prompt = f"""Please summarize the following content, retaining the most important information and data. The summary should:
1. Retain all key numerical values, gene names, cell types and other core information
2. Remove redundant descriptive text
3. Maintain clear structure
4. Keep within {max_summary_length} characters

Original content:
{content}

Please provide a concise summary:"""
                else:
                    summarization_prompt = f"""请对以下内容进行摘要，保留最重要的信息和数据。摘要应该：
1. 保留所有关键的数值、基因名称、细胞类型等核心信息
2. 去除冗余的描述性文字
3. 保持清晰的结构
4. 控制在{max_summary_length}字符以内

原始内容：
{content}

请提供简洁的摘要："""

                messages = [{"role": "user", "content": summarization_prompt}]
                summary = await openai_client(messages)

                # 验证摘要是否成功生成
                if summary and len(summary.strip()) > 0:
                    # 摘要过长也不截断，保持完整
                    print(f"✅ 摘要生成成功 (尝试 {attempt + 1}/{max_retries})")
                    return summary  # 直接返回摘要，移除前缀
                else:
                    print(f"⚠️ 摘要为空，重试 ({attempt + 1}/{max_retries})")

            except Exception as e:
                print(f"❌ 摘要生成失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # 指数退避：2秒、4秒

        # 所有重试失败，返回原内容（不截断）
        print(f"❌ 摘要生成失败（已重试{max_retries}次），返回原内容")
        return content