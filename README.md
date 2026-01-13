# AgentType

> 统一的细胞类型分析工具包，集成四个专业 Agent 提供完整的细胞类型注释流程

[![PyPI version](https://badge.fury.io/py/agentype.svg)](https://badge.fury.io/py/agentype)
[![Python Version](https://img.shields.io/pypi/pyversions/agentype.svg)](https://pypi.org/project/agentype/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 核心特性

- **四大专业 Agent**：MainAgent（主调度）、SubAgent（基因查询）、DataAgent（数据处理）、AppAgent（细胞注释）
- **多种注释算法**：集成 SingleR、scType、CellTypist 等主流算法
- **灵活的数据格式**：支持 RDS、H5AD、H5、CSV、JSON 等多种格式
- **国际化支持**：内置中文和英文双语 Prompt 系统
- **MCP 协议**：基于 Model Context Protocol 的 Agent 间通信
- **完善的日志**：统一的日志管理和结果输出系统

## 快速开始

### 安装

```bash
pip install agentype
```

### 配置

创建配置文件 `agentype_config.json`：

```json
{
  "llm": {
    "api_key": "your-api-key-here",
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

或使用环境变量：

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_API_BASE="https://api.openai.com/v1"
export OPENAI_MODEL="gpt-4o"
```

### 基本使用

#### 完整工作流（推荐）

使用 MainAgent 的完整工作流进行细胞类型注释：

```python
from agentype.api.main_workflow import process_workflow_sync

# 处理单细胞数据
result = process_workflow_sync(
    input_data="path/to/your_data.rds",  # 支持 RDS, H5AD, H5 等格式
    tissue_type="PBMC",                   # 组织类型
    cluster_column="seurat_clusters",     # 聚类列名
    # LLM 配置
    api_key="your-api-key",
    api_base="https://api.openai.com/v1",
    model="gpt-4o",
    # 输出配置
    output_dir="./outputs",
    language="zh",                        # 'zh' 或 'en'
    enable_streaming=True,
    enable_llm_logging=True
)

# 查看结果
if result['success']:
    print(f"Session ID: {result['session_id']}")
    print(f"结果文件: {result['result_file']}")
    print(f"输出文件: {result['output_file_paths']}")
    print(f"Token 统计: {result['token_stats']}")
else:
    print(f"处理失败: {result['error']}")
```

#### 单独使用各个 Agent

**AppAgent - 细胞类型注释**：

```python
from agentype.appagent.tools.celltypist_simple import celltypist_annotation

# 使用 CellTypist
result = celltypist_annotation(
    adata_path="your_data.h5ad",
    model_name="Immune_All_Low.pkl",
    species="human"
)
```

**SubAgent - 基因查询**：

```python
from agentype.subagent.tools.fetchers.cellmarker_fetcher import search_cell_markers

# 查询细胞标记基因
markers = search_cell_markers(
    gene_symbols=["CD4", "CD8A", "CD3E"],
    tissue_type="Blood"
)
```

**DataAgent - 数据格式转换**：

```python
from agentype.dataagent.tools.data_converters import convert_rds_to_h5ad

# 转换 RDS 到 H5AD
h5ad_path = convert_rds_to_h5ad(
    rds_path="your_data.rds",
    output_path="output.h5ad"
)
```

### 命令行工具

```bash
# 启动所有 MCP 服务器
celltype-server

# 项目管理工具
celltype-manage status      # 查看项目状态
celltype-manage config      # 查看配置
celltype-manage examples    # 运行示例
```

## 测试数据

由于文件大小限制，测试数据未包含在仓库中。

### 使用自己的数据

AgentType 支持多种单细胞数据格式：

- **H5AD** (推荐): Scanpy/AnnData 格式
  ```python
  import scanpy as sc
  adata = sc.read_h5ad("your_data.h5ad")
  ```

- **RDS**: R Seurat 对象
  ```python
  from agentype import convert_rds_to_h5ad
  adata = convert_rds_to_h5ad("your_data.rds")
  ```

- **H5/HDF5**: HDF5 格式
- **CSV/TSV**: 基因表达矩阵（行为基因，列为细胞）

### 示例数据集

你可以使用公开的单细胞数据集进行测试：

```python
import scanpy as sc

# 下载 Scanpy 内置的 PBMC 3k 数据集
adata = sc.datasets.pbmc3k()

# 使用 AgentType 进行分析
from agentype import annotate_cells
result = await annotate_cells(
    adata=adata,
    method="celltypist",
    species="human"
)
```

**推荐数据源**:
- [10X Genomics 公开数据集](https://www.10xgenomics.com/resources/datasets)
- [Scanpy 内置数据集](https://scanpy.readthedocs.io/en/stable/api.html#module-scanpy.datasets)
- [CELLxGENE 数据门户](https://cellxgene.cziscience.com/)

## 系统依赖

### Python 环境

- **Python 版本**: ≥ 3.8
- **核心依赖**: scanpy、pandas、numpy、fastapi 等（自动安装）

### R 环境（AppAgent 注释功能需要）

AgentType 的部分细胞注释功能依赖 R 语言和相关 R 包：

#### 安装 R（≥ 4.0）

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y r-base r-base-dev
```

**macOS:**
```bash
brew install r
```

**Windows:**
下载并安装：https://cran.r-project.org/bin/windows/base/

#### 安装 R 包

启动 R 控制台并安装以下包：

```r
# 安装 BiocManager
install.packages("BiocManager")

# 安装 SingleR（用于参考数据集注释）
BiocManager::install("SingleR")

# 安装其他依赖
install.packages(c("Seurat", "ggplot2", "dplyr"))
```

#### scType 数据库

scType 算法所需的数据库文件（ScTypeDB_full.xlsx）已内置在包中，无需额外下载。

### CellTypist（可选）

如需使用 CellTypist 算法：

```bash
pip install celltypist
```

### 可选依赖

```bash
# 机器学习功能
pip install agentype[ml]

# 数据可视化
pip install agentype[viz]

# 性能优化
pip install agentype[performance]

# 完整安装
pip install agentype[annotation,ml,viz,performance]
```

## 配置

### API 密钥设置

AgentType 使用 LLM 进行智能分析，需要配置 API 密钥：

```bash
export OPENAI_API_KEY="your-api-key-here"
export OPENAI_API_BASE="https://api.openai.com/v1"  # 可选
export OPENAI_MODEL="gpt-4"                         # 可选
```

### 语言切换

```bash
# 使用中文 Prompts（默认）
export CELLTYPE_LANGUAGE=zh

# 使用英文 Prompts
export CELLTYPE_LANGUAGE=en
```

## 文档

- [API 文档](docs/api.md) - 详细的 API 使用说明
- [安装指南](docs/installation.md) - 完整的安装和配置说明
- [配置说明](docs/configuration.md) - 高级配置选项
- [包信息](docs/package_info.md) - 包结构和组织说明
- [更新日志](docs/changelog.md) - 版本历史和变更记录

## 四大 Agent 功能

### MainAgent - 主调度器
统一工作流编排，协调其他 Agent，管理复杂分析流程。

```python
from agentype import process_workflow

result = await process_workflow(
    task="分析基因表达数据并注释细胞类型",
    data_path="your_data.h5ad"
)
```

### SubAgent - 基因查询服务
提供基因信息查询、细胞标记查询和富集分析。

```python
from agentype import analyze_genes

result = await analyze_genes(
    genes=["CD4", "CD8A", "CD3E"],
    analysis_type="marker_search"
)
```

### DataAgent - 数据处理专家
支持多种数据格式转换、质量控制和预处理。

```python
from agentype import process_data

result = await process_data(
    input_path="data.rds",
    output_format="h5ad",
    qc=True
)
```

### AppAgent - 细胞注释工具
集成 SingleR、scType、CellTypist 等主流注释算法。

```python
from agentype import annotate_cells

result = await annotate_cells(
    data_path="your_data.h5ad",
    method="singler",
    reference="BlueprintEncodeData"
)
```

## 示例代码

项目提供了一个简单直接的使用示例。

### 完整工作流示例

```bash
# 1. 创建配置文件
cp agentype_config.example.json agentype_config.json
# 编辑配置，填入您的 API key

# 2. 运行示例
python -m agentype.examples.complete_workflow_example
```

这个示例展示了如何使用 `process_workflow_sync` API 处理单个文件，是最推荐的使用方式。详见 [examples/README.md](agentype/examples/README.md)。

## 环境检查

安装后可使用以下命令检查环境配置：

```python
from agentype import check_environment

# 检查 Python 依赖
check_environment(check_r=False)

# 检查 R 环境和 R 包
check_environment(check_r=True)
```

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 支持与反馈

如遇到问题或有建议，请：
1. 查看详细日志（默认位置：`outputs/logs/`）
2. 检查配置文件（`~/.config/agentype/config.json` 或项目目录下的配置文件）
3. 参考 [文档](docs/) 目录中的详细说明

## 版本信息

当前版本：**1.0.1**

主要更新：
- 统一配置管理系统
- 集中式输出目录
- 标准化的 API 接口
- 完整的文档和示例
- 国际化支持（中英文）
