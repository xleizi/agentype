#!/usr/bin/env python3
"""
agentype - 映射写回工具
Author: cuilei
Version: 1.0
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
import subprocess
from datetime import datetime
import tempfile
from typing import Dict, Any, Optional, Union

# 导入项目模块

# 导入统一配置系统
from agentype.config import get_session_id_for_filename


def _default_output_path() -> Path:
    """生成默认输出路径。"""
    # 使用统一配置系统
    from agentype.mainagent.services import mcp_server
    output_dir = mcp_server._CONFIG.get_results_dir()
    session_id = get_session_id_for_filename()
    return output_dir / f"seurat_with_celltype_{session_id}.rds"


def map_cluster_types(
    seurat_path: str,
    mapping_json_or_path: Union[str, Dict[str, str]],
    cluster_col: str = "seurat_clusters",
    output_col: str = "agentype",
    output_rds: Optional[str] = None,
) -> Dict[str, Any]:
    """
    调用 R 在 Seurat 对象中写入 cluster→celltype 映射，并保存更新后的 RDS。

    Args:
        seurat_path: 输入 Seurat 对象路径（.rds 或 .h5）
        mapping_json_or_path: JSON 文件路径、JSON 字符串，或字典对象（形如 {"cluster0":"Fibroblast"}）
        cluster_col: 需要映射的 meta.data 列名（默认 "seurat_cluster"）
        output_col: 写入的新列名（默认 "celltype"）
        output_rds: 输出 RDS 路径；默认写入统一输出目录下带时间戳文件

    Returns:
        字典，包含 success、output_rds、unmapped_clusters 等信息

    Raises:
        FileNotFoundError: Seurat 输入文件不存在
        RuntimeError: R 脚本执行失败或超时
    """
    sp = Path(seurat_path)
    if not sp.exists():
        raise FileNotFoundError(f"Seurat 输入文件不存在: {seurat_path}")

    # 处理映射数据：支持字典、JSON字符串或文件路径
    if isinstance(mapping_json_or_path, dict):
        # 如果传入的是字典，转换为JSON字符串
        mapping_json_str = json.dumps(mapping_json_or_path, ensure_ascii=False)
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        with tmp as f:
            f.write(mapping_json_str)
        mapping_path = Path(tmp.name)
    elif os.path.exists(mapping_json_or_path):
        # 如果是文件路径
        mapping_path = Path(mapping_json_or_path)
    else:
        # 如果是JSON字符串
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        with tmp as f:
            f.write(mapping_json_or_path)
        mapping_path = Path(tmp.name)

    # 输出路径
    out_rds = Path(output_rds) if output_rds else _default_output_path()
    out_rds.parent.mkdir(parents=True, exist_ok=True)

    # R 侧的简要汇总 JSON（便于跨语言通信）
    summary_json = out_rds.with_suffix(".map_summary.json")

    # 构建 R 代码（使用f-string风格，参考singleR_simple.py）
    r_code = f'''
options(warn=1)
suppressMessages({{
  if (!require("Seurat", quietly = TRUE)) {{
    install.packages("Seurat"); library(Seurat)
  }}
  if (!require("jsonlite", quietly = TRUE)) {{
    install.packages("jsonlite"); library(jsonlite)
  }}
}})

data_path <- {json.dumps(str(sp))}
mapping_path <- {json.dumps(str(mapping_path))}
cluster_col <- {json.dumps(cluster_col)}
output_col <- {json.dumps(output_col)}
out_rds <- {json.dumps(str(out_rds))}
summary_path <- {json.dumps(str(summary_json))}

# 读取对象（支持 .h5 通过 easySCFr::loadH5）
load_seurat <- function(p) {{
  file_ext <- tools::file_ext(p)
  if (tolower(file_ext) == "h5") {{
    if (!require("easySCFr", quietly = TRUE)) {{
      if (!requireNamespace("devtools", quietly = TRUE)) install.packages("devtools")
      devtools::install_github("xleizi/easySCF/r")
      library(easySCFr)
    }}
    sce <- loadH5(p)
    return(sce)
  }} else {{
    return(readRDS(p))
  }}
}}

result <- list(success = FALSE)
tryCatch({{
  sce <- load_seurat(data_path)
  md <- sce@meta.data
  if (is.null(md) || !is.data.frame(md)) stop("seurat@meta.data 不可用")
  if (!(cluster_col %in% colnames(md))) {{
    stop(sprintf("列 '%s' 不存在于 seurat@meta.data", cluster_col))
  }}

  mapping <- jsonlite::fromJSON(mapping_path)
  mapping <- unlist(mapping, use.names = TRUE)
  if (is.null(names(mapping)) || any(is.na(names(mapping)))) {{
    stop("JSON 需为具名对象, 例如 {{'cluster0':'Fibroblast'}}")
  }}

  cluster_vals <- md[[cluster_col]]
  if (is.numeric(cluster_vals)) {{
    cluster_chr <- as.character(as.integer(cluster_vals))
  }} else if (is.factor(cluster_vals)) {{
    cluster_chr <- as.character(cluster_vals)
  }} else {{
    cluster_chr <- as.character(cluster_vals)
  }}

  keys_prefixed <- paste0("cluster", cluster_chr)
  labels <- unname(mapping[keys_prefixed])

  # 兜底：去掉前缀再次匹配
  strip_prefix <- function(x) gsub("^cluster", "", x, ignore.case = TRUE)
  mapping_stripped <- mapping
  names(mapping_stripped) <- strip_prefix(names(mapping))
  labels2 <- unname(mapping_stripped[cluster_chr])
  need_fill <- is.na(labels) & !is.na(labels2)
  labels[need_fill] <- labels2[need_fill]

  sce[[output_col]] <- labels

  # 未匹配簇
  unmapped <- unique(cluster_chr[is.na(labels)])
  # 保存
  saveRDS(sce, out_rds)

  result <- list(
    success = TRUE,
    input_file = data_path,
    output_rds = out_rds,
    cluster_col = cluster_col,
    output_col = output_col,
    total_rows = nrow(md),
    unmapped_clusters = if (length(unmapped) == 0) list() else as.list(unmapped),
    mapping_keys = as.list(names(mapping))
  )
}}, error = function(e) {{
  result <<- list(success = FALSE, error = as.character(e))
}})

jsonlite::write_json(result, summary_path, auto_unbox = TRUE, pretty = TRUE)
cat("结果已保存到:", out_rds, "\\n")
cat("汇总写入:", summary_path, "\\n")
'''

    try:
        proc = subprocess.run(
            ["Rscript", "-e", r_code],
            capture_output=True,
            text=True
        )
        if proc.returncode != 0:
            raise RuntimeError(f"R 脚本执行失败:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
        if not summary_json.exists():
            raise RuntimeError("未生成汇总 JSON，总结信息缺失")
        with summary_json.open("r", encoding="utf-8") as f:
            summary = json.load(f)
        # 附带 R 标准输出，便于排查
        summary["r_stdout"] = proc.stdout
        summary["r_stderr"] = proc.stderr
        return summary
    finally:
        # 若 mapping 是临时文件，尝试清理
        if isinstance(mapping_json_or_path, dict) or not os.path.exists(str(mapping_json_or_path)):
            try:
                mapping_path.unlink(missing_ok=True)  # type: ignore[attr-defined]
            except Exception:
                pass