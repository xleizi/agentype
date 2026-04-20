# AgentType

> LLM-powered automatic cell type annotation toolkit for single-cell RNA sequencing

[![PyPI version](https://badge.fury.io/py/agentype.svg)](https://badge.fury.io/py/agentype)
[![Python Version](https://img.shields.io/pypi/pyversions/agentype.svg)](https://pypi.org/project/agentype/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[中文文档](README_zh.md)

## Installation

```bash
pip install agentype
```

Optional dependencies:

```bash
# CellTypist annotation algorithm
pip install agentype[annotation]

# Full installation
pip install agentype[annotation,ml,viz]
```

## Configuration

Create `agentype_config.json`:

```json
{
  "llm": {
    "api_key": "your-api-key",
    "api_base": "https://api.openai.com/v1",
    "model": "gpt-4o"
  },
  "project": {
    "language": "en",
    "enable_streaming": true,
    "enable_logging": true
  }
}
```

Or configure via environment variables:

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_API_BASE="https://api.openai.com/v1"
export OPENAI_MODEL="gpt-4o"
```

## Quick Start

### Full Workflow (Recommended)

```python
from agentype.api.main_workflow import process_workflow_sync

result = process_workflow_sync(
    input_data="path/to/data.rds",      # supports RDS, H5AD, H5, CSV
    tissue_type="PBMC",                  # tissue type
    cluster_column="seurat_clusters",    # cluster label column
    api_key="your-api-key",
    api_base="https://api.openai.com/v1",
    model="gpt-4o",
    output_dir="./outputs",
    language="en",                       # 'en' or 'zh'
    enable_streaming=True,
    enable_llm_logging=True,
)

if result["success"]:
    print(f"Session ID:       {result['session_id']}")
    print(f"Iterations:       {result['total_iterations']}")
    print(f"Output files:     {result['output_file_paths']}")
else:
    print(f"Error:            {result['error']}")
```

### Parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `input_data` | str | Path to input file |
| `tissue_type` | str | Tissue type, e.g. `"PBMC"`, `"Liver"` |
| `cluster_column` | str | Column name of cluster labels in the data |
| `species` | str \| None | Species; auto-detected when `None` |
| `api_key` | str | LLM API key |
| `api_base` | str | LLM API base URL |
| `model` | str | Model name |
| `output_dir` | str | Directory for output files |
| `language` | str | Prompt language: `"en"` or `"zh"` |
| `enable_streaming` | bool | Enable streaming output |
| `enable_thinking` | bool | Enable thinking mode |
| `enable_llm_logging` | bool | Enable LLM call logging |

### Return Value

| Field | Type | Description |
| --- | --- | --- |
| `success` | bool | Whether the run succeeded |
| `session_id` | str | Session ID for this run |
| `total_iterations` | int | Number of agent iterations |
| `output_file_paths` | dict | Output paths, including `rds_file` |
| `result_file` | str | Path to the summary result file |
| `token_stats` | dict | Token usage statistics |
| `error` | str | Error message on failure |

## Using Individual Agents

**AppAgent — cell type annotation:**

```python
from agentype.appagent.tools.celltypist_simple import celltypist_annotation

result = celltypist_annotation(
    adata_path="data.h5ad",
    model_name="Immune_All_Low.pkl",
    species="human"
)
```

**SubAgent — cell marker gene query:**

```python
from agentype.subagent.tools.fetchers.cellmarker_fetcher import search_cell_markers

markers = search_cell_markers(
    gene_symbols=["CD4", "CD8A", "CD3E"],
    tissue_type="Blood"
)
```

**DataAgent — data format conversion:**

```python
from agentype.dataagent.tools.data_converters import convert_rds_to_h5ad

h5ad_path = convert_rds_to_h5ad(
    rds_path="data.rds",
    output_path="output.h5ad"
)
```

## CLI Tools

```bash
celltype-server          # Start all MCP servers
celltype-manage status   # Show project status
celltype-manage config   # Show current configuration
```

## License

MIT License
