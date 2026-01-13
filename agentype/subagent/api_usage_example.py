#!/usr/bin/env python3
"""
agentype - 细胞类型分析API使用示例
Author: cuilei
Version: 1.0
"""

import requests
from agentype.subagent.utils.file_utils import load_gene_list_from_file

# API配置
API_BASE_URL = "http://localhost:8585/api/v1"

def test_health_check():
    """测试健康检查接口"""
    print("🔍 测试健康检查接口...")
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        response.raise_for_status()
        result = response.json()
        print(f"✅ 服务状态: {result['status']}, 版本: {result['version']}")
        return True
    except Exception as e:
        print(f"❌ 健康检查失败: {str(e)}")
        return False

def analyze_celltype(gene_list, tissue_type=None, cell_type=None,
                     openai_api_base="https://api.openai.com/v1", 
                     openai_api_key="", 
                     openai_model="gpt-4o", 
                     max_iterations=20,
                     max_retries_per_call=5,
                     timeout=None):
    """
    分析细胞类型
    
    Args:
        gene_list (str): 逗号分隔的基因列表
        tissue_type (str, optional): 组织类型，如'骨髓'、'血液'、'肌肉'等
        cell_type (str, optional): 细胞类型提示，用于优先判断细胞亚群
        timeout (int or None): HTTP请求超时时间（秒），None表示无超时限制
    
    Returns:
        dict: 分析结果
    """
    print(f"🧬 开始分析基因列表: {gene_list}")
    if tissue_type:
        print(f"🏥 组织类型: {tissue_type}")
    if cell_type:
        print(f"🧫 细胞类型提示: {cell_type}")
    
    # 请求数据
    request_data = {
        "gene_list": gene_list,
        "openai_api_base": openai_api_base,
        "openai_api_key": openai_api_key,
        "openai_model": openai_model,
        "tissue_type": tissue_type,
        "cell_type": cell_type,
        "max_iterations": max_iterations,
        "max_retries_per_call": max_retries_per_call
    }
    
    try:
        if timeout:
            print(f"⏳ 正在分析，请耐心等待（最多{timeout}秒）...")
        else:
            print("⏳ 正在分析，请耐心等待（无超时限制）...")
        response = requests.post(
            f"{API_BASE_URL}/analyze",
            json=request_data,
            timeout=timeout,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        result = response.json()
        
        if result["success"]:
            print(f"✅ 分析成功!")
            print(f"📊 推断的细胞类型: {result['cell_type']}")
            print(f"🔄 总迭代次数: {result['total_iterations']}")
            print(f"📝 分析日志条目数: {len(result['analysis_log'])}")
            if result.get('log_file_path'):
                print(f"📄 详细日志文件: {result['log_file_path']}")
            if result.get('final_llm_output'):
                print(f"🤖 最终LLM输出: {result['final_llm_output'][:200]}...")
        else:
            print(f"❌ 分析失败: {result.get('error_message', '未知错误')}")
            
        return result
        
    except requests.exceptions.Timeout:
        print("⏰ 请求超时，分析可能仍在进行中，请查看日志文件")
        return None
    except Exception as e:
        print(f"❌ 分析请求失败: {str(e)}")
        return None
    
def main():
    """主函数"""
    print("=" * 60)
    print("🧬 细胞类型分析API使用示例")
    print("=" * 60)
    
    # 1. 健康检查
    if not test_health_check():
        print("❌ 服务不可用，请检查API服务是否正常运行")
        return
    
    print()
    
    genes_file = "../genes.txt"
    gene_list = load_gene_list_from_file(str(genes_file), max_genes=30)
    
    analyze_celltype(gene_list, tissue_type="骨髓", timeout=None,
                     openai_api_base="https://api.siliconflow.cn/v1",
                     openai_api_key="sk-paypkckrtunjtcmrfagtmpqotnjrhcrhsmtpnsmwquxxvokd",
                     openai_model="Pro/deepseek-ai/DeepSeek-V3",
                     max_iterations=20,
                     max_retries_per_call=5
                     )
    
    print("\n" + "=" * 60)
    print("🎉 分析完成!")
    print("=" * 60)

if __name__ == "__main__":
    main()
