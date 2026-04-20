# AgentType

> 基于大语言模型的单细胞 RNA 测序细胞类型自动注释工具包

[![PyPI version](https://badge.fury.io/py/agentype.svg)](https://badge.fury.io/py/agentype)
[![Python Version](https://img.shields.io/pypi/pyversions/agentype.svg)](https://pypi.org/project/agentype/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[English](README.md)

## 安装

```bash
pip install agentype
```

安装可选依赖：

```bash
# CellTypist 注释算法
pip install agentype[annotation]

# 完整安装
pip install agentype[annotation,ml,viz]
```

## 配置

创建 `agentype_config.json`：

```json
{
  "llm": {
    "api_key": "your-api-key",
    "api_base": "https://api.openai.com/v1",
    "model": "gpt-4o"
  },
  "project": {
    "language": "zh",
    "enable_streaming": true,
    "enable_logging": true
  }
}
```

也可以通过环境变量配置：

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_API_BASE="https://api.openai.com/v1"
export OPENAI_MODEL="gpt-4o"
```

## 快速上手

### 完整工作流（推荐）

```python
from agentype.api.main_workflow import process_workflow_sync

result = process_workflow_sync(
    input_data="path/to/data.rds",      # 支持 RDS、H5AD、H5、CSV
    tissue_type="PBMC",                  # 组织类型
    cluster_column="seurat_clusters",    # 聚类列名
    api_key="your-api-key",
    api_base="https://api.openai.com/v1",
    model="gpt-4o",
    output_dir="./outputs",
    language="zh",                       # 'zh' 或 'en'
    enable_streaming=True,
    enable_llm_logging=True,
)

if result["success"]:
    print(f"Session ID:  {result['session_id']}")
    print(f"迭代次数:    {result['total_iterations']}")
    print(f"输出文件:    {result['output_file_paths']}")
else:
    print(f"失败原因:    {result['error']}")
```

### 主要参数

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `input_data` | str | 输入文件路径 |
| `tissue_type` | str | 组织类型，如 `"PBMC"`、`"Liver"` |
| `cluster_column` | str | 数据中聚类标签的列名 |
| `species` | str \| None | 物种，`None` 时自动检测 |
| `api_key` | str | LLM API 密钥 |
| `api_base` | str | LLM API 地址 |
| `model` | str | 使用的模型名称 |
| `output_dir` | str | 结果输出目录 |
| `language` | str | Prompt 语言，`"zh"` 或 `"en"` |
| `enable_streaming` | bool | 是否启用流式输出 |
| `enable_thinking` | bool | 是否启用思考模式 |
| `enable_llm_logging` | bool | 是否记录 LLM 日志 |

### 返回值

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `success` | bool | 是否成功 |
| `session_id` | str | 本次会话 ID |
| `total_iterations` | int | Agent 迭代次数 |
| `output_file_paths` | dict | 输出文件路径，含 `rds_file` 等 |
| `result_file` | str | 汇总结果文件路径 |
| `token_stats` | dict | Token 消耗统计 |
| `error` | str | 失败时的错误信息 |

## 单独使用各 Agent

**AppAgent — 细胞类型注释：**

```python
from agentype.appagent.tools.celltypist_simple import celltypist_annotation

result = celltypist_annotation(
    adata_path="data.h5ad",
    model_name="Immune_All_Low.pkl",
    species="human"
)
```

**SubAgent — 细胞标记基因查询：**

```python
from agentype.subagent.tools.fetchers.cellmarker_fetcher import search_cell_markers

markers = search_cell_markers(
    gene_symbols=["CD4", "CD8A", "CD3E"],
    tissue_type="Blood"
)
```

**DataAgent — 数据格式转换：**

```python
from agentype.dataagent.tools.data_converters import convert_rds_to_h5ad

h5ad_path = convert_rds_to_h5ad(
    rds_path="data.rds",
    output_path="output.h5ad"
)
```

## 命令行工具

```bash
celltype-server          # 启动所有 MCP 服务器
celltype-manage status   # 查看项目状态
celltype-manage config   # 查看当前配置
```

## 许可证

MIT License
