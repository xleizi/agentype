#!/usr/bin/env python3
"""
agentype - 验证器基类
Author: cuilei
Version: 2.0

所有Agent验证器的共享逻辑，提供统一的React响应格式验证。
子类可以通过重写 _validate_agent_specific() 添加特定验证逻辑。
"""

from dataclasses import dataclass
from typing import Dict, List, Any
import re


@dataclass
class BaseValidator:
    """验证器基类 - 所有Agent验证器的共享逻辑"""
    language: str = "zh"

    def _ok(self, ok: bool, message: str, **extra) -> Dict:
        """构建验证结果字典"""
        d = {"ok": ok, "message": message}
        d.update(extra)
        return d

    @staticmethod
    def validate_response_format(response: str, has_reasoning: bool = False) -> Dict[str, Any]:
        """验证React响应格式（核心共享逻辑）

        Args:
            response: AI响应内容
            has_reasoning: 是否有reasoning_content（DeepSeek Reasoner模型）
                          当为True时，允许没有<thought>标签

        Returns:
            验证结果字典，包含是否有效和问题列表
        """
        issues = []

        # 🌟 关键修改：DeepSeek Reasoner模型有reasoning_content时，
        # 没有<thought>标签不算错误（推理过程在reasoning_content中）
        if "<thought>" not in response and not has_reasoning:
            issues.append("缺少 <thought> 标签")

        # 检查是否有action或final_answer
        has_action = "<action>" in response
        has_final_answer = "<final_answer>" in response or "</final_answer>" in response

        if not has_action and not has_final_answer:
            issues.append("缺少 <action> 或 <final_answer> 标签")

        # 检查标签是否成对（XML风格）
        if "<thought>" in response and "</thought>" not in response:
            issues.append("<thought> 标签未正确闭合")

        if has_action and "</action>" not in response:
            issues.append("<action> 标签未正确闭合")

        if "<final_answer>" in response and "</final_answer>" not in response:
            issues.append("<final_answer> 标签未正确闭合")

        # 🔥 关键检查：检查是否有多余的observation标签（LLM不应该生成observation）
        if "<observation>" in response:
            issues.append("检测到非法的 <observation> 标签 - LLM 不应该自行生成观察结果")

        # 检查中文React格式的兼容性
        has_chinese_format = any(keyword in response for keyword in ["思考：", "行动：", "回答："])
        has_xml_format = any(keyword in response for keyword in ["<thought>", "<action>", "<final_answer>"])

        if not has_chinese_format and not has_xml_format:
            issues.append("未检测到有效的 React 格式（中文或XML）")

        # 🔍 扩展点：允许子类添加额外验证
        additional_issues = BaseValidator._validate_agent_specific(response)
        if additional_issues:
            issues.extend(additional_issues)

        return {
            "valid": len(issues) == 0,
            "issues": issues
        }

    @staticmethod
    def _validate_agent_specific(response: str) -> List[str]:
        """扩展点：Agent特定的验证逻辑

        子类可以重写此方法添加自己的验证规则。
        例如：
        - MainAgent: 簇完成度检查
        - AppAgent: 注释工作流验证

        Args:
            response: AI响应内容

        Returns:
            额外的验证问题列表
        """
        return []

    @staticmethod
    def build_correction_prompt(validation_result: Dict[str, Any],
                               available_tools: List[Dict],
                               language: str = "zh") -> str:
        """构建修正提示（共享逻辑）

        Args:
            validation_result: 验证结果
            available_tools: 可用工具列表
            language: 语言（zh/en）

        Returns:
            修正提示字符串
        """
        from agentype.prompts import get_prompt_manager

        manager = get_prompt_manager(language)
        template = manager.get_common_prompt('BASE_CORRECTION_TEMPLATE')

        issues = validation_result.get('issues', [])
        issues_text = '\n'.join(['- ' + issue for issue in issues])
        tools_text = ', '.join([tool.get('name', '未知') for tool in available_tools])

        return template.format(
            issues=issues_text,
            available_tools=tools_text
        )
