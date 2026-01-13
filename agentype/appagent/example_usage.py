#!/usr/bin/env python3
"""
agentype - App Agent 使用示例
Author: cuilei
Version: 1.0
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
current_dir = Path(__file__).parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

from agentype.appagent import CelltypeAnnotationAgent, MCPClient

async def example_direct_agent_usage():
    """直接使用Agent的示例"""
    print("=== 直接使用CelltypeAnnotationAgent ===")
    
    # 创建代理实例
    agent = CelltypeAnnotationAgent()
    
    # 测试组织类型分析
    test_tissues = [
        "免疫系统", 
        "大脑组织", 
        "小鼠脑部",
        "肺部细胞",
        None
    ]
    
    print("\n组织类型智能分析测试:")
    for tissue in test_tissues:
        config = agent.analyze_tissue_type(tissue)
        print(f"输入: {tissue} -> 配置: {config}")
    
    # 如果有数据文件，可以运行完整流水线
    rds_path = "/root/code/gitpackage/agentype/utils/sce.rds"
    h5ad_path = "/root/code/gitpackage/agentype/utils/data.h5ad"
    
    if Path(rds_path).exists() and Path(h5ad_path).exists():
        print(f"\n运行完整注释流水线:")
        print(f"RDS文件: {rds_path}")
        print(f"H5AD文件: {h5ad_path}")
        
        try:
            result = agent.run_full_annotation_pipeline(
                rds_path=rds_path,
                h5ad_path=h5ad_path,
                tissue_description="免疫系统细胞"
            )
            
            print("流水线执行完成!")
            print(f"成功率: {result['pipeline_info']['summary']['success_rate']}")
            
            # 显示每个方法的结果摘要
            for method, result_data in result["results"].items():
                status = result_data.get("status", "unknown")
                print(f"- {method}: {status}")
                if status == "success":
                    annotations = result_data.get("annotations", {})
                    print(f"  注释了 {len(annotations)} 个簇")
                elif status == "error":
                    error = result_data.get("error", "未知错误")
                    print(f"  错误: {error}")
        
        except Exception as e:
            print(f"流水线执行失败: {e}")
    else:
        print("\n未找到测试数据文件，跳过完整流水线测试")
        print(f"需要文件: {rds_path}, {h5ad_path}")

async def example_mcp_client_usage():
    """使用MCP客户端的示例"""
    print("\n\n=== 使用MCP客户端接口 ===")
    
    # 创建MCP客户端
    client = MCPClient()
    
    try:
        # 启动MCP服务器
        print("启动MCP服务器...")
        success = await client.start_server()
        
        if not success:
            print("❌ MCP服务器启动失败")
            return
        
        # 列出可用工具
        print("\n获取可用工具列表...")
        tools = await client.list_tools()
        print(f"可用工具数量: {len(tools)}")
        for tool in tools[:5]:  # 只显示前5个工具
            print(f"- {tool.get('name', 'unknown')}: {tool.get('description', 'no description')[:50]}...")
        
        # 测试获取celldex数据集信息
        print("\n测试获取celldex数据集信息...")
        result = await client.get_celldex_projects_info("zh")
        if result.get("success"):
            print("✅ celldex数据集信息获取成功")
        else:
            print(f"❌ 获取失败: {result.get('error')}")
        
        # 测试获取scType组织类型
        print("\n测试获取scType组织类型...")
        result = await client.get_sctype_tissues()
        if result.get("success"):
            print("✅ scType组织类型获取成功")
        else:
            print(f"❌ 获取失败: {result.get('error')}")
        
        # 测试获取CellTypist模型
        print("\n测试获取CellTypist模型...")
        result = await client.get_celltypist_models()
        if result.get("success"):
            print("✅ CellTypist模型信息获取成功")
        else:
            print(f"❌ 获取失败: {result.get('error')}")
        
    except Exception as e:
        print(f"MCP客户端测试失败: {e}")
    
    finally:
        # 停止服务器
        print("\n停止MCP服务器...")
        await client.stop_server()

def example_configuration():
    """配置管理示例"""
    print("\n\n=== 配置管理示例 ===")
    
    from agentype.appagent import get_cache_info, clear_cache
    
    # 获取缓存信息
    cache_info = get_cache_info()
    print("缓存信息:")
    print(f"- 缓存目录: {cache_info['cache_dir']}")
    print(f"- 目录大小: {cache_info['size_mb']} MB")
    print(f"- 子目录数量: {len(cache_info['subdirs'])}")
    
    # 清理临时缓存
    print("\n清理临时缓存...")
    result = clear_cache("temp")
    if result["cleared"]:
        print(f"✅ 清理成功，释放了 {result['freed_mb']} MB 空间")
    else:
        print(f"❌ 清理失败: {result['message']}")

async def main():
    """主函数"""
    print("CellType App Agent 使用示例")
    print("=" * 50)
    
    # 1. 直接使用Agent
    await example_direct_agent_usage()
    
    # 2. 使用MCP客户端
    await example_mcp_client_usage()
    
    # 3. 配置管理
    example_configuration()
    
    print("\n示例运行完成！")

if __name__ == "__main__":
    asyncio.run(main())