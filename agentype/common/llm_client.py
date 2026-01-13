#!/usr/bin/env python3
"""
agentype - 共享 LLM 客户端
Author: cuilei
Version: 1.0

支持 DeepSeek Reasoner 的 reasoning_content 特性
"""

import requests
import time
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime


class ObservationHallucinationError(Exception):
    """LLM 在响应中生成了 <observation> 标签（幻觉错误）

    <observation> 标签应该由 Agent 在调用工具后添加，
    LLM 不应该自己生成此标签。如果检测到，需要立即中断并重试。
    """
    pass


class LLMClient:
    """统一的 LLM API 客户端

    特性：
    - 支持流式和非流式调用
    - 完整支持 DeepSeek Reasoner 的 reasoning_content
    - 统一的日志记录接口（通过回调函数）
    - 统一的 token 统计接口
    - 统一的错误处理和重试逻辑
    """

    def __init__(self, config, logger_callbacks: Optional[Dict[str, Callable]] = None):
        """初始化 LLM 客户端

        Args:
            config: 配置对象，包含 openai_api_key, openai_api_base, openai_model
            logger_callbacks: 日志回调函数字典，可选键值：
                - 'info': 信息日志回调
                - 'success': 成功日志回调
                - 'warning': 警告日志回调
                - 'error': 错误日志回调
        """
        self.config = config
        self.logger_callbacks = logger_callbacks or {}
        self._last_reasoning_length = 0  # 记录最后一次请求的 reasoning_content 长度

    def _normalize_api_url(self) -> str:
        """智能标准化 API URL

        支持各种输入格式：
        1. 自动添加 https:// 前缀（如果缺少），支持 http:// 和 https://
        2. 自动添加 /v1 路径（如果缺少且需要）
        3. 自动添加 /chat/completions 后缀（如果缺少）

        示例：
            - api.deepseek.com → https://api.deepseek.com/v1/chat/completions
            - https://api.deepseek.com → https://api.deepseek.com/v1/chat/completions
            - http://localhost:8000 → http://localhost:8000/v1/chat/completions
            - api.deepseek.com/v1 → https://api.deepseek.com/v1/chat/completions
            - https://api.openai.com/v1 → https://api.openai.com/v1/chat/completions

        Returns:
            标准化的完整 API URL
        """
        url = self.config.openai_api_base.strip()

        # 1. 处理协议（http/https）
        if not url.startswith(('http://', 'https://')):
            # 没有协议，默认添加 https://
            url = f"https://{url}"

        # 2. 移除末尾的斜杠
        url = url.rstrip('/')

        # 3. 处理 /chat/completions 后缀
        if url.endswith('/chat/completions'):
            # 已经有完整路径，检查是否需要添加 /v1
            if '/v1/chat/completions' in url:
                # 已包含 /v1，直接返回
                return url
            else:
                # 缺少 /v1，插入到 /chat/completions 之前
                # 例如：https://api.deepseek.com/chat/completions
                #   → https://api.deepseek.com/v1/chat/completions
                url = url.replace('/chat/completions', '/v1/chat/completions')
                return url

        # 4. 处理 /v1 路径
        if not url.endswith('/v1'):
            # 没有 /v1，添加它
            url = f"{url}/v1"

        # 5. 添加 /chat/completions
        url = f"{url}/chat/completions"

        return url

    def has_reasoning(self) -> bool:
        """检查最后一次请求是否包含 reasoning_content"""
        return self._last_reasoning_length > 0

    def _log(self, level: str, message: str):
        """内部日志方法"""
        callback = self.logger_callbacks.get(level)
        if callback:
            callback(message)

    def _log_info(self, message: str):
        self._log('info', message)

    def _log_success(self, message: str):
        self._log('success', message)

    def _log_warning(self, message: str):
        self._log('warning', message)

    def _log_error(self, message: str):
        self._log('error', message)

    async def call_api(
        self,
        messages: List[Dict],
        timeout: int = 270,
        stream: bool = False,
        enable_thinking: bool = False,
        request_type: str = "main",
        llm_logger = None,
        console_logger = None
    ) -> str:
        """调用 OpenAI API（支持 DeepSeek Reasoner）

        Args:
            messages: 对话消息列表
            timeout: 超时时间（秒）
            stream: 是否使用流式输出
            enable_thinking: 是否启用思考输出
            request_type: 请求类型（用于日志记录）
            llm_logger: LLM日志记录器实例（可选）
            console_logger: 控制台日志记录器实例（可选）

        Returns:
            LLM 响应内容
        """
        start_time = datetime.now()
        data = {}
        payload = {}

        try:
            headers = {
                "Authorization": f"Bearer {self.config.openai_api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.config.openai_model,
                "messages": messages,
                "temperature": 0.1,
                "stream": stream,
                "enable_thinking": enable_thinking
            }

            # 日志：请求信息
            self._log_info("📤 发送 LLM 请求...")
            self._log_info(f"   🌐 URL: {self._normalize_api_url()}")
            self._log_info(f"   🤖 模型: {payload['model']}")
            self._log_info(f"   💬 消息数: {len(messages)}")
            self._log_info(f"   ⏱️  超时: {timeout}秒")
            streaming_text = "✅ 已启用" if stream else "❌ 已禁用"
            self._log_info(f"   🌊 流式输出: {streaming_text}")

            # 添加超时重试逻辑（最多3次）
            max_retries = 30
            last_timeout_error = None

            for retry_attempt in range(max_retries):
                try:
                    if retry_attempt > 0:
                        self._log_warning(f"⚠️ 第 {retry_attempt + 1}/{max_retries} 次重试 LLM 调用...")

                    response = requests.post(
                        self._normalize_api_url(),
                        headers=headers,
                        json=payload,
                        timeout=timeout,
                        stream=stream
                    )
                    response.raise_for_status()
                    break  # 成功，跳出重试循环

                except (requests.exceptions.Timeout, requests.exceptions.ReadTimeout, requests.exceptions.HTTPError) as error:
                    # 处理 429 速率限制错误
                    if isinstance(error, requests.exceptions.HTTPError) and error.response.status_code == 429:
                        if retry_attempt < max_retries - 1:
                            # 从响应头读取 Retry-After，如果没有则使用 60 秒
                            retry_after = error.response.headers.get('Retry-After', '60')
                            try:
                                wait_time = int(retry_after)
                            except ValueError:
                                wait_time = 60

                            self._log_warning(f"⏱️ 遇到速率限制 (429)，暂停 {wait_time} 秒后重试...")
                            time.sleep(wait_time)
                            continue
                        else:
                            self._log_error(f"❌ 遇到速率限制 (429)，已达最大重试次数 ({max_retries})")
                            raise error

                    # 其他 HTTP 错误直接抛出
                    if isinstance(error, requests.exceptions.HTTPError):
                        raise error

                    # 处理超时错误（保持原有逻辑）
                    last_timeout_error = error
                    if retry_attempt < max_retries - 1:
                        self._log_warning(f"⏱️ LLM 调用超时 ({timeout}秒)，将进行重试...")
                        continue
                    else:
                        self._log_error(f"❌ LLM 调用超时 ({timeout}秒)，已达最大重试次数 ({max_retries})")
                        raise last_timeout_error

            content = ""
            reasoning_content = ""  # 🌟 DeepSeek Reasoner: 累积推理内容

            if stream:
                # 流式输出处理
                self._log_info("📥 接收流式响应...")
                reasoning_char_count = 0  # 🌟 DeepSeek Reasoner: 推理内容字符数
                content_char_count = 0
                first_reasoning_chunk = True  # 🌟 标记是否是第一个推理chunk

                try:
                    for line in response.iter_lines():
                        if line:
                            line_str = line.decode('utf-8')
                            if line_str.startswith('data: '):
                                data_str = line_str[6:]
                                if data_str.strip() == '[DONE]':
                                    break

                                try:
                                    import json
                                    chunk_data = json.loads(data_str)

                                    if 'choices' in chunk_data and len(chunk_data['choices']) > 0:
                                        delta = chunk_data['choices'][0].get('delta', {})

                                        # 🌟 DeepSeek Reasoner: 处理 reasoning_content
                                        if 'reasoning_content' in delta:
                                            reasoning_chunk = delta['reasoning_content']
                                            if reasoning_chunk is not None:
                                                reasoning_content += reasoning_chunk
                                                reasoning_char_count += len(reasoning_chunk)
                                                # 实时显示推理过程（灰色显示，区别于最终答案）
                                                print(f"\033[90m{reasoning_chunk}\033[0m", end='', flush=True)
                                                # 写入日志文件（仿照 content 的处理方式）
                                                if console_logger and console_logger.file_output:
                                                    with open(console_logger.log_file, 'a', encoding='utf-8') as f:
                                                        # 第一个chunk：写入开始标记
                                                        if first_reasoning_chunk:
                                                            f.write("[推理开始]\n")
                                                            first_reasoning_chunk = False
                                                        # 直接写入原始内容（无标签）
                                                        f.write(reasoning_chunk)
                                                        f.flush()

                                        # 处理正常的 content
                                        if 'content' in delta:
                                            chunk = delta['content']
                                            if chunk is not None:
                                                content += chunk
                                                content_char_count += len(chunk)

                                                # 🚨 检测 LLM 是否错误生成了 <observation> 标签
                                                if '<observation>' in content.lower():
                                                    self._log_error("❌ 检测到 LLM 错误生成 <observation> 标签（幻觉），立即中断")
                                                    # 停止接收流式数据
                                                    raise ObservationHallucinationError(
                                                        "LLM 在响应中生成了 <observation> 标签，这是错误的行为。"
                                                        "<observation> 标签应该由 Agent 在调用工具后添加。"
                                                    )

                                                print(chunk, end='', flush=True)
                                                if console_logger and console_logger.file_output:
                                                    with open(console_logger.log_file, 'a', encoding='utf-8') as f:
                                                        f.write(chunk)
                                                        f.flush()

                                    # 🌟 DeepSeek Reasoner: 记录 usage（包含 reasoning_tokens）
                                    if 'usage' in chunk_data:
                                        data['usage'] = chunk_data['usage']
                                        data['model'] = chunk_data.get('model', payload.get('model'))

                                except json.JSONDecodeError as json_err:
                                    self._log_warning(f"⚠️ JSON 解析失败: {json_err}, 行内容: {data_str[:100]}")
                                    continue

                    print()  # 换行

                    # 🌟 DeepSeek Reasoner: 写入推理结束标记
                    if reasoning_char_count > 0 and console_logger and console_logger.file_output:
                        with open(console_logger.log_file, 'a', encoding='utf-8') as f:
                            f.write(f"\n[推理结束 ({reasoning_char_count}字符)]\n")
                            f.flush()

                    # 🌟 DeepSeek Reasoner: 显示统计信息
                    if reasoning_content:
                        self._log_success(f"✅ 推理内容已接收 ({reasoning_char_count} 字符)")
                    self._log_success(f"✅ 流式响应完成 ({content_char_count} 字符)")

                except Exception as stream_error:
                    self._log_error(f"\n❌ 流式输出失败: {stream_error}")
                    self._log_warning("⚠️ 尝试回退到非流式模式...")
                    if not content.strip():
                        self._log_info("🔄 使用非流式模式重试...")
                        payload["stream"] = False
                        response = requests.post(
                            self._normalize_api_url(),
                            headers=headers,
                            json=payload,
                            timeout=timeout,
                        )
                        response.raise_for_status()
                        data = response.json()
                        message = data["choices"][0]["message"]
                        reasoning_content = message.get("reasoning_content", "")  # 🌟 DeepSeek Reasoner
                        content = message.get("content", "")
                        self._log_success(f"✅ 非流式响应完成 ({len(content)} 字符)")
            else:
                # 非流式输出处理
                data = response.json()
                message = data["choices"][0]["message"]
                reasoning_content = message.get("reasoning_content", "")  # 🌟 DeepSeek Reasoner
                content = message.get("content", "")

                # 🌟 DeepSeek Reasoner: 显示推理内容
                if reasoning_content:
                    self._log_info(f"🧠 推理过程 ({len(reasoning_content)} 字符):")
                    self._log_info(f"   {reasoning_content[:200]}...")

            # 日志：响应信息
            self._log_info("📥 LLM 响应")
            self._log_info(f"   📏 响应长度: {len(content)} 字符")

            # 🌟 LLM 日志记录（包含 reasoning_content）
            if llm_logger:
                request_data = {
                    "url": self._normalize_api_url(),
                    "headers": {k: (v if k != "Authorization" else "Bearer [REDACTED]") for k, v in headers.items()},
                    "payload": payload,
                }
                extra_info = {
                    "duration_seconds": (datetime.now() - start_time).total_seconds(),
                    "usage": data.get("usage", {}),
                    "model_used": data.get("model", payload.get("model")),
                    "reasoning_content": reasoning_content,  # 🌟 记录推理内容
                    "reasoning_length": len(reasoning_content)  # 🌟 推理内容长度
                }

                # 记录为通用 chat completion (usage 数据会保存到日志文件)
                llm_logger.log_request_response(
                    request_type=request_type,
                    request_data=request_data,
                    response_data=content,
                    success=True,
                    extra_info=extra_info,
                )

            # 🌟 记录 reasoning_content 长度供验证使用
            self._last_reasoning_length = len(reasoning_content)

            return content

        except Exception as e:
            error_msg = f"OpenAI API 调用失败: {str(e)}"
            self._log_error(f"❌ {error_msg}")

            # 错误日志记录
            if llm_logger:
                request_data = {
                    "url": self._normalize_api_url(),
                    "headers": {"Authorization": "Bearer [REDACTED]", "Content-Type": "application/json"},
                    "payload": payload,
                }
                llm_logger.log_request_response(
                    request_type=request_type,
                    request_data=request_data,
                    response_data="",
                    success=False,
                    error_msg=error_msg,
                    extra_info={
                        "duration_seconds": (datetime.now() - start_time).total_seconds()
                    },
                )

            return error_msg
