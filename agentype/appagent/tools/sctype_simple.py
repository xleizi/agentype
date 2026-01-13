#!/usr/bin/env python3
"""
agentype - scType 极简Python工具
Author: cuilei
Version: 1.0
"""

import subprocess
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# 导入项目模块



def get_sctype_wrapper_path():
    """
    获取打包在Python包内的scType wrapper路径

    Returns:
        str: sctype_wrapper.R 文件的绝对路径
    """
    # 获取当前模块所在目录
    current_file = Path(__file__).resolve()
    # sctype资源文件应该在 tools/r/sctype/ 目录下
    sctype_dir = current_file.parent / "r" / "sctype"
    wrapper_path = sctype_dir / "sctype_wrapper.R"

    if not wrapper_path.exists():
        raise FileNotFoundError(
            f"scType wrapper file not found at: {wrapper_path}\n"
            f"Please ensure the package is properly installed with R resource files."
        )

    return str(wrapper_path)


def sctype_annotate(data_path, tissue_type="Immune system", output_path=None, cluster_column="seurat_clusters", max_cells_per_cluster=2000, random_seed=42):
    """
    使用scType进行细胞类型注释的核心函数

    参数:
        data_path: 数据文件路径（支持RDS或H5格式）
        tissue_type: 组织类型，默认"Immune system"
        output_path: 输出JSON文件路径，默认保存到统一输出目录
                    文件名格式: cellAgent_sctype_时间戳.json
        cluster_column: 聚类列名，默认"seurat_clusters"
        max_cells_per_cluster: 每个聚类最多保留的细胞数，默认2000。
                              如果聚类细胞数少于此值，保留全部细胞
        random_seed: 随机种子，用于抽样的可复现性，默认42

    返回:
        注释结果的字典，包含每个簇对应的细胞类型
    """
    
    # 检查输入文件
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"数据文件不存在: {data_path}")
    
    # 检测文件格式
    file_ext = os.path.splitext(data_path)[1].lower()
    if file_ext not in ['.rds', '.h5']:
        raise ValueError(f"不支持的文件格式: {file_ext}，仅支持 .rds 和 .h5 格式")
    
    is_h5_format = file_ext == '.h5'
    
    # 设置输出文件
    if output_path is None:
        # 使用统一配置系统
        from agentype.config import get_session_id_for_filename
        from agentype.appagent.services import mcp_server
        output_dir = mcp_server._CONFIG.get_results_dir()
        # 使用 session_id 生成输出文件名（统一前缀）
        session_id = get_session_id_for_filename()
        output_filename = f"sctype_annotation_result_{session_id}.json"
        output_path = output_dir / output_filename

    # 获取本地scType wrapper路径
    sctype_wrapper_path = get_sctype_wrapper_path()

    # 根据文件格式生成不同的R脚本
    if is_h5_format:
        data_loading_code = f'''
# 读取H5格式数据
cat("读取H5格式数据...\\n")
if (!require("easySCFr", quietly = TRUE)) {{
  if (!requireNamespace("devtools", quietly = TRUE)) install.packages("devtools")
  devtools::install_github("xleizi/easySCF/r")
  library(easySCFr)
}}
sce <- loadH5("{data_path}")
cat("H5数据读取并转换完成\\n")
'''
    else:
        data_loading_code = f'''
# 读取RDS格式数据
cat("读取RDS格式数据...\\n")
sce <- readRDS("{data_path}")
cat("RDS数据读取完成\\n")
'''

    # R代码字符串 - 基于原始R代码转换
    r_code = f'''
# 加载必要的包
suppressMessages({{
  if (!require("dplyr", quietly = TRUE)) install.packages("dplyr")
  if (!require("Seurat", quietly = TRUE)) install.packages("Seurat")
  if (!require("jsonlite", quietly = TRUE)) install.packages("jsonlite")
  if (!require("HGNChelper", quietly = TRUE)) install.packages("HGNChelper")
  
  library(dplyr)
  library(Seurat)
  library(jsonlite)
  library(HGNChelper)
}})

{data_loading_code}

cat("数据加载完成: 细胞数", ncol(sce), ", 基因数", nrow(sce), "\\n")

# 加载scType包装器 - 从打包的本地文件加载
sctype_loaded <- FALSE
cat("从本地包资源加载sctype_wrapper...\\n")
tryCatch({{
  source("{sctype_wrapper_path}")
  sctype_loaded <- TRUE
  cat("成功从本地加载sctype_wrapper\\n")
}}, error = function(e) {{
  cat("本地加载失败:", e$message, "\\n")
  stop("无法加载scType wrapper文件")
}})

# 设置聚类标识并进行抽样
Idents(sce) <- "{cluster_column}"
cat("设置聚类列:", "{cluster_column}", "\\n")

# 设置随机种子并按聚类抽样
set.seed({random_seed})
original_cells <- ncol(sce)
cat("开始抽样: 每个聚类最多", {max_cells_per_cluster}, "个细胞\\n")
sce <- subset(x = sce, downsample = {max_cells_per_cluster})
sampled_cells <- ncol(sce)
cat("抽样完成: 原始细胞数 =", original_cells, ", 抽样后细胞数 =", sampled_cells, "\\n")

# 释放抽样前的内存
gc(verbose = FALSE)
cat("已执行垃圾回收，释放抽样前的内存\\n")

# 获取scType资源文件目录（wrapper文件所在目录）
sctype_dir <- dirname("{sctype_wrapper_path}")
cat("scType资源目录:", sctype_dir, "\\n")

# 运行scType注释
cat("开始scType注释，组织类型:", "{tissue_type}", "\\n")
sce <- run_sctype(
  sce,
  known_tissue_type = "{tissue_type}",
  name = "sctype_celltype",
  scaled = FALSE,
  plot = FALSE,
  sctype_dir = sctype_dir
)

# scType 注释完成，执行垃圾回收
gc(verbose = FALSE)
cat("scType 注释完成，已清理中间数据\\n")

Idents(sce) <- "{cluster_column}"
# 使用{cluster_column}获取簇信息
cat("使用 Idents(sce) 获取簇信息\\n")
clusters <- levels(Idents(sce))
cat("检测到", length(clusters), "个簇:", paste(clusters, collapse = ", "), "\\n")

# 分析每个簇的细胞类型 - 使用sctype_celltype列
cluster_annotations <- list()

for (cluster in clusters) {{
  cluster_cells_idx <- which(Idents(sce) == cluster)
  
  if (length(cluster_cells_idx) > 0) {{
    # 获取该簇中的细胞类型分布
    cluster_celltypes <- sce@meta.data$sctype_celltype[cluster_cells_idx]
    celltype_table <- table(cluster_celltypes)
    
    # 找出最主要的细胞类型
    dominant_celltype <- names(celltype_table)[which.max(celltype_table)]
    max_count <- max(celltype_table)
    total_count <- length(cluster_cells_idx)
    proportion <- max_count / total_count
    
    # 计算置信度（如果有scType评分）
    if ("sctype_scores" %in% colnames(sce@meta.data)) {{
      cluster_confidence <- mean(sce@meta.data$sctype_scores[cluster_cells_idx], na.rm = TRUE)
    }} else {{
      cluster_confidence <- proportion  # 使用比例作为置信度的替代
    }}
    
    cluster_annotations[[paste0("cluster", as.character(cluster))]] <- list(
      celltype = dominant_celltype,
      confidence = round(cluster_confidence, 4),
      cell_count = max_count,
      total_cells = total_count,
      proportion = round(proportion, 4),
      all_celltypes = as.list(celltype_table)
    )
  }}
}}

# 结果提取完成，执行最终内存清理
gc(verbose = FALSE)
cat("结果提取完成，已执行最终内存清理\\n")

# 创建输出结果
result <- list(
  cluster_annotations = cluster_annotations,
  total_clusters = length(clusters),
  tissue_type = "{tissue_type}",
  annotation_date = as.character(Sys.Date()),
  input_file = "{data_path}",
  cluster_column = "{cluster_column}",
  total_cells = ncol(sce)
)

# 保存结果
write_json(result, "{output_path}", pretty = TRUE)
cat("结果已保存到: {output_path}\\n")
'''
    
    try:
        # 执行R代码
        result = subprocess.run(
            ['Rscript', '-e', r_code],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            error_msg = f"R脚本执行失败:\n{result.stderr}"
            raise RuntimeError(error_msg)
        
        # 读取结果
        with open(output_path, 'r', encoding='utf-8') as f:
            annotation_result = json.load(f)
        
        # 构建简洁的返回结果
        simple_result = {}
        for cluster_id, annotation in annotation_result['cluster_annotations'].items():
            simple_result[cluster_id] = {
                "celltype": annotation['celltype'],
                "proportion": annotation['proportion']
            }
        
        return {
            "success": True,
            "method": "scType",
            "output_file": str(output_path),
            "input_file": data_path,
            "tissue_type": tissue_type,
            "total_clusters": annotation_result.get('total_clusters'),
        }

    except Exception as e:
        raise RuntimeError(f"执行失败: {e}")


if __name__ == "__main__":
    # 测试函数
    try:
        result = sctype_annotate(
            # data_path="/root/code/gitpackage/agentype/utils/sce.rds",
            data_path="/root/code/gitpackage/agentype/utils/.agentype_cache/data_20250911_224809.h5",
            tissue_type="Immune system"
        )
        # 输出JSON格式结果
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"注释失败: {e}")
