#!/usr/bin/env python3
"""
agentype - AppAgent内容处理器
Author: cuilei
Version: 2.0

AppAgent的内容处理器，继承基类并添加注释结果处理方法。
保持原有类名CelltypeContentProcessor以避免破坏现有调用。
"""

import json
from typing import Dict, Any
from agentype.common.base_content_processor import BaseContentProcessor


class CelltypeContentProcessor(BaseContentProcessor):
    """AppAgent内容处理器

    继承BaseContentProcessor，并添加AppAgent特有的注释结果处理方法。
    主要处理SingleR、scType、CellTypist三种注释方法的结果。

    注：保持原有类名`CelltypeContentProcessor`以避免破坏现有的Agent类调用。
    """

    def process_annotation_result(self, content: str, method: str) -> str:
        """处理注释结果内容，根据不同方法优化输出

        Args:
            content: 原始内容
            method: 注释方法名称 (SingleR, scType, CellTypist)

        Returns:
            处理后的内容
        """
        # 不截断，保持内容完整性
        try:
            # 尝试解析JSON格式的注释结果
            result_data = json.loads(content)

            if method == "SingleR":
                return self._process_singler_result(result_data)
            elif method == "scType":
                return self._process_sctype_result(result_data)
            elif method == "CellTypist":
                return self._process_celltypist_result(result_data)
            else:
                return self._process_generic_result(result_data)

        except json.JSONDecodeError:
            # 非JSON内容直接返回
            return content

    def _process_singler_result(self, data: Dict[str, Any]) -> str:
        """处理SingleR注释结果"""
        if not isinstance(data, dict):
            return json.dumps({"method": "SingleR", "raw": data}, ensure_ascii=False, indent=2)

        # 提取关键信息
        processed = {
            "method": "SingleR",
            "success": data.get("success", False)
        }

        # 传递文件路径信息
        if data.get("output_file"):
            processed["output_file"] = data.get("output_file")
        # 有些实现把路径放在 data 字段
        if isinstance(data.get("data"), str):
            processed["output_file"] = data.get("data")
        if data.get("input_file"):
            processed["input_file"] = data.get("input_file")

        if data.get("success"):
            # 提取注释结果摘要（若上游提供）
            annotations = data.get("annotations", {})
            if annotations:
                cell_types = set()
                total_cells = 0

                for cluster, info in annotations.items():
                    if isinstance(info, dict):
                        cell_type = info.get("celltype", "Unknown")
                        cell_types.add(cell_type)
                        total_cells += info.get("cell_count", 0)

                processed["summary"] = {
                    "total_clusters": len(annotations),
                    "unique_cell_types": len(cell_types),
                    "identified_types": list(cell_types),
                    "total_cells": total_cells
                }

                # 如果簇数较少，保留详细信息
                if len(annotations) <= 10:
                    processed["cluster_annotations"] = annotations
                else:
                    # 只保留前5个簇的详细信息
                    top_clusters = dict(list(annotations.items())[:5])
                    processed["cluster_annotations"] = top_clusters
                    processed["note"] = f"显示前5个簇的详细信息，完整结果包含{len(annotations)}个簇"
        else:
            processed["error"] = data.get("error", "未知错误")

        return json.dumps(processed, ensure_ascii=False, indent=2)

    def _process_sctype_result(self, data: Dict[str, Any]) -> str:
        """处理scType注释结果"""
        if not isinstance(data, dict):
            return json.dumps({"method": "scType", "raw": data}, ensure_ascii=False, indent=2)

        processed = {
            "method": "scType",
            "success": data.get("success", False)
        }
        if data.get("output_file"):
            processed["output_file"] = data.get("output_file")
        if isinstance(data.get("data"), str):
            processed["output_file"] = data.get("data")
        if data.get("input_file"):
            processed["input_file"] = data.get("input_file")
        if data.get("tissue_type"):
            processed["tissue_type_used"] = data.get("tissue_type")

        if data.get("success"):
            annotations = data.get("annotations", {})
            tissue_type = data.get("tissue_type_used", "未知组织")

            if annotations:
                cell_types = []
                confidence_scores = []

                for cluster, info in annotations.items():
                    if isinstance(info, dict):
                        cell_type = info.get("celltype", "Unknown")
                        confidence = info.get("confidence", 0)
                        cell_types.append(cell_type)
                        confidence_scores.append(confidence)

                processed["summary"] = {
                    "tissue_type": tissue_type,
                    "total_clusters": len(annotations),
                    "identified_types": list(set(cell_types)),
                    "avg_confidence": sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
                }

                # 根据置信度排序，保留高置信度结果
                sorted_clusters = sorted(
                    annotations.items(),
                    key=lambda x: x[1].get("confidence", 0) if isinstance(x[1], dict) else 0,
                    reverse=True
                )

                if len(sorted_clusters) <= 8:
                    processed["cluster_annotations"] = dict(sorted_clusters)
                else:
                    processed["cluster_annotations"] = dict(sorted_clusters[:8])
                    processed["note"] = f"显示前8个高置信度簇，完整结果包含{len(annotations)}个簇"
        else:
            processed["error"] = data.get("error", "未知错误")

        return json.dumps(processed, ensure_ascii=False, indent=2)

    def _process_celltypist_result(self, data: Dict[str, Any]) -> str:
        """处理CellTypist注释结果"""
        if not isinstance(data, dict):
            return json.dumps({"method": "CellTypist", "raw": data}, ensure_ascii=False, indent=2)

        processed = {
            "method": "CellTypist",
            "success": data.get("success", False)
        }
        if data.get("output_file"):
            processed["output_file"] = data.get("output_file")
        if isinstance(data.get("data"), str):
            processed["output_file"] = data.get("data")
        if data.get("input_file"):
            processed["input_file"] = data.get("input_file")
        if data.get("model_name"):
            processed["model_used"] = data.get("model_name")

        if data.get("success"):
            annotations = data.get("annotations", {})
            model_used = data.get("model_used", "未知模型")

            if annotations:
                cell_types = []
                prediction_scores = []

                for cluster, info in annotations.items():
                    if isinstance(info, dict):
                        cell_type = info.get("predicted_labels", "Unknown")
                        score = info.get("prediction_score", 0)
                        cell_types.append(cell_type)
                        prediction_scores.append(score)

                processed["summary"] = {
                    "model_used": model_used,
                    "total_clusters": len(annotations),
                    "identified_types": list(set(cell_types)),
                    "avg_prediction_score": sum(prediction_scores) / len(prediction_scores) if prediction_scores else 0
                }

                # 根据预测分数排序
                sorted_clusters = sorted(
                    annotations.items(),
                    key=lambda x: x[1].get("prediction_score", 0) if isinstance(x[1], dict) else 0,
                    reverse=True
                )

                if len(sorted_clusters) <= 8:
                    processed["cluster_annotations"] = dict(sorted_clusters)
                else:
                    processed["cluster_annotations"] = dict(sorted_clusters[:8])
                    processed["note"] = f"显示前8个高预测分数簇，完整结果包含{len(annotations)}个簇"
        else:
            processed["error"] = data.get("error", "未知错误")

        return json.dumps(processed, ensure_ascii=False, indent=2)

    def _process_generic_result(self, data: Dict[str, Any]) -> str:
        """处理通用结果"""
        return json.dumps(data, ensure_ascii=False, indent=2)
