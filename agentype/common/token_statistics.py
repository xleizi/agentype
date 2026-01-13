#!/usr/bin/env python3
"""
agentype - Token统计管理模块
Author: cuilei
Version: 1.0
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import json


@dataclass
class ModelPricing:
    """模型定价信息"""
    prompt_price: float  # 输入token价格（每百万tokens或每千tokens）
    completion_price: float  # 输出token价格
    currency: str  # 货币单位：'CNY' 或 'USD'
    price_per_million: bool = True  # True: 价格按百万tokens计，False: 按千tokens计


class PricingRegistry:
    """模型定价注册表

    管理所有API的模型定价信息，支持根据api_base和model_name查询定价。
    """

    def __init__(self):
        """初始化定价注册表"""
        self._pricing_map: Dict[str, Dict[str, ModelPricing]] = {}
        self._setup_default_pricing()

    def _setup_default_pricing(self):
        """设置默认的模型定价"""

        # ===== SiliconFlow API (人民币计价，百万tokens) =====
        siliconflow_pricing = {
            "Pro/deepseek-ai/DeepSeek-V3": ModelPricing(2.0, 8.0, "CNY", True),
            "Pro/deepseek-ai/DeepSeek-R1": ModelPricing(4.0, 16.0, "CNY", True),
            "deepseek-ai/DeepSeek-R1": ModelPricing(4.0, 16.0, "CNY", True),
            "deepseek-ai/DeepSeek-V3": ModelPricing(2.0, 8.0, "CNY", True),
            # V3.1-Terminus 包括 pro 版本
            "deepseek-ai/DeepSeek-V3.1-Terminus": ModelPricing(4.0, 12.0, "CNY", True),
            "Pro/deepseek-ai/DeepSeek-V3.1-Terminus": ModelPricing(4.0, 12.0, "CNY", True),
            # V3.2-Exp 包括 pro 版本
            "deepseek-ai/DeepSeek-V3.2-Exp": ModelPricing(2.0, 3.0, "CNY", True),
            "Pro/deepseek-ai/DeepSeek-V3.2-Exp": ModelPricing(2.0, 3.0, "CNY", True),
        }
        self._pricing_map["https://api.siliconflow.cn/v1"] = siliconflow_pricing

        # ===== DeepSeek API (人民币计价，百万tokens) =====
        deepseek_pricing = {
            "deepseek-chat": ModelPricing(2.0, 3.0, "CNY", True),
            "deepseek-reasoner": ModelPricing(2.0, 3.0, "CNY", True),
        }
        self._pricing_map["https://api.deepseek.com"] = deepseek_pricing

        # ===== yansd666.top API (美元计价，百万tokens) =====
        yansd666_pricing = {
            "gpt-4o": ModelPricing(2.5, 10.0, "USD", True),
            "gpt-5-chat-latest": ModelPricing(1.25, 10.0, "USD", True),
            "o3": ModelPricing(2.0, 8.0, "USD", True),
            "gpt-5-nano-2025-08-07": ModelPricing(0.05, 0.4, "USD", True),
            "gpt-3.5-turbo": ModelPricing(0.5, 1.0, "USD", True),
        }
        self._pricing_map["https://yansd666.top/v1"] = yansd666_pricing

        # ===== OpenAI 和默认定价 (美元计价，千tokens) =====
        # 这些定价会作为默认值，当找不到特定API配置时使用
        self._default_pricing = {
            "gpt-4": ModelPricing(0.03, 0.06, "USD", False),
            "gpt-4o": ModelPricing(0.03, 0.06, "USD", False),
            "gpt-3.5": ModelPricing(0.001, 0.002, "USD", False),
            "gpt-3.5-turbo": ModelPricing(0.001, 0.002, "USD", False),
        }

    def get_pricing(self, model_name: str, api_base: Optional[str] = None) -> Optional[ModelPricing]:
        """获取模型定价

        Args:
            model_name: 模型名称
            api_base: API基础URL（可选）

        Returns:
            ModelPricing对象，如果找不到则返回None
        """
        # 如果提供了api_base，使用模糊匹配查找对应的API定价
        if api_base:
            # 遍历所有已注册的API，使用包含匹配
            for registered_url, api_pricing in self._pricing_map.items():
                if registered_url in api_base or api_base.startswith(registered_url):
                    # 在该API的定价表中查找模型
                    if model_name in api_pricing:
                        return api_pricing[model_name]

        # 在默认定价中查找（按模型名称的关键字匹配）
        model_lower = model_name.lower()
        for key, pricing in self._default_pricing.items():
            if key in model_lower:
                return pricing

        # 如果都找不到，返回默认的GPT-4定价
        return ModelPricing(0.03, 0.06, "USD", False)

    def calculate_cost(self,
                      prompt_tokens: int,
                      completion_tokens: int,
                      model_name: str,
                      api_base: Optional[str] = None) -> Tuple[float, str]:
        """计算成本

        Args:
            prompt_tokens: 输入token数
            completion_tokens: 输出token数
            model_name: 模型名称
            api_base: API基础URL

        Returns:
            (成本, 货币单位) 元组
        """
        pricing = self.get_pricing(model_name, api_base)

        if pricing.price_per_million:
            # 按百万tokens计价
            prompt_cost = (prompt_tokens / 1_000_000) * pricing.prompt_price
            completion_cost = (completion_tokens / 1_000_000) * pricing.completion_price
        else:
            # 按千tokens计价
            prompt_cost = (prompt_tokens / 1000) * pricing.prompt_price
            completion_cost = (completion_tokens / 1000) * pricing.completion_price

        total_cost = prompt_cost + completion_cost
        return (total_cost, pricing.currency)


# 全局定价注册表实例
_pricing_registry = PricingRegistry()


@dataclass
class TokenStatistics:
    """Token统计数据类"""

    # 基础统计
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    request_count: int = 0

    # 元数据
    model_name: str = ""
    agent_name: str = ""
    api_base: Optional[str] = None  # API 基础 URL,从日志中提取
    start_time: Optional[str] = None
    last_updated: Optional[str] = None

    def __post_init__(self):
        """初始化后设置时间戳"""
        if self.start_time is None:
            self.start_time = datetime.now().isoformat()
        self.last_updated = datetime.now().isoformat()

    def add_usage(self, usage_data: Dict[str, Any]) -> None:
        """
        添加一次API调用的token使用统计

        Args:
            usage_data: OpenAI API返回的usage数据
        """
        if not usage_data:
            return

        # 提取token数据
        prompt_tokens = usage_data.get("prompt_tokens", 0)
        completion_tokens = usage_data.get("completion_tokens", 0)
        total_tokens = usage_data.get("total_tokens", 0)

        # 如果total_tokens为0，尝试计算
        if total_tokens == 0 and (prompt_tokens > 0 or completion_tokens > 0):
            total_tokens = prompt_tokens + completion_tokens

        # 累计基础统计
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_tokens += total_tokens
        self.request_count += 1

        # 更新时间戳
        self.last_updated = datetime.now().isoformat()

    def get_estimated_cost(self, api_base: Optional[str] = None) -> Tuple[float, str]:
        """
        估算成本（支持多货币和多API）

        Args:
            api_base: API基础URL，用于确定定价策略（可选，如果未提供则使用实例的api_base）

        Returns:
            (成本, 货币单位) 元组，例如 (0.0020, "CNY") 或 (0.0015, "USD")
        """
        # 确定使用哪个 api_base: 优先使用实例的 api_base,否则使用参数
        effective_api_base = self.api_base if self.api_base else api_base

        # 使用定价注册表系统
        cost, currency = _pricing_registry.calculate_cost(
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            model_name=self.model_name,
            api_base=effective_api_base
        )
        return (cost, currency)

    def get_efficiency_score(self) -> float:
        """
        计算效率分数（completion_tokens / total_tokens）

        Returns:
            效率分数，范围0-1，越高表示输出相对于输入越多
        """
        if self.total_tokens == 0:
            return 0.0
        return self.completion_tokens / self.total_tokens

    def get_summary(self,
                   include_cost: bool = True,
                   api_base: Optional[str] = None) -> Dict[str, Any]:
        """
        获取统计摘要

        Args:
            include_cost: 是否包含成本估算
            api_base: API基础URL

        Returns:
            格式化的统计摘要
        """
        summary = {
            "agent_name": self.agent_name,
            "model_name": self.model_name,
            "total_tokens": self.total_tokens,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "request_count": self.request_count,
            "efficiency_score": round(self.get_efficiency_score(), 3),
            "start_time": self.start_time,
            "last_updated": self.last_updated
        }

        if include_cost:
            cost, currency = self.get_estimated_cost(api_base)
            summary["estimated_cost"] = round(cost, 4)
            summary["currency"] = currency

        return summary

    def reset(self) -> None:
        """重置所有统计数据"""
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.request_count = 0
        self.start_time = datetime.now().isoformat()
        self.last_updated = self.start_time

    def merge(self, other: 'TokenStatistics') -> 'TokenStatistics':
        """
        合并两个统计对象

        Args:
            other: 另一个TokenStatistics对象

        Returns:
            合并后的新TokenStatistics对象
        """
        merged = TokenStatistics(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            request_count=self.request_count + other.request_count,
            model_name=self.model_name or other.model_name,
            agent_name=f"{self.agent_name}+{other.agent_name}" if self.agent_name and other.agent_name else (self.agent_name or other.agent_name),
            api_base=self.api_base or other.api_base,
            start_time=min(self.start_time or "", other.start_time or "") or None,
            last_updated=max(self.last_updated or "", other.last_updated or "") or None
        )
        return merged

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TokenStatistics':
        """从字典创建TokenStatistics对象"""
        return cls(**data)

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'TokenStatistics':
        """从JSON字符串创建TokenStatistics对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)


class TokenReporter:
    """Token统计报告生成器"""

    def __init__(self, language: str = "zh"):
        """
        初始化报告生成器

        Args:
            language: 语言代码 ("zh" 或 "en")
        """
        self.language = language

    def format_large_number(self, number: int) -> str:
        """格式化大数字，添加千位分隔符"""
        return f"{number:,}"

    def generate_simple_report(self, stats: TokenStatistics, api_base: Optional[str] = None) -> str:
        """
        生成简洁的token消耗报告

        Args:
            stats: token统计数据
            api_base: API基础URL

        Returns:
            格式化的报告字符串
        """
        if self.language == "zh":
            if stats.total_tokens == 0:
                return "暂无token消耗记录"

            cost, currency = stats.get_estimated_cost(api_base=api_base)
            currency_symbol = "¥" if currency == "CNY" else "$"
            efficiency = stats.get_efficiency_score()

            # 格式化输入/输出token数
            prompt_tokens_str = self.format_large_number(stats.prompt_tokens)
            completion_tokens_str = self.format_large_number(stats.completion_tokens)
            total_tokens_str = self.format_large_number(stats.total_tokens)

            report = f"""📊 Token消耗: {total_tokens_str} tokens (输入: {prompt_tokens_str}, 输出: {completion_tokens_str})"""

            if cost > 0:
                report += f" (估算成本: {currency_symbol}{cost:.4f})"

            if stats.request_count > 1:
                report += f" | {stats.request_count}次请求"

            if efficiency > 0:
                report += f" | 效率: {efficiency:.1%}"

            return report

        else:  # English
            if stats.total_tokens == 0:
                return "No token usage recorded"

            cost, currency = stats.get_estimated_cost(api_base=api_base)
            currency_symbol = "¥" if currency == "CNY" else "$"
            efficiency = stats.get_efficiency_score()

            # Format input/output tokens
            prompt_tokens_str = self.format_large_number(stats.prompt_tokens)
            completion_tokens_str = self.format_large_number(stats.completion_tokens)
            total_tokens_str = self.format_large_number(stats.total_tokens)

            report = f"""📊 Token Usage: {total_tokens_str} tokens (input: {prompt_tokens_str}, output: {completion_tokens_str})"""

            if cost > 0:
                report += f" (Est. cost: {currency_symbol}{cost:.4f})"

            if stats.request_count > 1:
                report += f" | {stats.request_count} requests"

            if efficiency > 0:
                report += f" | Efficiency: {efficiency:.1%}"

            return report

    def generate_detailed_report(self, total_stats: TokenStatistics, agent_stats: Dict[str, TokenStatistics], api_base: Optional[str] = None) -> str:
        """
        生成详细的token消耗报告

        Args:
            total_stats: 总体统计
            agent_stats: 各Agent的统计字典
            api_base: API基础URL

        Returns:
            详细的格式化报告
        """
        if self.language == "zh":
            if total_stats.total_tokens == 0:
                return "暂无token消耗记录"

            lines = []
            lines.append("### 📊 Token消耗统计")
            lines.append("")

            # 总体统计
            cost, currency = total_stats.get_estimated_cost(api_base=api_base)
            currency_symbol = "¥" if currency == "CNY" else "$"
            total_line = f"**总消耗**: {self.format_large_number(total_stats.total_tokens)} tokens"
            if cost > 0:
                total_line += f" (预估成本: {currency_symbol}{cost:.4f})"
            lines.append(total_line)
            lines.append("")

            # 各Agent统计
            if agent_stats:
                lines.append("**分Agent统计**:")
                for agent_name, stats in agent_stats.items():
                    if stats.total_tokens > 0:
                        prompt_str = self.format_large_number(stats.prompt_tokens)
                        completion_str = self.format_large_number(stats.completion_tokens)
                        total_str = self.format_large_number(stats.total_tokens)
                        lines.append(
                            f"- {agent_name}: {total_str} tokens "
                            f"(输入: {prompt_str}, 输出: {completion_str}) "
                            f"({stats.request_count}次请求)"
                        )
                lines.append("")

            # 效率指标
            efficiency = total_stats.get_efficiency_score()
            if efficiency > 0:
                lines.append(f"**效率指标**: 输出效率 {efficiency:.1%}")
                if efficiency > 0.3:
                    lines.append("Token使用效率良好")
                elif efficiency > 0.2:
                    lines.append("Token使用效率一般")
                else:
                    lines.append("Token使用效率可优化")

            return "\n".join(lines)

        else:  # English
            if total_stats.total_tokens == 0:
                return "No token usage recorded"

            lines = []
            lines.append("### 📊 Token Usage Statistics")
            lines.append("")

            # Total statistics
            cost, currency = total_stats.get_estimated_cost(api_base=api_base)
            currency_symbol = "¥" if currency == "CNY" else "$"
            total_line = f"**Total Usage**: {self.format_large_number(total_stats.total_tokens)} tokens"
            if cost > 0:
                total_line += f" (Est. cost: {currency_symbol}{cost:.4f})"
            lines.append(total_line)
            lines.append("")

            # Per-agent statistics
            if agent_stats:
                lines.append("**By Agent**:")
                for agent_name, stats in agent_stats.items():
                    if stats.total_tokens > 0:
                        prompt_str = self.format_large_number(stats.prompt_tokens)
                        completion_str = self.format_large_number(stats.completion_tokens)
                        total_str = self.format_large_number(stats.total_tokens)
                        lines.append(
                            f"- {agent_name}: {total_str} tokens "
                            f"(input: {prompt_str}, output: {completion_str}) "
                            f"({stats.request_count} requests)"
                        )
                lines.append("")

            # Efficiency metrics
            efficiency = total_stats.get_efficiency_score()
            if efficiency > 0:
                lines.append(f"**Efficiency**: Output ratio {efficiency:.1%}")
                if efficiency > 0.3:
                    lines.append("Token usage efficiency is good")
                elif efficiency > 0.2:
                    lines.append("Token usage efficiency is fair")
                else:
                    lines.append("Token usage efficiency can be optimized")

            return "\n".join(lines)


# 便捷函数
def create_token_stats(agent_name: str = "", model_name: str = "") -> TokenStatistics:
    """创建新的token统计对象"""
    return TokenStatistics(agent_name=agent_name, model_name=model_name)


def merge_token_stats(stats_list: List[TokenStatistics]) -> TokenStatistics:
    """合并多个token统计对象"""
    if not stats_list:
        return TokenStatistics()

    result = stats_list[0]
    for stats in stats_list[1:]:
        result = result.merge(stats)

    return result