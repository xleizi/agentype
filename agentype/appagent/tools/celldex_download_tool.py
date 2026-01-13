#!/usr/bin/env python3
"""
agentype - MCP工具：下载celldex数据集
Author: cuilei
Version: 1.0
"""

import os
import sys
import re
import requests
import subprocess
from typing import Dict, Any, Optional, List
from pathlib import Path

# celldex数据集映射
DATASET_MAPPING = {
    "BlueprintEncodeData": {"func": "BlueprintEncodeData", "file": "bpe.se.rds"},
    "DatabaseImmuneCellExpressionData": {"func": "DatabaseImmuneCellExpressionData", "file": "dbie.se.rds"}, 
    "HumanPrimaryCellAtlasData": {"func": "HumanPrimaryCellAtlasData", "file": "hpca.se.rds"},
    "ImmGenData": {"func": "ImmGenData", "file": "immgen.se.rds"},
    "MonacoImmuneData": {"func": "MonacoImmuneData", "file": "monaco.se.rds"},
    "MouseRNAseqData": {"func": "MouseRNAseqData", "file": "mouse.se.rds"},
    "NovershternHematopoieticData": {"func": "NovershternHematopoieticData", "file": "nhe.se.rds"}
}

# 简化的数据集名称映射
DATASET_ALIASES = {
    "bpe": "BlueprintEncodeData",
    "dbie": "DatabaseImmuneCellExpressionData", 
    "hpca": "HumanPrimaryCellAtlasData",
    "immgen": "ImmGenData",
    "monaco": "MonacoImmuneData",
    "mouse": "MouseRNAseqData",
    "nhe": "NovershternHematopoieticData"
}

def _parse_r_errors(stderr_output: str) -> Dict[str, Any]:
    """
    使用正则表达式从R的stderr输出中解析关键错误信息
    
    Args:
        stderr_output (str): R脚本执行的stderr输出
        
    Returns:
        Dict[str, Any]: 解析后的错误信息
    """
    if not stderr_output:
        return {"parsed_errors": [], "error_type": "unknown", "main_error": ""}
    
    # 定义错误模式
    error_patterns = [
        # 中文错误信息
        (r'Error in (.+?) : (.+)', "execution_error"),
        (r'错误[:：](.+)', "general_error"),
        (r'不存在叫[\'"](.+?)[\'"]这个名字的程辑包', "package_not_found"),
        (r'停止执行', "execution_stopped"),
        (r'无法找到函数[\'"](.+?)[\'"]', "function_not_found"),
        
        # 英文错误信息
        (r'Error: (.+)', "general_error"),
        (r'there is no package called [\'"](.+?)[\'"]', "package_not_found"),
        (r'could not find function [\'"](.+?)[\'"]', "function_not_found"),
        (r'object [\'"](.+?)[\'"] not found', "object_not_found"),
    ]
    
    parsed_errors = []
    error_type = "unknown"
    main_error = ""
    
    # 按行分割stderr输出
    lines = stderr_output.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 跳过正常的包载入信息
        if any(skip_pattern in line for skip_pattern in [
            "载入需要的程辑包", "载入程辑包", "Loading required package",
            "The following objects are masked", "Welcome to Bioconductor",
            "Vignettes contain introductory material"
        ]):
            continue
            
        # 检查错误模式
        for pattern, err_type in error_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                error_info = {
                    "line": line,
                    "type": err_type,
                    "matched_groups": match.groups()
                }
                parsed_errors.append(error_info)
                
                # 设置主要错误类型和信息
                if not main_error or err_type in ["package_not_found", "execution_error", "general_error"]:
                    error_type = err_type
                    main_error = line
                break
    
    return {
        "parsed_errors": parsed_errors,
        "error_type": error_type,
        "main_error": main_error,
        "total_error_lines": len(parsed_errors)
    }

def _create_cache_dir(cache_dir: str) -> str:
    """创建缓存目录"""
    # 展开用户目录
    cache_path = Path(cache_dir).expanduser()
    celldex_cache = cache_path / "celldex"
    celldex_cache.mkdir(parents=True, exist_ok=True)
    return str(celldex_cache)

def _download_with_r(dataset_name: str, cache_dir: str) -> Dict[str, Any]:
    """使用R的celldex包下载数据"""
    try:
        dataset_info = DATASET_MAPPING[dataset_name]
        func_name = dataset_info["func"]
        file_name = dataset_info["file"]
        
        # 检查R环境
        try:
            subprocess.run(['R', '--version'], capture_output=True, check=True)
        except:
            return {
                "status": "error",
                "dataset": dataset_name,
                "download_method": "celldex",
                "error": "错误：未找到R环境，请安装R语言环境"
            }
        
        # 转换为绝对路径
        output_path = os.path.abspath(os.path.join(cache_dir, file_name))
        
        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        # 构建R脚本 (修复拼写错误: cellde2x -> celldex)
        r_script = f'''
# 加载celldex包
library(celldex)

# 设置详细输出
cat("正在下载 {dataset_name}...\\n")
data <- celldex::{func_name}()
cat("数据下载成功\\n")

# 保存到指定路径
cat("正在保存到:", "{output_path}", "\\n")
saveRDS(data, "{output_path}")
cat("数据已保存到: {output_path}\\n")
'''
        
        # 执行R脚本
        result = subprocess.run(['R', '--slave', '--no-restore', '--no-save'], 
                              input=r_script, text=True, capture_output=True, encoding='utf-8')
        
        # 解析错误信息
        error_analysis = _parse_r_errors(result.stderr) if result.stderr else {}
        
        # 检查执行结果
        if result.returncode == 0:
            # 验证输出文件是否存在
            if os.path.exists(output_path):
                return {
                    "status": "success",
                    "dataset": dataset_name,
                    "file_path": output_path,
                    "download_method": "celldex",
                    "message": f"成功使用celldex包下载 {dataset_name}",
                    "file_size": os.path.getsize(output_path),
                    "r_output": result.stdout.strip() if result.stdout else "",
                    "r_returncode": result.returncode,
                    "error_analysis": error_analysis
                }
            else:
                return {
                    "status": "error",
                    "dataset": dataset_name,
                    "download_method": "celldex",
                    "error": f"R脚本执行成功但未找到输出文件: {output_path}",
                    "r_output": result.stdout.strip() if result.stdout else "",
                    "r_error": result.stderr.strip() if result.stderr else "",
                    "r_returncode": result.returncode,
                    "error_analysis": error_analysis
                }
        else:
            # 构建详细的错误信息
            error_msg = f"R脚本执行失败，返回代码: {result.returncode}"
            if error_analysis.get("main_error"):
                error_msg += f" - 主要错误: {error_analysis['main_error']}"
            
            return {
                "status": "error",
                "dataset": dataset_name,
                "download_method": "celldex",
                "error": error_msg,
                "r_output": result.stdout.strip() if result.stdout else "",
                "r_error": result.stderr.strip() if result.stderr else "",
                "r_returncode": result.returncode,
                "error_analysis": error_analysis,
                "parsed_error": error_analysis.get("main_error", "未知错误"),
                "error_type": error_analysis.get("error_type", "unknown")
            }
                
    except Exception as e:
        return {
            "status": "error", 
            "dataset": dataset_name,
            "download_method": "celldex",
            "error": f"R下载过程中发生异常: {str(e)}"
        }

def _download_with_http(dataset_name: str, cache_dir: str) -> Dict[str, Any]:
    """使用HTTP从备用源下载数据"""
    try:
        dataset_info = DATASET_MAPPING[dataset_name]
        file_name = dataset_info["file"]
        
        # 构建下载URL和输出路径
        url = f"https://agent.s1f.ren/d/files/rds/celldex/{file_name}"
        output_path = os.path.join(cache_dir, file_name)
        
        # 发起HTTP请求
        response = requests.get(url, stream=True, timeout=300)  # 5分钟超时
        response.raise_for_status()
        
        # 写入文件
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # 验证文件是否下载完成
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return {
                "status": "success",
                "dataset": dataset_name, 
                "file_path": output_path,
                "download_method": "http",
                "message": f"成功从HTTP备用源下载 {dataset_name}",
                "file_size": os.path.getsize(output_path),
                "url": url
            }
        else:
            return {
                "status": "error",
                "dataset": dataset_name,
                "download_method": "http", 
                "error": "HTTP下载完成但文件为空或不存在"
            }
            
    except requests.RequestException as e:
        return {
            "status": "error",
            "dataset": dataset_name,
            "download_method": "http",
            "error": f"HTTP下载失败: {str(e)}"
        }
    except Exception as e:
        return {
            "status": "error",
            "dataset": dataset_name, 
            "download_method": "http",
            "error": f"HTTP下载过程中发生异常: {str(e)}"
        }

def download_celldex_dataset(dataset_name: str, cache_dir: str = "~/.cache/agentype") -> Dict[str, Any]:
    """
    下载celldex数据集的MCP工具函数
    
    Args:
        dataset_name (str): 数据集名称，支持完整名称或简写
        cache_dir (str): 缓存目录，默认~/.cache/agentype
        
    Returns:
        Dict[str, Any]: 下载结果信息
    """
    try:
        # 处理数据集名称别名
        if dataset_name in DATASET_ALIASES:
            dataset_name = DATASET_ALIASES[dataset_name]
        
        # 验证数据集名称
        if dataset_name not in DATASET_MAPPING:
            available_datasets = list(DATASET_MAPPING.keys()) + list(DATASET_ALIASES.keys())
            return {
                "status": "error",
                "error": f"不支持的数据集: {dataset_name}",
                "available_datasets": available_datasets
            }
        
        # 创建缓存目录
        cache_path = _create_cache_dir(cache_dir)
        
        # 检查文件是否已存在
        file_name = DATASET_MAPPING[dataset_name]["file"]
        existing_file = os.path.join(cache_path, file_name)
        if os.path.exists(existing_file):
            return {
                "status": "success",
                "dataset": dataset_name,
                "file_path": existing_file, 
                "download_method": "cached",
                "message": f"数据集 {dataset_name} 已存在于缓存中",
                "file_size": os.path.getsize(existing_file)
            }
        
        # 尝试使用celldex包下载
        result = _download_with_r(dataset_name, cache_path)
        if result["status"] == "success":
            return result
        
        # celldex下载失败，尝试HTTP备用下载
        http_result = _download_with_http(dataset_name, cache_path)
        if http_result["status"] == "success":
            http_result["fallback_reason"] = f"celldex下载失败: {result.get('error', '未知原因')}"
            return http_result
        
        # 两种方法都失败
        return {
            "status": "error",
            "dataset": dataset_name,
            "error": "所有下载方法都失败",
            "celldex_error": result.get("error", "未知错误"),
            "http_error": http_result.get("error", "未知错误"),
            "error_analysis": result.get("error_analysis", {})
        }
        
    except Exception as e:
        return {
            "status": "error",
            "dataset": dataset_name,
            "error": f"下载过程中发生异常: {str(e)}"
        }