#!/usr/bin/env python3
"""
agentype - 日志记录
Author: cuilei
Version: 1.0
"""

import json
import sys
from pathlib import Path
from typing import Dict
from datetime import datetime

class LLMLogger:
    """LLM 请求和响应日志记录器
    
    负责记录所有的 LLM API 调用，包括完整的请求参数和响应内容，
    以 JSON 格式保存到指定的日志文件中。
    """
    
    def __init__(self, log_dir: str = "llm_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 获取 session_id（完整格式：session_20251023_142530）
        try:
            from agentype.mainagent.config.session_config import get_session_id
            session_id = get_session_id()
        except ImportError:
            # 如果导入失败，回退到时间戳格式
            session_id = "session_" + datetime.now().strftime("%Y%m%d_%H%M%S")

        # 使用 session_id 生成日志文件名
        self.log_file = self.log_dir / f"llm_requests_{session_id}.jsonl"

        print(f"📝 LLM 日志将保存到: {self.log_file}", file=sys.stderr)
        print(f"📋 Session ID: {session_id}", file=sys.stderr)
    
    def log_request_response(self, 
                           request_type: str,
                           request_data: Dict, 
                           response_data: str,
                           success: bool = True,
                           error_msg: str = None,
                           extra_info: Dict = None):
        """记录单次 LLM 请求和响应
        
        Args:
            request_type: 请求类型 ("chat_completion", "summarization", "retry")
            request_data: 完整请求数据
            response_data: 完整的响应数据
            success: 是否成功
            error_msg: 错误消息（如果有）
            extra_info: 额外信息
        """
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "request_type": request_type,
                "success": success,
                "request": request_data,
                "response": response_data,
                "response_length": len(response_data) if response_data else 0
            }
            
            if error_msg:
                log_entry["error"] = error_msg
            
            if extra_info:
                log_entry["extra_info"] = extra_info
            
            # 以 JSON Lines 格式写入文件
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
                
            print(f"📋 已记录 {request_type} 请求日志", file=sys.stderr)
            
        except Exception as e:
            print(f"❌ 记录日志失败: {e}", file=sys.stderr)
    
    def get_log_summary(self) -> Dict:
        """获取日志摘要统计"""
        try:
            if not self.log_file.exists():
                return {"total_requests": 0, "success_count": 0, "error_count": 0}
            
            total_requests = 0
            success_count = 0
            error_count = 0
            request_types = {}
            
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        total_requests += 1
                        
                        if entry.get("success", False):
                            success_count += 1
                        else:
                            error_count += 1
                        
                        req_type = entry.get("request_type", "unknown")
                        request_types[req_type] = request_types.get(req_type, 0) + 1
                        
                    except json.JSONDecodeError:
                        continue
            
            return {
                "total_requests": total_requests,
                "success_count": success_count,
                "error_count": error_count,
                "request_types": request_types,
                "log_file": str(self.log_file)
            }
            
        except Exception as e:
            print(f"❌ 获取日志摘要失败: {e}", file=sys.stderr)
            return {"error": str(e)}

    async def close(self):
        """关闭日志记录器（兼容性方法）"""
        pass