#!/usr/bin/env python3
"""
agentype - Filetool模块
Author: cuilei
Version: 1.0
"""

import subprocess
from typing import List, Dict, Any, Optional

# 创建和运行Python文件，使用当前Python环境
def create_and_run_python_file(file_path: str, file_name: str, code: str, auto_delete: bool = True) -> Dict[str, Any]:
    """
    创建Python文件，写入代码并在当前Python环境中执行
    
    Args:
        file_path (str): 文件保存的目录路径，如 "D:/projects" 或 "."
        file_name (str): Python文件名（不含.py扩展名），如 "data_analysis"
        code (str): 要写入文件的Python代码
        auto_delete (bool): 是否在执行完成后自动删除文件，默认为True
        
    Returns:
        dict: 包含执行结果的详细信息
    """
    import os
    import tempfile
    import sys
    
    try:
        # 确保文件名以.py结尾
        if not file_name.endswith('.py'):
            file_name += '.py'
        
        # 构建完整文件路径
        full_file_path = os.path.join(file_path, file_name)
        
        # 确保目录存在
        os.makedirs(file_path, exist_ok=True)
        
        # 写入代码到文件（覆盖策略）
        with open(full_file_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        # 使用当前Python环境执行
        command = f'"{sys.executable}" "{full_file_path}"'
        
        # 执行文件
        result = subprocess.run(
            command, 
            shell=True, 
            capture_output=True, 
            text=True, 
            cwd=file_path,  # 设置工作目录
            encoding='utf-8',
            errors='replace',
            timeout=300  # 5分钟超时
        )
        
        # 准备返回结果
        execution_result = {
            "status": "success" if result.returncode == 0 else "error",
            "file_path": full_file_path,
            "file_name": file_name,
            "python_executable": sys.executable,
            "returncode": result.returncode,
            "output": result.stdout.strip() if result.stdout else "",
            "error": result.stderr.strip() if result.stderr else "",
            "command": command
        }
        
        # 如果有错误输出，添加到结果中
        if result.returncode != 0:
            execution_result["status"] = "error"
            execution_result["error_details"] = f"代码执行失败，返回码: {result.returncode}"
        
        # 处理文件删除逻辑
        if auto_delete:
            try:
                os.remove(full_file_path)
                execution_result["file_deleted"] = True
                execution_result["delete_status"] = "文件已自动删除"
            except Exception as delete_error:
                execution_result["file_deleted"] = False
                execution_result["delete_error"] = f"删除文件失败: {str(delete_error)}"
        else:
            execution_result["file_deleted"] = False
            execution_result["delete_status"] = "文件已保留（根据参数设置）"
        
        return execution_result
        
    except subprocess.TimeoutExpired:
        # 超时情况下也尝试删除文件
        cleanup_result = {}
        if auto_delete and 'full_file_path' in locals():
            try:
                os.remove(full_file_path)
                cleanup_result = {"file_deleted": True, "delete_status": "超时后文件已清理"}
            except:
                cleanup_result = {"file_deleted": False, "delete_status": "超时后文件清理失败"}
        
        return {
            "status": "timeout",
            "error": "代码执行超时（60秒），可能存在无限循环或长时间运行的操作",
            "file_path": full_file_path if 'full_file_path' in locals() else None,
            **cleanup_result
        }
    except FileNotFoundError as e:
        return {
            "status": "error",
            "error": f"文件操作失败: {str(e)}",
            "suggestion": "请检查文件路径是否正确，确保有写入权限"
        }
    except Exception as e:
        # 异常情况下也尝试删除文件
        cleanup_result = {}
        if auto_delete and 'full_file_path' in locals():
            try:
                os.remove(full_file_path)
                cleanup_result = {"file_deleted": True, "delete_status": "异常后文件已清理"}
            except:
                cleanup_result = {"file_deleted": False, "delete_status": "异常后文件清理失败"}
        
        return {
            "status": "exception",
            "error": f"创建或执行Python文件时发生异常: {str(e)}",
            "file_path": full_file_path if 'full_file_path' in locals() else None,
            **cleanup_result
        }

# 创建和运行R文件，使用系统安装的R环境
def create_and_run_r_file(file_path: str, file_name: str, code: str, auto_delete: bool = True) -> Dict[str, Any]:
    """
    创建R文件，写入代码并在系统R环境中执行
    
    Args:
        file_path (str): 文件保存的目录路径，如 "D:/projects" 或 "."
        file_name (str): R文件名（不含.R扩展名），如 "data_analysis"
        code (str): 要写入文件的R代码
        auto_delete (bool): 是否在执行完成后自动删除文件，默认为True
        
    Returns:
        dict: 包含执行结果的详细信息
    """
    import os
    import shutil
    
    try:
        # 确保文件名以.R结尾
        if not file_name.lower().endswith('.r'):
            file_name += '.R'
        
        # 构建完整文件路径
        full_file_path = os.path.join(file_path, file_name)
        
        # 确保目录存在
        os.makedirs(file_path, exist_ok=True)
        
        # 写入代码到文件（覆盖策略）
        with open(full_file_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        # 查找R可执行文件
        r_executable = shutil.which('R')
        if not r_executable:
            r_executable = shutil.which('Rscript')
        
        if not r_executable:
            return {
                "status": "error",
                "error": "未找到R或Rscript可执行文件，请确保已安装R环境",
                "suggestion": "请安装R语言环境，或确保R在系统PATH中"
            }
        
        # 构建执行命令，使用Rscript执行（更适合脚本执行）
        if r_executable.endswith('R'):
            command = f'"{r_executable}" --slave --no-restore --file="{full_file_path}"'
        else:  # Rscript
            command = f'"{r_executable}" "{full_file_path}"'

        # 执行文件
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=file_path,  # 设置工作目录
            encoding='utf-8',
            errors='replace'
        )
        
        # 准备返回结果
        execution_result = {
            "status": "success" if result.returncode == 0 else "error",
            "file_path": full_file_path,
            "file_name": file_name,
            "r_executable": r_executable,
            "returncode": result.returncode,
            "output": result.stdout.strip() if result.stdout else "",
            "error": result.stderr.strip() if result.stderr else "",
            "command": command
        }
        
        # 如果有错误输出，添加到结果中
        if result.returncode != 0:
            execution_result["status"] = "error"
            execution_result["error_details"] = f"R代码执行失败，返回码: {result.returncode}"
        
        # 处理文件删除逻辑
        if auto_delete:
            try:
                os.remove(full_file_path)
                execution_result["file_deleted"] = True
                execution_result["delete_status"] = "文件已自动删除"
            except Exception as delete_error:
                execution_result["file_deleted"] = False
                execution_result["delete_error"] = f"删除文件失败: {str(delete_error)}"
        else:
            execution_result["file_deleted"] = False
            execution_result["delete_status"] = "文件已保留（根据参数设置）"
        
        return execution_result

    except FileNotFoundError as e:
        return {
            "status": "error",
            "error": f"文件操作失败: {str(e)}",
            "suggestion": "请检查文件路径是否正确，确保有写入权限"
        }
    except Exception as e:
        # 异常情况下也尝试删除文件
        cleanup_result = {}
        if auto_delete and 'full_file_path' in locals():
            try:
                os.remove(full_file_path)
                cleanup_result = {"file_deleted": True, "delete_status": "异常后文件已清理"}
            except:
                cleanup_result = {"file_deleted": False, "delete_status": "异常后文件清理失败"}
        
        return {
            "status": "exception",
            "error": f"创建或执行R文件时发生异常: {str(e)}",
            "file_path": full_file_path if 'full_file_path' in locals() else None,
            **cleanup_result
        }

# 简单地读取文件
def read_file(file_path: str) -> str:
    """
    读取指定文件的全部内容
    
    Args:
        file_path (str): 要读取的文件的绝对路径或相对路径，支持各种文本文件格式
                        例如: "D:/example.txt", "/home/user/data.json", "config.ini"
    
    Returns:
        str: 文件的完整文本内容，保持原有的换行符和格式
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

# 简单地写文件
def write_to_file(file_path: str, content: str) -> str:
    """
    将指定内容写入文件，如果文件不存在则创建，如果存在则覆盖
    
    Args:
        file_path (str): 目标文件的绝对路径，支持创建新文件
        content (str): 要写入文件的文本内容，支持包含换行符的多行文本
    
    Returns:
        str: 成功时返回 "写入成功"，用于确认操作完成
    """
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content.replace("\\n", "\n"))
    return "写入成功"

# 简答地执行系统命令
def run_terminal_command(command: str, level: str = "dangerous") -> Dict[str, Any]:

    """
    执行系统终端命令并返回详细的执行结果，如果指令不危险，请添加 "safe" 级别

    Args:
        command (str): 要执行的终端命令字符串，支持各种系统命令和参数
        level (str): 命令的安全级别，默认为 "dangerous"，可选 "safe" 表示安全命令，高危指令执行前会提示用户确认

    Returns:
        dict: 包含执行结果的字典，根据执行状态返回不同格式
    """
    if level == "dangerous":
        confirm = input(f"警告：即将执行系统命令 '{command}'，请确认是否继续 (y/n): ").strip().lower()
        if confirm != "y":
            return {"status": "aborted", "message": "用户取消执行"}

    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True,encoding='utf-8',errors='replace',)
        return {"status": "success", "output": result.stdout}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "returncode": e.returncode, "error": e.stderr}
    except Exception as e:
        return {"status": "exception", "error": str(e)}