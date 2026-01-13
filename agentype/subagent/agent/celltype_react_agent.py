#!/usr/bin/env python3
"""
agentype - Celltype React Agent模块
Author: cuilei
Version: 1.0
"""

import asyncio
import gc
import json
import os
import re
import requests
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# Token统计模块
from agentype.common.token_statistics import TokenReporter

# 导入 prompts
from agentype.subagent.config.prompts import (
    SUPPORTED_LANGUAGES,
    DEFAULT_LANGUAGE,
    get_system_prompt_template,
    get_fallback_prompt_template,
    get_user_query_templates,
)

# 导入重构后的模块
from agentype.subagent.config.settings import ConfigManager
from agentype.subagent.clients.mcp_client import MCPClient
from agentype.subagent.utils.content_processor import ContentProcessor
from agentype.subagent.utils.parser import ReactParser
from agentype.subagent.utils.validator import ValidationUtils
from agentype.subagent.utils.i18n import _
from agentype.subagent.utils.path_manager import path_manager
from agentype.subagent.utils.output_logger import OutputLogger
# 导入共享模块
from agentype.common.llm_client import LLMClient
from agentype.common.llm_logger import LLMLogger
from agentype.common.streaming_filter import StreamingFilter

class CellTypeReactAgent:
    """细胞类型分析 React Agent
    
    该类是整个系统的核心，负责协调 MCP 客户端、内容处理器、
    验证工具等组件，执行完整的细胞类型分析流程。
    """
    
    def __init__(self,
                 config: ConfigManager,
                 server_script: str = None,
                 max_content_length: int = 10000,
                 enable_summarization: bool = True,
                 max_iterations: int = 50,
                 context_summary_threshold: int = 15,
                 max_context_length: int = 150000,
                 enable_llm_logging: bool = True,
                 log_dir: str = None,
                 language: str = "zh",
                 enable_streaming: bool = True,
                 api_timeout: int = 300,
                 enable_console_output: bool = True,
                 console_output: bool = None,
                 file_output: bool = None,
                 session_id: str = None):

        # 🌟 设置 session_id（如果提供）
        # 注意：在MCP模式下，session_id已在MCP Server启动时设置，此处不再重复打印
        if session_id:
            from agentype.mainagent.config.session_config import set_session_id
            set_session_id(session_id)

        # 组件初始化
        self.config = config
        # 如果没有指定server_script，使用路径管理器获取默认路径
        if server_script is None:
            server_script = str(path_manager.get_mcp_server_path())
        self.mcp_client = MCPClient(server_script, config=self.config)
        self.content_processor = ContentProcessor(max_content_length, enable_summarization)
        self.parser = ReactParser()
        self.validator = ValidationUtils()
        
        # 语言设置
        self.language = language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
        
        # LLM 日志记录器
        self.enable_llm_logging = enable_llm_logging
        if enable_llm_logging:
            # 如果没有指定log_dir，使用 ConfigManager 的日志目录
            if log_dir is None:
                from pathlib import Path
                llm_log_dir = str(Path(self.config.log_dir) / "llm" / "SubAgent")
            else:
                llm_log_dir = str(path_manager.get_llm_log_dir(log_dir))
            self.llm_logger = LLMLogger(llm_log_dir)
        else:
            self.llm_logger = None
        
        # 运行时状态
        self.available_tools = []
        self.max_iterations = max_iterations
        self.context_summary_threshold = context_summary_threshold
        self.max_context_length = max_context_length
        
        # API配置
        self.enable_streaming = enable_streaming
        self.api_timeout = api_timeout

        # 初始化控制台输出日志器 - 支持精细化控制
        # 参数优先级：console_output/file_output > enable_console_output
        if console_output is not None or file_output is not None:
            # 使用精细化控制参数
            self.console_output = console_output if console_output is not None else True
            self.file_output = file_output if file_output is not None else True
        else:
            # 向后兼容：使用enable_console_output
            self.console_output = enable_console_output
            self.file_output = enable_console_output

        # 只有在至少一个输出方式启用时才创建logger
        if self.console_output or self.file_output:
            self.console_logger = OutputLogger(
                log_prefix="celltypeSubagent",
                console_output=self.console_output,
                file_output=self.file_output,
                log_dir=str(self.config.log_dir)
            )
        else:
            self.console_logger = None

        # 初始化token报告器
        self.token_reporter = TokenReporter(language=self.language)

        # 🌟 初始化共享 LLM 客户端（支持 DeepSeek Reasoner）
        self.llm_client = LLMClient(
            config=config,
            logger_callbacks={
                'info': self._log_info,
                'success': self._log_success,
                'warning': self._log_warning,
                'error': self._log_error
            }
        )
    
    async def initialize(self) -> bool:
        """初始化 agent - 启动 MCP 服务器并获取工具列表"""
        # 启动 MCP 服务器
        if not await self.mcp_client.start_server():
            self._log_error("❌ MCP 服务器启动失败")
            return False

        # 获取可用工具
        self.available_tools = await self.mcp_client.list_tools()

        # 🌟 新增：验证工具列表是否为空
        if not self.available_tools:
            self._log_error("❌ 警告：可用工具列表为空！")
            self._log_error("   MCP 服务器可能未正确初始化，或者没有注册任何工具")
            return False

        # 🌟 新增：显示已加载的工具信息
        self._log_success(f"✅ 已加载 {len(self.available_tools)} 个工具")
        tool_names = [t.get('name', 'unknown') for t in self.available_tools]
        self._log_info(f"📋 工具列表: {', '.join(tool_names)}")

        return True
    
    def set_language(self, language: str):
        """设置分析语言"""
        if language in SUPPORTED_LANGUAGES:
            self.language = language
            self._log_info(_("agent.language_set", language=language))
        else:
            self._log_warning(_("agent.language_not_supported", language=language, supported=SUPPORTED_LANGUAGES))

    def _get_system_prompt(self) -> str:
        """获取 React 系统 prompt"""
        try:
            work_dir = os.getenv("CELLTYPE_WORK_DIR", str(Path.cwd()))

            print(f"🔍 调试输出: SubAgent配置信息:")
            print(f"   - 工作目录: {work_dir}")

            # 使用指定语言的模板格式化
            template = get_system_prompt_template(self.language)
            tool_list = "\n".join([f"{i+1}. {tool.get('name', 'Unknown')}: {tool.get('description', '')}"
                                  for i, tool in enumerate(self.available_tools)])

            # 根据语言设置缓存状态
            cache_status = "✓ MCP 服务器已启动" if self.language == 'zh' else "✓ MCP Server Started"

            # 获取当前运行目录的文件列表
            try:
                files = [f for f in os.listdir('.') if os.path.isfile(f)]
                file_list = ', '.join(files)
            except Exception:
                file_list = "celltype_mcp_server.py, prompts.py, celltype_react_agent_mcp.py"

            return template.format(
                tool_list=tool_list,
                operating_system="Linux",
                cache_status=cache_status,
                file_list=file_list
            )
        except Exception as e:
            # fallback 到简化版本
            self._log_warning(_("agent.template_fallback", error=e))
            fallback_template = get_fallback_prompt_template(self.language)
            tool_names = ', '.join([tool.get('name', '') for tool in self.available_tools])
            return fallback_template.format(tool_names=tool_names)
    
    async def _call_openai(self, messages: List[Dict], timeout: int = 270, stream: bool = False, request_type: str = "main") -> str:
        """调用 OpenAI API - 使用共享 LLM 客户端（支持 DeepSeek Reasoner）

        包含对 <observation> 幻觉的检测和自动重试机制
        """
        from agentype.common.llm_client import ObservationHallucinationError

        max_hallucination_retries = 3

        for retry in range(max_hallucination_retries):
            try:
                response = await self.llm_client.call_api(
                    messages=messages,
                    timeout=timeout,
                    stream=stream,
                    request_type=request_type,
                    llm_logger=self.llm_logger,
                    console_logger=self.console_logger
                )
                # 成功获取响应，跳出重试循环
                return response

            except ObservationHallucinationError as e:
                self._log_error(f"❌ LLM 产生幻觉（生成了 <observation> 标签）- 重试 {retry + 1}/{max_hallucination_retries}")

                if retry < max_hallucination_retries - 1:
                    # 还有重试机会，添加纠正提示
                    from agentype.prompts import get_prompt_manager

                    manager = get_prompt_manager(self.language)
                    correction_content = manager.get_common_prompt('HALLUCINATION_CORRECTION_MESSAGE')

                    correction_message = {
                        "role": "user",
                        "content": correction_content
                    }
                    messages.append(correction_message)
                    self._log_warning("🔄 添加纠正提示，准备重试...")
                    continue
                else:
                    # 超过最大重试次数
                    self._log_error(f"❌ LLM 持续产生幻觉，已达到最大重试次数 ({max_hallucination_retries})")
                    raise

        # 理论上不会到达这里
        raise RuntimeError("未预期的代码路径")

    async def _retry_llm_call_with_correction(self, messages: List[Dict], validation_result: Dict, max_retries: int = 10, timeout: int = 270) -> str:
        """重新调用 LLM 并提供修正指导"""
        retry_count = 0
        response = ""

        while retry_count < max_retries:
            retry_count += 1
            self._log_info(_("retry.llm_retry", retry=retry_count, max_retries=max_retries))
            self._log_warning(_("retry.last_response_issues", issues=', '.join(validation_result['issues'])))

            # 构建修正提示
            correction_prompt = ValidationUtils.build_correction_prompt(validation_result, self.available_tools, self.language)

            # 添加修正提示到消息历史
            correction_messages = messages.copy()
            correction_messages.append({"role": "user", "content": correction_prompt})

            # 重新调用 LLM，保持与主调用相同的流式输出设置
            response = await self._call_openai(correction_messages, timeout, stream=self.enable_streaming, request_type="retry")

            # 为重试调用添加额外的日志标记
            if self.llm_logger:
                self._log_info(_("retry.retry_logged", count=retry_count))

            # 🌟 修改：验证时传递 has_reasoning 参数
            new_validation = ValidationUtils.validate_response_format(
                response,
                has_reasoning=self.llm_client.has_reasoning()
            )

            if new_validation['valid']:
                self._log_success(_("retry.retry_success"))
                return response
            else:
                self._log_error(_("retry.retry_failed", count=retry_count, issues=', '.join(new_validation['issues'])))
                validation_result = new_validation

        self._log_error(_("retry.max_retries_reached"))
        return response

    async def _summarize_context(self, messages: List[Dict]) -> List[Dict]:
        """当对话历史过长时，总结上下文以减少token消耗

        Args:
            messages: 当前的对话历史

        Returns:
            总结后的消息列表
        """
        try:
            self._log_warning(_("context.too_long"))

            # 保留系统消息和最初的用户查询
            system_message = messages[0] if messages and messages[0]["role"] == "system" else None
            initial_query = messages[1] if len(messages) > 1 and messages[1]["role"] == "user" else None

            # 查找之前的总结消息
            existing_summary = None
            summary_index = -1
            for i, msg in enumerate(messages):
                if msg.get("role") == "assistant" and "[上下文总结]" in msg.get("content", ""):
                    existing_summary = msg
                    summary_index = i
                    break

            # 确定需要总结的对话历史范围
            # 需要保留的重要工具结果（如get_gene_info）
            important_messages = []

            if existing_summary and summary_index > 1:
                # 如果已有总结，从总结后开始到倒数几轮
                raw_conversation = messages[summary_index+1:-4] if len(messages) > summary_index + 5 else messages[summary_index+1:]
                recent_messages = messages[-4:] if len(messages) > summary_index + 5 else []
            else:
                # 如果没有总结，从第3条消息开始（跳过系统消息和初始查询）
                raw_conversation = messages[2:-4] if len(messages) > 6 else messages[2:]
                recent_messages = messages[-4:] if len(messages) > 6 else []

            # 从raw_conversation中提取重要的get_gene_info结果
            conversation_to_summarize = []
            for i, msg in enumerate(raw_conversation):
                # 检查是否是get_gene_info的observation
                is_gene_info_result = False
                if msg.get("role") == "user" and "<observation>" in msg.get("content", ""):
                    # 查找前一条消息，看是否是get_gene_info调用
                    if i > 0:
                        prev_msg = raw_conversation[i-1]
                        if (prev_msg.get("role") == "assistant" and
                            "get_gene_info" in prev_msg.get("content", "")):
                            is_gene_info_result = True

                if is_gene_info_result:
                    important_messages.append(msg)  # 保留，不总结
                else:
                    conversation_to_summarize.append(msg)  # 可以总结

            if not conversation_to_summarize:
                self._log_info(_("context.no_history"))
                return messages

            # 构建总结prompt
            conversation_text = ""
            for msg in conversation_to_summarize:
                role = msg["role"]
                content = msg["content"]
                conversation_text += f"\n{role.upper()}: {content}\n"

            # 根据是否存在之前的总结来构建不同的prompt
            from agentype.prompts import get_prompt_manager
            manager = get_prompt_manager(self.language)

            if existing_summary:
                existing_summary_content = existing_summary.get("content", "").replace("[上下文总结] 之前的分析进展：", "").strip()
                template = manager.get_agent_specific_prompt('subagent', 'CONTEXT_SUMMARY_INCREMENTAL_TEMPLATE')
                summarization_prompt = template.format(
                    existing_summary=existing_summary_content,
                    conversation=conversation_text
                )
            else:
                template = manager.get_agent_specific_prompt('subagent', 'CONTEXT_SUMMARY_INITIAL_TEMPLATE')
                summarization_prompt = template.format(
                    conversation=conversation_text
                )

            # 调用OpenAI进行总结，保持与主调用相同的流式输出设置
            summary_messages = [{"role": "user", "content": summarization_prompt}]
            summary = await self._call_openai(summary_messages, timeout=self.api_timeout, stream=self.enable_streaming, request_type="summary")  # 上下文总结使用配置的超时时间

            # 记录总结请求日志
            if self.llm_logger:
                self._log_info(_("context.summary_logged"))

            # 构建新的消息列表
            new_messages = []

            # 保留系统消息
            if system_message:
                new_messages.append(system_message)

            # 保留初始查询
            if initial_query:
                new_messages.append(initial_query)

            # 添加更新的总结消息（替换之前的总结）
            summary_message = {
                "role": "assistant",
                "content": f"[上下文总结] 之前的分析进展：{summary}"
            }
            new_messages.append(summary_message)

            # 添加保留的重要消息（如get_gene_info结果）
            if important_messages:
                new_messages.extend(important_messages)
                self._log_info(f"💎 保留了 {len(important_messages)} 条重要工具结果（如get_gene_info）")

            # 添加最近的消息以保持连续性
            new_messages.extend(recent_messages)

            self._log_success(_("context.summary_completed"))
            self._log_info(_("context.original_messages", count=len(messages)))
            self._log_info(_("context.summarized_messages", count=len(new_messages)))
            self._log_info(_("context.summary_length", length=len(summary)))

            return new_messages

        except Exception as e:
            error_msg = f"上下文总结失败: {e}"
            self._log_error(f"❌ {error_msg}")

            # 总结失败时，简单地保留最近的消息
            if len(messages) > 10:
                self._log_info(_("context.simple_strategy"))
                return messages[-10:]

            return messages

    async def analyze_celltype(self, gene_list: str, tissue_type: str = None, cell_type: str = None, species: str = None) -> Dict:
        """分析细胞类型

        Args:
            gene_list: 基因列表，逗号分隔
            tissue_type: 组织类型（可选），如"骨髓"、"血液"等
            cell_type: 细胞类型提示（可选），用于优先判断细胞亚群
            species: 物种信息（可选），如"Human"、"Mouse"等

        Returns:
            分析结果字典
        """
        # 🌟 物种处理逻辑
        detected_species = species  # 优先使用传入的

        if not detected_species:
            # 自动检测
            self.console_logger.info("🔍 未提供物种参数，SubAgent自动检测...")
            from agentype.subagent.utils.common import SpeciesDetector

            # 从基因列表提取基因
            genes = [g.strip() for g in gene_list.split(',') if g.strip()]

            detector = SpeciesDetector()
            detected_species = detector.detect_species_simple(genes)
            self.console_logger.info(f"✅ 检测到物种: {detected_species}")
        else:
            self.console_logger.info(f"✅ 使用传入的物种参数: {detected_species}")
        self._log_header(_("analysis.starting", genes=gene_list))
        if tissue_type:
            self._log_info(_("analysis.tissue_type", tissue=tissue_type))
        if cell_type:
            self._log_info(f"🧫 细胞类型提示: {cell_type}")
        
        # 准备系统 prompt 和用户查询
        system_prompt = self._get_system_prompt()
        
        # 根据是否有组织类型生成不同的查询
        query_templates = get_user_query_templates(self.language)
        template_args = {"gene_list": gene_list}
        template_key = None

        if cell_type:
            template_args["cell_type"] = cell_type
            if tissue_type and "with_tissue_and_celltype" in query_templates:
                template_key = "with_tissue_and_celltype"
                template_args["tissue_type"] = tissue_type
            elif "with_celltype" in query_templates:
                template_key = "with_celltype"
            elif tissue_type and "with_tissue" in query_templates:
                template_key = "with_tissue"
                template_args["tissue_type"] = tissue_type
        elif tissue_type and "with_tissue" in query_templates:
            template_key = "with_tissue"
            template_args["tissue_type"] = tissue_type

        if not template_key:
            template_key = "without_tissue"

        template = query_templates.get(template_key) or query_templates["without_tissue"]
        user_query = template.format(**template_args)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"<question>{user_query}</question>"}
        ]
        
        self._log_info(_("analysis.system_prompt_length", length=len(system_prompt)))
        self._log_info(_("analysis.user_query", query=user_query) + "\n")
        
        analysis_log = []
        iteration = 0
        final_celltype = None
        final_answer_text = None
        
        while iteration < self.max_iterations:
            iteration += 1
            self._log_header(_("analysis.iteration", iteration=iteration))
            
            # 检查是否需要进行上下文总结
            should_summarize = False
            summarize_reason = ""
            
            # 检查迭代次数阈值
            if iteration == self.context_summary_threshold:
                should_summarize = True
                summarize_reason = f"达到迭代次数阈值（第{iteration}次迭代）"
                
            # if len(messages) > self.context_summary_threshold:
            #     should_summarize = True
            #     summarize_reason = f"消息数量超过阈值（{len(messages)}）"
            
            # 检查上下文长度（估算token数量）
            total_content_length = sum(len(msg.get("content", "")) for msg in messages)
            self._log_info(_("analysis.current_messages") + f" {len(messages)}")
            self._log_info(_("analysis.current_context_length") + f" {total_content_length}")
            if total_content_length > self.max_context_length:
                should_summarize = True
                if summarize_reason:
                    summarize_reason += f" 且上下文过长（{total_content_length}字符，阈值{self.max_context_length}）"
                else:
                    summarize_reason = f"上下文过长（{total_content_length}字符，阈值{self.max_context_length}）"
            
            # 执行总结
            if should_summarize and len(messages) > 6:
                self._log_warning(_("analysis.context_compression", reason=summarize_reason))
                messages = await self._summarize_context(messages)
            
            # 使用全局配置决定是否使用流式输出
            if self.enable_streaming:
                self._log_info(_("analysis.streaming_enabled", iteration=iteration))
            
            # 调用 OpenAI（使用配置的超时时间）
            response = await self._call_openai(messages, timeout=self.api_timeout, stream=self.enable_streaming)
            self._log_info(_("analysis.ai_response_length", length=len(response)))

            # 🌟 新增：验证响应格式，传递 has_reasoning 参数
            # DeepSeek Reasoner 模型有 reasoning_content 时，允许没有 <thought> 标签
            validation = ValidationUtils.validate_response_format(
                response,
                has_reasoning=self.llm_client.has_reasoning()
            )
            
            if not validation['valid']:
                self._log_warning(_("analysis.format_validation_failed", issues=', '.join(validation['issues'])))
                response = await self._retry_llm_call_with_correction(messages, validation, 50, self.api_timeout)
            else:
                self._log_success(_("analysis.format_validation_passed"))
            
            analysis_log.append({
                "iteration": iteration,
                "response": response,
                "validation": validation,
                "type": "ai_response"
            })
            
            # 检查是否包含 final_answer
            if '</final_answer>' in response:
                # 提取并保存 final_answer 内容
                try:
                    match = re.search(r'<final_answer>(.*?)</final_answer>', response, re.DOTALL)
                    if match:
                        final_answer_text = match.group(1).strip()
                except Exception:
                    pass

                final_celltype = ReactParser.extract_celltype(response)
                if final_celltype:
                    self._log_success(_("analysis.analysis_completed", celltype=final_celltype))
                    break
                else:
                    self._log_warning(_("analysis.final_answer_no_celltype"))
            
            # 🌟 新增：提取并执行 action，支持详细错误处理
            action = ReactParser.extract_action(response, self.available_tools)

            # 检查 action 提取结果
            if action and 'error' in action:
                # Action 提取失败 - 记录详细错误信息
                self._log_warning(f"❌ Action 提取失败: {action.get('message', '未知错误')}")

                # 根据错误类型记录详细信息
                if action['error'] == 'invalid_action_format':
                    self._log_error(f"   原因：action 格式不正确")
                    self._log_error(f"   内容: {action.get('action_text', '')[:100]}...")
                elif action['error'] == 'invalid_tool_name':
                    self._log_error(f"   原因：无效的工具名称")
                    self._log_error(f"   请求工具: {action.get('func_name', 'unknown')}")
                    self._log_error(f"   可用工具: {', '.join(action.get('available_tools', []))}")

                # 检查是否有 final_answer，如果有则正常结束
                if '</final_answer>' in response:
                    self._log_info("   响应中包含 final_answer，忽略 action 错误")
                    # 不执行工具调用，但继续循环以处理 final_answer
                else:
                    self._log_error("   响应中既无有效 action 也无 final_answer，异常退出")
                    break

            elif action:
                # Action 提取成功 - 执行工具调用
                function_name = action['function']
                parameters_str = action['parameters']
                parameters = ReactParser.parse_parameters(parameters_str)

                self._log_info(_("tools.call.calling", name=function_name, params=parameters))

                # 执行 MCP 工具调用
                tool_result = await self.mcp_client.call_tool(function_name, parameters)

                if tool_result and tool_result.get("success"):
                    raw_content = tool_result.get("content", "")
                    self._log_success(_("tools.call.success", length=len(raw_content)))

                    # 处理内容长度
                    result_content = await self.content_processor.process_tool_result_content(
                        raw_content, self._call_openai, self.language,
                        tool_name=function_name, tool_params=parameters, mcp_client=self.mcp_client
                    )
                else:
                    result_content = json.dumps({
                        "error": tool_result.get("error", "工具调用失败") if tool_result else "无响应",
                        "success": False
                    }, ensure_ascii=False)
                    self._log_error(_("tools.call.failed"))

                # 记录分析日志
                analysis_log.append({
                    "iteration": iteration,
                    "action": action,
                    "result": result_content,
                    "type": "tool_call"
                })

                # 构造 observation 并添加到对话
                observation = f"<observation>{result_content}</observation>"
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content": observation})
            else:
                # action 为 None - 没有找到 <action> 标签
                # 这可能是正常的（响应中有 final_answer 而非 action）
                self._log_info(_("tools.call.no_action"))
                break
        
        self._log_header(f"\n{_('analysis.summary.title')}")
        self._log_info(_("analysis.summary.total_iterations", iterations=iteration))
        self._log_info(_("analysis.summary.final_celltype", celltype=final_celltype))
        self._log_info(_("analysis.summary.tool_calls", count=len([log for log in analysis_log if log['type'] == 'tool_call'])))
        if iteration >= self.context_summary_threshold:
            self._log_info(_("analysis.summary.context_summary", threshold=self.context_summary_threshold))
        
        # 打印 LLM 日志统计
        if self.llm_logger:
            try:
                log_summary = self.llm_logger.get_log_summary()
                self._log_info(_("analysis.summary.llm_stats", total=log_summary.get('total_requests', 0)))
                self._log_info(_("analysis.summary.success_failure", success=log_summary.get('success_count', 0), failure=log_summary.get('error_count', 0)))
                self._log_info(_("analysis.summary.log_file", file=log_summary.get('log_file', 'N/A')))
            except Exception as e:
                self._log_error(_("analysis.summary.stats_failed", error=e))
        
        return {
            "gene_list": gene_list,
            "tissue_type": tissue_type,
            "final_celltype": final_celltype,
            "final_answer": final_answer_text,
            "total_iterations": iteration,
            # "context_summarized": iteration >= self.context_summary_threshold,
            # "context_summary_threshold": self.context_summary_threshold,
            # "analysis_log": analysis_log,
            # "llm_log_summary": self.llm_logger.get_log_summary() if self.llm_logger else None,
            "success": final_celltype is not None,
            "detected_species": detected_species  # 🌟 新增：返回物种信息
        }
    
    async def cleanup(self):
        """清理资源"""
        try:
            # 停止 MCP 服务器
            await self.mcp_client.stop_server()
            
            # 关闭 LLM 日志记录器
            if self.llm_logger:
                await self.llm_logger.close()
            
            # 清理对象引用
            self.available_tools = []
            
            # 给异步清理过程充足时间
            await asyncio.sleep(0.3)
            
            # 强制垃圾回收，清理未引用的对象
            gc.collect()
            
            # 再次延迟确保垃圾回收完成
            await asyncio.sleep(0.1)
            
        except Exception as e:
            self._log_warning(f"⚠️ 清理资源时出现异常: {e}")
        
        self._log_success("✅ 资源清理完成")

    def _log_info(self, message: str) -> None:
        """输出信息日志"""
        if self.console_logger:
            self.console_logger.info(message)
        else:
            print(message)

    def _log_success(self, message: str) -> None:
        """输出成功日志"""
        if self.console_logger:
            self.console_logger.success(message)
        else:
            print(message)

    def _log_error(self, message: str) -> None:
        """输出错误日志"""
        if self.console_logger:
            self.console_logger.error(message)
        else:
            print(message)

    def _log_warning(self, message: str) -> None:
        """输出警告日志"""
        if self.console_logger:
            self.console_logger.warning(message)
        else:
            print(message)

    def _log_header(self, message: str) -> None:
        """输出标题日志"""
        if self.console_logger:
            self.console_logger.header(message)
        else:
            print(message)

    def _log_separator(self, char: str = "=", length: int = 60) -> None:
        """输出分隔线"""
        if self.console_logger:
            self.console_logger.separator(char, length)
        else:
            print(char * length)
