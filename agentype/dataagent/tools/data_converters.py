#!/usr/bin/env python3
"""
agentype - 数据转换工具模块
Author: cuilei
Version: 1.0
"""

import json
import subprocess
import os
from anndata import AnnData
import pandas as pd
from typing import Dict, Any, Optional

# 导入项目模块

# 导入统一配置系统
from agentype.config import get_session_id_for_filename

def run_r_sce_to_h5(seurat_file: str, output_file: Optional[str] = None, config=None) -> Dict[str, Any]:
    """
    将Seurat RDS文件转换为easySCF H5格式

    参数:
    seurat_file: Seurat RDS文件路径
    output_file: 输出H5文件路径（可选，不指定则自动生成）

    返回:
    成功时返回包含转换信息的Dict，失败时抛出RuntimeError

    注意:
    输出文件会自动保存到配置的结果目录，使用 session_id 命名
    """
    # 如果未指定输出路径，则自动生成
    if output_file is None:
        session_id = get_session_id_for_filename()
        if config:
            results_dir = config.get_results_dir()
        else:
            # 降级：从mcp_server模块获取
            from agentype.dataagent.services import mcp_server
            results_dir = mcp_server._CONFIG.get_results_dir()
        h5_file = str(results_dir / f'sce_{session_id}.h5')
    else:
        h5_file = output_file
    
    try:
        subprocess.run(['R', '--version'], capture_output=True, check=True)
    except:
        error_msg = "错误：未找到R环境，请安装R语言环境"
        print(error_msg)
        raise RuntimeError(error_msg)

    # 转换为绝对路径
    seurat_file = os.path.abspath(seurat_file)
    if not os.path.exists(seurat_file):
        error_msg = f"错误：文件不存在: {seurat_file}"
        print(error_msg)
        raise RuntimeError(error_msg)
    
    # 如果指定了输出路径，确保输出目录存在
    h5_file = os.path.abspath(h5_file)
    output_dir = os.path.dirname(h5_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        print(f"✓ 创建输出目录: {output_dir}")
    
    # 使用绝对路径的R脚本
    r_script = f'''
    library(Seurat)
    library(easySCFr)
    
    # 设置详细输出
    cat("正在读取RDS文件:", "{seurat_file}", "\\n")
    sce <- readRDS("{seurat_file}")
    cat("RDS文件读取成功\\n")
    
    cat("正在保存为H5格式:", "{h5_file}", "\\n")
    saveH5(sce, "{h5_file}")
    cat("RDS文件已成功转换为H5格式:", "{h5_file}", "\\n")
    '''
    
    try:
        print(f"正在将 {seurat_file} 转换为H5格式...")
        print(f"输出文件: {h5_file}")
        
        result = subprocess.run(['R', '--slave', '--no-restore', '--no-save'], 
                              input=r_script, text=True, capture_output=True, encoding='utf-8')
        
        print("R执行完成，返回代码:", result.returncode)
        
        if result.stdout:
            print("R输出:")
            print(result.stdout)
        
        if result.stderr:
            print("R错误输出:")
            print(result.stderr)
            
        if result.returncode == 0:
            # 验证输出文件是否存在
            if os.path.exists(h5_file):
                file_size = os.path.getsize(h5_file)
                success_msg = f"✓ RDS转H5转换成功完成: {h5_file}"
                print(success_msg)

                # 返回统一Dict格式
                return {
                    "success": True,
                    "method": "run_r_sce_to_h5",
                    "input_file": seurat_file,
                    "output_file": h5_file,
                    "file_size": file_size,
                    "message": success_msg
                }
            else:
                error_msg = f"✗ R脚本执行成功但未找到输出文件: {h5_file}"
                print(error_msg)
                raise RuntimeError(error_msg)
        else:
            error_msg = f"✗ R脚本执行失败，返回代码: {result.returncode}, 错误信息: {result.stderr}"
            print(error_msg)
            raise RuntimeError(error_msg)

    except RuntimeError:
        # 直接重新抛出已格式化的 RuntimeError
        raise
    except Exception as e:
        error_msg = f"✗ 转换过程中发生异常: {e}"
        print(error_msg)
        raise RuntimeError(error_msg)

def run_r_findallmarkers(seurat_file: str, pval_threshold: float = 0.05, cluster_column: str = "seurat_clusters", output_file: Optional[str] = None, config=None) -> Optional[Dict]:
    """
    运行R语言FindAllMarkers分析并直接输出JSON格式

    参数:
    seurat_file: Seurat RDS文件路径
    pval_threshold: p值阈值
    cluster_column: 聚类列名，默认"seurat_clusters"
    output_file: 输出JSON文件路径（可选，不指定则自动生成）

    返回:
    成功时返回marker基因字典，失败时返回None

    注意:
    输出文件会自动保存到配置的结果目录，使用 session_id 命名
    """
    # 如果未指定输出路径，则自动生成
    if output_file is None:
        session_id = get_session_id_for_filename()
        if config:
            results_dir = config.get_results_dir()
        else:
            # 降级：从mcp_server模块获取
            from agentype.dataagent.services import mcp_server
            results_dir = mcp_server._CONFIG.get_results_dir()
        output_file = str(results_dir / f'cluster_markers_{session_id}.json')
    
    try:
        subprocess.run(['R', '--version'], capture_output=True, check=True)
    except:
        print("错误：未找到R环境，请安装R语言环境")
        return None
    
    if not os.path.exists(seurat_file):
        print(f"错误：文件不存在: {seurat_file}")
        return None
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    # R脚本（包含完整的结果验证，防止生成空JSON文件）
    r_script = f'''
library(Seurat)
library(jsonlite)
sce <- readRDS("{seurat_file}")
print("Seurat对象已加载")

# 设置聚类列
Idents(sce) <- "{cluster_column}"

# 数据标准化
if ("RNA" %in% names(sce@assays)) {{
  if("layers" %in% names(attributes(sce[["RNA"]]))){{
    if (!("data" %in% names(sce@assays$RNA@layers))) {{
        sce <- NormalizeData(sce)
    }}
  }} else {{
    if(!("data" %in% names(attributes(sce[["RNA"]])))){{
        sce <- NormalizeData(sce)
    }}
  }}
}}

# 运行 FindAllMarkers
alm <- FindAllMarkers(sce, only.pos = TRUE, min.pct = 0.25, logfc.threshold = 0.25)

# ========== 验证步骤 1: 检查 FindAllMarkers 结果 ==========
if (is.null(alm) || nrow(alm) == 0) {{
  stop("FindAllMarkers 未找到任何差异基因。可能原因：数据质量问题、cluster之间差异太小、或阈值设置过严格。")
}}

significant_alm <- alm[alm$p_val_adj < {pval_threshold}, ]
cluster_to_genes <- split(as.character(significant_alm$gene), significant_alm$cluster)
names(cluster_to_genes) <- paste0("cluster", names(cluster_to_genes))

write_json(cluster_to_genes, "{output_file}", pretty = TRUE, auto_unbox = FALSE)
'''

    try:
        print(f"正在对 {seurat_file} 运行FindAllMarkers分析...")
        result = subprocess.run(['R', '--slave', '--no-restore'],
                              input=r_script, text=True, capture_output=True, encoding='utf-8')

        # 显示R的标准输出（包括诊断信息）
        if result.stdout:
            print("R输出:")
            print(result.stdout)

        # 检查R脚本执行状态
        if result.returncode == 0:
            print("✓ R脚本执行成功")

            # 检查JSON文件是否生成
            if not os.path.exists(output_file):
                raise RuntimeError("R未能创建JSON文件")

            # 加载JSON文件
            with open(output_file, 'r', encoding='utf-8') as f:
                marker_genes = json.load(f)

            # ========== 额外验证：防止空JSON文件 ==========
            # 虽然R脚本已经验证，但并行处理时可能出现竞态条件
            if not marker_genes:
                raise RuntimeError(f"JSON文件为空（没有任何cluster）：{output_file}")

            # 检查是否所有cluster都是空列表
            total_genes = sum(len(genes) for genes in marker_genes.values())
            if total_genes == 0:
                error_msg = (
                    f"JSON文件包含cluster，但所有cluster的marker基因列表都为空\n"
                    f"Cluster数量: {len(marker_genes)}\n"
                    f"Cluster列表: {list(marker_genes.keys())}\n"
                    f"问题文件: {output_file}\n"
                    f"可能原因：数据质量问题、阈值设置过严格、或并行处理时文件被覆盖"
                )
                raise RuntimeError(error_msg)

            # 统计信息
            print(f"✓ FindAllMarkers分析成功完成")
            print(f"  Cluster数量: {len(marker_genes)}")
            print(f"  总marker基因数: {total_genes}")
            for cluster, genes in marker_genes.items():
                print(f"    {cluster}: {len(genes)} 个基因")

            # 返回统一格式
            return {
                "success": True,
                "method": "run_r_findallmarkers",
                "output_file": str(output_file),
                "input_file": seurat_file,
                "marker_genes": marker_genes,
                "cluster_count": len(marker_genes),
                "total_genes": total_genes,
                "pval_threshold": pval_threshold,
                "cluster_column": cluster_column
            }

        else:
            # R脚本执行失败
            error_msg = f"R脚本执行失败 (返回码: {result.returncode})"
            print(f"✗ {error_msg}")

            # 解析stderr中的错误信息
            if result.stderr:
                print("R错误输出:")
                error_lines = result.stderr.strip().split('\n')

                # 查找关键错误信息
                for line in error_lines:
                    if 'Error' in line or 'stop' in line or '错误' in line:
                        print(f"  ❌ {line}")
                        error_msg += f"\n{line}"
                    elif 'Warning' in line or '警告' in line:
                        print(f"  ⚠️  {line}")
                    else:
                        print(f"     {line}")

                # 提取诊断建议
                if "未找到任何显著的 marker 基因" in result.stderr:
                    print("\n💡 建议：")
                    print("   1. 尝试放宽p值阈值（当前: {pval_threshold}）")
                    print("   2. 调整FindAllMarkers参数：min.pct, logfc.threshold")
                    print("   3. 检查数据质量和cluster定义")
                elif "未找到任何差异基因" in result.stderr:
                    print("\n💡 建议：")
                    print("   1. 检查cluster之间是否有足够的差异")
                    print("   2. 降低FindAllMarkers的阈值")
                    print("   3. 确认数据已正确标准化")
                elif "没有足够的 marker 基因" in result.stderr:
                    print("\n💡 建议：")
                    print("   1. 放宽p值阈值或降低min_genes_per_cluster要求")
                    print("   2. 某些cluster可能确实缺乏特异性marker")

            raise RuntimeError(error_msg)

    except RuntimeError:
        # 直接抛出已格式化的 RuntimeError
        raise
    except Exception as e:
        # 其他异常包装为 RuntimeError
        import traceback
        traceback.print_exc()
        raise RuntimeError(f"FindAllMarkers分析过程中发生异常: {e}")

def load_scanpy_data(file_path: str) -> Dict[str, Any]:
    """
    使用scanpy加载数据文件

    参数:
    file_path: 数据文件路径（支持.h5ad等格式）

    返回:
    成功时返回包含AnnData对象的Dict，失败时抛出RuntimeError
    """
    try:
        import scanpy as sc

        if not os.path.exists(file_path):
            error_msg = f"错误：文件不存在: {file_path}"
            print(error_msg)
            raise RuntimeError(error_msg)

        print(f"正在使用scanpy加载 {file_path}...")

        if file_path.endswith('.h5ad'):
            sce = sc.read_h5ad(file_path)
        elif file_path.endswith('.h5'):
            try:
                from easySCFpy import loadH5
                print("使用easySCFpy读取H5格式数据（easySCF格式）...")
                sce = loadH5(file_path)
            except ImportError:
                raise RuntimeError(
                    "需要easySCFpy包来读取H5文件。\n"
                    "请安装: pip install easySCFpy"
                )
        elif file_path.endswith('.csv'):
            sce = sc.read_csv(file_path)
        else:
            print("警告：未知文件格式，尝试使用read_h5ad加载")
            sce = sc.read_h5ad(file_path)

        print(f"✓ 成功加载，包含 {sce.n_obs} 个细胞，{sce.n_vars} 个基因")

        # 返回统一Dict格式
        return {
            "success": True,
            "method": "load_scanpy_data",
            "input_file": file_path,
            "adata": sce,
            "n_obs": sce.n_obs,
            "n_vars": sce.n_vars,
            "message": f"成功加载 {sce.n_obs} 个细胞，{sce.n_vars} 个基因"
        }

    except RuntimeError:
        raise
    except ImportError:
        error_msg = "错误：未找到scanpy包，请安装: pip install scanpy"
        print(error_msg)
        raise RuntimeError(error_msg)
    except Exception as e:
        error_msg = f"✗ 加载文件失败: {e}"
        print(error_msg)
        raise RuntimeError(error_msg)

def load_h5_with_easyscfpy(h5_file: str) -> Optional[Any]:
    """
    使用easySCFpy加载h5文件
    """
    try:
        from easySCFpy import loadH5
        return loadH5(h5_file)
    except ImportError:
        print("错误：未找到easySCFpy包，请安装: pip install easySCFpy")
        return None

def easyscfpy_h5_to_json(h5_file: str, pval_threshold: float = 0.05, cluster_column: str = None, output_file: Optional[str] = None, config=None) -> Dict[str, Any]:
    """
    使用easySCFpy加载h5文件，并转换为JSON格式

    参数:
    h5_file: H5文件路径
    pval_threshold: p值阈值
    cluster_column: 聚类列名，为None时自动搜索 ['seurat_clusters', 'leiden', 'louvain']
    output_file: 输出JSON文件路径（可选，不指定则自动生成）

    返回:
    成功时返回包含marker基因信息的Dict，失败时抛出RuntimeError

    注意:
    输出文件会自动保存到配置的结果目录，使用 session_id 命名
    """
    try:
        sce = load_h5_with_easyscfpy(h5_file)
        if sce is None:
            raise RuntimeError(f"加载H5文件失败: {h5_file}")
        return process_scanpy_data(sce, pval_threshold, cluster_column, output_file, config)
    except RuntimeError:
        raise
    except Exception as e:
        error_msg = f"✗ 转换过程中出现错误: {e}"
        print(error_msg)
        raise RuntimeError(error_msg)

def scanpy_path_to_json(scanpy_path: str, pval_threshold: float = 0.05, cluster_column: str = None, output_file: Optional[str] = None, config=None) -> Dict[str, Any]:
    """
    处理scanpy数据，运行差异分析，从路径中加载数据

    参数:
    scanpy_path: scanpy文件路径
    pval_threshold: p值阈值
    cluster_column: 聚类列名，为None时自动搜索 ['seurat_clusters', 'leiden', 'louvain']
    output_file: 输出JSON文件路径（可选，不指定则自动生成）

    返回:
    成功时返回包含marker基因信息的Dict，失败时抛出RuntimeError

    注意:
    输出文件会自动保存到配置的结果目录，使用 session_id 命名
    """
    try:
        sce_result = load_scanpy_data(scanpy_path)
        if sce_result is None:
            raise RuntimeError(f"加载文件失败: {scanpy_path}")

        # 从Dict中提取AnnData对象
        sce = sce_result.get("adata")
        if sce is None:
            raise RuntimeError("加载的数据不包含AnnData对象")

        return process_scanpy_data(sce, pval_threshold, cluster_column, output_file, config)
    except RuntimeError:
        raise
    except Exception as e:
        error_msg = f"✗ 转换过程中出现错误: {e}"
        print(error_msg)
        raise RuntimeError(error_msg)


def convert_scanpy_file_to_h5(input_file: str, output_file: Optional[str] = None, config=None) -> Dict[str, Any]:
    """
    从文件加载scanpy数据并保存为easySCF H5格式

    参数:
    input_file: 输入数据文件路径（支持.h5ad等格式）
    output_file: 输出H5文件路径（可选，不指定则自动生成）

    返回:
    成功时返回包含转换信息的Dict，失败时抛出RuntimeError

    注意:
    输出文件会自动保存到配置的结果目录，使用 session_id 命名
    """
    try:
        # 加载scanpy数据
        sce_result = load_scanpy_data(input_file)
        if sce_result is None:
            raise RuntimeError(f"加载文件失败: {input_file}")

        # 从Dict中提取AnnData对象
        sce = sce_result.get("adata")
        if sce is None:
            raise RuntimeError("加载的数据不包含AnnData对象")

        # 保存为H5格式，传递output_file参数
        return save_scanpy_to_h5(sce, output_file)

    except RuntimeError:
        raise
    except Exception as e:
        error_msg = f"✗ 文件转换过程中发生异常: {e}"
        print(error_msg)
        raise RuntimeError(error_msg)

def process_scanpy_data(sce: AnnData, pval_threshold: float = 0.05, cluster_column: str = None, output_file: Optional[str] = None, config=None) -> Dict[str, Any]:
    """
    处理scanpy数据，运行差异分析

    参数:
    sce: AnnData对象
    pval_threshold: p值阈值
    cluster_column: 聚类列名，为None时自动搜索 ['seurat_clusters', 'leiden', 'louvain']
    output_file: 输出JSON文件路径（可选，不指定则自动生成）

    返回:
    成功时返回包含marker基因信息的Dict，失败时抛出RuntimeError

    注意:
    输出文件会自动保存到配置的结果目录，使用 session_id 命名
    """
    # 如果未指定输出路径，则自动生成
    if output_file is None:
        session_id = get_session_id_for_filename()
        if config:
            results_dir = config.get_results_dir()
        else:
            # 降级：从mcp_server模块获取
            from agentype.dataagent.services import mcp_server
            results_dir = mcp_server._CONFIG.get_results_dir()
        output_file = str(results_dir / f'cluster_marker_genes_{session_id}.json')

    try:
        import scanpy as sc
                
        # 数据预处理
        if sce.X.max() > 20:  # 原始计数数据
            print("⚠️ 进行对数化处理...")
            sc.pp.normalize_total(sce)
            sc.pp.log1p(sce)
            print("✓ 数据对数化处理完成")
        
        # 查找聚类信息
        cluster_key = None
        if cluster_column:
            # 用户指定了聚类列
            if cluster_column in sce.obs.columns:
                cluster_key = cluster_column
                print(f"✓ 使用指定的聚类列: {cluster_column}")
            else:
                print(f"⚠️ 指定的聚类列 '{cluster_column}' 不存在，尝试自动搜索")

        if cluster_key is None:
            # 自动搜索聚类列
            for key in ['seurat_clusters', 'leiden', 'louvain']:
                if key in sce.obs.columns:
                    cluster_key = key
                    print(f"✓ 使用 {cluster_key} 聚类信息")
                    break

        if cluster_key is None:
            print("✗ 错误：未找到聚类信息，自动使用分辨率1进行leiden聚类分析")
            sc.pp.scale(sce)
            sc.pp.pca(sce)
            sc.pp.neighbors(sce, n_neighbors=20, n_pcs=15)
            sc.tl.leiden(sce, resolution=1.0)
            cluster_key = 'leiden'
            print(f"✓ 使用自动生成的 leiden 聚类信息")
        
        # 运行差异基因分析
        print(f"🔬 正在运行差异基因分析...")
        sc.tl.rank_genes_groups(sce, cluster_key, method='wilcoxon')
        
        # 调用保存函数
        from .save_marker_genes import save_marker_genes_to_json
        result = save_marker_genes_to_json(sce, output_file, pval_threshold)

        # save_marker_genes_to_json 应该返回Dict或抛出异常
        if result is None:
            raise RuntimeError("save_marker_genes_to_json返回None")

        # 如果返回的是Dict但需要补充字段，在这里添加
        if isinstance(result, dict) and "method" not in result:
            result["method"] = "process_scanpy_data"

        return result

    except RuntimeError:
        raise
    except ImportError:
        error_msg = "错误：未找到scanpy包，请安装: pip install scanpy"
        print(error_msg)
        raise RuntimeError(error_msg)
    except Exception as e:
        error_msg = f"✗ 处理scanpy数据失败: {e}"
        print(error_msg)
        raise RuntimeError(error_msg)


def convert_r_markers_csv_to_json(csv_file: str, pval_threshold: float = 0.05, output_file: Optional[str] = None, config=None) -> Dict[str, Any]:
    """
    将FindAllMarkers的CSV结果转换为JSON格式

    参数:
    csv_file: CSV文件路径
    pval_threshold: p值阈值
    output_file: 输出JSON文件路径（可选，不指定则自动生成）

    返回:
    成功时返回包含marker基因信息的Dict，失败时抛出RuntimeError

    注意:
    输出文件会自动保存到配置的结果目录，使用 session_id 命名
    """
    # 如果未指定输出路径，则自动生成
    if output_file is None:
        session_id = get_session_id_for_filename()
        if config:
            results_dir = config.get_results_dir()
        else:
            # 降级：从mcp_server模块获取
            from agentype.dataagent.services import mcp_server
            results_dir = mcp_server._CONFIG.get_results_dir()
        output_file = str(results_dir / f'cluster_marker_genes_{session_id}.json')

    try:
        # 确保输出目录存在
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        print(f"正在读取 {csv_file}...")
        markers_df = pd.read_csv(csv_file)
        
        # 检查必要的列
        required_cols = ['cluster', 'gene', 'p_val_adj']
        for col in required_cols:
            if col not in markers_df.columns:
                error_msg = f"错误：未找到必要的列: {col}"
                print(error_msg)
                raise RuntimeError(error_msg)

        # 筛选显著的基因
        significant_markers = markers_df[markers_df['p_val_adj'] < pval_threshold]
        print(f"筛选出 {len(significant_markers)} 个显著的marker基因")

        # 生成marker基因字典
        marker_genes = {}
        clusters = significant_markers['cluster'].unique()

        for cluster in sorted(clusters):
            cluster_markers = significant_markers[
                significant_markers['cluster'] == cluster
            ]['gene'].tolist()

            marker_genes[f'cluster{cluster}'] = cluster_markers

        # 保存为JSON文件
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(marker_genes, f, ensure_ascii=False, indent=2)

        # 统计信息
        total_genes = sum(len(genes) for genes in marker_genes.values())
        print(f"✓ 成功提取 {len(marker_genes)} 个分簇的marker基因")
        print(f"结果已保存到 {output_file}")

        # 返回统一Dict格式
        return {
            "success": True,
            "method": "convert_r_markers_csv_to_json",
            "input_file": csv_file,
            "output_file": str(output_file),
            "marker_genes": marker_genes,
            "cluster_count": len(marker_genes),
            "total_genes": total_genes,
            "pval_threshold": pval_threshold
        }

    except RuntimeError:
        raise
    except FileNotFoundError:
        error_msg = f"错误：找不到文件 {csv_file}"
        print(error_msg)
        raise RuntimeError(error_msg)
    except Exception as e:
        error_msg = f"✗ 转换过程中出现错误: {e}"
        print(error_msg)
        raise RuntimeError(error_msg)

def save_scanpy_to_h5(sce: AnnData, output_file: Optional[str] = None) -> Dict[str, Any]:
    """
    将scanpy AnnData对象保存为easySCF H5格式

    参数:
    sce: AnnData对象
    output_file: 输出H5文件路径（可选，不指定则自动生成）

    返回:
    成功时返回包含保存信息的Dict，失败时抛出RuntimeError

    注意:
    输出文件会自动保存到配置的结果目录，使用 session_id 命名
    """
    # 如果未指定输出路径，则自动生成
    if output_file is None:
        session_id = get_session_id_for_filename()
        if config:
            results_dir = config.get_results_dir()
        else:
            # 降级：从mcp_server模块获取
            from agentype.dataagent.services import mcp_server
            results_dir = mcp_server._CONFIG.get_results_dir()
        h5_file = str(results_dir / f'data_{session_id}.h5')
    else:
        h5_file = output_file

    try:
        from easySCFpy import saveH5

        # 确保输出目录存在
        h5_file = os.path.abspath(h5_file)
        output_dir = os.path.dirname(h5_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            print(f"✓ 创建输出目录: {output_dir}")
        
        print(f"正在保存scanpy数据为H5格式: {h5_file}")
        saveH5(sce, h5_file)
        
        # 验证输出文件是否存在
        if os.path.exists(h5_file):
            file_size = os.path.getsize(h5_file)
            success_msg = f"✓ scanpy数据已成功保存为H5格式: {h5_file}"
            print(success_msg)

            # 返回统一Dict格式（注意：这里没有明确的input_file，使用空字符串）
            return {
                "success": True,
                "method": "save_scanpy_to_h5",
                "input_file": "",  # AnnData对象没有原始文件路径
                "output_file": h5_file,
                "file_size": file_size,
                "message": success_msg
            }
        else:
            error_msg = f"✗ 保存失败，未找到输出文件: {h5_file}"
            print(error_msg)
            raise RuntimeError(error_msg)

    except RuntimeError:
        raise
    except ImportError:
        error_msg = "错误：未找到easySCFpy包，请安装: pip install easySCFpy"
        print(error_msg)
        raise RuntimeError(error_msg)
    except Exception as e:
        error_msg = f"✗ 保存过程中发生异常: {e}"
        print(error_msg)
        raise RuntimeError(error_msg)
