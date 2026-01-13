#!/usr/bin/env python3
"""
agentype - 簇相关工具集合
Author: cuilei
Version: 1.0
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Iterable, List, Union

# 导入项目模块

# 导入统一配置系统
from agentype.config import get_session_id_for_filename
from agentype.prompts import get_prompt_manager

# 导入会话配置
try:
    from agentype.mainagent.config.session_config import get_session_id
    USE_SESSION_ISOLATION = True
except ImportError:
    USE_SESSION_ISOLATION = False
    def get_session_id():
        """回退函数：如果会话配置不可用，使用默认值"""
        return "default"


# ========== 共用辅助函数 ==========

def _auto_load_file_path(path_key: str) -> Optional[str]:
    """自动加载当前 session 的文件路径

    Args:
        path_key: 路径键名，如 'marker_genes_json', 'singler_result', 'sctype_result', 'celltypist_result'

    Returns:
        文件路径，如果加载失败返回 None
    """
    try:
        from agentype.mainagent.tools.file_paths_tools import load_file_paths_bundle
        bundle = load_file_paths_bundle()
        if bundle.get("success"):
            return bundle.get(path_key)
    except Exception:
        pass
    return None

def _load_json(file_path: str) -> Optional[Dict[str, Any]]:
    """安全地加载 JSON 文件。

    Args:
        file_path: JSON 文件路径

    Returns:
        解析后的 JSON 数据，如果加载失败则返回 None
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _normalize_cluster_key(keys: Iterable[str], cluster: str) -> Optional[str]:
    """查找最匹配的簇键名。

    接受 "1", 1, "cluster1" 等输入，尝试匹配 "cluster1" 等键名。

    Args:
        keys: 可用的键名集合
        cluster: 要匹配的簇标识符

    Returns:
        匹配的键名，如果未找到则返回 None
    """
    s = str(cluster).strip()
    candidates = []

    if s.lower().startswith("cluster"):
        candidates.append(s)
        # 也尝试数字部分
        tail = s[7:]
        if tail:
            candidates.append(tail)
    else:
        candidates.append(s)
        candidates.append(f"cluster{s}")

    key_set = {str(k) for k in keys}
    for cand in candidates:
        if cand in key_set:
            return cand

    # 不区分大小写的后备匹配
    lower_map = {str(k).lower(): str(k) for k in keys}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]

    return None


# ========== 簇注释保存/加载功能（原 cluster_saver.py）==========

def _get_default_dir() -> str:
    """获取默认存储目录（从全局配置获取）"""
    from pathlib import Path as _Path
    from agentype.mainagent.tools.file_paths_tools import _GLOBAL_CONFIG

    # 优先使用全局配置的 results_dir
    if _GLOBAL_CONFIG and hasattr(_GLOBAL_CONFIG, 'results_dir'):
        default_results_dir = _Path(_GLOBAL_CONFIG.results_dir)
        default_results_dir.mkdir(parents=True, exist_ok=True)
        return str(default_results_dir)
    else:
        # 不再回退，抛出明确错误
        raise RuntimeError(
            "全局配置未初始化！cluster_tools 需要有效的配置。\n"
            "请确保在使用此工具前，MCP Server 已正确启动并调用了 set_global_config()。"
        )

# 不再在模块级调用（延迟到使用时）
DEFAULT_DIR = None


def save_cluster_type(
    cluster_id: Union[str, int],
    cell_type: Union[str, int],
) -> Dict[str, Any]:
    """保存单个cluster的注释到bundle，并自动检测完成度。

    将cluster映射直接保存在bundle文件中，保存后自动检测所有簇的完成度。

    Args:
        cluster_id: 簇ID
        cell_type: 细胞类型

    Returns:
        包含保存状态和完成度信息的字典：
        {
            "success": True,
            "cluster_id": "cluster0",
            "cell_type": "T cell",
            "completion_status": {
                "all_completed": False,
                "total_clusters": 15,
                "completed_clusters": 1,
                "completion_rate": 0.067,
                "incomplete_clusters": ["cluster1", "cluster2", ...]
            },
            "reminder": "📊 当前进度：已完成 1/15 个簇 (6.7%)。还有未完成的簇：cluster1, cluster2, cluster3, cluster4, cluster5 等共14个。请继续处理剩余的簇。"
        }

    Raises:
        IOError: 保存失败时抛出
    """
    try:
        from agentype.mainagent.tools.file_paths_tools import save_cluster_mapping

        # 1. 保存簇映射
        result = save_cluster_mapping(str(cluster_id), str(cell_type))

        if not result.get("success"):
            raise IOError(f"保存cluster {cluster_id}={cell_type}失败: {result.get('error')}")

        # 2. 自动检测完成度
        completion_status = check_cluster_completion()

        # 3. 生成智能提醒
        manager = get_prompt_manager()
        if completion_status.get("all_completed"):
            template = manager.get_agent_specific_prompt('mainagent', 'CLUSTER_PROGRESS_COMPLETE_MESSAGE')
            next_action = manager.get_agent_specific_prompt('mainagent', 'CLUSTER_PROGRESS_ACTION_PHASE5')
            reminder = template.format(
                total_clusters=completion_status['total_clusters'],
                next_action=next_action
            )
        else:
            # 未完成的情况
            completed = completion_status["completed_clusters"]
            total = completion_status["total_clusters"]
            incomplete = completion_status["incomplete_clusters"]

            # 生成未完成簇的预览（最多显示5个）
            incomplete_preview = ", ".join(incomplete[:5])
            if len(incomplete) > 5:
                suffix_template = manager.get_agent_specific_prompt('mainagent', 'CLUSTER_PROGRESS_INCOMPLETE_PREVIEW_SUFFIX')
                incomplete_preview += suffix_template.format(count=len(incomplete))

            template = manager.get_agent_specific_prompt('mainagent', 'CLUSTER_PROGRESS_INCOMPLETE_MESSAGE')
            next_action = manager.get_agent_specific_prompt('mainagent', 'CLUSTER_PROGRESS_ACTION_CONTINUE')
            reminder = template.format(
                completed=completed,
                total=total,
                completion_rate=completion_status["completion_rate"],
                incomplete_preview=incomplete_preview,
                next_action=next_action
            )

        # 4. 返回完整信息
        return {
            "success": True,
            "cluster_id": str(cluster_id),
            "cell_type": str(cell_type),
            "completion_status": completion_status,
            "reminder": reminder
        }

    except Exception as e:
        import logging
        logging.error(f"保存cluster {cluster_id}={cell_type}时出错: {e}")
        raise IOError(f"保存cluster失败: {e}")


def load_cluster_types() -> Dict[str, str]:
    """从bundle加载所有cluster映射数据。

    直接从bundle文件的cluster_mapping字段读取数据。

    Returns:
        簇ID到细胞类型的映射字典
    """
    try:
        from agentype.mainagent.tools.file_paths_tools import load_cluster_mapping
        return load_cluster_mapping()
    except Exception:
        return {}


# ========== 簇结果读取功能（原 cluster_result_reader.py）==========

def _extract_for_cluster(data: Dict[str, Any], cluster: str) -> Optional[Dict[str, Any]]:
    """从注释数据中提取指定簇的信息。

    Args:
        data: 注释结果数据
        cluster: 簇标识符

    Returns:
        提取的簇信息，如果未找到则返回 None
    """
    if not data:
        return None
    annotations = data.get("cluster_annotations")
    if not isinstance(annotations, dict):
        return None
    match_key = _normalize_cluster_key(annotations.keys(), cluster)
    if match_key is None:
        return None
    entry = annotations.get(match_key)
    if not isinstance(entry, dict):
        return None
    # Return the most useful subset, present across tools
    result: Dict[str, Any] = {
        "celltype": entry.get("celltype"),
        "proportion": entry.get("proportion"),
    }
    # include confidence if available (SingleR/scType)
    if "confidence" in entry:
        result["confidence"] = entry.get("confidence")
    return result


def read_cluster_results(
    cluster: str,
    singler_result: Optional[str] = None,
    sctype_result: Optional[str] = None,
    celltypist_result: Optional[str] = None,
) -> Dict[str, Any]:
    """从三种方法的结果 JSON 中读取指定簇的合并结果。

    Args:
        cluster: 簇ID，例如 "1" 或 "cluster1"
        singler_result: SingleR 结果 JSON 路径，默认自动读取当前 session 的结果文件
        sctype_result: scType 结果 JSON 路径，默认自动读取当前 session 的结果文件
        celltypist_result: CellTypist 结果 JSON 路径，默认自动读取当前 session 的结果文件

    Returns:
        包含各方法结果的合并字典
    """
    # 🌟 自动加载当前 session 的结果文件路径
    if singler_result is None or sctype_result is None or celltypist_result is None:
        try:
            from agentype.mainagent.tools.file_paths_tools import load_file_paths_bundle
            bundle = load_file_paths_bundle()
            if bundle.get("success"):
                if singler_result is None:
                    singler_result = bundle.get("singler_result") or ""
                if sctype_result is None:
                    sctype_result = bundle.get("sctype_result") or ""
                if celltypist_result is None:
                    celltypist_result = bundle.get("celltypist_result") or ""
        except Exception:
            # 如果自动加载失败，使用空字符串作为后备
            if singler_result is None:
                singler_result = ""
            if sctype_result is None:
                sctype_result = ""
            if celltypist_result is None:
                celltypist_result = ""

    sr = _load_json(singler_result) if singler_result else None
    sc = _load_json(sctype_result) if sctype_result else None
    ct = _load_json(celltypist_result) if celltypist_result else None

    # Normalize cluster label in output (e.g., 1 -> cluster1, cluster1 -> cluster1)
    s = str(cluster).strip()
    out = {
        "cluster": f"cluster{s[7:]}" if s.lower().startswith("cluster") else f"cluster{s}",
        "files": {
            "singler": singler_result,
            "sctype": sctype_result,
            "celltypist": celltypist_result,
        },
        "results": {
            "SingleR": _extract_for_cluster(sr, cluster),
            "scType": _extract_for_cluster(sc, cluster),
            "CellTypist": _extract_for_cluster(ct, cluster),
        },
    }
    # success if at least one method found a result
    out["success"] = any(v is not None for v in out["results"].values())
    return out


# ========== 基因提取功能（原 cluster_gene_extractor.py）==========

def extract_cluster_genes(cluster_name: str, gene_count: int = 50, marker_genes_json_path: Optional[str] = None) -> List[str]:
    """从 JSON 文件中提取指定簇的基因。

    Args:
        cluster_name: 簇名称（支持 "1", "cluster1" 等格式）
        gene_count: 要提取的基因数量
        marker_genes_json_path: JSON 文件路径，默认自动读取当前 session 的 marker genes 文件

    Returns:
        基因名称列表

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 簇不存在或 gene_count 无效
        Exception: JSON 解析错误或其他错误
    """
    # 参数验证
    if gene_count <= 0:
        raise ValueError("基因数量必须大于 0")

    # 🌟 自动加载当前 session 的 marker_genes_json 路径
    if marker_genes_json_path is None:
        marker_genes_json_path = _auto_load_file_path("marker_genes_json")
        if marker_genes_json_path is None:
            raise FileNotFoundError(
                "未找到当前 session 的 marker genes 文件。"
                "请先运行数据处理生成 marker genes，或手动指定 marker_genes_json_path 参数。"
            )

    # 加载 JSON 文件
    data = _load_json(marker_genes_json_path)
    if data is None:
        if not Path(marker_genes_json_path).exists():
            raise FileNotFoundError(f"文件不存在: {marker_genes_json_path}")
        else:
            raise Exception(f"无法解析 JSON 文件: {marker_genes_json_path}")

    # 查找匹配的簇键
    cluster_key = _normalize_cluster_key(data.keys(), cluster_name)
    if cluster_key is None:
        available_clusters = list(data.keys())
        raise ValueError(f"簇 '{cluster_name}' 不存在。可用的簇: {available_clusters}")

    # 获取基因列表
    genes = data.get(cluster_key)
    if not isinstance(genes, list):
        raise ValueError(f"簇 '{cluster_key}' 的数据格式无效，应为基因列表")

    # 提取指定数量的基因
    if gene_count >= len(genes):
        return genes.copy()
    else:
        return genes[:gene_count]


def get_all_cluster_ids(marker_genes_json_path: Optional[str] = None) -> List[str]:
    """获取 JSON 文件中所有簇的编号。

    Args:
        marker_genes_json_path: JSON 文件路径，默认自动读取当前 session 的 marker genes 文件

    Returns:
        所有簇编号的列表

    Raises:
        FileNotFoundError: 文件不存在
        Exception: JSON 解析错误
    """
    # 🌟 自动加载当前 session 的 marker_genes_json 路径
    if marker_genes_json_path is None:
        marker_genes_json_path = _auto_load_file_path("marker_genes_json")
        if marker_genes_json_path is None:
            raise FileNotFoundError(
                "未找到当前 session 的 marker genes 文件。"
                "请先运行数据处理生成 marker genes，或手动指定 marker_genes_json_path 参数。"
            )

    data = _load_json(marker_genes_json_path)
    if data is None:
        if not Path(marker_genes_json_path).exists():
            raise FileNotFoundError(f"文件不存在: {marker_genes_json_path}")
        else:
            raise Exception(f"无法解析 JSON 文件: {marker_genes_json_path}")

    return list(data.keys())


def get_cluster_info(marker_genes_json_path: Optional[str] = None) -> Dict[str, int]:
    """获取 JSON 文件中所有簇的基因数量信息。

    Args:
        marker_genes_json_path: JSON 文件路径，默认自动读取当前 session 的 marker genes 文件

    Returns:
        簇名称到基因数量的映射

    Raises:
        FileNotFoundError: 文件不存在
        Exception: JSON 解析错误
    """
    # 🌟 自动加载当前 session 的 marker_genes_json 路径
    if marker_genes_json_path is None:
        marker_genes_json_path = _auto_load_file_path("marker_genes_json")
        if marker_genes_json_path is None:
            raise FileNotFoundError(
                "未找到当前 session 的 marker genes 文件。"
                "请先运行数据处理生成 marker genes，或手动指定 marker_genes_json_path 参数。"
            )

    data = _load_json(marker_genes_json_path)
    if data is None:
        if not Path(marker_genes_json_path).exists():
            raise FileNotFoundError(f"文件不存在: {marker_genes_json_path}")
        else:
            raise Exception(f"无法解析 JSON 文件: {marker_genes_json_path}")

    info = {}
    for cluster_name, genes in data.items():
        if isinstance(genes, list):
            info[cluster_name] = len(genes)
        else:
            info[cluster_name] = 0

    return info


# ========== 簇完成度检查功能 ==========

def check_cluster_completion(
    marker_genes_path: Optional[str] = None
) -> Dict[str, Any]:
    """检查所有簇是否已完成注释。

    自动使用当前会话ID检查对应会话的完成状态。

    Args:
        marker_genes_path: marker基因JSON文件路径，默认自动读取当前 session 的 marker genes 文件

    Returns:
        包含完成状态信息的字典
    """
    try:
        # 🌟 自动加载当前 session 的 marker_genes_path
        if marker_genes_path is None:
            marker_genes_path = _auto_load_file_path("marker_genes_json")
            if marker_genes_path is None:
                return {
                    "success": False,
                    "error": "未找到当前 session 的 marker genes 文件。请先运行数据处理生成 marker genes，或手动指定 marker_genes_path 参数。",
                    "all_completed": False,
                    "total_clusters": 0,
                    "completed_clusters": 0,
                    "completion_rate": 0.0,
                    "incomplete_clusters": []
                }

        # 加载marker基因数据获取所有簇
        marker_data = _load_json(marker_genes_path)
        if marker_data is None:
            return {
                "success": False,
                "error": f"无法加载marker基因文件: {marker_genes_path}",
                "all_completed": False,
                "total_clusters": 0,
                "completed_clusters": 0,
                "completion_rate": 0.0,
                "incomplete_clusters": []
            }

        # 获取所有簇名称
        all_clusters = set(marker_data.keys())
        total_count = len(all_clusters)

        # 加载当前会话已注释的簇
        annotated_clusters = load_cluster_types()

        # 找出已完成注释的簇（标准化键名进行匹配）
        completed_clusters = set()
        for cluster in all_clusters:
            # 尝试多种键名匹配
            cluster_variations = [
                cluster,  # 原始名称如"cluster0"
                cluster.replace("cluster", ""),  # 数字部分如"0"
                f"cluster{cluster}" if not cluster.startswith("cluster") else cluster
            ]

            for variation in cluster_variations:
                if variation in annotated_clusters and annotated_clusters[variation].strip():
                    completed_clusters.add(cluster)
                    break

        # 计算未完成的簇
        incomplete_clusters = list(all_clusters - completed_clusters)
        completed_count = len(completed_clusters)
        completion_rate = completed_count / total_count if total_count > 0 else 0.0

        return {
            "success": True,
            "all_completed": len(incomplete_clusters) == 0,
            "total_clusters": total_count,
            "completed_clusters": completed_count,
            "completion_rate": completion_rate,
            "incomplete_clusters": sorted(incomplete_clusters),
            "completed_cluster_list": sorted(list(completed_clusters))
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"检查簇完成度时出错: {e}",
            "all_completed": False,
            "total_clusters": 0,
            "completed_clusters": 0,
            "completion_rate": 0.0,
            "incomplete_clusters": []
        }


def get_incomplete_clusters(
    marker_genes_path: Optional[str] = None
) -> List[str]:
    """获取未完成注释的簇列表。

    Args:
        marker_genes_path: marker基因JSON文件路径，默认自动读取当前 session 的 marker genes 文件

    Returns:
        未完成注释的簇名称列表
    """
    result = check_cluster_completion(marker_genes_path)
    return result.get("incomplete_clusters", [])


def calculate_completion_rate(
    marker_genes_path: Optional[str] = None
) -> float:
    """计算簇注释完成率。

    Args:
        marker_genes_path: marker基因JSON文件路径，默认自动读取当前 session 的 marker genes 文件

    Returns:
        完成率（0.0-1.0）
    """
    result = check_cluster_completion(marker_genes_path)
    return result.get("completion_rate", 0.0)


def format_completion_summary(
    marker_genes_path: Optional[str] = None
) -> str:
    """格式化簇完成度摘要信息。

    Args:
        marker_genes_path: marker基因JSON文件路径，默认自动读取当前 session 的 marker genes 文件

    Returns:
        格式化的完成度摘要字符串
    """
    result = check_cluster_completion(marker_genes_path)

    if not result["success"]:
        return f"❌ 检查失败: {result['error']}"

    manager = get_prompt_manager()
    summary_template = manager.get_agent_specific_prompt('mainagent', 'CLUSTER_COMPLETION_SUMMARY_TEMPLATE')
    summary = summary_template.format(
        completed=result['completed_clusters'],
        total=result['total_clusters'],
        completion_rate=result['completion_rate']
    )

    if result["all_completed"]:
        suffix = manager.get_agent_specific_prompt('mainagent', 'CLUSTER_COMPLETION_SUMMARY_ALL_DONE')
        summary += f"\n{suffix}"
    else:
        incomplete_clusters = result["incomplete_clusters"]
        incomplete_count = len(incomplete_clusters)
        incomplete_preview = ", ".join(incomplete_clusters[:5])
        if incomplete_count > 5:
            preview_suffix = manager.get_agent_specific_prompt('mainagent', 'CLUSTER_COMPLETION_INCOMPLETE_PREVIEW_SUFFIX')
            incomplete_preview += preview_suffix.format(count=incomplete_count)

        suffix_template = manager.get_agent_specific_prompt('mainagent', 'CLUSTER_COMPLETION_SUMMARY_INCOMPLETE')
        summary += "\n" + suffix_template.format(
            incomplete_count=incomplete_count,
            incomplete_preview=incomplete_preview
        )

    return summary


# ========== 细胞类型名称统一化功能 ==========

def unify_cell_type_names(
    cluster_mapping_data: str,
    output_json_path: str
) -> Dict[str, Any]:
    """将细胞类型映射保存为JSON文件。

    Args:
        cluster_mapping_data: 映射数据的JSON字符串
        output_json_path: 输出json文件路径

    Returns:
        包含成功状态的字典，失败时包含错误信息
    """
    try:
        # 解析JSON字符串
        mapping_data = json.loads(cluster_mapping_data)

        # 保存到文件
        output_path = Path(output_json_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", encoding="utf-8") as f:
            json.dump(mapping_data, f, ensure_ascii=False, indent=2)

        return {"success": True}

    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON解析失败: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ========== 会话管理功能 ==========

def list_all_sessions() -> List[str]:
    """列出所有历史会话。

    从扁平化的文件名中提取session_id。

    Returns:
        会话ID列表，按时间倒序排列（最新的在前）
    """
    save_dir = DEFAULT_DIR if DEFAULT_DIR else _get_default_dir()
    d = Path(save_dir)
    if not d.exists():
        return []

    # 从文件名中提取session_id（格式：cluster_mapping_X_session_YYYYMMDD_HHMMSS_xxx.json）
    sessions = set()
    for p in d.glob("cluster_mapping_*_session_*.json"):
        # 提取文件名中的session_id部分
        parts = p.stem.split('_')
        # 找到 'session' 关键词的位置
        try:
            session_idx = parts.index('session')
            # session_id 是从 'session' 开始到结尾的所有部分
            session_id = '_'.join(parts[session_idx:])
            sessions.add(session_id)
        except (ValueError, IndexError):
            continue

    # 按时间倒序排序（最新的在前）
    return sorted(list(sessions), reverse=True)


def load_cluster_types_by_session(
    session_id: str
) -> Dict[str, str]:
    """读取指定会话的所有簇注释。

    用于查看历史会话的注释结果。使用扁平化文件命名。

    Args:
        session_id: 会话ID

    Returns:
        簇ID到细胞类型的映射
    """
    save_dir = DEFAULT_DIR if DEFAULT_DIR else _get_default_dir()
    base_dir = Path(save_dir)

    if not base_dir.exists():
        return {}

    # 使用扁平化文件名模式：cluster_mapping_*_{session_id}.json
    result: Dict[str, str] = {}
    pattern = f"cluster_mapping_*_{session_id}.json"
    for p in sorted(base_dir.glob(pattern)):
        try:
            with p.open("r", encoding="utf-8") as f:
                item = json.load(f)
            c = str(item.get("cluster", "")).strip()
            t = str(item.get("type", "")).strip()
            if c:
                result[c] = t
        except Exception:
            continue
    return result


def get_session_summary() -> Dict[str, Any]:
    """获取所有会话的摘要信息。

    Returns:
        包含所有会话摘要的字典
    """
    sessions = list_all_sessions()
    current_session = get_session_id() if USE_SESSION_ISOLATION else "default"

    summary = {
        "current_session": current_session,
        "total_sessions": len(sessions),
        "sessions": []
    }

    for session_id in sessions:
        save_dir = DEFAULT_DIR if DEFAULT_DIR else _get_default_dir()
        base_dir = Path(save_dir)
        # 使用扁平化文件名模式统计cluster数量
        pattern = f"cluster_mapping_*_{session_id}.json"
        cluster_count = len(list(base_dir.glob(pattern)))

        # 尝试从会话ID解析时间
        created_at = "Unknown"
        if session_id.startswith("session_"):
            try:
                from datetime import datetime
                timestamp_part = session_id.replace("session_", "")
                dt = datetime.strptime(timestamp_part, "%Y%m%d_%H%M%S")
                created_at = dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass

        summary["sessions"].append({
            "session_id": session_id,
            "created_at": created_at,
            "cluster_count": cluster_count,
            "is_current": session_id == current_session
        })

    return summary
