#!/usr/bin/env python3
"""
agentype - MCP客户端基类
Author: cuilei
Version: 1.0

通用的MCP协议客户端实现，支持完整的配置传递机制。
各Agent可以继承此基类并自定义client_name。
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional


class BaseMCPClient:
    """MCP 协议客户端基类

    负责与 FastMCP 服务器的通信，包括连接管理、请求发送、
    工具调用等功能。使用 stdio 方式与服务器进程通信。

    支持完整的配置传递机制：
    - 敏感信息（API Key）通过环境变量传递
    - 非敏感配置通过命令行参数传递
    """

    def __init__(self, server_script: str, client_name: str, config=None):
        """初始化 MCP 客户端

        Args:
            server_script: MCP 服务器脚本路径
            client_name: 客户端名称（如 "celltype-main-agent"）
            config: 配置对象（ConfigManager），包含 API 密钥和其他配置
        """
        self.server_script = server_script
        self.client_name = client_name
        self.config = config
        self.process = None
        self.request_id = 0

    async def start_server(self) -> bool:
        """启动 FastMCP 服务器

        使用混合方案传递配置：
        - 敏感信息（API Key）通过环境变量传递
        - 非敏感配置通过命令行参数传递
        """
        try:
            print("🚀 启动 FastMCP 服务器...")

            # 检查服务器脚本是否存在
            server_path = Path(self.server_script)
            if not server_path.exists():
                print(f"❌ MCP服务器脚本不存在: {server_path}")
                print(f"   请检查路径是否正确")
                return False

            server_dir = server_path.parent.absolute()
            project_root = server_dir.parent.absolute()  # 项目根目录

            # 1. 准备环境变量（包含敏感信息）
            env = os.environ.copy()

            # 设置 PYTHONPATH
            current_pythonpath = env.get('PYTHONPATH', '')
            if current_pythonpath:
                env['PYTHONPATH'] = f"{project_root}{os.pathsep}{current_pythonpath}"
            else:
                env['PYTHONPATH'] = str(project_root)

            # 设置 API Key（敏感信息，通过环境变量传递）
            if self.config and hasattr(self.config, 'openai_api_key') and self.config.openai_api_key:
                env['OPENAI_API_KEY'] = self.config.openai_api_key
            elif 'OPENAI_API_KEY' not in env:
                print("⚠️ 未提供 API Key，子 Agent 可能无法正常工作")

            # 2. 获取当前会话ID
            from agentype.mainagent.config.session_config import get_session_id
            current_session_id = get_session_id()

            # 3. 构建命令行参数（非敏感配置）
            cmd = ['python', self.server_script]

            if self.config:
                # 添加非敏感配置参数
                if hasattr(self.config, 'openai_api_base') and self.config.openai_api_base:
                    cmd.extend(['--api-base', self.config.openai_api_base])

                if hasattr(self.config, 'openai_model') and self.config.openai_model:
                    cmd.extend(['--model', self.config.openai_model])

                if hasattr(self.config, 'output_dir') and self.config.output_dir:
                    cmd.extend(['--output-dir', str(self.config.output_dir)])

                if hasattr(self.config, 'language') and self.config.language:
                    cmd.extend(['--language', self.config.language])

                if hasattr(self.config, 'enable_streaming'):
                    cmd.extend(['--enable-streaming', str(self.config.enable_streaming).lower()])

                if hasattr(self.config, 'enable_thinking'):
                    cmd.extend(['--enable-thinking', str(self.config.enable_thinking).lower()])

            # session_id 始终传递
            cmd.extend(['--session-id', current_session_id])

            # 4. 启动服务器进程
            # 注意：不设置 cwd，让子进程继承父进程的工作目录
            # 这样可以避免相对路径被错误地解析到包目录下
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )

            print("✅ FastMCP 服务器已启动")

            # 检查服务器进程状态
            if self.process.returncode is not None:
                stderr_output = await self.process.stderr.read()
                print(f"❌ 服务器进程异常退出，退出码: {self.process.returncode}")
                if stderr_output:
                    print(f"   错误输出: {stderr_output.decode()}")
                return False

            # 初始化 MCP 连接
            await self._initialize_mcp()

            return True

        except Exception as e:
            print(f"❌ 启动 FastMCP 服务器失败: {e}")
            return False

    async def _initialize_mcp(self):
        """初始化 MCP 连接"""
        # 发送 initialize 请求
        init_request = {
            "jsonrpc": "2.0",
            "id": self._get_request_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-09-01",
                "capabilities": {
                    "tools": {}
                },
                "clientInfo": {
                    "name": self.client_name,
                    "version": "1.0.0"
                }
            }
        }

        response = await self._send_request(init_request)

        if response and not response.get("error"):
            # 发送 initialized 通知
            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }
            await self._send_notification(initialized_notification)
        else:
            print(f"❌ MCP 初始化失败: {response}")

    def _get_request_id(self) -> int:
        """获取请求 ID"""
        self.request_id += 1
        return self.request_id

    async def _send_request(self, request: Dict) -> Optional[Dict]:
        """发送 MCP 请求并等待响应

        Args:
            request: MCP请求字典

        Note:
            使用固定4小时超时（14400秒），适应长时间运行的数据处理任务
        """
        if not self.process:
            return None

        try:
            # 发送请求
            request_json = json.dumps(request) + '\n'
            self.process.stdin.write(request_json.encode())
            await self.process.stdin.drain()

            # 持续读取响应直到获得有效JSON
            # 使用固定超时机制，适应长时间运行的数据处理工具
            max_read_time = 14400  # 固定4小时超时（14400秒），防止长时间运行的数据处理工具被中断
            start_time = asyncio.get_event_loop().time()
            lines_read = 0

            while True:
                # 检查是否超时
                if asyncio.get_event_loop().time() - start_time > max_read_time:
                    print(f"❌ 读取超时({max_read_time}秒),已读取{lines_read}行", file=sys.stderr)
                    return None

                response_line = await self.process.stdout.readline()

                if not response_line:
                    print("❌ 未收到任何响应", file=sys.stderr)
                    return None

                lines_read += 1
                response_text = response_line.decode().strip()

                if not response_text:
                    continue  # 跳过空行

                # 如果是JSON格式，尝试解析
                if response_text.startswith('{') and response_text.endswith('}'):
                    try:
                        response = json.loads(response_text)
                        # print(response_text)
                        print(response)
                        if lines_read > 1000:
                            print(f"✅ 成功读取JSON响应(共{lines_read}行,耗时{asyncio.get_event_loop().time() - start_time:.1f}秒)", file=sys.stderr)
                        return response  # 成功获得JSON响应
                    except json.JSONDecodeError:
                        # JSON格式错误，输出调试信息但继续读取
                        print(f"🔍 JSON格式错误: {response_text}", file=sys.stderr)
                        continue

                # 非JSON行 - 输出调试信息但继续读取
                print(f"🔍 调试输出: {response_text}", file=sys.stderr)

        except Exception as e:
            print(f"❌ MCP 请求失败: {e}")
            return None

    async def _send_notification(self, notification: Dict):
        """发送 MCP 通知（无需响应）"""
        if not self.process:
            return

        try:
            notification_json = json.dumps(notification) + '\n'
            self.process.stdin.write(notification_json.encode())
            await self.process.stdin.drain()
        except Exception as e:
            print(f"❌ 发送通知失败: {e}")

    async def list_tools(self) -> List[Dict]:
        """获取可用工具列表"""
        request = {
            "jsonrpc": "2.0",
            "id": self._get_request_id(),
            "method": "tools/list"
        }

        response = await self._send_request(request)
        if response and "result" in response:
            tools = response["result"].get("tools", [])
            return tools

        return []

    async def call_tool(self, tool_name: str, arguments: Dict) -> Optional[Dict]:
        """调用 MCP 工具

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Note:
            MCP工具调用固定使用4小时超时（14400秒）
        """
        request = {
            "jsonrpc": "2.0",
            "id": self._get_request_id(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        response = await self._send_request(request)

        if response and "result" in response:
            result = response["result"]
            content = result.get("content", [])

            # 合并所有内容
            full_content = ""
            for item in content:
                if item.get("type") == "text":
                    full_content += item.get("text", "")

            return {"content": full_content, "success": True}

        elif response and "error" in response:
            error = response["error"]
            print(f"❌ MCP 工具调用失败: {error}")
            return {"error": error, "success": False}

        print("❌ MCP 工具调用无响应")
        return {"error": "无响应", "success": False}

    async def stop_server(self):
        """停止 FastMCP 服务器"""
        if self.process:
            print("🛑 停止 FastMCP 服务器...")
            try:
                # 关闭所有管道以避免资源泄漏
                pipes_to_close = []

                # 收集需要关闭的管道
                if self.process.stdin and hasattr(self.process.stdin, 'is_closing') and not self.process.stdin.is_closing():
                    pipes_to_close.append(('stdin', self.process.stdin))
                elif self.process.stdin:
                    pipes_to_close.append(('stdin', self.process.stdin))

                # stdout 和 stderr 通常是 StreamReader，没有 is_closing 方法
                if self.process.stdout:
                    pipes_to_close.append(('stdout', self.process.stdout))
                if self.process.stderr:
                    pipes_to_close.append(('stderr', self.process.stderr))

                # 逐个关闭管道
                for pipe_name, pipe in pipes_to_close:
                    try:
                        if hasattr(pipe, 'close'):
                            pipe.close()
                        if hasattr(pipe, 'wait_closed'):
                            await asyncio.wait_for(pipe.wait_closed(), timeout=2.0)
                    except Exception as e:
                        print(f"⚠️ 关闭{pipe_name}管道时出现异常: {e}")

                # 终止进程
                self.process.terminate()

                # 等待进程结束，设置超时以避免无限等待
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    # 如果进程不响应terminate，强制杀死
                    self.process.kill()
                    await self.process.wait()

                print("✅ FastMCP 服务器已停止")

            except ProcessLookupError:
                print("⚠️ FastMCP 服务器进程已不存在")
            except Exception as e:
                print(f"⚠️ 停止FastMCP服务器时出现异常: {e}")
            finally:
                self.process = None
