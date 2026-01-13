#!/usr/bin/env python3
"""
agentype - AnnData 聚类→细胞类型映射工具
Author: cuilei
Version: 1.0
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Iterable, Optional, Union

# 导入统一配置系统
from agentype.config import get_session_id_for_filename


def _parse_mapping(mapping: Union[str, Dict[str, str]]) -> Dict[str, str]:
    """解析映射输入：
    - 若为字典，直接返回
    - 若为字符串：若是现有文件路径则读取 JSON 文件，否则当作 JSON 字符串解析
    返回: dict[str,str]
    """
    if isinstance(mapping, dict):
        return {str(k): str(v) for k, v in mapping.items()}
    if isinstance(mapping, str):
        p = Path(mapping)
        if p.exists():
            with p.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return {str(k): str(v) for k, v in data.items()}
        # 作为 JSON 字符串解析
        data = json.loads(mapping)
        if not isinstance(data, dict):
            raise ValueError("映射 JSON 必须为对象 (e.g. {\"cluster0\":\"Fibroblast\"})")
        return {str(k): str(v) for k, v in data.items()}
    raise TypeError("mapping 必须是 dict 或 JSON 字符串/文件路径")


def _strip_prefix(key: str) -> str:
    import re
    return re.sub(r"^\s*(?i:cluster[_ ]?)", "", str(key))


def _default_output_h5ad_path(input_path: str) -> Path:
    """生成默认输出路径，类似 mapping_tools.py 的 _default_output_path"""
    # 使用统一配置系统
    from agentype.mainagent.services import mcp_server
    output_dir = mcp_server._CONFIG.get_results_dir()
    session_id = get_session_id_for_filename()
    return output_dir / f"adata_with_celltype_{session_id}.h5ad"


def apply_cluster_mapping_to_adata(
    adata,
    mapping: Union[str, Dict[str, str]],
    *,
    cluster_columns: Iterable[str] = ("seurat_clusters", "leiden", "louvain"),
    output_col: str = "agentype",
) -> Dict:
    """将 cluster→celltype 映射写入 AnnData.obs。

    Args:
      adata: AnnData 对象
      mapping: dict 或 JSON（字符串/文件路径），键可为 "cluster0" 或 "0" 形式
      cluster_columns: 优先使用的聚类列顺序
      output_col: 输出到 obs 的列名

    Returns:
      一个总结字典，包含 used_column、unmapped_clusters 等
    """
    try:
        import pandas as pd  # noqa: F401
        import numpy as np  # noqa: F401
    except Exception as e:
        raise RuntimeError(f"需要 pandas/numpy 依赖: {e}")

    # 选择聚类列
    chosen_col: Optional[str] = None
    for c in cluster_columns:
        if c in adata.obs.columns:
            chosen_col = c
            break
    if chosen_col is None:
        raise ValueError(
            f"未在 adata.obs 中找到任何聚类列: {list(cluster_columns)}"
        )

    # 解析映射
    mapping_dict = _parse_mapping(mapping)

    # 建立两套映射：
    # 1) 优先使用带前缀的键 cluster{n}
    # 2) 兜底：去前缀后的纯数字键 {n}
    mapping_prefixed = {str(k): v for k, v in mapping_dict.items()}
    mapping_plain = {_strip_prefix(k): v for k, v in mapping_dict.items()}

    # 取聚类列并标准化为纯字符（数字转 int 再转字符串）
    s = adata.obs[chosen_col]
    if hasattr(s, "cat"):
        s = s.astype(str)
    else:
        # 转为字符串，但若为数值则取其整数表现
        try:
            s_num = s.astype(int)
            s = s_num.astype(str)
        except Exception:
            s = s.astype(str)

    # 先按 cluster{val} 匹配，再按 {val} 匹配
    # 使用逐元素映射以保持优先级
    def _map_val(v: str):
        v = str(v)
        m = mapping_prefixed.get(f"cluster{v}")
        if m is not None:
            return m
        return mapping_plain.get(v)

    mapped = s.map(_map_val)

    # 写入 obs
    adata.obs[output_col] = mapped

    # 统计
    unmapped_mask = mapped.isna()
    unmapped_clusters = sorted(set(s[unmapped_mask].tolist())) if unmapped_mask.any() else []

    return {
        "success": True,
        "used_column": chosen_col,
        "output_col": output_col,
        "total_cells": int(adata.n_obs),
        "mapped_cells": int((~unmapped_mask).sum()),
        "unmapped_cells": int(unmapped_mask.sum()),
        "unmapped_clusters": unmapped_clusters,
        "mapping_keys": list(mapping_dict.keys()),
    }


def map_cluster_types_to_adata(
    h5ad_path: str,
    mapping_json_or_path: Union[str, Dict[str, str]],
    cluster_col: str = "seurat_clusters",
    output_col: str = "celltype",
    output_h5ad: Optional[str] = None,
) -> Dict[str, Any]:
    """
    将 cluster→celltype 映射写入 AnnData 对象并保存新的 H5AD 文件。

    Args:
        h5ad_path: 输入 AnnData 对象路径（支持 .h5ad 和 .h5 格式）
        mapping_json_or_path: JSON 文件路径、JSON 字符串，或字典对象（形如 {"cluster0":"Fibroblast"}）
        cluster_col: 需要映射的 obs 列名（默认 "seurat_clusters"，智能回退到 leiden/louvain）
        output_col: 写入的新列名（默认 "celltype"）
        output_h5ad: 输出 H5AD 路径；默认写入当前目录 .agentype_cache/ 下带时间戳文件

    Returns:
        字典，包含 success、output_h5ad、used_column 等信息

    Raises:
        FileNotFoundError: AnnData 输入文件不存在
        RuntimeError: 加载或处理失败
    """
    try:
        import scanpy as sc  # type: ignore
    except Exception as e:
        raise RuntimeError(f"需要 scanpy 依赖: {e}")

    h5ad_path_obj = Path(h5ad_path)
    if not h5ad_path_obj.exists():
        raise FileNotFoundError(f"AnnData 输入文件不存在: {h5ad_path}")

    # 输出路径
    out_h5ad = Path(output_h5ad) if output_h5ad else _default_output_h5ad_path(h5ad_path)
    out_h5ad.parent.mkdir(parents=True, exist_ok=True)

    # 检测文件格式并读取 AnnData（参考 celltypist_simple.py）
    file_ext = os.path.splitext(h5ad_path)[1].lower()
    if file_ext not in ['.h5ad', '.h5']:
        raise ValueError(f"不支持的文件格式: {file_ext}，仅支持 .h5ad 和 .h5 格式")

    is_h5_format = file_ext == '.h5'

    if is_h5_format:
        # 使用easySCFpy读取H5文件
        try:
            from easySCFpy import loadH5  # type: ignore
            print(f"使用easySCFpy读取H5格式数据: {h5ad_path}")
            adata = loadH5(h5ad_path)
        except ImportError:
            print(f"easySCFpy不可用，尝试使用scanpy读取H5文件: {h5ad_path}")
            adata = sc.read_10x_h5(h5ad_path)
            adata.var_names_unique()
    else:
        # 读取H5AD文件
        print(f"读取H5AD文件: {h5ad_path}")
        adata = sc.read_h5ad(h5ad_path)

    # 智能选择聚类列：优先级 用户指定 -> seurat_clusters -> leiden -> louvain
    cluster_candidates = [cluster_col, "seurat_clusters", "leiden", "louvain"]
    chosen_col: Optional[str] = None

    for col in cluster_candidates:
        if col in adata.obs.columns:
            chosen_col = col
            break

    if chosen_col is None:
        available_cols = [col for col in cluster_candidates if col in adata.obs.columns]
        raise ValueError(
            f"未在 adata.obs 中找到任何可用的聚类列。\n"
            f"尝试的列: {cluster_candidates}\n"
            f"可用的列: {list(adata.obs.columns)}"
        )

    # 应用映射
    summary = apply_cluster_mapping_to_adata(
        adata,
        mapping_json_or_path,
        cluster_columns=(chosen_col,),  # 只使用选中的列
        output_col=output_col,
    )

    # 保存文件
    adata.write(out_h5ad)

    # 添加输出文件信息
    summary.update({
        "output_h5ad": str(out_h5ad),
        "input_h5ad": str(h5ad_path),
    })

    return summary


__all__ = ["apply_cluster_mapping_to_adata", "map_cluster_types_to_adata"]

