#!/usr/bin/env python3
"""
agentype - 内容处理器基类
Author: cuilei
Version: 2.0

所有Agent内容处理器的共享逻辑，提供统一的内容处理策略。
子类可以重写特定方法实现Agent特有的处理逻辑。
"""

import json
import asyncio
from typing import Optional, Callable, Dict, Any
from agentype.prompts import get_prompt_manager


class BaseContentProcessor:
    """内容处理器基类 - 所有Agent内容处理器的共享逻辑"""

    def __init__(self, max_content_length: int = 30000, enable_summarization: bool = True):
        """初始化内容处理器

        Args:
            max_content_length: 最大内容长度阈值（默认30000字符）
            enable_summarization: 是否启用LLM摘要功能
        """
        self.max_content_length = max_content_length
        self.enable_summarization = enable_summarization

    def truncate_content(self, content: str) -> str:
        """智能清理内容（不截断长度，只清理JSON空字段）

        子类可以重写此方法实现自己的清理策略

        Args:
            content: 原始内容

        Returns:
            清理后的内容（保持完整长度）
        """
        # 优先处理 JSON 数据，删除无用的空字段
        if content.strip().startswith('{') or content.strip().startswith('['):
            try:
                parsed = json.loads(content)
                cleaned = self._clean_json_data(parsed)
                return json.dumps(cleaned, separators=(',', ':'), ensure_ascii=False)
            except:
                pass

        # 非JSON数据直接返回原内容（不截断）
        return content

    async def process_tool_result_content(self,
                                        content: str,
                                        openai_client: Optional[Callable] = None,
                                        language: str = "zh",
                                        tool_name: str = None,
                                        tool_params: dict = None,
                                        mcp_client = None) -> str:
        """处理工具返回内容（共享核心流程）

        根据内容长度自动选择处理策略：
        1. 长度OK -> 保持原样
        2. 长度过长 -> 尝试减少数据量
        3. 减少失败 -> LLM摘要（如果内容>30000）
        4. 摘要失败 -> 保持原内容完整性

        Args:
            content: 工具返回的原始内容
            openai_client: LLM客户端（用于摘要）
            language: 语言设置
            tool_name: 工具名称
            tool_params: 工具参数
            mcp_client: MCP客户端（用于重新调用工具）

        Returns:
            处理后的内容
        """
        # 只做JSON清理，不截断长度
        content = self.truncate_content(content)
        content_length = len(content)

        if content_length <= self.max_content_length:
            print(f"✅ 内容长度OK: {content_length}")
            return content
        else:
            print(f"⚠️ 内容过长: {content_length}")

            # 🔍 扩展点：尝试减少数据内容
            if self._should_reduce_content(tool_name, content_length, tool_params, mcp_client):
                print("🔄 尝试减少数据内容")
                reduced_content = await self._reduce_data_content(content, tool_params, mcp_client, tool_name)
                if reduced_content:
                    print(f"✅ 内容减少成功，新长度: {len(reduced_content)}")
                    return reduced_content
                else:
                    print("❌ 内容减少失败")

            # 如果数据减少失败或不适用，尝试摘要或保持原内容
            if self.enable_summarization and content_length > 30000 and openai_client:
                print("📝 生成内容摘要")
                return await self._summarize_content(content, openai_client, language=language)
            else:
                print("📏 保持内容完整性，返回原内容")
                return content

    def _should_reduce_content(self, tool_name: str, content_length: int,
                              tool_params: dict, mcp_client) -> bool:
        """判断是否应该减少内容（扩展点）

        子类可以重写此方法定义自己的减少条件。
        例如：
        - SubAgent: 针对get_gene_info工具
        - MainAgent/DataAgent: 针对数据处理工具

        Args:
            tool_name: 工具名称
            content_length: 内容长度
            tool_params: 工具参数
            mcp_client: MCP客户端

        Returns:
            是否应该尝试减少内容
        """
        return False  # 默认不减少

    async def _reduce_data_content(self, content: str, tool_params: dict,
                                  mcp_client, tool_name: str) -> Optional[str]:
        """减少数据内容（扩展点）

        子类可以重写此方法实现自己的减少策略。
        例如：
        - SubAgent: 减少基因数量并重新调用get_gene_info
        - DataAgent: 减少处理的行数或基因数

        Args:
            content: 原始内容
            tool_params: 工具参数
            mcp_client: MCP客户端
            tool_name: 工具名称

        Returns:
            减少后的内容，失败返回None
        """
        return None  # 默认不减少

    async def _summarize_content(self, content: str, openai_client: Callable,
                                max_summary_length: int = 2000,
                                language: str = "zh") -> str:
        """使用LLM对内容进行摘要（共享逻辑，带重试和验证机制）

        最多重试3次，使用指数退避策略。

        Args:
            content: 原始内容
            openai_client: LLM客户端
            max_summary_length: 最大摘要长度
            language: 语言设置

        Returns:
            摘要内容（失败则返回原内容）
        """
        max_retries = 3

        for attempt in range(max_retries):
            try:
                # 构建摘要prompt
                if language == "zh":
                    manager = get_prompt_manager('zh')
                    template = manager.get_common_prompt('CONTENT_SUMMARY_PROMPT')
                else:
                    manager = get_prompt_manager('en')
                    template = manager.get_common_prompt('CONTENT_SUMMARY_PROMPT_EN')

                summarization_prompt = template.format(
                    max_length=max_summary_length,
                    content=content
                )

                messages = [{"role": "user", "content": summarization_prompt}]
                summary = await openai_client(messages)

                # 验证摘要是否成功生成
                if summary and len(summary.strip()) > 0:
                    # 摘要过长也不截断，保持完整
                    print(f"✅ 摘要生成成功 (尝试 {attempt + 1}/{max_retries})")
                    return summary
                else:
                    print(f"⚠️ 摘要为空，重试 ({attempt + 1}/{max_retries})")

            except Exception as e:
                print(f"❌ 摘要生成失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # 指数退避：2秒、4秒

        # 所有重试失败，返回原内容（不截断）
        print(f"❌ 摘要生成失败（已重试{max_retries}次），返回原内容")
        return content

    def _clean_json_data(self, data):
        """递归清理JSON数据，删除无用的空字段（共享工具方法）

        Args:
            data: 原始JSON数据

        Returns:
            清理后的JSON数据
        """
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
        """判断字段是否为无用的空字段（共享工具方法）

        Args:
            value: 字段值

        Returns:
            是否为空字段
        """
        if value == "" or value == []:
            return True
        if isinstance(value, list) and all(item == "" for item in value):
            return True
        if isinstance(value, dict) and len(value) == 0:
            return True
        return False

    def format_tool_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """格式化工具响应（共享工具方法）

        Args:
            response: 原始响应

        Returns:
            格式化后的响应
        """
        if not response:
            return {"success": False, "error": "空响应"}

        # 处理content字段
        if "content" in response:
            response["content"] = self.process_content(str(response["content"]))

        return response

    def process_content(self, content: str, content_type: str = "text") -> str:
        """处理内容（简化版本，不截断长度）

        Args:
            content: 原始内容
            content_type: 内容类型

        Returns:
            处理后的内容（保持完整）
        """
        if not content:
            return ""

        # 直接返回原内容，不截断
        return content

    def _summarize_content_simple(self, content: str) -> str:
        """内容摘要（简化版，不使用LLM）

        Args:
            content: 原始内容

        Returns:
            摘要内容
        """
        # 简化的摘要逻辑：取开头和结尾
        if len(content) <= self.max_content_length:
            return content

        half_length = self.max_content_length // 2 - 50
        summary = (
            content[:half_length] +
            "\n\n...[中间内容已省略]...\n\n" +
            content[-half_length:]
        )
        return summary

    def extract_json_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        """从文本中提取JSON（共享工具方法）

        Args:
            text: 包含JSON的文本

        Returns:
            提取的JSON对象，失败返回None
        """
        try:
            # 尝试直接解析
            return json.loads(text)
        except json.JSONDecodeError:
            # 尝试提取代码块中的JSON
            import re
            json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
            match = re.search(json_pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass

            # 尝试找到第一个完整的JSON对象
            start = text.find('{')
            if start >= 0:
                bracket_count = 0
                for i, char in enumerate(text[start:], start):
                    if char == '{':
                        bracket_count += 1
                    elif char == '}':
                        bracket_count -= 1
                        if bracket_count == 0:
                            try:
                                return json.loads(text[start:i+1])
                            except json.JSONDecodeError:
                                break

            return None
