#!/usr/bin/env python3
"""
agentype - Data Processor Agent模块
Author: cuilei
Version: 1.0
"""

import asyncio
import gc
import json
import os
import requests
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Union, Optional
import sys

# Token统计模块
from agentype.common.token_statistics import TokenReporter

# AnnData 相关导入
try:
    from anndata import AnnData
    import scanpy as sc
    ANNDATA_AVAILABLE = True
except ImportError:
    AnnData = None
    sc = None
    ANNDATA_AVAILABLE = False

# 导入 prompts
from agentype.dataagent.config.prompts import (
    SUPPORTED_LANGUAGES,
    DEFAULT_LANGUAGE,
    get_system_prompt_template,
    get_fallback_prompt_template,
    get_user_query_templates
)

# 导入重构后的模块
from agentype.dataagent.config.settings import ConfigManager
from agentype.dataagent.clients.mcp_client import MCPClient
from agentype.dataagent.utils.content_processor import ContentProcessor
from agentype.dataagent.utils.parser import ReactParser
from agentype.dataagent.utils.validator import ValidationUtils
from agentype.dataagent.utils.i18n import _
from agentype.dataagent.utils.path_manager import path_manager
from agentype.dataagent.utils.output_logger import OutputLogger
# 导入共享模块
from agentype.common.llm_client import LLMClient
from agentype.common.llm_logger import LLMLogger
from agentype.common.streaming_filter import StreamingFilter
# 导入文件路径工具
from agentype.mainagent.tools.file_paths_tools import load_file_paths_bundle

class DataProcessorReactAgent:
    """数据处理 React Agent
    
    该类是数据处理系统的核心，负责协调 MCP 客户端、内容处理器、
    验证工具等组件，执行完整的数据处理流程。
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

        # 配置验证
        print(f"🔍 调试输出: DataAgent初始化开始...")

        # 🌟 设置 session_id（如果提供）
        # 注意：在MCP模式下，session_id已在MCP Server启动时设置，此处不再重复打印
        if session_id:
            from agentype.mainagent.config.session_config import set_session_id
            set_session_id(session_id)

        if not config:
            raise ValueError("配置对象不能为空")

        # 验证关键配置项
        if not hasattr(config, 'openai_api_base') or not config.openai_api_base:
            raise ValueError("缺少必要配置: openai_api_base")
        if not hasattr(config, 'openai_api_key') or not config.openai_api_key:
            raise ValueError("缺少必要配置: openai_api_key")

        print(f"✅ 配置验证通过")
        print(f"🔍 调试输出: API Base: {config.openai_api_base}")
        print(f"🔍 调试输出: API Key: {'***已设置***' if config.openai_api_key else 'None'}")
        print(f"🔍 调试输出: Model: {getattr(config, 'openai_model', 'default')}")

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
                llm_log_dir = str(Path(self.config.log_dir) / "llm" / "DataAgent")
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
                log_prefix="celltypeDataAgent",
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
        """初始化 agent"""
        print(f"🔍 调试输出: DataAgent开始初始化...")

        # 启动 MCP 服务器
        print(f"🔍 调试输出: 启动MCP服务器...")
        if not await self.mcp_client.start_server():
            print(f"❌ MCP服务器启动失败")
            return False
        print(f"✅ MCP服务器启动成功")

        # 获取可用工具
        print(f"🔍 调试输出: 获取可用工具列表...")
        self.available_tools = await self.mcp_client.list_tools()
        print(f"✅ 获取到 {len(self.available_tools)} 个工具")

        # 验证LLM日志记录器是否正常
        if self.llm_logger:
            print(f"✅ LLM日志记录器已启用: {self.llm_logger.log_dir}")
        else:
            print(f"⚠️ LLM日志记录器未启用")

        print(f"✅ DataAgent初始化完成")
        return True
    
    def set_language(self, language: str):
        """设置分析语言"""
        if language in SUPPORTED_LANGUAGES:
            self.language = language
            self._log_success(_("agent.language_set", language=language))
        else:
            self._log_warning(_("agent.language_not_supported", language=language, supported=SUPPORTED_LANGUAGES))

    def _get_system_prompt(self) -> str:
        """获取数据处理 React 系统 prompt"""
        try:
            # 使用实际的配置路径（显示绝对路径，便于调试和监测）
            base_dir = Path(self.config.output_dir)
            work_dir = base_dir
            results_dir = Path(self.config.results_dir)

            # 生成示例文件路径
            input_file_example = str(work_dir / "data.rds")
            input_h5_example = str(work_dir / "data.h5")
            marker_genes_json_example = str(results_dir / "cluster_marker_genes.json")

            print(f"🔍 调试输出: DataAgent路径示例（仅供参考，实际路径由MCP Server配置决定）:")
            print(f"   - 工作目录示例: {work_dir.as_posix()}")
            print(f"   - 结果目录示例: {results_dir.as_posix()}")
            print(f"   - RDS示例: {input_file_example}")
            print(f"   - H5示例: {input_h5_example}")
            print(f"   - marker_genes_json示例: {marker_genes_json_example}")

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
                file_list = "data_processor_mcp_server.py, data_processor_agent.py"

            # 格式化模板，一次性替换所有占位符
            return template.format(
                tool_list=tool_list,
                operating_system="Linux",
                cache_status=cache_status,
                file_list=file_list,
                # 添加动态路径参数
                results_dir=str(results_dir),
                input_file_example=input_file_example,
                input_h5_example=input_h5_example,
                json_file_example=marker_genes_json_example
            )

        except Exception as e:
            # fallback 到简化版本
            self._log_warning(_("agent.template_fallback", error=e))
            fallback_template = get_fallback_prompt_template(self.language)
            tool_names = ', '.join([tool.get('name', '') for tool in self.available_tools])
            return fallback_template.format(tool_names=tool_names)
    
    def _sort_files_by_priority(self, file_list):
        """按文件类型优先级排序：rds > h5ad > h5 > csv > json

        Args:
            file_list: 文件路径列表

        Returns:
            按优先级排序后的文件列表
        """
        priority_map = {
            '.rds': 1,
            '.h5ad': 2,
            '.h5': 3,
            '.csv': 4,
            '.json': 5
        }

        def get_priority(file_path):
            ext = os.path.splitext(str(file_path).lower())[1]
            return priority_map.get(ext, 99)  # 未知格式排在最后

        return sorted(file_list, key=get_priority)

    def _auto_detect_species_from_json(self, marker_genes_json: str) -> Optional[Dict]:
        """
        从JSON文件自动检测物种（不使用LLM）

        Args:
            marker_genes_json: marker基因JSON文件路径

        Returns:
            物种检测结果字典，包含detected_species、confidence等信息
            如果检测失败返回None
        """
        try:
            from agentype.dataagent.utils.common import SpeciesDetector

            if not marker_genes_json or not os.path.exists(marker_genes_json):
                self._log_warning(f"⚠️ JSON文件不存在: {marker_genes_json}")
                return None

            self._log_info(f"🔍 正在从JSON文件自动检测物种: {marker_genes_json}")

            # 读取JSON并提取基因
            with open(marker_genes_json, 'r', encoding='utf-8') as f:
                data = json.load(f)

            gene_names = []
            # 支持多种JSON格式
            if isinstance(data, dict):
                # 格式1: {"cell_type1": ["gene1", "gene2"], ...}
                for value in data.values():
                    if isinstance(value, list):
                        gene_names.extend(value)
                # 格式2: {"genes": ["gene1", "gene2"]}
                if 'genes' in data and isinstance(data['genes'], list):
                    gene_names = data['genes']
            elif isinstance(data, list):
                # 格式3: ["gene1", "gene2", ...]
                if all(isinstance(item, str) for item in data):
                    gene_names = data
                # 格式4: [{"gene": "gene1"}, ...]
                elif all(isinstance(item, dict) for item in data):
                    for item in data:
                        if 'gene' in item:
                            gene_names.append(item['gene'])
                        elif 'symbol' in item:
                            gene_names.append(item['symbol'])

            # 去重
            gene_names = list(set(g for g in gene_names if g and isinstance(g, str)))

            if not gene_names:
                self._log_warning("⚠️ JSON文件中未找到基因信息")
                return None

            self._log_info(f"📊 从JSON提取到 {len(gene_names)} 个基因")

            # 调用检测器（阈值设置为0.8，最少5个基因）
            detector = SpeciesDetector(uppercase_threshold=0.8, min_genes_required=5)
            species, info = detector.detect_species_from_genes(gene_names)

            self._log_success(f"✅ DataAgent自动检测物种: {species} (置信度: {info.get('confidence')})")
            self._log_info(f"   大写比例: {info.get('uppercase_ratio'):.3f}, 有效基因数: {info.get('valid_genes')}")

            return {
                "detected_species": species,
                "detection_method": "json_genes_automatic",
                "confidence": info.get("confidence"),
                "gene_count": len(gene_names),
                "uppercase_ratio": info.get("uppercase_ratio"),
                "uppercase_count": info.get("uppercase_count"),
                "threshold": info.get("threshold")
            }
        except Exception as e:
            self._log_warning(f"⚠️ 自动物种检测失败: {e}")
            import traceback
            self._log_warning(f"   详细信息: {traceback.format_exc()}")
            return None
    
    def _save_anndata_to_h5ad(self, adata: 'AnnData') -> str:
        """将 AnnData 对象保存为 h5ad 文件
        
        Args:
            adata: scanpy AnnData 对象
            
        Returns:
            保存的 h5ad 文件路径
        """
        if not ANNDATA_AVAILABLE or AnnData is None:
            raise ImportError("scanpy 和 anndata 库未安装，无法处理 AnnData 对象")
        
        # 使用统一的缓存管理器获取缓存目录
        from agentype.dataagent.config.cache_config import get_cache_dir
        from agentype.config import get_session_id_for_filename
        cache_dir = get_cache_dir()

        # 使用 session_id 生成文件名
        session_id = get_session_id_for_filename()
        h5ad_filename = f"adata_{session_id}.h5ad"
        h5ad_path = cache_dir / h5ad_filename
        
        try:
            self._log_info(f"📊 AnnData 对象信息: {adata.n_obs} 细胞, {adata.n_vars} 基因")

            # 保存为 h5ad 文件，使用适度压缩
            self._log_info(f"💾 正在保存 AnnData 对象到: {h5ad_path}")
            adata.write_h5ad(str(h5ad_path), compression='gzip')

            self._log_success(f"✓ AnnData 对象已成功保存为 h5ad 文件")
            return str(h5ad_path)

        except Exception as e:
            self._log_error(f"❌ 保存 AnnData 对象时发生错误: {e}")
            raise
    
    class StreamingFilter:
        """流式输出内容过滤器"""
        
        def __init__(self):
            self.buffer = ""
            self.state = "normal"  # normal, in_action, in_thought, in_final_answer
            self.pending_output = ""
        
        def filter_chunk(self, new_chunk: str) -> str:
            """过滤新的内容块，返回应该显示的部分"""
            if not new_chunk:
                return ""
            
            output = ""
            self.buffer += new_chunk
            
            processed = 0
            i = 0
            
            while i < len(self.buffer):
                # 检查是否有足够的字符进行标签匹配
                remaining = self.buffer[i:]
                
                if self.state == "normal":
                    if remaining.startswith('<action>'):
                        self.state = "in_action"
                        i += len('<action>')
                        processed = i
                    elif remaining.startswith('<thought>'):
                        self.state = "in_thought"
                        i += len('<thought>')
                        processed = i
                    elif remaining.startswith('<final_answer>'):
                        self.state = "in_final_answer"
                        i += len('<final_answer>')
                        processed = i
                    elif remaining.startswith('<'):
                        # 可能是不完整的标签，停止处理
                        potential_tags = ['<action>', '<thought>', '<final_answer>']
                        is_potential = False
                        for tag in potential_tags:
                            if tag.startswith(remaining[:min(len(remaining), len(tag))]):
                                is_potential = True
                                break
                        
                        if is_potential and len(remaining) < 15:  # 标签长度限制
                            break  # 等待更多内容
                        else:
                            output += self.buffer[i]
                            i += 1
                            processed = i
                    else:
                        output += self.buffer[i]
                        i += 1
                        processed = i
                        
                elif self.state == "in_action":
                    if remaining.startswith('</action>'):
                        self.state = "normal"
                        i += len('</action>')
                        processed = i
                    elif remaining.startswith('</') and len(remaining) < 10:
                        # 可能是不完整的结束标签
                        if '</action>'.startswith(remaining):
                            break  # 等待更多内容
                        else:
                            i += 1
                            processed = i
                    else:
                        # 跳过action内容
                        i += 1
                        processed = i
                        
                elif self.state == "in_thought":
                    if remaining.startswith('</thought>'):
                        self.state = "normal"
                        i += len('</thought>')
                        processed = i
                    elif remaining.startswith('</') and len(remaining) < 11:
                        # 可能是不完整的结束标签
                        if '</thought>'.startswith(remaining):
                            break  # 等待更多内容
                        else:
                            output += self.buffer[i]
                            i += 1
                            processed = i
                    else:
                        output += self.buffer[i]
                        i += 1
                        processed = i
                        
                elif self.state == "in_final_answer":
                    if remaining.startswith('</final_answer>'):
                        self.state = "normal"
                        i += len('</final_answer>')
                        processed = i
                    elif remaining.startswith('</') and len(remaining) < 16:
                        # 可能是不完整的结束标签
                        if '</final_answer>'.startswith(remaining):
                            break  # 等待更多内容
                        else:
                            output += self.buffer[i]
                            i += 1
                            processed = i
                    else:
                        output += self.buffer[i]
                        i += 1
                        processed = i
            
            # 保留未处理的部分
            self.buffer = self.buffer[processed:]
            return output

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
            response = await self._call_openai(correction_messages, timeout, stream=self.enable_streaming)
            
            # 为重试调用添加额外的日志标记
            if self.llm_logger:
                self._log_info(_("retry.retry_logged", count=retry_count))
            
            # 验证新响应
            new_validation = ValidationUtils.validate_response_format(response)
            
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
            if existing_summary and summary_index > 1:
                # 如果已有总结，从总结后开始到倒数几轮
                conversation_to_summarize = messages[summary_index+1:-4] if len(messages) > summary_index + 5 else messages[summary_index+1:]
                recent_messages = messages[-4:] if len(messages) > summary_index + 5 else []
            else:
                # 如果没有总结，从第3条消息开始（跳过系统消息和初始查询）
                conversation_to_summarize = messages[2:-4] if len(messages) > 6 else messages[2:]
                recent_messages = messages[-4:] if len(messages) > 6 else []
            
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
            if existing_summary:
                existing_summary_content = existing_summary.get("content", "").replace("[上下文总结] 之前的处理进展：", "").strip()
                summarization_prompt = f"""请基于之前的总结，继续总结新增的数据处理对话历史：

之前的总结：
{existing_summary_content}

新增的对话历史：
{conversation_text}

请更新总结，整合新发现的信息，包含：
1. 已执行的主要工具调用及其结果
2. 发现的重要数据信息或处理线索  
3. 当前处理进展和待解决的问题

总结应该简明扼要，重点关注对后续处理有用的信息。"""
            else:
                summarization_prompt = f"""请总结以下数据处理的对话历史，保留关键信息和重要发现：

对话历史：
{conversation_text}

请生成一个简洁的总结，包含：
1. 已执行的主要工具调用及其结果
2. 发现的重要数据信息或处理线索
3. 当前处理进展和待解决的问题

总结应该简明扼要，重点关注对后续处理有用的信息。"""

            # 调用OpenAI进行总结，保持与主调用相同的流式输出设置
            summary_messages = [{"role": "user", "content": summarization_prompt}]
            summary = await self._call_openai(summary_messages, timeout=self.api_timeout, stream=self.enable_streaming)  # 上下文总结使用配置的超时时间
            
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
    
    async def process_data(self, input_data: Union[str, List[str], 'AnnData'], species: Optional[str] = None) -> Dict:
        """处理数据

        Args:
            input_data: 输入数据，可以是：
                - 单个文件路径字符串
                - 文件路径列表
                - scanpy AnnData 对象
            species: 可选的物种参数(从MainAgent传递)

        Returns:
            处理结果字典
        """
        # 检测并处理 AnnData 对象
        if ANNDATA_AVAILABLE and AnnData is not None and isinstance(input_data, AnnData):
            self._log_info("🧬 检测到 AnnData 对象，正在保存为 h5ad 文件...")
            input_data = self._save_anndata_to_h5ad(input_data)
            self._log_success(f"✓ AnnData 对象已保存为: {input_data}")
        
        self._log_info(_("data_analysis.starting", files=input_data))
        
        # 准备系统 prompt 和用户查询
        system_prompt = self._get_system_prompt()
        
        # 获取用户查询模板
        query_templates = get_user_query_templates(self.language)
        
        # 根据输入类型生成用户查询
        if isinstance(input_data, str):
            # 单文件处理
            user_query = query_templates["single_file"].format(file_path=input_data)
        elif isinstance(input_data, (list, tuple)):
            # 多文件处理，按优先级排序
            sorted_files = self._sort_files_by_priority(input_data)
            main_file = sorted_files[0]
            file_paths_str = ", ".join(sorted_files)
            user_query = query_templates["multiple_files"].format(
                file_paths=file_paths_str, 
                main_file=main_file
            )
        else:
            # 兜底处理
            user_query = f"请分析并处理这个数据文件：{input_data}。请自动识别文件格式和适合的处理方式。"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"<question>{user_query}</question>"}
        ]
        
        self._log_info(_("data_analysis.system_prompt_length", length=len(system_prompt)))
        self._log_info(_("data_analysis.user_query", query=user_query) + "\n")
        
        analysis_log = []
        iteration = 0
        final_result = None
        
        while iteration < self.max_iterations:
            iteration += 1
            self._log_info(_("data_analysis.iteration", iteration=iteration))
            
            # 检查是否需要进行上下文总结
            should_summarize = False
            summarize_reason = ""
            
            # 检查迭代次数阈值
            if iteration == self.context_summary_threshold:
                should_summarize = True
                summarize_reason = f"达到迭代次数阈值（第{iteration}次迭代）"
                
            # 检查上下文长度（估算token数量）
            total_content_length = sum(len(msg.get("content", "")) for msg in messages)
            self._log_info(_("data_analysis.current_messages") + f" {len(messages)}")
            self._log_info(_("data_analysis.current_context_length") + f" {total_content_length}")
            if total_content_length > self.max_context_length:
                should_summarize = True
                if summarize_reason:
                    summarize_reason += f" 且上下文过长（{total_content_length}字符，阈值{self.max_context_length}）"
                else:
                    summarize_reason = f"上下文过长（{total_content_length}字符，阈值{self.max_context_length}）"
            
            # 执行总结
            if should_summarize and len(messages) > 6:
                self._log_info(_("data_analysis.context_compression", reason=summarize_reason))
                messages = await self._summarize_context(messages)
            
            # 使用全局配置决定是否使用流式输出
            if self.enable_streaming:
                self._log_info(_("data_analysis.streaming_enabled", iteration=iteration))
            
            # 调用 OpenAI（使用配置的超时时间）
            response = await self._call_openai(messages, timeout=self.api_timeout, stream=self.enable_streaming)
            self._log_info(_("data_analysis.ai_response_length", length=len(response)))
            
            # 验证响应格式
            validation = ValidationUtils.validate_response_format(response)
            
            if not validation['valid']:
                self._log_warning(_("data_analysis.format_validation_failed", issues=', '.join(validation['issues'])))
                response = await self._retry_llm_call_with_correction(messages, validation, 10, self.api_timeout)
            else:
                self._log_success(_("data_analysis.format_validation_passed"))
            
            analysis_log.append({
                "iteration": iteration,
                "response": response,
                "validation": validation,
                "type": "ai_response"
            })
            
            # 检查是否包含 final_answer
            if '</final_answer>' in response:
                final_result = ReactParser.extract_final_answer(response)
                if final_result:
                    self._log_success(_("data_analysis.analysis_completed", result=final_result))
                    break
                else:
                    self._log_warning(_("data_analysis.final_answer_no_result"))
            
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
                self._log_info(_("tools.call.no_action"))
                break
                
        
        self._log_header(f"\n{_('data_analysis.summary.title')}")
        self._log_info(_("data_analysis.summary.total_iterations", iterations=iteration))
        self._log_info(_("data_analysis.summary.final_result", result=final_result))
        self._log_info(_("data_analysis.summary.tool_calls", count=len([log for log in analysis_log if log['type'] == 'tool_call'])))
        if iteration >= self.context_summary_threshold:
            self._log_info(_("data_analysis.summary.context_summary", threshold=self.context_summary_threshold))
        
        # 打印 LLM 日志统计
        if self.llm_logger:
            try:
                log_summary = self.llm_logger.get_log_summary()
                self._log_info(_("data_analysis.summary.llm_stats", total=log_summary.get('total_requests', 0)))
                self._log_info(_("data_analysis.summary.success_failure", success=log_summary.get('success_count', 0), failure=log_summary.get('error_count', 0)))
                self._log_info(_("data_analysis.summary.log_file", file=log_summary.get('log_file', 'N/A')))
            except Exception as e:
                self._log_error(_("data_analysis.summary.stats_failed", error=e))
        
        # ✅ 从bundle读取路径（MCP工具已自动保存到bundle）
        bundle = load_file_paths_bundle()
        output_file_paths = {}

        if bundle.get("success"):
            # 提取所有可能的文件路径字段
            path_keys = ['rds_file', 'h5ad_file', 'h5_file', 'marker_genes_json', 'sce_h5', 'scanpy_h5']
            for key in path_keys:
                value = bundle.get(key)
                if value:  # 只保留非空值
                    output_file_paths[key] = value

            self._log_info(f"📁 从bundle读取到 {len(output_file_paths)} 个文件路径")

            # 打印读取的路径
            if output_file_paths:
                self._log_header(f"\n📁 从bundle读取的文件路径:")
                for file_type, path in output_file_paths.items():
                    self._log_info(f"   {file_type}: {path}")
        else:
            self._log_warning("⚠️ 未能从bundle读取路径")

        # 🌟 新增：自动物种检测逻辑（如果未提供species参数）
        detected_species_info = None
        if not species:
            # 查找JSON文件（从输出路径或输入参数）
            marker_genes_json = output_file_paths.get("marker_genes_json") or output_file_paths.get("marker_json")

            if marker_genes_json:
                self._log_info("🔍 未提供物种参数，尝试从JSON文件自动检测...")
                detected_species_info = self._auto_detect_species_from_json(marker_genes_json)

                if detected_species_info:
                    self._log_success(f"✅ 自动检测物种成功: {detected_species_info.get('detected_species')}")
                else:
                    self._log_warning("⚠️ 未能从JSON文件检测到物种信息")
            else:
                self._log_info("ℹ️  无JSON文件可用于物种检测")
        else:
            self._log_info(f"✅ 使用传入的物种参数: {species}")

        return {
            "input_data": input_data,
            "final_result": final_result,
            "output_file_paths": output_file_paths,  # 从bundle读取的文件路径
            "total_iterations": iteration,
            "context_summarized": iteration >= self.context_summary_threshold,
            "context_summary_threshold": self.context_summary_threshold,
            "analysis_log": analysis_log,
            "llm_log_summary": self.llm_logger.get_log_summary() if self.llm_logger else None,
            "success": final_result is not None,
            # 🌟 新增：物种信息
            "species": species,  # 用户指定的物种(如果有)
            "detected_species": detected_species_info.get("detected_species") if detected_species_info else None,
            "species_detection_info": detected_species_info,  # 详细的检测信息
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
