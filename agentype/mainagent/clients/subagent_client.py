#!/usr/bin/env python3
"""
agentype - 子Agent客户端管理器
Author: cuilei
Version: 1.0
"""

import asyncio
import json
from typing import Dict, List, Optional, Any
from datetime import datetime

from .mcp_client import MCPClient
from agentype.mainagent.config.settings import ConfigManager, SubAgentConfig
from agentype.mainagent.config.cache_config import CacheManager


class SubAgentClientManager:
    """子Agent客户端管理器"""

    def __init__(self, config: ConfigManager, cache_manager: Optional[CacheManager] = None):
        """
        初始化子Agent客户端管理器

        Args:
            config: 配置管理器
            cache_manager: 缓存管理器（可选）
        """
        self.config = config
        self.cache_manager = cache_manager
        self.clients: Dict[str, MCPClient] = {}
        self.connection_status: Dict[str, Dict] = {}

    async def initialize_all_clients(self) -> bool:
        """初始化所有子Agent客户端"""
        print("🔗 初始化所有子Agent客户端...")
        success_count = 0
        enabled_agents = self.config.get_enabled_subagents()

        for agent_config in enabled_agents:
            if await self.initialize_client(agent_config):
                success_count += 1

        print(f"✅ 成功连接 {success_count}/{len(enabled_agents)} 个子Agent")
        return success_count > 0

    async def initialize_client(self, agent_config: SubAgentConfig) -> bool:
        """
        初始化单个子Agent客户端

        Args:
            agent_config: 子Agent配置

        Returns:
            bool: 初始化是否成功
        """
        try:
            client = MCPClient(
                server_script=agent_config.server_script
            )

            if await client.start_server():
                self.clients[agent_config.name] = client
                self.connection_status[agent_config.name] = {
                    "status": "connected",
                    "connected_at": datetime.now().isoformat(),
                    "error": None
                }

                print(f"✅ {agent_config.name} 客户端初始化成功")
                return True
            else:
                self.connection_status[agent_config.name] = {
                    "status": "failed",
                    "connected_at": None,
                    "error": "初始化失败"
                }

                print(f"❌ {agent_config.name} 客户端初始化失败")
                return False

        except Exception as e:
            error_msg = f"初始化异常: {str(e)}"
            self.connection_status[agent_config.name] = {
                "status": "error",
                "connected_at": None,
                "error": error_msg
            }

            print(f"❌ {agent_config.name} 客户端初始化异常: {e}")
            return False

    async def get_client(self, agent_name: str) -> Optional[MCPClient]:
        """
        获取指定子Agent的客户端

        Args:
            agent_name: 子Agent名称

        Returns:
            Optional[MCPClient]: MCP客户端实例
        """
        client = self.clients.get(agent_name)
        if client and client.is_connected:
            return client

        # 尝试重新连接
        agent_config = self.config.get_subagent_config(agent_name)
        if agent_config and agent_config.enabled:
            print(f"🔄 尝试重新连接 {agent_name}...")
            if await self.initialize_client(agent_config):
                return self.clients.get(agent_name)

        return None

    async def call_subagent_tool(self, agent_name: str, tool_name: str, arguments: Dict) -> Optional[Dict]:
        """
        调用子Agent的工具

        Args:
            agent_name: 子Agent名称
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            Optional[Dict]: 调用结果
        """
        client = await self.get_client(agent_name)
        if not client:
            return {
                "success": False,
                "error": f"无法连接到 {agent_name}",
                "agent_name": agent_name,
                "tool_name": tool_name
            }

        return await client.call_tool(tool_name, arguments)

    async def list_subagent_tools(self, agent_name: str) -> List[Dict]:
        """
        列出子Agent的工具

        Args:
            agent_name: 子Agent名称

        Returns:
            List[Dict]: 工具列表
        """
        client = await self.get_client(agent_name)
        if not client:
            print(f"❌ 无法连接到 {agent_name}")
            return []

        return await client.list_tools()

    async def get_all_tools(self) -> Dict[str, List[Dict]]:
        """
        获取所有子Agent的工具列表

        Returns:
            Dict[str, List[Dict]]: 按Agent名称分组的工具列表
        """
        all_tools = {}
        for agent_name in self.clients.keys():
            tools = await self.list_subagent_tools(agent_name)
            all_tools[agent_name] = tools
        return all_tools

    async def health_check_all(self) -> Dict[str, bool]:
        """
        对所有子Agent进行健康检查

        Returns:
            Dict[str, bool]: 每个Agent的健康状态
        """
        health_status = {}
        tasks = []

        for agent_name, client in self.clients.items():
            task = asyncio.create_task(client.health_check())
            task.agent_name = agent_name
            tasks.append(task)

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(results):
                agent_name = tasks[i].agent_name
                if isinstance(result, Exception):
                    health_status[agent_name] = False
                    print(f"⚠️ {agent_name} 健康检查异常: {result}")
                else:
                    health_status[agent_name] = result

        return health_status

    async def reconnect_all(self) -> Dict[str, bool]:
        """
        重新连接所有失败的子Agent

        Returns:
            Dict[str, bool]: 每个Agent的重连结果
        """
        reconnect_results = {}
        health_status = await self.health_check_all()

        for agent_name, is_healthy in health_status.items():
            if not is_healthy:
                agent_config = self.config.get_subagent_config(agent_name)
                if agent_config and agent_config.enabled:
                    reconnect_results[agent_name] = await self.initialize_client(agent_config)
                else:
                    reconnect_results[agent_name] = False
            else:
                reconnect_results[agent_name] = True

        return reconnect_results

    def get_status_summary(self) -> Dict[str, Any]:
        """
        获取状态摘要

        Returns:
            Dict[str, Any]: 状态摘要
        """
        total_agents = len(self.config.get_enabled_subagents())
        connected_agents = len([c for c in self.clients.values() if c.is_connected])

        client_details = {}
        for agent_name, client in self.clients.items():
            client_details[agent_name] = client.get_status()

        return {
            "total_agents": total_agents,
            "connected_agents": connected_agents,
            "connection_rate": connected_agents / total_agents if total_agents > 0 else 0,
            "clients": client_details,
            "connection_status": self.connection_status
        }

    async def execute_parallel_calls(self, calls: List[Dict]) -> List[Dict]:
        """
        并行执行多个工具调用

        Args:
            calls: 调用配置列表，每个元素包含 {agent_name, tool_name, arguments}

        Returns:
            List[Dict]: 执行结果列表

        Note:
            所有工具调用统一使用固定4小时超时（14400秒）
        """
        tasks = []
        for call_config in calls:
            task = asyncio.create_task(
                self.call_subagent_tool(
                    agent_name=call_config["agent_name"],
                    tool_name=call_config["tool_name"],
                    arguments=call_config.get("arguments", {})
                )
            )
            task.call_config = call_config
            tasks.append(task)

        if not tasks:
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)
        formatted_results = []

        for i, result in enumerate(results):
            call_config = tasks[i].call_config
            if isinstance(result, Exception):
                formatted_results.append({
                    "success": False,
                    "error": f"执行异常: {str(result)}",
                    "agent_name": call_config["agent_name"],
                    "tool_name": call_config["tool_name"],
                    "arguments": call_config.get("arguments", {})
                })
            else:
                formatted_results.append(result)

        return formatted_results

    async def shutdown_all(self):
        """关闭所有客户端"""
        print("🛑 关闭所有子Agent客户端...")
        tasks = []

        for client in self.clients.values():
            task = asyncio.create_task(client.stop_server())
            tasks.append(task)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self.clients.clear()
        self.connection_status.clear()
        print("✅ 所有子Agent客户端已关闭")

    def get_all_connection_status(self) -> Dict[str, Dict]:
        """
        获取所有连接状态

        Returns:
            Dict[str, Dict]: 所有连接状态
        """
        return self.connection_status.copy()

    async def cleanup_all_clients(self):
        """清理所有客户端"""
        await self.shutdown_all()