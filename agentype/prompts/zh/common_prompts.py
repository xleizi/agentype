#!/usr/bin/env python3
"""
Common 中文Prompt模板
共享的基础prompt，供所有Agent使用

Author: cuilei
Version: 2.0
"""

# 基础修正提示模板（从base_validator.py迁移）
BASE_CORRECTION_TEMPLATE = """⚠️ 您的上次响应格式不正确，请修正以下问题：
{issues}

📝 请严格按照以下 XML 格式回答：
1. <thought>您的推理过程</thought>
2. 然后是以下之一：
   - <action>工具名称(参数)</action> - 如果需要调用工具继续分析
   - <final_answer>完整报告和结论</final_answer> - 如果分析完成

🚨 重要提醒：
- 禁止生成 <observation> 标签 - 它们由系统在工具执行后自动注入
- 输出 <action> 后请等待系统注入 <observation>
- 提供 <final_answer> 时，必须在其后包含 <file_paths> 部分
- 格式示例：
  <final_answer>您的分析报告</final_answer>
  <file_paths>
    <rds_file>/path/to/file.rds</rds_file>
    <marker_genes_json>/path/to/results.json</marker_genes_json>
  </file_paths>

可用工具: {available_tools}"""


# 幻觉检测修正消息（从subagent/agent/celltype_react_agent.py迁移）
HALLUCINATION_CORRECTION_MESSAGE = """⚠️ **错误提示**：
你的上一个响应中包含了 <observation> 标签，这是不允许的。
<observation> 标签是系统保留标签，由 Agent 在调用工具后自动添加。
你只需要生成 <thought>、<action> 或 <final_answer> 标签。

请重新生成你的响应，**不要包含** <observation> 标签。"""


# 内容摘要提示（从base_content_processor.py迁移）
CONTENT_SUMMARY_PROMPT = """请对以下内容进行摘要，保留最重要的信息和数据。摘要应该：
1. 保留所有关键的数值、基因名称、细胞类型等核心信息
2. 去除冗余的描述性文字
3. 保持清晰的结构
4. 控制在{max_length}字符以内

原始内容：
{content}

请提供简洁的摘要："""


# 英文版本的内容摘要提示（从base_content_processor.py迁移）
CONTENT_SUMMARY_PROMPT_EN = """Please summarize the following content, retaining the most important information and data. The summary should:
1. Retain all key numerical values, gene names, cell types and other core information
2. Remove redundant descriptive text
3. Maintain clear structure
4. Keep within {max_length} characters

Original content:
{content}

Please provide a concise summary:"""


# 标准命名别名（供PromptManager使用）
SYSTEM_PROMPT = ""  # common prompts没有system prompt
FALLBACK_PROMPT = ""
USER_QUERY_TEMPLATES = {}
CORRECTION_TEMPLATE = BASE_CORRECTION_TEMPLATE  # 使用基础修正模板作为默认
