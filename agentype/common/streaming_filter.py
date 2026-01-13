#!/usr/bin/env python3
"""
agentype - 流式输出内容过滤器
Author: cuilei
Version: 2.0

所有Agent共享的流式输出过滤器，用于在流式输出时隐藏action和celltype标签内容。
"""


class StreamingFilter:
    """流式输出内容过滤器

    使用状态机模式处理流式输出，隐藏<action>和<celltype>标签的内容，
    同时显示<thought>和<final_answer>的内容。

    状态转换：
    - normal: 正常输出
    - in_action: 在<action>标签内，隐藏内容
    - in_celltype: 在<celltype>标签内，隐藏内容
    - in_thought: 在<thought>标签内，显示内容
    - in_final_answer: 在<final_answer>标签内，显示内容
    """

    def __init__(self):
        """初始化过滤器"""
        self.buffer = ""
        self.state = "normal"  # normal, in_action, in_celltype, in_thought, in_final_answer
        self.pending_output = ""

    def filter_chunk(self, new_chunk: str) -> str:
        """过滤新的内容块，返回应该显示的部分

        Args:
            new_chunk: 新到达的内容块

        Returns:
            应该显示给用户的内容
        """
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
                elif remaining.startswith('<celltype>'):
                    self.state = "in_celltype"
                    i += len('<celltype>')
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
                    potential_tags = ['<action>', '<celltype>', '<thought>', '<final_answer>']
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

            elif self.state == "in_celltype":
                if remaining.startswith('</celltype>'):
                    self.state = "normal"
                    i += len('</celltype>')
                    processed = i
                elif remaining.startswith('</') and len(remaining) < 12:
                    # 可能是不完整的结束标签
                    if '</celltype>'.startswith(remaining):
                        break  # 等待更多内容
                    else:
                        i += 1
                        processed = i
                else:
                    # 跳过celltype内容
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
