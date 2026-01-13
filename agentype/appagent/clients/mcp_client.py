#!/usr/bin/env python3
"""
agentype - AppAgent MCP客户端
Author: cuilei
Version: 1.0
"""

from agentype.common.mcp_client import BaseMCPClient


class MCPClient(BaseMCPClient):
    """AppAgent 的 MCP 客户端

    继承自 BaseMCPClient，设置特定的 client_name。
    """

    def __init__(self, server_script: str, config=None):
        """初始化 AppAgent MCP 客户端

        Args:
            server_script: MCP 服务器脚本路径
            config: 配置对象（ConfigManager），包含 API 密钥和其他配置
        """
        super().__init__(
            server_script=server_script,
            client_name="celltype-app-agent-client",
            config=config
        )
