#!/usr/bin/env python3
"""
agentype - Main React Agent模块
Author: cuilei
Version: 1.0
"""

import gc
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Any

# 导入 prompts（保持与其他 Agent 一致的接口）
from agentype.mainagent.config.prompts import (
    SUPPORTED_LANGUAGES,
    DEFAULT_LANGUAGE,
    get_system_prompt_template,
    get_fallback_prompt_template,
    get_user_query_templates,
)

# Token统计模块
from agentype.common.token_statistics import TokenStatistics, TokenReporter, merge_token_stats
from agentype.common.log_token_parser import LogTokenParser

# 基础组件
from agentype.mainagent.config.settings import ConfigManager
from agentype.mainagent.clients.mcp_client import MCPClient
from agentype.mainagent.utils.content_processor import ContentProcessor
from agentype.mainagent.utils.parser import ReactParser
from agentype.mainagent.utils.validator import ValidationUtils
from agentype.mainagent.utils.i18n import _, set_language as _set_i18n_language
from agentype.mainagent.utils.path_manager import path_manager
from agentype.mainagent.utils.output_logger import OutputLogger
from agentype.mainagent.tools.cluster_tools import check_cluster_completion
from agentype.mainagent.tools.file_paths_tools import load_file_paths_bundle
# 导入共享模块
from agentype.common.llm_client import LLMClient
from agentype.common.llm_logger import LLMLogger


class MainReactAgent:
    """MainAgent React 实现（对齐其它 Agent 的写法）

    子 Agent 视为 MainAgent MCP 服务器提供的工具封装，
    不在此直接加载子 Agent。通过调用自身 MCP 工具完成数据处理、
    基因分析与细胞注释。
    """

    def __init__(self,
                 config: Optional[ConfigManager] = None,
                 server_script: str = None,
                 max_content_length: int = 10000,
                 enable_summarization: bool = True,
                 max_iterations: int = 30,
                 context_summary_threshold: int = 50,  # 🆕 从30提高到50，给LLM更多迭代空间完成所有阶段
                 max_context_length: int = 150000,  # token阈值保持不变
                 enable_llm_logging: bool = True,
                 log_dir: str = None,
                 language: str = "zh",
                 enable_streaming: bool = True,
                 api_timeout: int = 300,
                 console_output: bool = True,
                 file_output: bool = True):

        # 配置与 MCP 客户端
        self.config = config or ConfigManager.from_env()
        if server_script is None:
            server_script = str(path_manager.get_mcp_server_path())
        # ⭐ 传入 config 给 MCPClient，用于混合配置传递（环境变量 + 命令行参数）
        self.mcp_client = MCPClient(server_script, config=self.config)

        # React 组件
        self.content_processor = ContentProcessor(max_content_length, enable_summarization)
        self.parser = ReactParser()
        self.validator = ValidationUtils()

        # 语言与 LLM 日志
        self.language = language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
        # 同步 i18n 语言环境
        try:
            _set_i18n_language(self.language)
        except Exception:
            pass
        self.enable_llm_logging = enable_llm_logging
        # 如果没有指定log_dir，使用 ConfigManager 的日志目录
        if log_dir is None:
            from pathlib import Path
            log_dir = str(Path(self.config.log_dir) / "llm" / "MainAgent")
        self.llm_logger = LLMLogger(log_dir) if enable_llm_logging else None

        # Token统计报告器
        self.token_reporter = TokenReporter(language=self.language)

        # 初始化输出日志器
        if console_output or file_output:
            self.console_logger = OutputLogger(
                log_prefix="celltypeMainagent",
                console_output=console_output,
                file_output=file_output,
                log_dir=str(self.config.log_dir)
            )
        else:
            self.console_logger = None

        # 🌟 初始化共享 LLM 客户端（支持 DeepSeek Reasoner）
        self.llm_client = LLMClient(
            config=self.config,
            logger_callbacks={
                'info': self._log_info,
                'success': self._log_success,
                'warning': self._log_warning,
                'error': self._log_error
            }
        )

        # 运行时
        self.available_tools: List[Dict] = []
        self.max_iterations = max_iterations
        self.context_summary_threshold = context_summary_threshold
        self.max_context_length = max_context_length
        self.enable_streaming = enable_streaming
        self.api_timeout = api_timeout

        # 🆕 流程完成度检查状态追踪
        self.workflow_completion_reminder_sent = False  # 记录是否已发送过完成度提醒

    async def initialize(self) -> bool:
        """初始化 Main Agent"""
        self._log_info("🚀 正在初始化 MainAgent…")
        if not await self.mcp_client.start_server():
            self._log_error("❌ MainAgent MCP 服务器启动失败")
            return False
        self.available_tools = await self.mcp_client.list_tools()
        self._log_success(f"✅ MainAgent MCP 已启动，工具数: {len(self.available_tools)}")
        return True

    async def cleanup(self) -> None:
        """清理资源"""
        try:
            await self.mcp_client.stop_server()
            if self.llm_logger:
                await self.llm_logger.close()
            gc.collect()
            self._log_success("✅ MainAgent 资源清理完成")
        except Exception as e:
            self._log_warning(f"⚠️ 资源清理时出现异常: {e}")

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

    def set_language(self, language: str):
        """设置语言"""
        if language in SUPPORTED_LANGUAGES:
            self.language = language
            self._log_info(f"🌍 语言已设置为: {language}")
            # 同步 i18n 语言环境
            try:
                _set_i18n_language(language)
            except Exception:
                pass
        else:
            self._log_error(f"❌ 不支持的语言: {language}，支持的语言: {SUPPORTED_LANGUAGES}")

    def _get_system_prompt(self) -> str:
        """获取 React 系统 prompt"""
        try:
            template = get_system_prompt_template(self.language)
            tool_list = "\n".join([f"{i+1}. {t.get('name', 'Unknown')}: {t.get('description', '')}" for i, t in enumerate(self.available_tools)])
            cache_status = "✓ MCP 服务器已启动" if self.language == 'zh' else "✓ MCP Server Started"
            import os
            try:
                files = [f for f in os.listdir('.') if os.path.isfile(f)]
                file_list = ', '.join(files[:10])
            except Exception:
                file_list = "main_react_agent.py, mcp_server.py, prompts.py"
            return template.format(
                tool_list=tool_list,
                operating_system="Linux",
                cache_status=cache_status,
                file_list=file_list
            )
        except Exception as e:
            self._log_warning(f"⚠️ 使用系统提示模板失败，使用备选模板: {e}")
            fallback_template = get_fallback_prompt_template(self.language)
            tool_names = ', '.join([t.get('name', '') for t in self.available_tools])
            return fallback_template.format(tool_names=tool_names)


    async def _call_openai(self, messages: List[Dict], timeout: int = 270, stream: bool = False, request_type: str = "main") -> str:
        """调用 OpenAI API - 使用共享 LLM 客户端（支持 DeepSeek Reasoner）"""
        return await self.llm_client.call_api(
            messages=messages,
            timeout=timeout,
            stream=stream,
            request_type=request_type,
            llm_logger=self.llm_logger,
            console_logger=self.console_logger
        )
    async def _retry_llm_call_with_correction(self, messages: List[Dict], validation_result: Dict, max_retries: int = 10, timeout: int = 270) -> str:
        """重新调用 LLM 并提供修正指导"""
        retry_count = 0
        response = ""

        while retry_count < max_retries:
            retry_count += 1
            self._log_warning(_("retry.llm_retry", retry=retry_count, max_retries=max_retries))
            self._log_info(_("retry.last_response_issues", issues=', '.join(validation_result['issues'])))

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

            # 验证新响应格式
            new_validation = ValidationUtils.validate_response_format(response)

            # 🚨 额外检查：重试响应中是否仍包含跳过行为
            skip_patterns = [
                r"跳过剩余", r"时间关系", r"跳过.*?簇", r"省略.*?分析",
                r"直接进入后续", r"结束处理", r"跳过.*?cluster",
                r"由于.*?跳过", r"将跳过.*?的详细分析"
            ]
            still_trying_to_skip = any(re.search(pattern, response, re.IGNORECASE) for pattern in skip_patterns)

            if still_trying_to_skip and '</final_answer>' in response:
                self._log_warning(f"🚨 重试第{retry_count}次仍检测到跳过行为，继续重试")
                from agentype.prompts import get_prompt_manager

                manager = get_prompt_manager(self.language)
                skip_message = manager.get_agent_specific_prompt('mainagent', 'SKIP_DETECTION_RETRY_MESSAGE')

                new_validation = {
                    "valid": False,
                    "issues": skip_message['issues']
                }
                validation_result = new_validation
                continue

            if new_validation['valid']:
                self._log_success(_("retry.retry_success"))
                return response
            else:
                self._log_warning(_("retry.retry_failed", count=retry_count, issues=', '.join(new_validation['issues'])))
                validation_result = new_validation

        self._log_error(_("retry.max_retries_reached"))
        return response

    async def _summarize_context(self, messages: List[Dict]) -> List[Dict]:
        """改进的上下文总结，保留关键工具调用结果以防止状态丢失

        Args:
            messages: 当前的对话历史

        Returns:
            总结后的消息列表
        """
        try:
            self._log_info(_("context.too_long"))

            # 保留系统消息和最初的用户查询
            system_message = messages[0] if messages and messages[0]["role"] == "system" else None
            initial_query = messages[1] if len(messages) > 1 and messages[1]["role"] == "user" else None

            # 🆕 识别关键工具调用 - 这些不应该被总结丢失
            critical_tools = ['load_cluster_types', 'save_cluster_type', 'get_all_cluster_ids',
                            'check_cluster_completion', 'extract_cluster_genes']
            critical_messages = []

            # 查找之前的总结消息
            existing_summary = None
            summary_index = -1
            for i, msg in enumerate(messages):
                if msg.get("role") == "assistant" and "[上下文总结]" in msg.get("content", ""):
                    existing_summary = msg
                    summary_index = i
                    break

            # 确定需要总结的对话历史范围 (🆕 保留最近5个消息)
            if existing_summary and summary_index > 1:
                # 如果已有总结，从总结后开始到倒数5轮
                conversation_to_summarize = messages[summary_index+1:-5] if len(messages) > summary_index + 6 else messages[summary_index+1:]
                recent_messages = messages[-5:] if len(messages) > summary_index + 6 else []
            else:
                # 如果没有总结，从第3条消息开始（跳过系统消息和初始查询）
                conversation_to_summarize = messages[2:-5] if len(messages) > 7 else messages[2:]
                recent_messages = messages[-5:] if len(messages) > 7 else []

            # 🆕 从要总结的消息中提取关键工具调用结果
            for msg in conversation_to_summarize:
                content = msg.get("content", "")
                # 检查是否包含关键工具的调用或observation
                if any(tool in content for tool in critical_tools):
                    # 保留完整的工具调用和其observation
                    critical_messages.append(msg)

            if not conversation_to_summarize:
                self._log_info(_("context.nothing_to_summarize"))
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
                existing_summary_content = existing_summary.get("content", "").replace("[上下文总结] 之前的处理进展：", "").strip()
                template = manager.get_agent_specific_prompt('mainagent', 'CONTEXT_SUMMARY_INCREMENTAL_TEMPLATE')
                summarization_prompt = template.format(
                    existing_summary=existing_summary_content,
                    conversation=conversation_text
                )
            else:
                template = manager.get_agent_specific_prompt('mainagent', 'CONTEXT_SUMMARY_INITIAL_TEMPLATE')
                summarization_prompt = template.format(
                    conversation=conversation_text
                )

            # 调用OpenAI进行总结，保持与主调用相同的流式输出设置
            summary_messages = [{"role": "user", "content": summarization_prompt}]
            summary = await self._call_openai(summary_messages, timeout=self.api_timeout, stream=self.enable_streaming, request_type="summary")

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
                "content": f"[上下文总结] 之前的处理进展：{summary}"
            }
            new_messages.append(summary_message)

            # 🆕 插入保留的关键工具调用消息 (最近5个)
            if critical_messages:
                self._log_info(f"💾 保留 {len(critical_messages)} 个关键工具调用结果")
                new_messages.extend(critical_messages[-5:])

            # 添加最近的消息以保持连续性
            new_messages.extend(recent_messages)

            self._log_success(_("context.summary_completed"))
            self._log_info(_("context.original_count", count=len(messages)))
            self._log_info(_("context.summarized_count", count=len(new_messages)))
            self._log_info(_("context.summary_length", length=len(summary)))

            return new_messages

        except Exception as e:
            error_msg = _("context.summary_failed", error=str(e))
            self._log_error(f"❌ {error_msg}")

            # 总结失败时，简单地保留最近的消息
            if len(messages) > 8:
                self._log_warning(_("context.fallback_strategy"))
                return messages[-8:]

            return messages

    def _build_user_query(self, user_request: str, extra: Optional[Dict[str, Any]] = None) -> str:
        """构建统一用户问题文本，可附加额外上下文参数"""
        templates = get_user_query_templates(self.language)
        # 若提供了结构化的 data/tissue/species 信息，优先使用 unified 模板，便于LLM理解和正确调用工具
        if extra:
            data_path = extra.get("data_path") or extra.get("rds_path") or extra.get("h5ad_path") or extra.get("h5_path")
            tissue = extra.get("tissue_type") or extra.get("tissue_description")
            species = extra.get("species")
            if data_path or tissue or species:
                unified_tpl = templates.get("unified")
                if unified_tpl:
                    return unified_tpl.format(
                        data_path=data_path or "",
                        tissue=tissue or "",
                        species=species or ""
                    )

        # 回退到通用工作流模板，并在末尾附上原始附加参数JSON
        tpl = templates.get("full_workflow") or "请为以下任务运行完整工作流：{task_description}"
        base = tpl.format(task_description=user_request)
        if extra:
            try:
                extra_json = json.dumps(extra, ensure_ascii=False)
                return base + f"\n\n附加参数: {extra_json}"
            except Exception:
                return base
        return base

    async def process_request(self, user_request: str, input_data: Optional[Dict[str, Any]] = None, tissue_type: Optional[str] = None, cluster_column: str = "seurat_clusters") -> Dict[str, Any]:
        """处理用户请求：直接进入 LLM React 循环"""
        try:
            self._log_info(f"📋 处理用户请求(React): {user_request}")
            return await self.process_with_llm_react(user_request, input_data=input_data, tissue_type=tissue_type, cluster_column=cluster_column)
        except Exception as e:
            return {"success": False, "error": f"请求处理异常: {e}"}

    async def process_with_llm_react(self, user_input: Optional[str] = None, input_data: Optional[Any] = None, tissue_type: Optional[str] = None, cluster_column: str = "seurat_clusters", species: Optional[str] = None) -> Dict:
        """基于 LLM 的 React 推理与 MCP 工具调用循环"""
        # 规范化输入
        extra: Optional[Dict[str, Any]] = None
        if isinstance(input_data, str):
            extra = {"data_path": input_data}
        elif isinstance(input_data, dict):
            # 复制一份，避免外部引用被意外修改
            extra = dict(input_data)
        else:
            extra = None

        # 统一组织类型入参（支持多种键名 + 显式参数）
        # 支持的键名：tissue_type / tissue / tissue_description / 组织 / 组织类型 / organ
        def _get_tissue_from_extra(d: Dict[str, Any]) -> Optional[str]:
            for key in (
                "tissue_type", "tissue", "tissue_description", "组织", "组织类型", "organ"
            ):
                if key in d and d[key]:
                    try:
                        val = str(d[key]).strip()
                        if val:
                            return val
                    except Exception:
                        pass
            return None

        # 规范化 tissue 到 extra 中
        if extra is None:
            extra = {}

        normalized_tissue = tissue_type or _get_tissue_from_extra(extra)
        if normalized_tissue:
            extra["tissue_type"] = normalized_tissue

        # 🌟 新增：添加 species 到 extra
        if species:
            extra["species"] = species
            # 与部分工具的参数名保持兼容（enhanced_cell_annotation 使用 tissue_description）
            extra.setdefault("tissue_description", normalized_tissue)

        # 规范化 cluster_column 到 extra 中
        if cluster_column:
            extra["cluster_column"] = cluster_column

        if not user_input:
            has_data_path = extra and any(k in extra for k in ("data_path", "rds_path", "h5ad_path", "h5_path"))
            has_tissue = extra and any(k in extra for k in ("tissue_type", "tissue_description"))
            if has_data_path and has_tissue:
                user_input = "请在指定组织背景下完成细胞类型分析与注释，并给出最终结果"
            elif has_data_path:
                user_input = "请对提供的数据进行细胞类型分析与注释，并给出最终结果"
            else:
                user_input = "执行完整的细胞类型分析流程"

        system_prompt = self._get_system_prompt()
        user_query = self._build_user_query(user_input, extra=extra)
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"<question>{user_query}</question>"},
        ]

        analysis_log: List[Dict[str, Any]] = []
        iteration = 0
        final_answer = None

        while True:
            iteration += 1

            # 长上下文控制
            total_chars = sum(len(m.get("content", "")) for m in messages)
            if total_chars > self.max_context_length or iteration == self.context_summary_threshold:
                messages = await self._summarize_context(messages)

            response = await self._call_openai(messages, timeout=self.api_timeout, stream=self.enable_streaming)
            self._log_info(f"📏 AI响应长度: {len(response)}")

            # 验证响应格式
            validation = self.validator.validate_response_format(response)

            if not validation['valid']:
                self._log_error(f"❌ 格式验证失败: {', '.join(validation['issues'])}")
                response = await self._retry_llm_call_with_correction(messages, validation, 10, self.api_timeout)
            else:
                self._log_success("✅ 格式验证通过")

            analysis_log.append({
                "iteration": iteration,
                "response": response,
                "validation": validation,
                "type": "ai_response"
            })

            # 🚨 预检查：检测可能的跳过行为
            skip_patterns = [
                r"跳过剩余",
                r"时间关系",
                r"跳过.*?簇",
                r"省略.*?分析",
                r"直接进入后续",
                r"结束处理",
                r"跳过.*?cluster",
                r"由于.*?跳过",
                r"将跳过.*?的详细分析"
            ]
            skip_detected = any(re.search(pattern, response, re.IGNORECASE) for pattern in skip_patterns)

            if skip_detected and '</final_answer>' in response:
                self._log_warning("🚨 检测到尝试跳过循环的行为，强制要求继续处理")
                from agentype.prompts import get_prompt_manager

                manager = get_prompt_manager(self.language)
                skip_message = manager.get_agent_specific_prompt('mainagent', 'SKIP_DETECTION_INITIAL_MESSAGE')

                skip_validation_result = {
                    "valid": False,
                    "issues": skip_message['issues']
                }
                response = await self._retry_llm_call_with_correction(messages, skip_validation_result, 10, self.api_timeout)
                analysis_log.append({
                    "iteration": iteration,
                    "response": response,
                    "validation": {"valid": False, "issues": ["检测到跳过行为，已强制重试"]},
                    "type": "ai_response_retry_for_skip_prevention"
                })

            # 检查是否包含 final_answer
            if '</final_answer>' in response:
                final_result = ReactParser.extract_final_answer(response)
                if final_result:
                    # 防御性检查：确保全局配置存在
                    from agentype.mainagent.tools.file_paths_tools import set_global_config, _GLOBAL_CONFIG
                    if _GLOBAL_CONFIG is None:
                        # 如果全局配置丢失，重新设置
                        set_global_config(self.config)
                        self._log_warning("⚠️ 检测到全局配置丢失，已重新初始化")

                    # 直接从 bundle 读取文件路径
                    self._log_info("📦 从 bundle 读取文件路径信息...")
                    bundle_result = load_file_paths_bundle()

                    if bundle_result.get("success"):
                        # 从扁平化结构中提取所有路径字段（排除元数据字段）
                        metadata_keys = {"success", "session_id", "timestamp", "metadata", "cluster_mapping"}
                        extracted_paths = {k: v for k, v in bundle_result.items() if k not in metadata_keys and v}

                        # 🆕 流程完成度验证：检查必要的输出文件是否存在
                        required_outputs = ['annotated_rds', 'annotated_h5ad']  # Phase 6 和 Phase 7 的输出
                        missing_outputs = [key for key in required_outputs if not extracted_paths.get(key)]

                        if missing_outputs:
                            # 检测到缺失的输出文件
                            if not self.workflow_completion_reminder_sent:
                                # 第一次检测到缺失，发送提醒
                                self._log_warning(f"⚠️ 检测到工作流未完全完成，缺少: {', '.join(missing_outputs)}")
                                self._log_info("📢 提醒 LLM 继续执行剩余阶段...")

                                # 🆕 从prompt获取工作流完成度验证消息
                                from agentype.prompts import get_prompt_manager

                                manager = get_prompt_manager(self.language)
                                workflow_message = manager.get_agent_specific_prompt(
                                    'mainagent',
                                    'WORKFLOW_COMPLETION_INITIAL_MESSAGE'
                                )

                                # 格式化 issues 列表，填充缺失的输出文件
                                formatted_issues = [
                                    issue.format(missing_outputs=', '.join(missing_outputs))
                                    if '{missing_outputs}' in issue
                                    else issue
                                    for issue in workflow_message['issues']
                                ]

                                validation_result = {
                                    "valid": False,
                                    "issues": formatted_issues
                                }

                                # 设置标志位，记录已发送提醒
                                self.workflow_completion_reminder_sent = True

                                # 重新调用 LLM，要求继续执行
                                response = await self._retry_llm_call_with_correction(
                                    messages, validation_result, 10, self.api_timeout
                                )
                                analysis_log.append({
                                    "iteration": iteration,
                                    "response": response,
                                    "validation": {"valid": False, "issues": ["工作流未完成，已发送提醒"]},
                                    "type": "ai_response_retry_for_workflow_completion"
                                })
                                continue  # 继续循环，不 break
                            else:
                                # 第二次仍然缺失，接受结束
                                self._log_warning(f"⚠️ 已提醒 LLM 但仍输出 final_answer，接受当前结果")
                                self._log_info(f"📁 注意：缺少输出文件 {', '.join(missing_outputs)}")
                                # 继续执行，允许退出

                        self._log_success(f"✅ 分析完成，结果: {final_result}")
                        self._log_info(f"📁 已从 bundle 读取到路径信息")

                        # 直接使用 final_result，不添加 token 统计报告
                        final_answer = final_result
                        break
                    else:
                        # Bundle 读取失败
                        self._log_error("❌ 无法从 bundle 读取文件路径")
                        self._log_error(f"   Bundle 返回: {bundle_result}")
                        validation_result = {
                            "valid": False,
                            "issues": [
                                "系统无法从 bundle 读取文件路径信息",
                                "可能原因：工具未正确保存路径到 bundle",
                                "请检查之前的工具调用是否成功执行"
                            ]
                        }
                        response = await self._retry_llm_call_with_correction(messages, validation_result, 10, self.api_timeout)
                        analysis_log.append({
                            "iteration": iteration,
                            "response": response,
                            "validation": {"valid": False, "issues": ["Bundle路径读取失败，已重试"]},
                            "type": "ai_response_retry_for_bundle_failure"
                        })
                        continue
                else:
                    self._log_warning("⚠️ 发现final_answer标签但无法提取内容")

            # 提取并执行 action
            action = ReactParser.extract_action(response, self.available_tools)
            if action:
                # 检查是否有解析错误
                if 'error' in action:
                    error_msg = action.get('message', action.get('error'))
                    self._log_warning(f"Action解析错误: {error_msg}")
                    # 构造observation让LLM知道问题
                    error_observation = f"<observation>{{\"error\": \"{error_msg}\"}}</observation>"
                    messages.append({"role": "user", "content": error_observation})
                    continue

                function_name = action['function']
                parameters_str = action['parameters']
                parameters = ReactParser.parse_parameters(parameters_str)

                self._log_info(f"🔧 调用工具: {function_name}, 参数: {parameters}")

                # 执行 MCP 工具调用
                tool_result = await self.mcp_client.call_tool(function_name, parameters)

                if tool_result and tool_result.get("success"):
                    raw_content = tool_result.get("content", "")
                    self._log_success(f"✅ 工具调用成功，内容长度: {len(raw_content)}")

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
                    self._log_error("❌ 工具调用失败")

                # 记录分析日志
                analysis_log.append({
                    "iteration": iteration,
                    "action": action,
                    "result": result_content,
                    "type": "tool_call"
                })

                # 💰 工具调用后收集token统计
                try:
                    tool_token_summary = await self._collect_all_token_stats()
                    simple_report = tool_token_summary.get('simple_report', '')

                    if simple_report:
                        self._log_info(f"💰 {simple_report}")
                except Exception as e:
                    self._log_warning(f"⚠️ Token统计失败: {e}")

                # 🔍 进度监控：特定工具调用后检查簇完成度
                progress_reminder = ""
                if function_name in ["enhanced_gene_analysis", "save_cluster_type"]:
                    try:
                        # 尝试从之前的分析日志中找到marker基因文件路径
                        marker_genes_path = None
                        for log_entry in reversed(analysis_log):
                            if log_entry.get("type") == "tool_call" and "marker_genes_json" in str(log_entry.get("result", "")):
                                result_str = str(log_entry.get("result", ""))
                                if ".agentype_cache" in result_str and "cluster_marker_genes" in result_str:
                                    # 简单提取路径
                                    path_match = re.search(r'/[^\s"]+cluster_marker_genes[^\s"]*\.json', result_str)
                                    if path_match:
                                        marker_genes_path = path_match.group()
                                        break

                        if marker_genes_path:
                            completion_status = check_cluster_completion(marker_genes_path)
                            if completion_status.get("success", False):
                                completed = completion_status.get("completed_clusters", 0)
                                total = completion_status.get("total_clusters", 0)
                                rate = completion_status.get("completion_rate", 0)

                                from agentype.prompts import get_prompt_manager

                                manager = get_prompt_manager(self.language)

                                if not completion_status.get("all_completed", False):
                                    incomplete = completion_status.get("incomplete_clusters", [])
                                    reminder_template = manager.get_agent_specific_prompt('mainagent', 'PROGRESS_REMINDER_TEMPLATE')
                                    progress_reminder = reminder_template.format(
                                        completed=completed,
                                        total=total,
                                        incomplete_clusters=', '.join(incomplete[:5])
                                    )
                                else:
                                    complete_template = manager.get_agent_specific_prompt('mainagent', 'CLUSTER_PROGRESS_COMPLETE_MESSAGE')
                                    next_action = manager.get_agent_specific_prompt('mainagent', 'CLUSTER_PROGRESS_ACTION_GENERAL_NEXT')
                                    completion_message = complete_template.format(
                                        total_clusters=total,
                                        next_action=next_action
                                    )
                                    progress_reminder = f"\n\n{completion_message}"

                                self._log_info(progress_reminder)
                    except Exception as e:
                        self._log_warning(f"⚠️ 进度监控检查失败: {e}")

                # 构造 observation 并添加到对话
                observation = f"<observation>{result_content}{progress_reminder}</observation>"
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content": observation})
            else:
                # 没有工具调用且没有final_answer，强制要求LLM提供final_answer
                self._log_warning("⚠️ 未检测到有效的工具调用且无final_answer，要求提供最终答案")
                validation_result = {
                    "valid": False,
                    "issues": ["必须提供<final_answer>标签和文件路径信息来完成分析"]
                }
                response = await self._retry_llm_call_with_correction(messages, validation_result, 10, self.api_timeout)
                # 重新分析新的响应
                analysis_log.append({
                    "iteration": iteration,
                    "response": response,
                    "validation": {"valid": False, "issues": ["缺少final_answer，已重试"]},
                    "type": "ai_response_retry_for_final_answer"
                })
                continue

        # 使用新的优先级方法解析文件路径
        # 如果循环正常结束（有final_answer），应该已经提取了paths
        extracted_paths = {}
        final_cluster_completion_status = None

        # 查找最后一个包含final_answer的AI响应
        last_final_answer_response = None
        for log_entry in reversed(analysis_log):
            if log_entry.get('type') == 'ai_response':
                response_content = log_entry.get('response', '')
                if ReactParser.has_final_answer(response_content):
                    last_final_answer_response = response_content
                    break

        # 查找最后一次簇完成度检查结果
        for log_entry in reversed(analysis_log):
            if log_entry.get('type') == 'cluster_completion_verification':
                final_cluster_completion_status = log_entry.get('cluster_completion_check')
                break

        if last_final_answer_response:
            # 从 bundle 读取路径信息
            bundle_result = load_file_paths_bundle()
            if bundle_result.get("success"):
                # 从扁平化结构中提取所有路径字段（排除元数据字段）
                metadata_keys = {"success", "session_id", "timestamp", "metadata", "cluster_mapping"}
                extracted_paths = {k: v for k, v in bundle_result.items() if k not in metadata_keys}
                valid_paths = {k: v for k, v in extracted_paths.items() if v}
                if valid_paths:
                    self._log_header("\n📁 最终文件路径 (从 bundle 读取):")
                    for file_type, path in valid_paths.items():
                        self._log_info(f"   {file_type}: {path}")
            else:
                self._log_warning("⚠️ 无法从 bundle 读取文件路径")
        else:
            self._log_warning("⚠️ 未找到包含final_answer的响应")

        self._log_header(f"\n📊 分析总结:")
        self._log_info(f"总迭代次数: {iteration}")
        self._log_info(f"最终结果: {final_answer}")
        self._log_info(f"工具调用次数: {len([log for log in analysis_log if log['type'] == 'tool_call'])}")

        # 打印簇完成度信息
        if final_cluster_completion_status:
            self._log_header(f"🔍 簇注释完成情况:")
            if final_cluster_completion_status.get("success", False):
                completed = final_cluster_completion_status.get("completed_clusters", 0)
                total = final_cluster_completion_status.get("total_clusters", 0)
                rate = final_cluster_completion_status.get("completion_rate", 0)
                self._log_success(f"   ✅ 已完成: {completed}/{total} ({rate:.1%})")

                if final_cluster_completion_status.get("all_completed", False):
                    self._log_success(f"   🎉 所有簇已完成注释")
                else:
                    incomplete = final_cluster_completion_status.get("incomplete_clusters", [])
                    self._log_warning(f"   ⚠️  未完成: {', '.join(incomplete[:3])}{'...' if len(incomplete) > 3 else ''}")
            else:
                self._log_error(f"   ❌ 检查失败: {final_cluster_completion_status.get('error', '未知错误')}")
        else:
            self._log_info(f"   ℹ️  未进行簇完成度检查")

        if iteration >= self.context_summary_threshold:
            self._log_info(f"上下文总结: 已在第{self.context_summary_threshold}次迭代时触发")

        # 打印 LLM 日志统计
        if self.llm_logger:
            try:
                log_summary = self.llm_logger.get_log_summary()
                self._log_info(f"LLM统计: 总请求{log_summary.get('total_requests', 0)}次")
                self._log_info(f"成功/失败: {log_summary.get('success_count', 0)}/{log_summary.get('error_count', 0)}")
                self._log_info(f"日志文件: {log_summary.get('log_file', 'N/A')}")
            except Exception as e:
                self._log_warning(f"获取LLM统计失败: {e}")

        # 判断最终成功条件
        all_clusters_completed = True
        if final_cluster_completion_status:
            all_clusters_completed = final_cluster_completion_status.get("all_completed", False)
            if final_cluster_completion_status.get("success", True):
                # 如果检查成功，使用检查结果
                pass
            else:
                # 如果检查失败，默认为已完成（避免阻止流程）
                all_clusters_completed = True

        final_success = final_answer is not None and bool(extracted_paths) and all_clusters_completed

        # 收集所有Agent的token统计
        token_summary = await self._collect_all_token_stats()

        # 获取当前 session_id
        from agentype.mainagent.config.session_config import get_session_id
        current_session_id = get_session_id()

        # 构建完整的返回结果
        result_data = {
            "session_id": current_session_id,  # 会话ID，用于追踪和日志
            "language": self.language,  # 当前使用的语言（zh/en）
            "api_base": self.config.openai_api_base,  # API URL
            "model": self.config.openai_model,  # 使用的模型
            "input_data": user_input,
            "final_result": final_answer,
            "output_file_paths": extracted_paths,  # 解析出的文件路径
            "total_iterations": iteration,
            "context_summarized": iteration >= self.context_summary_threshold,
            "context_summary_threshold": self.context_summary_threshold,
            "analysis_log": analysis_log,
            "llm_log_summary": self.llm_logger.get_log_summary() if self.llm_logger else None,
            "cluster_completion_status": final_cluster_completion_status,
            "all_clusters_completed": all_clusters_completed,
            "token_stats": token_summary,
            "success": final_success
        }

        # ===== 保存 JSON 结果到文件 =====
        try:
            import json
            from datetime import datetime
            # 使用 results/celltypeMainagent 目录
            results_dir = self.config.get_results_dir()

            # 构建文件路径: outputs/results/celltypeMainagent/result_{session_id}.json
            result_filename = f"result_{current_session_id}.json"
            result_file_path = results_dir / result_filename

            # 保存 JSON 文件
            with open(result_file_path, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)

            # 添加保存信息到返回结果
            result_data["result_file"] = str(result_file_path)
            result_data["result_saved_at"] = datetime.now().isoformat()

            self._log_success(f"✅ 分析结果已保存: {result_file_path}")

        except Exception as e:
            self._log_warning(f"⚠️ 保存结果文件失败: {e}")
            # 保存失败不影响主流程
            result_data["result_file"] = None
            result_data["result_save_error"] = str(e)

        # 返回完整结果（包含保存的文件路径）
        return result_data

    async def _collect_all_token_stats(self) -> Dict[str, Any]:
        """收集所有Agent的token统计信息

        策略：
        所有 Agent (包括 MainAgent) 统一通过日志文件解析统计
        """
        try:
            # 获取当前 session_id
            from agentype.mainagent.config.session_config import get_session_id
            current_session_id = get_session_id()

            # 初始化日志解析器
            # 使用配置的日志目录
            from pathlib import Path
            log_base_dir = str(Path(self.config.log_dir) / "llm")

            self._log_info(f"📂 从日志目录解析所有 Agent 统计: {log_base_dir}")

            # 定义所有需要查询的 Agent (包括 MainAgent)
            agents_to_query = ["MainAgent", "SubAgent", "DataAgent", "AppAgent"]
            all_agent_stats = {}

            try:
                log_parser = LogTokenParser(log_base_dir)

                # 解析每个 Agent 的日志
                for agent_name in agents_to_query:
                    try:
                        stats = log_parser.parse_agent_logs(agent_name, current_session_id)
                        all_agent_stats[agent_name] = stats

                        if stats.total_tokens > 0:
                            prompt_str = f"{stats.prompt_tokens:,}"
                            completion_str = f"{stats.completion_tokens:,}"
                            total_str = f"{stats.total_tokens:,}"
                            self._log_success(
                                f"✅ {agent_name}: {total_str} tokens "
                                f"(输入: {prompt_str}, 输出: {completion_str}) "
                                f"({stats.request_count} 次请求)"
                            )
                        else:
                            self._log_info(f"📭 {agent_name}: 暂无 token 消耗")

                    except Exception as e:
                        self._log_warning(f"⚠️ 解析 {agent_name} 日志失败: {e}")
                        # 创建空统计对象作为占位符
                        all_agent_stats[agent_name] = TokenStatistics(agent_name=agent_name)

            except Exception as e:
                self._log_warning(f"⚠️ 初始化日志解析器失败: {e}")
                # 降级：所有 Agent 使用空统计
                for agent_name in agents_to_query:
                    all_agent_stats[agent_name] = TokenStatistics(agent_name=agent_name)

            # 分离 MainAgent 和子 Agent
            main_agent_stats = all_agent_stats.get("MainAgent", TokenStatistics(agent_name="MainAgent"))
            sub_agent_stats = {k: v for k, v in all_agent_stats.items() if k != "MainAgent"}

            # 合并所有token统计
            total_stats = merge_token_stats(list(all_agent_stats.values()))
            total_stats.agent_name = "Total"

            self._log_success(f"📊 总 Token 统计: {total_stats.total_tokens:,} tokens")

            # 生成报告，从 total_stats 中获取 api_base（由日志解析器提取）
            # 优先使用 total_stats.api_base，如果为空则使用 config
            api_base = total_stats.api_base if total_stats.api_base else self.config.openai_api_base
            simple_report = self.token_reporter.generate_simple_report(total_stats, api_base=api_base)
            detailed_report = self.token_reporter.generate_detailed_report(total_stats, sub_agent_stats, api_base=api_base)

            return {
                "main_agent": main_agent_stats.get_summary(api_base=api_base),
                "sub_agents": {name: stats.get_summary(api_base=api_base) for name, stats in sub_agent_stats.items()},
                "total": total_stats.get_summary(api_base=api_base),
                "simple_report": simple_report,
                "detailed_report": detailed_report
            }

        except Exception as e:
            self._log_error(f"❌ 收集token统计失败: {e}")
            return {
                "main_agent": {"error": str(e)},
                "sub_agents": {},
                "total": {"error": str(e)},
                "simple_report": f"统计失败: {e}",
                "detailed_report": f"统计失败: {e}",
                "error": str(e)
            }

    # 已去除旧的兼容性工作流入口与解析器包装，统一由 React 驱动
