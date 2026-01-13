#!/usr/bin/env python3
"""
agentype - Celltype Annotation Agent模块
Author: cuilei
Version: 1.0
"""

import asyncio
import gc
import json
import os
import requests
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import sys

# Token统计模块
from agentype.common.token_statistics import TokenReporter

# Prompts for CellType App Agent
from agentype.appagent.config.prompts import (
    SUPPORTED_LANGUAGES,
    DEFAULT_LANGUAGE,
    get_system_prompt_template,
    get_fallback_prompt_template,
    get_user_query_templates,
    build_unified_user_query,
)
from agentype.common.language_manager import get_current_language

# Core components
from agentype.appagent.config.settings import ConfigManager
from agentype.appagent.clients.mcp_client import MCPClient
from agentype.appagent.utils.content_processor import CelltypeContentProcessor
from agentype.appagent.utils.parser import CelltypeReactParser
from agentype.appagent.utils.validator import CelltypeValidationUtils
from agentype.appagent.utils.i18n import _
from agentype.appagent.utils.output_logger import CelltypeOutputLogger
from agentype.appagent.utils.path_manager import path_manager
# 导入共享模块
from agentype.common.llm_client import LLMClient
from agentype.common.llm_logger import LLMLogger
from agentype.common.streaming_filter import StreamingFilter
# 导入文件路径工具
from agentype.mainagent.tools.file_paths_tools import load_file_paths_bundle


class CelltypeAnnotationAgent:
    """细胞类型注释 React Agent（App Agent）

    参考 DataProcessorReactAgent 与 CellTypeReactAgent 的结构与逻辑，
    使用本模块 prompts 中规定的注释流程与格式进行迭代式工具调用与推理。
    """

    def __init__(
        self,
        config: Optional[ConfigManager] = None,
        server_script: str = None,
        max_content_length: int = 10000,
        enable_summarization: bool = True,
        max_iterations: int = 50,
        context_summary_threshold: int = 15,
        max_context_length: int = 150000,
        enable_llm_logging: bool = True,
        log_dir: str = None,
        language: Optional[str] = None,
        enable_streaming: bool = True,
        api_timeout: int = 300,
        enable_console_output: bool = True,
        console_output: bool = None,
        file_output: bool = None,
        session_id: str = None,
    ):
        # 🌟 设置 session_id（如果提供）
        # 注意：在MCP模式下，session_id已在MCP Server启动时设置，此处不再重复打印
        if session_id:
            from agentype.mainagent.config.session_config import set_session_id
            set_session_id(session_id)

        # 配置
        self.config = config or ConfigManager()

        # 如果没有指定server_script，使用路径管理器获取默认路径
        if server_script is None:
            server_script = str(path_manager.get_mcp_server_path())
        self.mcp_client = MCPClient(server_script, config=self.config)

        # 内容处理、解析与验证
        self.content_processor = CelltypeContentProcessor(
            max_content_length=max_content_length,
            enable_summarization=enable_summarization,
        )
        self.parser = CelltypeReactParser()
        self.validator = CelltypeValidationUtils()

        # 语言
        resolved_language = language or get_current_language()
        self.language = resolved_language if resolved_language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE

        # LLM 日志
        self.enable_llm_logging = enable_llm_logging
        # 如果没有指定log_dir，使用 ConfigManager 的日志目录
        if log_dir is None:
            from pathlib import Path
            log_dir = str(Path(self.config.log_dir) / "llm" / "AppAgent")
        self.llm_logger = LLMLogger(log_dir) if enable_llm_logging else None

        # 运行时
        self.available_tools: List[Dict] = []
        self.max_iterations = max_iterations
        self.context_summary_threshold = context_summary_threshold
        self.max_context_length = max_context_length

        # API
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
            self.console_logger = CelltypeOutputLogger(
                log_prefix="celltypeAppAgent",
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
        """启动 MCP 服务器并获取工具列表"""
        if not await self.mcp_client.start_server():
            return False
        self.available_tools = await self.mcp_client.list_tools()
        return True

    def set_language(self, language: str):
        if language in SUPPORTED_LANGUAGES:
            self.language = language
            self._log_success(_("agent.language_set", language=language))
        else:
            self._log_warning(_("agent.language_not_supported", language=language, supported=SUPPORTED_LANGUAGES))

    def _get_system_prompt(self) -> str:
        """根据 AppAgent 的系统模板构造系统提示语"""
        try:
            work_dir = os.getenv("CELLTYPE_WORK_DIR", str(Path.cwd()))

            print(f"🔍 调试输出: AppAgent配置信息:")
            print(f"   - 工作目录: {work_dir}")

            template = get_system_prompt_template(self.language)
            tool_list = "\n".join(
                [f"{i+1}. {t.get('name', 'Unknown')}: {t.get('description', '')}" for i, t in enumerate(self.available_tools)]
            )

            cache_status = "✓ MCP 服务器已启动" if self.language == "zh" else "✓ MCP Server Started"

            try:
                files = [f for f in os.listdir(work_dir) if os.path.isfile(os.path.join(work_dir, f))]
                file_list = ", ".join(files)
            except Exception:
                file_list = "celltype_annotation_agent.py, prompts.py, mcp_server.py"

            return template.format(
                tool_list=tool_list,
                operating_system="Linux",
                cache_status=cache_status,
                file_list=file_list,
            )
        except Exception as e:
            self._log_warning(_("agent.template_fallback", error=e))
            fallback = get_fallback_prompt_template(self.language)
            tool_names = ", ".join([t.get("name", "") for t in self.available_tools])
            return fallback.format(tool_names=tool_names)

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

    async def _retry_llm_call_with_correction(
        self, messages: List[Dict], validation_result: Dict, max_retries: int = 10, timeout: int = 270
    ) -> str:
        retry_count = 0
        response = ""
        while retry_count < max_retries:
            retry_count += 1
            self._log_warning(_("retry.llm_retry", retry=retry_count, max_retries=max_retries))
            self._log_info(_("retry.last_response_issues", issues=", ".join(validation_result.get("issues", []))))

            correction_prompt = CelltypeValidationUtils.build_annotation_correction_prompt(
                validation_result, self.available_tools, self.language
            )
            correction_messages = messages.copy()
            correction_messages.append({"role": "user", "content": correction_prompt})
            response = await self._call_openai(correction_messages, timeout, stream=self.enable_streaming)

            new_validation = CelltypeValidationUtils.validate_response_format(response)
            if new_validation.get("valid"):
                self._log_success(_("retry.retry_success"))
                return response
            else:
                self._log_error(_("retry.retry_failed", count=retry_count, issues=", ".join(new_validation.get("issues", []))))
                validation_result = new_validation
        self._log_error(_("retry.max_retries_reached"))
        return response

    async def _summarize_context(self, messages: List[Dict]) -> List[Dict]:
        """当对话过长时，对历史进行总结，插入一条 [上下文总结] 消息以压缩上下文"""
        try:
            self._log_warning(_("context.too_long"))
            system_message = messages[0] if messages and messages[0]["role"] == "system" else None
            initial_query = messages[1] if len(messages) > 1 and messages[1]["role"] == "user" else None

            existing_summary = None
            summary_index = -1
            for i, msg in enumerate(messages):
                if msg.get("role") == "assistant" and "[上下文总结]" in msg.get("content", ""):
                    existing_summary = msg
                    summary_index = i
                    break

            if existing_summary and summary_index > 1:
                conversation_to_summarize = messages[summary_index + 1 : -4] if len(messages) > summary_index + 5 else messages[summary_index + 1 :]
                recent_messages = messages[-4:] if len(messages) > summary_index + 5 else []
            else:
                conversation_to_summarize = messages[2:-4] if len(messages) > 6 else messages[2:]
                recent_messages = messages[-4:] if len(messages) > 6 else []

            if not conversation_to_summarize:
                self._log_info(_("context.no_history"))
                return messages

            conversation_text = ""
            for msg in conversation_to_summarize:
                conversation_text += f"\n{msg['role'].upper()}: {msg['content']}\n"

            if existing_summary:
                existing_summary_content = existing_summary.get("content", "").replace("[上下文总结] 之前的注释进展：", "").strip()
                summarization_prompt = (
                    "请基于之前的总结，继续总结新增的细胞类型注释对话历史：\n\n"
                    f"之前的总结：\n{existing_summary_content}\n\n新增的对话历史：\n{conversation_text}\n\n"
                    "请更新总结，整合新发现的信息，包含：\n"
                    "1. 已执行的主要工具调用及其结果\n"
                    "2. 发现的重要信息或线索\n"
                    "3. 当前进展和待解决的问题\n"
                    "总结要简明扼要，聚焦后续注释流程有用的信息。"
                )
            else:
                summarization_prompt = (
                    "请总结以下细胞类型注释的对话历史，保留关键信息和重要发现：\n\n"
                    f"对话历史：\n{conversation_text}\n\n"
                    "请生成一个简洁的总结，包含：\n"
                    "1. 已执行的主要工具调用及其结果\n"
                    "2. 发现的重要信息或线索\n"
                    "3. 当前进展和待解决的问题\n"
                    "总结要简明扼要，聚焦后续注释流程有用的信息。"
                )

            summary_messages = [{"role": "user", "content": summarization_prompt}]
            summary = await self._call_openai(summary_messages, timeout=self.api_timeout, stream=self.enable_streaming)

            new_messages: List[Dict] = []
            if system_message:
                new_messages.append(system_message)
            if initial_query:
                new_messages.append(initial_query)
            new_messages.append({"role": "assistant", "content": f"[上下文总结] 之前的注释进展：{summary}"})
            new_messages.extend(recent_messages)

            self._log_success(_("context.summary_completed"))
            self._log_info(_("context.original_messages", count=len(messages)))
            self._log_info(_("context.summarized_messages", count=len(new_messages)))
            self._log_info(_("context.summary_length", length=len(summary)))
            return new_messages
        except Exception as e:
            self._log_error(f"❌ 上下文总结失败: {e}")
            return messages[-10:] if len(messages) > 10 else messages

    def _build_user_query(
        self,
        rds_path: Optional[str],
        h5ad_path: Optional[str],
        tissue_description: Optional[str],
        marker_json_path: Optional[str],
        species: Optional[str],
        h5_path: Optional[str] = None,
        cluster_column: Optional[str] = None,
    ) -> str:
        """使用统一模板构建 <question> 内容，未提供字段以“无/None”占位"""
        file_paths = {
            'rds_file': rds_path,
            'h5ad_file': h5ad_path,
            'h5_file': h5_path,
            'marker_genes_json': marker_json_path,
        }
        return build_unified_user_query(
            file_paths=file_paths,
            tissue_description=tissue_description,
            species=species,
            language=self.language,
            cluster_column=cluster_column,
        )

    async def annotate(
        self,
        rds_path: Optional[str],
        h5ad_path: Optional[str],
        tissue_description: Optional[str] = None,
        marker_json_path: Optional[str] = None,
        species: Optional[str] = None,
        h5_path: Optional[str] = None,
        cluster_column: Optional[str] = None,
    ) -> Dict:
        """执行基于 prompts 的 React 注释流程（迭代调用工具直到 <final_answer>）"""
        self._log_header(_("annotation.pipeline.starting", default="开始细胞类型注释 React 流程"))

        # 🌟 增强物种检测逻辑
        final_species = species
        species_detection_result = None

        if not final_species:
            self.console_logger.info("🔍 未提供物种参数，AppAgent自动检测...")

            # 优先级1: 从 marker JSON 检测
            if marker_json_path:
                from agentype.appagent.tools.species_detection import detect_species_from_marker_json
                try:
                    detected, info = detect_species_from_marker_json(marker_json_path)
                    if info.get("confidence") in ["high", "medium"]:
                        final_species = detected
                        species_detection_result = info
                        self.console_logger.success(f"✅ 从JSON检测到: {detected} (置信度: {info.get('confidence')})")
                except Exception as e:
                    self.console_logger.warning(f"⚠️ JSON检测失败: {e}")

            # 优先级2: 从 H5AD 检测
            if not final_species and h5ad_path:
                from agentype.appagent.tools.species_detection import detect_species_from_h5ad
                try:
                    detected, info = detect_species_from_h5ad(h5ad_path)
                    if info.get("confidence") in ["high", "medium"]:
                        final_species = detected
                        species_detection_result = info
                        self.console_logger.success(f"✅ 从H5AD检测到: {detected} (置信度: {info.get('confidence')})")
                except Exception as e:
                    self.console_logger.warning(f"⚠️ H5AD检测失败: {e}")

            # 优先级3: 从 RDS 检测
            if not final_species and rds_path:
                from agentype.appagent.tools.species_detection import detect_species_from_rds
                try:
                    detected, info = detect_species_from_rds(rds_path)
                    if info.get("confidence") in ["high", "medium"]:
                        final_species = detected
                        species_detection_result = info
                        self.console_logger.success(f"✅ 从RDS检测到: {detected} (置信度: {info.get('confidence')})")
                except Exception as e:
                    self.console_logger.warning(f"⚠️ RDS检测失败: {e}")

            # 降级到默认值
            if not final_species:
                final_species = "Human"
                self.console_logger.warning("⚠️ 所有检测失败，使用默认物种: Human")
        else:
            self.console_logger.info(f"✅ 使用传入的物种参数: {final_species}")

        system_prompt = self._get_system_prompt()
        user_query = self._build_user_query(
            rds_path,
            h5ad_path,
            tissue_description,
            marker_json_path,
            final_species,  # 🌟 使用检测或传入的物种
            h5_path,
            cluster_column,
        )

        messages: List[Dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"<question>{user_query}</question>"},
        ]

        self._log_info(_("analysis.system_prompt_length", length=len(system_prompt)))
        self._log_info(_("analysis.user_query", query=user_query) + "\n")

        analysis_log: List[Dict] = []
        iteration = 0
        final_answer = None

        while iteration < self.max_iterations:
            iteration += 1
            self._log_info(_("analysis.iteration", iter=iteration, max=self.max_iterations))

            # 长上下文处理
            total_chars = sum(len(m.get("content", "")) for m in messages)
            if total_chars > self.max_context_length:
                messages = await self._summarize_context(messages)

            response = await self._call_openai(messages, timeout=self.api_timeout, stream=self.enable_streaming)
            validation = CelltypeValidationUtils.validate_response_format(response)

            analysis_log.append({"iteration": iteration, "response": response, "validation": validation, "type": "ai_response"})

            if not validation.get("valid"):
                self._log_warning(_("validation.response_invalid"))
                response = await self._retry_llm_call_with_correction(messages, validation, timeout=self.api_timeout)
                analysis_log.append({"iteration": iteration, "response": response, "type": "ai_response_retry"})

            if "</final_answer>" in response:
                final_answer = CelltypeReactParser.extract_final_answer(response)
                if final_answer:
                    self._log_success(_("analysis.analysis_completed", celltype=final_answer[:60] + ("..." if len(final_answer) > 60 else "")))
                    break
                else:
                    self._log_warning(_("analysis.final_answer_no_celltype"))

            action = CelltypeReactParser.extract_action(response, self.available_tools)
            if action:
                # 检查是否有解析错误
                if 'error' in action:
                    error_msg = action.get('message', action.get('error'))
                    self._log_warning(f"Action解析错误: {error_msg}")
                    # 构造observation让LLM知道问题
                    error_observation = f"<observation>{{\"error\": \"{error_msg}\"}}</observation>"
                    messages.append({"role": "user", "content": error_observation})
                    continue

                function_name = action["function"]
                parameters_str = action["parameters"]
                parameters = CelltypeReactParser.parse_parameters(parameters_str)

                self._log_info(_("tools.call.calling", name=function_name, params=parameters))
                tool_result = await self.mcp_client.call_tool(function_name, parameters)

                if tool_result and tool_result.get("success"):
                    raw_content = tool_result.get("content", "")
                    self._log_success(_("tools.call.success", length=len(raw_content)))

                    # 针对三种核心方法进行结果内容处理，其他工具直接传递原始内容
                    method_map = {
                        "singleR_annotate_tool": "SingleR",
                        "sctype_annotate_tool": "scType",
                        "celltypist_annotate_tool": "CellTypist",
                    }
                    method = method_map.get(function_name)
                    result_content = (
                        self.content_processor.process_annotation_result(raw_content, method) if method else raw_content
                    )
                else:
                    result_content = json.dumps(
                        {
                            "error": tool_result.get("error", "工具调用失败") if tool_result else "无响应",
                            "success": False,
                        },
                        ensure_ascii=False,
                    )
                    self._log_error(_("tools.call.failed"))

                analysis_log.append({"iteration": iteration, "action": action, "result": result_content, "type": "tool_call"})

                observation = f"<observation>{result_content}</observation>"
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content": observation})
            else:
                self._log_info(_("tools.call.no_action"))
                break

        # 总结
        self._log_header(f"\n{_('analysis.summary.title')}")
        self._log_info(_("analysis.summary.total_iterations", iterations=iteration))
        self._log_info(_("analysis.summary.tool_calls", count=len([log for log in analysis_log if log.get('type') == 'tool_call'])))
        if iteration >= self.context_summary_threshold:
            self._log_info(_("analysis.summary.context_summary", threshold=self.context_summary_threshold))

        # ✅ 从bundle读取路径（MCP工具已自动保存到bundle）
        bundle = load_file_paths_bundle()
        output_file_paths = {}

        if bundle.get("success"):
            # 提取AppAgent相关的7个文件路径字段
            path_keys = ['rds_file', 'h5ad_file', 'h5_file', 'marker_genes_json',
                         'singler_result', 'sctype_result', 'celltypist_result']
            for key in path_keys:
                value = bundle.get(key)
                if value:  # 只保留非空值
                    output_file_paths[key] = value

            self._log_info(f"📁 从bundle读取到 {len(output_file_paths)} 个文件路径")

            # 打印读取的路径
            if output_file_paths:
                self._log_header("\n📁 从bundle读取的文件路径:")
                for file_type, path in output_file_paths.items():
                    self._log_info(f"   {file_type}: {path}")
        else:
            self._log_warning("⚠️ 未能从bundle读取路径")

        return {
            "inputs": {
                "rds_path": rds_path,
                "h5ad_path": h5ad_path,
                "h5_path": h5_path,
                "tissue_description": tissue_description,
                "marker_json_path": marker_json_path,
                "species": species,
                "cluster_column": cluster_column,
            },
            "final_answer": final_answer,
            "output_file_paths": output_file_paths,
            "total_iterations": iteration,
            "context_summarized": iteration >= self.context_summary_threshold,
            "context_summary_threshold": self.context_summary_threshold,
            "analysis_log": analysis_log,
            "llm_log_summary": (self.llm_logger.get_log_summary() if self.llm_logger else None),
            "success": final_answer is not None,
            # 🌟 新增：物种信息
            "species": final_species,  # 最终使用的物种
            "species_detection_info": species_detection_result,  # 检测详情
        }

    # 兼容性与便捷方法（非React）：
    def analyze_tissue_type(self, tissue_description: Optional[str]) -> Dict:
        """基于简单规则的组织类型分析与推荐（便捷函数）"""
        result = CelltypeValidationUtils.validate_tissue_type(tissue_description or "")
        tissue = result.get("tissue_type") or ""
        # 简单的推荐策略
        recommended = {
            "SingleR_reference_hint": "ImmGenData" if (tissue and any(k in tissue.lower() for k in ["免疫", "immune"])) else "HumanPrimaryCellAtlasData",
            "scType_tissue_hint": "Immune system" if (tissue and any(k in tissue.lower() for k in ["免疫", "immune"])) else "Blood",
            "CellTypist_model_hint": "Immune_All_High.pkl" if (tissue and any(k in tissue.lower() for k in ["免疫", "immune"])) else None,
        }
        return {"input": tissue_description, "normalized_tissue": tissue, "recognized": result.get("has_recognized_keywords", False), "recommendation": recommended}

    def run_full_annotation_pipeline(
        self, rds_path: str, h5ad_path: str, tissue_description: Optional[str] = None
    ) -> Dict:
        """直接调用 MCP 提供的一体化流水线工具（非React）。同步包装以便简易使用。"""
        async def _run():
            try:
                if not await self.initialize():
                    return {"success": False, "error": "Failed to start MCP server"}
                result = await self.mcp_client.celltype_annotation_pipeline(rds_path, h5ad_path, tissue_description)
                return result or {"success": False, "error": "No response"}
            finally:
                await self.cleanup()

        return asyncio.get_event_loop().run_until_complete(_run())

    async def cleanup(self):
        """释放资源"""
        try:
            await self.mcp_client.stop_server()

            # 关闭 LLM 日志记录器
            if self.llm_logger:
                await self.llm_logger.close()

            self.available_tools = []
            await asyncio.sleep(0.3)
            gc.collect()
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
