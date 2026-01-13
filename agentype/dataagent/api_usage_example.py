#!/usr/bin/env python3
"""
agentype - 单细胞数据处理API使用示例
Author: cuilei
Version: 1.0
"""

import requests
import json
from pathlib import Path

# API配置
API_BASE_URL = "http://localhost:8000/api/v1"

def test_health_check():
    """测试健康检查接口"""
    print("🔍 测试健康检查接口...")
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        response.raise_for_status()
        result = response.json()
        print(f"✅ 服务状态: {result['status']}, 版本: {result.get('version', 'N/A')}")
        return True
    except Exception as e:
        print(f"❌ 健康检查失败: {str(e)}")
        return False

def process_data_file(file_path, output_dir=None, timeout=300):
    """
    处理数据文件
    
    Args:
        file_path (str): 数据文件路径
        output_dir (str, optional): 输出目录
        timeout (int): HTTP请求超时时间（秒）
    
    Returns:
        dict: 处理结果
    """
    print(f"🔄 开始处理数据文件: {file_path}")
    
    # 请求数据
    request_data = {
        "input_data": file_path,
        "config": {
            "output_dir": output_dir or "./.agentype_cache"
        }
    }
    
    try:
        print(f"⏳ 正在处理，请耐心等待（最多{timeout}秒）...")
        response = requests.post(
            f"{API_BASE_URL}/process",
            json=request_data,
            timeout=timeout,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        result = response.json()
        
        if result.get("success"):
            print(f"✅ 处理成功!")
            print(f"📊 处理场景: {result.get('scenario_name', 'N/A')}")
            if result.get('output_files'):
                print("📁 输出文件:")
                for file_type, file_path in result.get('output_files', {}).items():
                    print(f"  {file_type}: {file_path}")
            if result.get('statistics'):
                print(f"📈 统计信息: {result.get('statistics')}")
        else:
            print(f"❌ 处理失败: {result.get('error', '未知错误')}")
            
        return result
        
    except requests.exceptions.Timeout:
        print("⏰ 请求超时，处理可能仍在进行中，请查看输出目录")
        return None
    except Exception as e:
        print(f"❌ 处理请求失败: {str(e)}")
        return None

def get_processing_status():
    """获取处理状态信息"""
    print("📊 获取处理状态...")
    try:
        response = requests.get(f"{API_BASE_URL}/status")
        response.raise_for_status()
        result = response.json()
        print(f"🤖 Agent状态: {result}")
        return result
    except Exception as e:
        print(f"❌ 获取状态失败: {str(e)}")
        return None

def list_supported_formats():
    """列出支持的数据格式"""
    print("📋 获取支持的数据格式...")
    try:
        response = requests.get(f"{API_BASE_URL}/formats")
        response.raise_for_status()
        result = response.json()
        print("🔧 支持的数据格式:")
        for fmt in result.get('formats', []):
            print(f"  - {fmt}")
        return result
    except Exception as e:
        print(f"❌ 获取格式列表失败: {str(e)}")
        return None

def main():
    """主函数"""
    print("=" * 60)
    print("🧬 单细胞数据处理API使用示例")
    print("=" * 60)
    
    # 1. 健康检查
    if not test_health_check():
        print("❌ 服务不可用，请先启动API服务:")
        print("   python celltypeDataAgent/run.py --mode api")
        return
    
    print()
    
    # 2. 获取系统状态
    get_processing_status()
    print()
    
    # 3. 列出支持格式
    list_supported_formats()
    print()
    
    # 4. 处理测试文件
    test_files = [
        "../utils/sce.rds",      # RDS文件
        "../utils/data.h5ad",    # AnnData文件  
        "../utils/data.h5",      # H5文件
    ]
    
    for test_file in test_files:
        file_path = Path(test_file)
        if file_path.exists():
            print(f"🧪 测试处理文件: {test_file}")
            result = process_data_file(str(file_path), timeout=600)  # 10分钟超时
            print("-" * 50)
        else:
            print(f"⚠️ 测试文件不存在，跳过: {test_file}")
        print()
    
    print("=" * 60)
    print("🎉 API使用示例完成!")
    print("=" * 60)

if __name__ == "__main__":
    main()