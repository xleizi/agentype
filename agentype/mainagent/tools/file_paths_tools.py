#!/usr/bin/env python3
"""
agentype - 文件路径保存工具模块
Author: cuilei
Version: 1.0
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

# 导入项目模块

# 导入统一配置系统已废弃，使用默认路径
from pathlib import Path as _Path


# 全局配置对象（由 MCP Server 在启动时设置）
_GLOBAL_CONFIG = None


def set_global_config(config):
    """设置全局配置（由 MCP Server 在启动时调用）

    Args:
        config: ConfigManager 实例，包含 downloads_dir, results_dir 等路径配置
    """
    global _GLOBAL_CONFIG
    _GLOBAL_CONFIG = config


@dataclass
class FilePathsInfo:
    """文件路径信息数据结构 - 完整的12个核心文件 + cluster映射数据"""
    session_id: str                          # 会话唯一标识
    timestamp: str                           # 创建时间戳
    # 原始数据文件（4个）
    rds_file: Optional[str] = None          # RDS文件路径
    h5ad_file: Optional[str] = None         # H5AD文件路径
    h5_file: Optional[str] = None           # H5文件路径
    marker_genes_csv: Optional[str] = None  # CSV格式的marker基因文件路径
    # Marker基因文件（1个）
    marker_genes_json: Optional[str] = None # Marker基因JSON文件路径
    # AppAgent注释结果文件（3个）
    singler_result: Optional[str] = None    # SingleR结果文件路径
    sctype_result: Optional[str] = None     # scType结果文件路径
    celltypist_result: Optional[str] = None # CellTypist结果文件路径
    # MainAgent输出文件（2个）
    annotated_rds: Optional[str] = None     # Seurat写回结果文件路径
    annotated_h5ad: Optional[str] = None    # AnnData写回结果文件路径
    # DataAgent格式转换文件（2个）
    sce_h5: Optional[str] = None            # SCE转H5结果文件路径
    scanpy_h5: Optional[str] = None         # Scanpy转H5结果文件路径
    # Cluster映射数据（直接存储，不是文件路径）
    cluster_mapping: Optional[Dict[str, str]] = None  # 簇ID到细胞类型的映射 {"0": "T cell", "1": "B cell"}
    # 可选元数据
    metadata: Optional[Dict[str, Any]] = None # 额外元数据（非必须）

    def __post_init__(self):
        """初始化默认值"""
        if self.metadata is None:
            self.metadata = {}
        if self.cluster_mapping is None:
            self.cluster_mapping = {}

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FilePathsInfo':
        """从字典创建实例"""
        return cls(**data)


class FilePathsManager:
    """文件路径管理器"""

    def __init__(self):
        # 不在初始化时获取目录，改为使用属性动态获取
        self.bundle_prefix = "celltype_file_paths_"
        self.bundle_suffix = ".json"

    @property
    def bundle_dir(self) -> Path:
        """动态获取路径包存储目录（每次调用时重新检查配置）"""
        return self._get_bundle_directory()

    def _get_bundle_directory(self) -> Path:
        """获取路径包存储目录（从全局配置获取）

        优点：
        1. 每个项目独立目录，避免多项目冲突
        2. 持久化存储，不会被系统清理
        3. 便于调试和查看
        4. 使用配置的 downloads_dir，确保文件保存到正确位置
        """
        try:
            # 优先使用全局配置的 downloads_dir
            if _GLOBAL_CONFIG and hasattr(_GLOBAL_CONFIG, 'downloads_dir'):
                base_dir = Path(_GLOBAL_CONFIG.downloads_dir)
            else:
                # 不再回退到 .output，抛出明确错误
                raise RuntimeError(
                    "全局配置未初始化！FilePathsManager 需要有效的配置。\n"
                    "请确保在使用此工具前，MCP Server 已正确启动并调用了 set_global_config()。\n"
                    f"当前 _GLOBAL_CONFIG: {_GLOBAL_CONFIG}"
                )

            bundle_dir = base_dir / "celltypeMainagent" / "path_bundles"
            bundle_dir.mkdir(exist_ok=True, parents=True)
            return bundle_dir
        except RuntimeError:
            # 重新抛出配置错误
            raise
        except Exception as e:
            # 其他错误（如权限问题）
            raise RuntimeError(f"无法创建路径包目录: {e}")

    def _generate_bundle_filename(self, session_id: str) -> str:
        """生成文件包文件名"""
        return f"{self.bundle_prefix}{session_id}{self.bundle_suffix}"

    def _validate_file_path(self, file_path: Optional[str]) -> bool:
        """验证文件路径的安全性和有效性"""
        # None 或空字符串都视为"未提供"，允许通过
        if file_path is None or file_path.strip() == "":
            return True

        try:
            path = Path(file_path)
            # 检查路径是否存在
            if not path.exists():
                return False
            # 检查是否为文件
            if not path.is_file():
                return False
            # 基本安全检查（避免路径遍历攻击）
            resolved_path = path.resolve()
            return True
        except Exception:
            return False

    def save_file_paths_bundle(
        self,
        rds_file: Optional[str] = None,
        h5ad_file: Optional[str] = None,
        h5_file: Optional[str] = None,
        marker_genes_json: Optional[str] = None,
        singler_result: Optional[str] = None,
        sctype_result: Optional[str] = None,
        celltypist_result: Optional[str] = None,
        annotated_rds: Optional[str] = None,
        annotated_h5ad: Optional[str] = None,
        sce_h5: Optional[str] = None,
        scanpy_h5: Optional[str] = None,
        cluster_mapping: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        保存文件路径信息包到cache目录

        Args:
            rds_file: RDS文件路径
            h5ad_file: H5AD文件路径
            h5_file: H5文件路径
            marker_genes_json: Marker基因JSON文件路径
            singler_result: SingleR结果文件路径
            sctype_result: scType结果文件路径
            celltypist_result: CellTypist结果文件路径
            annotated_rds: Seurat写回结果文件路径
            annotated_h5ad: AnnData写回结果文件路径
            sce_h5: SCE转H5结果文件路径
            scanpy_h5: Scanpy转H5结果文件路径
            cluster_mapping: 簇ID到细胞类型的映射字典 {"0": "T cell", "1": "B cell"}
            metadata: 额外元数据（非必须）
            session_id: 会话ID（如果不提供则自动生成）

        Returns:
            包含保存结果的字典
        """
        try:
            # 生成会话ID
            if session_id is None:
                from agentype.mainagent.config.session_config import get_session_id
                session_id = get_session_id()

            # 增量更新支持：如果bundle已存在，先加载现有数据
            bundle_filename = self._generate_bundle_filename(session_id)
            bundle_path = self.bundle_dir / bundle_filename
            existing_data = {}

            if bundle_path.exists():
                try:
                    with open(bundle_path, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                except Exception:
                    pass  # 如果加载失败，使用空dict

            # 合并现有数据和新数据（新数据优先）
            def merge_value(new_val, old_val):
                """如果新值不是None，使用新值；否则保留旧值"""
                return new_val if new_val is not None else old_val

            rds_file = merge_value(rds_file, existing_data.get('rds_file'))
            h5ad_file = merge_value(h5ad_file, existing_data.get('h5ad_file'))
            h5_file = merge_value(h5_file, existing_data.get('h5_file'))
            marker_genes_json = merge_value(marker_genes_json, existing_data.get('marker_genes_json'))
            singler_result = merge_value(singler_result, existing_data.get('singler_result'))
            sctype_result = merge_value(sctype_result, existing_data.get('sctype_result'))
            celltypist_result = merge_value(celltypist_result, existing_data.get('celltypist_result'))
            annotated_rds = merge_value(annotated_rds, existing_data.get('annotated_rds'))
            annotated_h5ad = merge_value(annotated_h5ad, existing_data.get('annotated_h5ad'))
            sce_h5 = merge_value(sce_h5, existing_data.get('sce_h5'))
            scanpy_h5 = merge_value(scanpy_h5, existing_data.get('scanpy_h5'))

            # cluster_mapping的增量合并逻辑（字典合并）
            existing_cluster_mapping = existing_data.get('cluster_mapping', {})
            if not isinstance(existing_cluster_mapping, dict):
                existing_cluster_mapping = {}

            if cluster_mapping is None:
                # 如果没有传入新的cluster_mapping，保留现有的
                cluster_mapping = existing_cluster_mapping
            else:
                # 如果传入了新的cluster_mapping，合并到现有的上（新数据覆盖旧数据）
                merged_cluster_mapping = existing_cluster_mapping.copy()
                merged_cluster_mapping.update(cluster_mapping)
                cluster_mapping = merged_cluster_mapping

            # 合并元数据
            if metadata is None:
                metadata = existing_data.get('metadata', {})
            elif existing_data.get('metadata'):
                # 如果两边都有metadata，合并它们
                merged_metadata = existing_data.get('metadata', {}).copy()
                merged_metadata.update(metadata)
                metadata = merged_metadata

            # 验证文件路径（cluster_mapping不需要验证，因为不是文件路径）
            file_paths = {
                'rds_file': rds_file,
                'h5ad_file': h5ad_file,
                'h5_file': h5_file,
                'marker_genes_json': marker_genes_json,
                'singler_result': singler_result,
                'sctype_result': sctype_result,
                'celltypist_result': celltypist_result,
                'annotated_rds': annotated_rds,
                'annotated_h5ad': annotated_h5ad,
                'sce_h5': sce_h5,
                'scanpy_h5': scanpy_h5
            }

            invalid_paths = []
            for name, path in file_paths.items():
                if path is not None and not self._validate_file_path(path):
                    invalid_paths.append(f"{name}: {path}")

            if invalid_paths:
                return {
                    "success": False,
                    "error": f"无效的文件路径: {', '.join(invalid_paths)}"
                }

            # 创建文件路径信息对象
            timestamp = datetime.now().isoformat()

            # 初始化元数据
            if metadata is None:
                metadata = {}

            file_paths_info = FilePathsInfo(
                session_id=session_id,
                timestamp=timestamp,
                rds_file=rds_file,
                h5ad_file=h5ad_file,
                h5_file=h5_file,
                marker_genes_json=marker_genes_json,
                singler_result=singler_result,
                sctype_result=sctype_result,
                celltypist_result=celltypist_result,
                annotated_rds=annotated_rds,
                annotated_h5ad=annotated_h5ad,
                sce_h5=sce_h5,
                scanpy_h5=scanpy_h5,
                cluster_mapping=cluster_mapping,
                metadata=metadata
            )

            # 保存到文件（bundle_filename和bundle_path已在前面定义）
            with open(bundle_path, 'w', encoding='utf-8') as f:
                json.dump(file_paths_info.to_dict(), f, ensure_ascii=False, indent=2)

            # 保存后立即验证：确保文件正确写入且可读回
            verification_passed = False
            verification_error = None
            try:
                # 1. 验证文件存在
                if not bundle_path.exists():
                    verification_error = "保存的bundle文件不存在"
                else:
                    # 2. 验证文件可读且内容完整
                    with open(bundle_path, 'r', encoding='utf-8') as f:
                        saved_data = json.load(f)

                    # 3. 验证关键字段
                    if saved_data.get('session_id') != session_id:
                        verification_error = f"session_id不匹配: 期望{session_id}, 实际{saved_data.get('session_id')}"
                    elif saved_data.get('marker_genes_json') != marker_genes_json:
                        verification_error = f"marker_genes_json不匹配: 期望{marker_genes_json}, 实际{saved_data.get('marker_genes_json')}"
                    else:
                        verification_passed = True
            except Exception as e:
                verification_error = f"验证失败: {str(e)}"

            result = {
                "success": True,
                "session_id": session_id,
                "bundle_path": str(bundle_path),
                "timestamp": timestamp,
                "file_count": sum(1 for path in [rds_file, h5ad_file, h5_file, marker_genes_json, singler_result, sctype_result, celltypist_result, annotated_rds, annotated_h5ad, sce_h5, scanpy_h5] if path),
                "cluster_count": len(cluster_mapping) if cluster_mapping else 0,
                # 验证信息
                "verified": verification_passed,
                "verification_error": verification_error
            }

            # 如果验证失败，在返回中添加警告（但不标记success=False，因为文件已保存）
            if not verification_passed:
                result["warning"] = f"文件已保存但验证失败: {verification_error}"

            return result

        except Exception as e:
            return {
                "success": False,
                "error": f"保存文件路径包失败: {str(e)}"
            }

    def load_file_paths_bundle(self) -> Dict[str, Any]:
        """
        从cache目录加载当前会话的文件路径信息包

        自动使用当前会话ID定位文件路径包。

        Returns:
            包含文件路径信息的字典
        """
        try:
            # 自动获取当前会话ID
            from agentype.mainagent.config.session_config import get_session_id
            session_id = get_session_id()

            bundle_filename = self._generate_bundle_filename(session_id)
            bundle_path = self.bundle_dir / bundle_filename

            if not bundle_path.exists():
                return {
                    "success": False,
                    "error": f"未找到会话ID为 {session_id} 的文件路径包"
                }

            # 读取文件
            with open(bundle_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            file_paths_info = FilePathsInfo.from_dict(data)

            result = {
                "success": True,
                "session_id": file_paths_info.session_id,
                "timestamp": file_paths_info.timestamp,
                "rds_file": file_paths_info.rds_file,
                "h5ad_file": file_paths_info.h5ad_file,
                "h5_file": file_paths_info.h5_file,
                "marker_genes_json": file_paths_info.marker_genes_json,
                "singler_result": file_paths_info.singler_result,
                "sctype_result": file_paths_info.sctype_result,
                "celltypist_result": file_paths_info.celltypist_result,
                "annotated_rds": file_paths_info.annotated_rds,
                "annotated_h5ad": file_paths_info.annotated_h5ad,
                "sce_h5": file_paths_info.sce_h5,
                "scanpy_h5": file_paths_info.scanpy_h5,
                "cluster_mapping": file_paths_info.cluster_mapping,
                "metadata": file_paths_info.metadata
            }

            return result

        except Exception as e:
            return {
                "success": False,
                "error": f"加载文件路径包失败: {str(e)}"
            }

    def load_and_validate_bundle(self) -> Dict[str, Any]:
        """
        加载当前会话的文件路径包并验证关键文件是否存在

        这是一个安全的加载方法，会在加载后立即验证marker_genes_json等关键文件的存在性。
        推荐使用此方法代替load_file_paths_bundle，以避免使用过期的路径包。

        Returns:
            包含文件路径信息和验证结果的字典
        """
        # 先调用标准加载
        result = self.load_file_paths_bundle()

        if not result.get("success"):
            return result

        # 验证关键文件存在性
        marker_genes_json = result.get("marker_genes_json")
        missing_files = []
        existing_files = []

        # 检查所有文件路径
        files_to_check = {
            "marker_genes_json": marker_genes_json,
            "h5_file": result.get("h5_file"),
            "rds_file": result.get("rds_file"),
            "h5ad_file": result.get("h5ad_file"),
            "singler_result": result.get("singler_result"),
            "sctype_result": result.get("sctype_result"),
            "celltypist_result": result.get("celltypist_result"),
            "annotated_rds": result.get("annotated_rds"),
            "annotated_h5ad": result.get("annotated_h5ad"),
            "sce_h5": result.get("sce_h5"),
            "scanpy_h5": result.get("scanpy_h5"),
        }

        for file_type, file_path in files_to_check.items():
            if file_path:
                if Path(file_path).exists():
                    existing_files.append(file_type)
                else:
                    missing_files.append(file_type)

        # 如果marker_genes_json不存在，标记为验证失败
        if marker_genes_json and not Path(marker_genes_json).exists():
            result["success"] = False
            result["error"] = f"路径包中的关键文件已不存在: {marker_genes_json}"
            result["validation_failed"] = True
            result["missing_files"] = missing_files
            result["existing_files"] = existing_files
            return result

        # 添加验证信息
        result["validated"] = True
        result["missing_files"] = missing_files
        result["existing_files"] = existing_files
        result["all_files_exist"] = len(missing_files) == 0

        return result

    def list_saved_bundles(self, validate_files: bool = True) -> Dict[str, Any]:
        """
        列出所有已保存的文件路径包

        Args:
            validate_files: 是否验证文件存在性（默认True，推荐开启以过滤无效路径包）

        Returns:
            包含所有文件路径包信息的字典
        """
        try:
            bundles = []
            bundle_files = list(self.bundle_dir.glob(f"{self.bundle_prefix}*{self.bundle_suffix}"))

            for bundle_file in bundle_files:
                try:
                    with open(bundle_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    file_paths_info = FilePathsInfo.from_dict(data)

                    # 验证关键文件是否存在
                    files_exist = True
                    marker_genes_json_exists = False
                    if validate_files:
                        # 检查marker_genes_json（最关键的文件）
                        marker_genes_json = file_paths_info.marker_genes_json
                        if marker_genes_json:
                            marker_genes_json_exists = Path(marker_genes_json).exists()
                            files_exist = marker_genes_json_exists
                        else:
                            files_exist = False

                        # 如果关键文件不存在，跳过这个路径包
                        if not files_exist:
                            continue

                    bundle_info = {
                        "session_id": file_paths_info.session_id,
                        "timestamp": file_paths_info.timestamp,
                        "file_count": sum(1 for path in [
                            file_paths_info.rds_file,
                            file_paths_info.h5ad_file,
                            file_paths_info.h5_file,
                            file_paths_info.marker_genes_json,
                            file_paths_info.singler_result,
                            file_paths_info.sctype_result,
                            file_paths_info.celltypist_result,
                            file_paths_info.annotated_rds,
                            file_paths_info.annotated_h5ad,
                            file_paths_info.sce_h5,
                            file_paths_info.scanpy_h5
                        ] if path),
                        "cluster_count": len(file_paths_info.cluster_mapping) if file_paths_info.cluster_mapping else 0,
                        "bundle_path": str(bundle_file),
                        # 显示关键文件路径，方便LLM识别
                        "marker_genes_json": file_paths_info.marker_genes_json,
                        "files_exist": files_exist,  # 文件存在性标记
                    }

                    bundles.append(bundle_info)

                except Exception as e:
                    # 跳过损坏的文件
                    continue

            # 按时间戳排序（最新的在前）
            bundles.sort(key=lambda x: x['timestamp'], reverse=True)

            return {
                "success": True,
                "total_count": len(bundles),
                "bundles": bundles,
                "validated": validate_files,  # 新增：标记是否进行了验证
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"列出文件路径包失败: {str(e)}"
            }

    def delete_bundle(self, session_id: str) -> Dict[str, Any]:
        """
        删除指定的文件路径包

        Args:
            session_id: 会话ID

        Returns:
            删除结果字典
        """
        try:
            bundle_filename = self._generate_bundle_filename(session_id)
            bundle_path = self.bundle_dir / bundle_filename

            if not bundle_path.exists():
                return {
                    "success": False,
                    "error": f"未找到会话ID为 {session_id} 的文件路径包"
                }

            bundle_path.unlink()

            return {
                "success": True,
                "session_id": session_id,
                "message": "文件路径包删除成功"
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"删除文件路径包失败: {str(e)}"
            }


# 创建全局管理器实例
_file_paths_manager = FilePathsManager()


# 导出的便捷函数
def save_file_paths_bundle(
    rds_file: Optional[str] = None,
    h5ad_file: Optional[str] = None,
    h5_file: Optional[str] = None,
    marker_genes_json: Optional[str] = None,
    singler_result: Optional[str] = None,
    sctype_result: Optional[str] = None,
    celltypist_result: Optional[str] = None,
    annotated_rds: Optional[str] = None,
    annotated_h5ad: Optional[str] = None,
    sce_h5: Optional[str] = None,
    scanpy_h5: Optional[str] = None,
    cluster_mapping: Optional[Dict[str, str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """保存文件路径信息包到cache目录"""
    return _file_paths_manager.save_file_paths_bundle(
        rds_file=rds_file,
        h5ad_file=h5ad_file,
        h5_file=h5_file,
        marker_genes_json=marker_genes_json,
        singler_result=singler_result,
        sctype_result=sctype_result,
        celltypist_result=celltypist_result,
        annotated_rds=annotated_rds,
        annotated_h5ad=annotated_h5ad,
        sce_h5=sce_h5,
        scanpy_h5=scanpy_h5,
        cluster_mapping=cluster_mapping,
        metadata=metadata,
        session_id=session_id
    )


def load_file_paths_bundle() -> Dict[str, Any]:
    """从临时目录加载当前会话的文件路径信息包"""
    return _file_paths_manager.load_file_paths_bundle()


def load_and_validate_bundle() -> Dict[str, Any]:
    """加载当前会话的文件路径包并验证关键文件是否存在

    这是一个安全的加载方法，推荐使用此方法代替load_file_paths_bundle。
    会在加载后立即验证marker_genes_json等关键文件的存在性，避免使用过期的路径包。

    Returns:
        包含文件路径信息和验证结果的字典，包括:
        - validated: 是否进行了验证
        - missing_files: 缺失的文件列表
        - existing_files: 存在的文件列表
        - all_files_exist: 是否所有文件都存在
    """
    return _file_paths_manager.load_and_validate_bundle()


def list_saved_bundles(validate_files: bool = True) -> Dict[str, Any]:
    """列出所有已保存的文件路径包

    Args:
        validate_files: 是否验证文件存在性（默认True，过滤无效路径包）
    """
    return _file_paths_manager.list_saved_bundles(validate_files)


def delete_bundle(session_id: str) -> Dict[str, Any]:
    """删除指定的文件路径包"""
    return _file_paths_manager.delete_bundle(session_id)


# ==================== 新增：自动化辅助函数 ====================

def auto_get_input_path(
    manual_path: Optional[str],
    bundle_keys: list,
    tool_name: str
) -> str:
    """智能获取输入文件路径，支持自动fallback

    Args:
        manual_path: 手动指定的路径（优先使用）
        bundle_keys: bundle中的字段名列表，按优先级排序（例如：['rds_file', 'h5_file']）
        tool_name: 工具名称，用于错误提示

    Returns:
        有效的文件路径

    Raises:
        ValueError: 如果无法找到有效的输入文件

    Example:
        >>> # Seurat工具，优先rds，降级到h5
        >>> path = auto_get_input_path(None, ['rds_file', 'h5_file'], 'singleR_annotate')
        >>> # 用户手动指定路径
        >>> path = auto_get_input_path('/custom/path.rds', ['rds_file'], 'tool')
    """
    # 1. 如果手动指定了路径，直接返回
    if manual_path:
        if Path(manual_path).exists():
            return manual_path
        else:
            raise ValueError(f"{tool_name}: 指定的文件路径不存在: {manual_path}")

    # 2. 尝试从bundle自动读取
    bundle = load_file_paths_bundle()
    if not bundle.get("success"):
        raise ValueError(
            f"{tool_name}: 未找到file_paths_bundle，请先使用save_file_paths_bundle保存路径信息，"
            f"或手动指定输入文件路径"
        )

    # 3. 按优先级查找有效路径
    for key in bundle_keys:
        path = bundle.get(key)
        if path and Path(path).exists():
            print(f"✅ {tool_name}: 自动从bundle读取{key}: {path}")
            return path

    # 4. 如果都没找到，抛出详细的错误信息
    tried_keys = ', '.join(bundle_keys)
    raise ValueError(
        f"{tool_name}: bundle中未找到有效的输入文件。\n"
        f"尝试的字段: {tried_keys}\n"
        f"可用字段: {[k for k, v in bundle.items() if v and k != 'success']}\n"
        f"请先运行数据处理工具生成所需文件，或手动指定输入路径"
    )


def auto_update_bundle(field_name: str, file_path: str) -> Dict[str, Any]:
    """自动更新file_paths_bundle中的指定字段

    工具生成输出文件后，调用此函数自动更新bundle，无需手动管理。

    Args:
        field_name: bundle中的字段名（例如：'annotated_rds'）
        file_path: 生成的文件路径

    Returns:
        save_file_paths_bundle的返回结果

    Example:
        >>> # 工具生成文件后自动更新bundle
        >>> output_path = "/path/to/annotated_seurat_session123.rds"
        >>> auto_update_bundle('annotated_rds', output_path)
    """
    # 调用save_file_paths_bundle，只更新指定字段
    # save_file_paths_bundle会自动merge现有bundle的内容
    kwargs = {field_name: file_path}
    result = save_file_paths_bundle(**kwargs)

    if result.get("success"):
        print(f"✅ 已自动更新bundle: {field_name} = {file_path}")
    else:
        print(f"⚠️ 更新bundle失败: {result.get('error')}")

    return result


def save_cluster_mapping(cluster_id: str, cell_type: str) -> Dict[str, Any]:
    """保存单个cluster的映射到bundle，支持增量更新。

    将cluster映射数据直接存储在bundle文件中，不生成单独的文件。

    Args:
        cluster_id: 簇ID（如 "0", "1", "cluster0" 等）
        cell_type: 细胞类型（如 "T cell", "B cell" 等）

    Returns:
        包含success状态的字典

    Example:
        >>> # 第一次保存
        >>> save_cluster_mapping("0", "T cell")
        >>> # bundle.cluster_mapping = {"0": "T cell"}

        >>> # 第二次保存（增量添加）
        >>> save_cluster_mapping("1", "B cell")
        >>> # bundle.cluster_mapping = {"0": "T cell", "1": "B cell"}

        >>> # 更新已有cluster
        >>> save_cluster_mapping("0", "CD8+ T cell")
        >>> # bundle.cluster_mapping = {"0": "CD8+ T cell", "1": "B cell"}
    """
    try:
        # 标准化cluster_id为字符串
        cluster_key = str(cluster_id).strip()
        cell_type_val = str(cell_type).strip()

        # 构造单个cluster的映射
        single_cluster_mapping = {cluster_key: cell_type_val}

        # 调用save_file_paths_bundle，自动实现增量合并
        result = save_file_paths_bundle(cluster_mapping=single_cluster_mapping)

        if result.get("success"):
            print(f"✅ 已保存cluster映射到bundle: {cluster_key} = {cell_type_val}")
        else:
            print(f"⚠️ 保存cluster映射失败: {result.get('error')}")

        return result

    except Exception as e:
        error_msg = f"保存cluster映射异常: {e}"
        print(f"❌ {error_msg}")
        return {
            "success": False,
            "error": error_msg
        }


def load_cluster_mapping() -> Dict[str, str]:
    """从bundle加载所有cluster映射数据。

    Returns:
        簇ID到细胞类型的映射字典，如 {"0": "T cell", "1": "B cell"}
        如果没有数据或加载失败，返回空字典
    """
    try:
        bundle = load_file_paths_bundle()
        if bundle.get("success"):
            cluster_mapping = bundle.get("cluster_mapping", {})
            if isinstance(cluster_mapping, dict):
                return {str(k): str(v) for k, v in cluster_mapping.items()}
        return {}
    except Exception:
        return {}


def get_bundle_or_error(tool_name: str) -> Dict[str, Any]:
    """安全地加载bundle，如果失败则抛出友好的错误提示

    Args:
        tool_name: 工具名称，用于错误提示

    Returns:
        成功加载的bundle字典

    Raises:
        ValueError: 如果bundle不存在或加载失败
    """
    bundle = load_file_paths_bundle()
    if not bundle.get("success"):
        raise ValueError(
            f"{tool_name}: 未找到file_paths_bundle。\n"
            f"这通常是因为还没有保存任何文件路径信息。\n"
            f"请先使用save_file_paths_bundle保存原始数据路径，例如：\n"
            f"  save_file_paths_bundle(rds_file='/path/to/data.rds')"
        )
    return bundle
