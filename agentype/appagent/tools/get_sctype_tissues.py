#!/usr/bin/env python3
"""
agentype - Get Sctype Tissues模块
Author: cuilei
Version: 1.0
"""

import pandas as pd
from typing import List


def get_sctype_tissues() -> List[str]:
    """
    从ScTypeDB Excel文件中提取所有唯一的组织类型
    优先使用GitHub原始地址，失败时使用备用地址
    
    Returns:
        包含所有组织类型的列表
    """
    # 主要地址和备用地址
    primary_url = "https://raw.githubusercontent.com/IanevskiAleksandr/sc-type/master/ScTypeDB_full.xlsx"
    backup_url = "https://agent.s1f.ren/d/files/rds/sctype/R/ScTypeDB_full.xlsx"
    
    # 尝试主要地址
    try:
        print(f"正在尝试从GitHub地址下载: {primary_url}")
        db_read = pd.read_excel(primary_url, engine='openpyxl')
        
        # 获取所有唯一的组织类型
        tissues = db_read['tissueType'].unique().tolist()
        print("成功从GitHub地址获取数据")
        
        return tissues
    
    except Exception as e:
        print(f"GitHub地址访问失败: {e}")
        
        # 尝试备用地址
        try:
            print(f"正在尝试备用地址: {backup_url}")
            db_read = pd.read_excel(backup_url, engine='openpyxl')
            
            # 获取所有唯一的组织类型
            tissues = db_read['tissueType'].unique().tolist()
            print("成功从备用地址获取数据")
            
            return tissues
        
        except Exception as backup_e:
            print(f"备用地址也访问失败: {backup_e}")
            return []


if __name__ == "__main__":
    # 测试函数
    tissues = get_sctype_tissues()
    print("ScTypeDB中的所有组织类型:")
    print(tissues)