#!/usr/bin/env python3
"""
agentype - SingleR 极简Python工具
Author: cuilei
Version: 1.0
"""

import subprocess
import json
import tempfile
import os
import sys
from pathlib import Path
from datetime import datetime

# 导入项目模块



def singleR_annotate(data_path, reference_path, output_path=None, cluster_column="seurat_clusters", max_cells_per_cluster=2000, random_seed=42):
    """
    使用SingleR进行细胞类型注释的核心函数

    参数:
        data_path: 数据文件路径（支持RDS或H5格式）
        reference_path: 参考数据库RDS文件路径
        output_path: 输出JSON文件路径，默认保存到统一输出目录
                    文件名格式: cellAgent_singleR_时间戳.json
        cluster_column: 聚类列名，默认"seurat_clusters"
        max_cells_per_cluster: 每个聚类最多保留的细胞数，默认2000（在注释前抽样以减少计算量）
        random_seed: 随机种子，用于抽样的可复现性，默认42

    返回:
        注释结果的字典
    """
    
    # 检查输入文件
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"数据文件不存在: {data_path}")
    if not os.path.exists(reference_path):
        raise FileNotFoundError(f"参考数据库文件不存在: {reference_path}")
    
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
        # 使用 session_id 生成输出文件名
        session_id = get_session_id_for_filename()
        # 使用统一的文件名前缀，便于下游识别
        output_filename = f"singleR_annotation_result_{session_id}.json"
        output_path = output_dir / output_filename
    
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
cat("H5数据读取完成\\n")
'''
    else:
        data_loading_code = f'''
# 读取RDS格式数据
cat("读取RDS格式数据...\\n")
sce <- readRDS("{data_path}")
cat("RDS数据读取完成\\n")
'''

    r_code = f'''
# 加载必要的包
suppressMessages({{
  if (!require("SingleR", quietly = TRUE)) {{
    if (!requireNamespace("BiocManager", quietly = TRUE)) {{
      install.packages("BiocManager")
    }}
    BiocManager::install("SingleR")
    library(SingleR)
  }}
  
  if (!require("Seurat", quietly = TRUE)) {{
    install.packages("Seurat")
    library(Seurat)
  }}
  
  if (!require("jsonlite", quietly = TRUE)) {{
    install.packages("jsonlite")
    library(jsonlite)
  }}
}})

{data_loading_code}

# 读取参考数据
ref_data <- readRDS("{reference_path}")

# 设置聚类标识
Idents(sce) <- "{cluster_column}"

# 按聚类抽样（在注释前减少计算量）
set.seed({random_seed})
original_cells <- ncol(sce)
cat("开始按簇抽样: 每个聚类最多", {max_cells_per_cluster}, "个细胞\\n")
sce <- subset(x = sce, downsample = {max_cells_per_cluster})
sampled_cells <- ncol(sce)
cat("抽样完成: 原始细胞数 =", original_cells, ", 抽样后细胞数 =", sampled_cells, "\\n")

# 释放抽样前的内存
gc(verbose = FALSE)
cat("已执行垃圾回收，释放抽样前的内存\\n")

# 更新抽样后的数据矩阵
if ("RNA" %in% names(sce@assays)) {{
  if("layers" %in% names(attributes(sce[["RNA"]]))){{
    if ("data" %in% names(sce@assays$RNA@layers)) {{
        test_data <- GetAssayData(sce, slot = "data", assay = "RNA")
      }} else {{
        test_data <- GetAssayData(sce, slot = "counts", assay = "RNA")
      }}
  }} else {{
    if("data" %in% names(attributes(sce[["RNA"]]))){{
      test_data <- GetAssayData(sce, slot = "data", assay = "RNA")
    }} else {{
      test_data <- GetAssayData(sce, slot = "counts", assay = "RNA")
    }}
  }}
}} else {{
  test_data <- GetAssayData(sce, slot = "data")
}}
cat("抽样后数据矩阵维度:", dim(test_data), "\\n")

# 执行SingleR注释
cat("开始SingleR注释...\\n")
pred <- SingleR(
  test = test_data,
  ref = ref_data,
  labels = ref_data$label.main,
  method = "classic"
)

cat("注释完成\\n")

# 添加结果到Seurat对象
sce@meta.data$singleR_celltype <- pred$labels
sce@meta.data$singleR_confidence <- apply(pred$scores, 1, max)

# 释放大型中间对象
rm(test_data)
gc(verbose = FALSE)
cat("已释放表达矩阵，节省内存\\n")

# 分析每个簇的细胞类型（已在抽样前设置Idents）
# 使用{cluster_column}获取簇信息
cluster_celltype_table <- table(pred$labels, Idents(sce))
cluster_annotations <- list()

for (cluster in levels(Idents(sce))) {{
  cluster_cells_idx <- which(Idents(sce) == cluster)
  cluster_cells <- cluster_celltype_table[, cluster]
  cluster_cells <- cluster_cells[cluster_cells > 0]
  
  if (length(cluster_cells) > 0) {{
    dominant_celltype <- names(cluster_cells)[which.max(cluster_cells)]
    max_count <- max(cluster_cells)
    total_count <- sum(cluster_cells)
    proportion <- max_count / total_count
    cluster_confidence <- mean(sce@meta.data$singleR_confidence[cluster_cells_idx])
    
    cluster_annotations[[paste0("cluster", as.character(cluster))]] <- list(
      celltype = dominant_celltype,
      confidence = round(cluster_confidence, 4),
      cell_count = max_count,
      total_cells = total_count,
      proportion = round(proportion, 4)
    )
  }}
}}

# 释放 pred 对象（包含大量评分数据）
rm(pred)
gc(verbose = FALSE)
cat("已释放 SingleR 预测对象\\n")

# 创建输出结果
result <- list(
  cluster_annotations = cluster_annotations,
  total_clusters = length(levels(Idents(sce))),
  annotation_date = Sys.Date(),
  input_file = "{data_path}",
  reference_file = "{reference_path}"
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
            error_msg = f"R脚本执行失败:\\n{result.stderr}"
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
            "method": "SingleR",
            "output_file": str(output_path),
            "input_file": data_path,
            "reference_file": reference_path,
            "total_clusters": annotation_result.get('total_clusters'),
        }

    except Exception as e:
        raise RuntimeError(f"执行失败: {e}")
