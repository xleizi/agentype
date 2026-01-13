#!/usr/bin/env python3
"""
agentype - LLM 日志 Token 统计解析器
Author: cuilei
Version: 1.0

从 JSONL 格式的 LLM 日志文件中提取和汇总 token 使用统计。
"""

import json
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
import sys

from agentype.common.token_statistics import TokenStatistics


class LogTokenParser:
    """LLM 日志 Token 统计解析器

    从保存在文件系统中的 JSONL 格式日志文件中解析 token 使用统计。
    支持跨进程的 token 统计收集，解决 MCP 架构下的统计丢失问题。
    """

    # Agent 名称到日志目录的映射
    AGENT_LOG_DIRS = {
        "MainAgent": "main_agent",
        "SubAgent": "sub_agent",
        "DataAgent": "data_agent",
        "AppAgent": "app_agent"
    }

    def __init__(self, log_base_dir: str):
        """初始化日志解析器

        Args:
            log_base_dir: 日志文件基础目录路径
        """
        self.log_base_dir = Path(log_base_dir)
        if not self.log_base_dir.exists():
            print(f"⚠️  日志目录不存在: {self.log_base_dir}", file=sys.stderr)

    @staticmethod
    def _extract_api_base(url: str) -> str:
        """从完整 URL 提取 API base URL

        Args:
            url: 完整的 API URL，如 "https://api.deepseek.com/v1/chat/completions"

        Returns:
            API base URL，如 "https://api.deepseek.com/v1"
        """
        # 移除常见的 API endpoint 路径
        endpoints = ['/chat/completions', '/completions', '/embeddings']
        for endpoint in endpoints:
            if url.endswith(endpoint):
                return url[:-len(endpoint)]
        # 如果没有匹配到，返回原URL
        return url

    def _find_log_file(self, agent_dir: str, session_id: str) -> Optional[Path]:
        """查找指定 Agent 和 session_id 的日志文件

        Args:
            agent_dir: Agent 目录名 (如 "sub_agent")
            session_id: 会话 ID

        Returns:
            日志文件路径，如果不存在则返回 None
        """
        log_dir = self.log_base_dir / agent_dir
        if not log_dir.exists():
            return None

        # 日志文件命名格式: llm_requests_{session_id}.jsonl
        # 注意: session_id 已包含 "session_" 前缀
        log_file = log_dir / f"llm_requests_{session_id}.jsonl"

        if log_file.exists():
            return log_file

        return None

    def _parse_log_file(self, log_file: Path, agent_name: str) -> TokenStatistics:
        """解析单个日志文件，提取 token 统计

        Args:
            log_file: 日志文件路径
            agent_name: Agent 名称 (用于统计对象)

        Returns:
            TokenStatistics 对象，包含该日志文件的所有 token 统计
        """
        stats = TokenStatistics(agent_name=agent_name)

        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        # 解析 JSON 行
                        log_entry = json.loads(line)

                        # 提取 usage 数据
                        extra_info = log_entry.get('extra_info', {})
                        usage_data = extra_info.get('usage', {})

                        if not usage_data:
                            # 没有 usage 数据，跳过这条记录
                            continue

                        # 添加到统计
                        stats.add_usage(usage_data)

                        # 更新模型名称（如果还没有设置）
                        if not stats.model_name and 'model_used' in extra_info:
                            stats.model_name = extra_info['model_used']

                        # 提取 API base URL（如果还没有设置）
                        if not stats.api_base:
                            request_data = log_entry.get('request', {})
                            url = request_data.get('url', '')
                            if url:
                                # 从完整 URL 提取 base URL
                                # 例如: https://api.deepseek.com/v1/chat/completions -> https://api.deepseek.com/v1
                                stats.api_base = self._extract_api_base(url)

                    except json.JSONDecodeError as e:
                        print(f"⚠️  解析日志行失败 [{log_file.name}:{line_num}]: {e}", file=sys.stderr)
                        continue
                    except Exception as e:
                        print(f"⚠️  处理日志行时出错 [{log_file.name}:{line_num}]: {e}", file=sys.stderr)
                        continue

            return stats

        except FileNotFoundError:
            print(f"⚠️  日志文件不存在: {log_file}", file=sys.stderr)
            return stats
        except Exception as e:
            print(f"❌ 解析日志文件失败 [{log_file}]: {e}", file=sys.stderr)
            return stats

    def parse_agent_logs(self, agent_name: str, session_id: str) -> TokenStatistics:
        """解析指定 Agent 的日志文件

        Args:
            agent_name: Agent 名称 ("MainAgent", "SubAgent", "DataAgent", "AppAgent")
            session_id: 会话 ID

        Returns:
            TokenStatistics 对象，如果日志不存在则返回空统计
        """
        agent_dir = self.AGENT_LOG_DIRS.get(agent_name)
        if not agent_dir:
            print(f"⚠️  未知的 Agent 名称: {agent_name}", file=sys.stderr)
            return TokenStatistics(agent_name=agent_name)

        log_file = self._find_log_file(agent_dir, session_id)
        if not log_file:
            # 没有找到日志文件，返回空统计
            return TokenStatistics(agent_name=agent_name)

        print(f"📊 解析 {agent_name} 日志: {log_file}", file=sys.stderr)
        stats = self._parse_log_file(log_file, agent_name)

        if stats.total_tokens > 0:
            print(f"✅ {agent_name} token 统计: {stats.total_tokens:,} tokens "
                  f"({stats.request_count} 次请求)", file=sys.stderr)
        else:
            print(f"📭 {agent_name} 暂无 token 消耗", file=sys.stderr)

        return stats

    def parse_all_agents(self, session_id: str,
                        include_agents: Optional[List[str]] = None) -> Dict[str, TokenStatistics]:
        """解析所有 Agent 的日志文件

        Args:
            session_id: 会话 ID
            include_agents: 要包含的 Agent 列表，None 表示所有 Agent

        Returns:
            字典，键为 Agent 名称，值为 TokenStatistics 对象
        """
        if include_agents is None:
            include_agents = list(self.AGENT_LOG_DIRS.keys())

        result = {}

        for agent_name in include_agents:
            stats = self.parse_agent_logs(agent_name, session_id)
            result[agent_name] = stats

        return result

    def get_log_file_info(self, session_id: str) -> Dict[str, Dict]:
        """获取所有 Agent 的日志文件信息（用于调试）

        Args:
            session_id: 会话 ID

        Returns:
            字典，包含每个 Agent 的日志文件信息
        """
        info = {}

        for agent_name, agent_dir in self.AGENT_LOG_DIRS.items():
            log_file = self._find_log_file(agent_dir, session_id)

            if log_file and log_file.exists():
                stat = log_file.stat()
                info[agent_name] = {
                    "exists": True,
                    "path": str(log_file),
                    "size_bytes": stat.st_size,
                    "size_kb": round(stat.st_size / 1024, 2),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                }
            else:
                info[agent_name] = {
                    "exists": False,
                    "path": str(self.log_base_dir / agent_dir / f"llm_requests_session_{session_id}.jsonl")
                }

        return info


# 便捷函数
def parse_logs_for_session(session_id: str,
                          log_base_dir: str = "/app/data/公共数据库/注释/outputs2/logs/llm",
                          include_agents: Optional[List[str]] = None) -> Dict[str, TokenStatistics]:
    """便捷函数：解析指定会话的所有 Agent 日志

    Args:
        session_id: 会话 ID
        log_base_dir: 日志基础目录
        include_agents: 要包含的 Agent 列表

    Returns:
        Agent 名称到 TokenStatistics 的字典
    """
    parser = LogTokenParser(log_base_dir)
    return parser.parse_all_agents(session_id, include_agents)


def get_total_tokens_from_logs(session_id: str,
                               log_base_dir: str = "/app/data/公共数据库/注释/outputs2/logs/llm") -> int:
    """便捷函数：获取所有 Agent 的总 token 数

    Args:
        session_id: 会话 ID
        log_base_dir: 日志基础目录

    Returns:
        总 token 数
    """
    stats_dict = parse_logs_for_session(session_id, log_base_dir)
    total = sum(stats.total_tokens for stats in stats_dict.values())
    return total
