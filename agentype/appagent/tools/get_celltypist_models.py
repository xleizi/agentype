#!/usr/bin/env python3
"""
agentype - CellTypist 模型获取工具
Author: cuilei
Version: 1.0
"""

import json
import sys
from typing import List, Dict


def get_celltypist_models() -> List[Dict[str, str]]:
    """
    获取CellTypist所有可用模型
    
    Returns:
        包含模型名称和描述的字典列表
    """
    
    try:
        from celltypist import models
        
        # 获取模型信息
        all_models_df = models.models_description()
        
        models_list = []
        for model_idx in all_models_df.index:
            model_row = all_models_df.loc[model_idx]
            models_list.append({
                "model_name": str(model_row['model']),
                "description": str(model_row['description'])
            })
        
        return models_list
        
    except ImportError:
        print("CellTypist未安装，请运行: pip install celltypist", file=sys.stderr)
        return []
    except Exception as e:
        print(f"获取模型信息失败: {e}", file=sys.stderr)
        return []


if __name__ == "__main__":
    models = get_celltypist_models()
    print(json.dumps(models, indent=2, ensure_ascii=False))