#!/usr/bin/env python3
"""
agentype - Service模块
Author: cuilei
Version: 1.0
"""

import logging
from typing import Optional

from agentype.subagent.agent.celltype_react_agent import CellTypeReactAgent
from agentype.subagent.api.models import CellTypeAnalysisRequest, CellTypeAnalysisResponse
from agentype.subagent.config.settings import ConfigManager
from agentype.subagent.utils.output_logger import create_logger
from agentype.subagent.utils.path_manager import path_manager

logger = logging.getLogger(__name__)

class CellTypeAPIService:
    """细胞类型分析API服务类"""
    
    def __init__(self, config: ConfigManager):
        # 使用路径管理器获取MCP服务器脚本路径
        mcp_server_path = str(path_manager.get_mcp_server_path())
        self.agent: Optional[CellTypeReactAgent] = CellTypeReactAgent(
            config=config,
            server_script=mcp_server_path
        )
        self.is_initialized = False
    
    async def initialize(self):
        """初始化Agent"""
        if not self.is_initialized and self.agent:
            try:
                success = await self.agent.initialize()
                if success:
                    self.is_initialized = True
                    logger.info(f"React Agent初始化成功，使用模型: {self.agent.config.openai_model}")
                else:
                    logger.error("React Agent初始化失败")
            except Exception as e:
                logger.error(f"初始化agent时发生错误: {str(e)}")
    
    async def analyze_celltype(self, request: CellTypeAnalysisRequest) -> CellTypeAnalysisResponse:
        """执行细胞类型分析"""
        if not self.is_initialized or not self.agent:
            return CellTypeAnalysisResponse(
                success=False,
                cell_type=None,
                final_llm_output=None,
                total_iterations=0,
                analysis_log=[],
                log_file_path=None,
                error_type="initialization_error",
                error_message="Agent未初始化或初始化失败"
            )
        
        # 创建日志器
        api_logger = create_logger(log_dir="./logs", log_prefix="celltype_api_analysis")
        log_file_path = None
        
        try:
            # 记录分析开始
            api_logger.header("🧬 细胞类型分析API调用")
            api_logger.separator("=", 60)
            api_logger.info(f"📋 输入基因列表: {request.gene_list}")
            if request.tissue_type:
                api_logger.info(f"🏥 组织类型: {request.tissue_type}")
            if request.cell_type:
                api_logger.info(f"🧫 细胞类型提示: {request.cell_type}")
            api_logger.info(f"🤖 使用模型: {self.agent.config.openai_model}")
            api_logger.separator("-", 60)
            
            # 获取日志文件路径
            log_file_path = str(api_logger.get_log_file_path()) if api_logger.get_log_file_path() else None
            if log_file_path:
                api_logger.info(f"📄 日志文件保存位置: {log_file_path}")
                api_logger.separator("-", 60)
            
            api_logger.info("🚀 开始细胞类型分析...")
            
            # 使用stdout捕获功能来捕获所有内部输出
            with api_logger.capture_stdout():
                result = await self.agent.analyze_celltype(
                    gene_list=request.gene_list,
                    tissue_type=request.tissue_type,
                    cell_type=request.cell_type
                )
            
            # 记录分析结果
            api_logger.success(f"✅ 分析结果: {result.get('final_celltype')}")
            
            api_logger.info("")
            api_logger.header("📊 分析统计信息:")
            api_logger.info(f"   - 总迭代数: {result.get('total_iterations')}")
            api_logger.info(f"   - 工具调用次数: {len([log for log in result.get('analysis_log', []) if log.get('type') == 'tool_call'])}")
            api_logger.info(f"   - 分析成功: {result.get('success')}")
            
            # 提取最终LLM输出
            final_llm_output = None
            for log_entry in reversed(result.get('analysis_log', [])):
                if log_entry.get('type') == 'ai_response':
                    final_llm_output = log_entry.get('response', '')
                    break
            
            api_logger.info("")
            api_logger.success("🎉 分析完成！")
            
            # 显示最终的日志文件位置
            if log_file_path:
                api_logger.info("")
                api_logger.info(f"📄 完整的分析日志已保存至: {log_file_path}")
            
            return CellTypeAnalysisResponse(
                success=result.get('success', False),
                cell_type=result.get('final_celltype'),
                final_llm_output=final_llm_output,
                total_iterations=result.get('total_iterations', 0),
                analysis_log=result.get('analysis_log', []),
                error_message=None
            )
            
        except Exception as e:
            error_msg = f"分析错误: {str(e)}"
            logger.error(f"分析过程中发生错误: {str(e)}")
            
            # 记录错误到日志文件
            api_logger.error(f"❌ {error_msg}")
            if log_file_path:
                api_logger.info(f"📄 错误日志已保存至: {log_file_path}")
            
            return CellTypeAnalysisResponse(
                success=False,
                cell_type=None,
                final_llm_output=None,
                total_iterations=0,
                analysis_log=[],
                error_message=f"分析错误: {str(e)}"
            )
        finally:
            # 关闭日志器
            api_logger.close()
    
    async def cleanup(self):
        """清理资源"""
        if self.agent:
            try:
                await self.agent.cleanup()
            except Exception as e:
                logger.error(f"清理资源时发生错误: {str(e)}")
            finally:
                self.agent = None
                self.is_initialized = False
