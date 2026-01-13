#!/usr/bin/env python3
"""
agentype - MCP工具：获取celldex项目信息
Author: cuilei
Version: 1.0
"""

from typing import Dict, Any

from .get_celldex_projects_bilingual import celldexProjectsInfo

def get_celldex_projects_info(language: str = "zh") -> Dict[str, Any]:
    """
    MCP工具函数：获取celldex所有项目信息
    
    Args:
        language (str): 输出语言，"zh"为中文，"en"为英文，默认中文
        
    Returns:
        Dict[str, Any]: 包含所有celldex数据集信息的字典
                       每个数据集包含name, description, species, cell_types, source, data_type
    """
    try:
        # 创建celldexProjectsInfo实例
        celldex = celldexProjectsInfo(language=language)
        
        # 获取所有项目信息
        projects = celldex.get_all_projects()
        
        return projects
        
    except Exception as e:
        return {
            "error": f"获取celldex项目信息时发生错误: {str(e)}",
            "status": "failed"
        }