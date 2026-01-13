#!/usr/bin/env python3
"""
Common English prompt templates
Shared base prompts for all agents

Author: cuilei (translated)
Version: 2.0
"""

# Base correction template (migrated from base_validator.py)
BASE_CORRECTION_TEMPLATE = """⚠️ Your previous response has formatting issues:
{issues}

📝 Please answer strictly using the following XML structure:
1. <thought>Your reasoning process</thought>
2. Then one of:
   - <action>tool_name(param="value")</action> - when a tool call is required
   - <final_answer>Complete report and conclusion</final_answer> - when the analysis is finished

🚨 Important reminders:
- Never emit an <observation> tag - it is injected by the system after tool execution
- After outputting an <action>, stop and wait for the injected <observation>
- When providing <final_answer>, you must append a <file_paths> section
- Example format:
  <final_answer>Your analysis report</final_answer>
  <file_paths>
    <rds_file>/path/to/file.rds</rds_file>
    <marker_genes_json>/path/to/results.json</marker_genes_json>
  </file_paths>

Available tools: {available_tools}"""


# Hallucination correction message (migrated from subagent/agent/celltype_react_agent.py)
HALLUCINATION_CORRECTION_MESSAGE = """⚠️ Format error detected:
Your previous response contained an <observation> tag, which is not allowed.
<observation> tags are reserved for the system and are inserted automatically after a tool call.

Please regenerate your response without using the <observation> tag."""


# Content summary prompt
CONTENT_SUMMARY_PROMPT = """Please summarize the following content while keeping the most important information and data. The summary must:
1. Preserve all key numerical values, gene names, cell types and other core facts
2. Remove redundant descriptive text
3. Maintain a clear structure
4. Stay within {max_length} characters

Original content:
{content}

Provide a concise summary:"""


# Alias for compatibility when explicitly requesting the English template
CONTENT_SUMMARY_PROMPT_EN = CONTENT_SUMMARY_PROMPT


# Standard naming aliases (used by PromptManager)
SYSTEM_PROMPT = ""  # common prompts do not define a system prompt
FALLBACK_PROMPT = ""
USER_QUERY_TEMPLATES = {}
CORRECTION_TEMPLATE = BASE_CORRECTION_TEMPLATE  # use the base correction template as default

