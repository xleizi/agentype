# AgentType 使用示例

## 完整工作流示例

`complete_workflow_example.py` 展示了最简单直接的使用方式，推荐所有用户使用。

### 运行步骤

```bash
# 1. 创建配置文件
cp ../agentype_config.example.json ../agentype_config.json
# 编辑配置文件，填入您的 API key

# 2. 运行示例
python complete_workflow_example.py
```

### 功能说明

- 使用 `process_workflow_sync` 高层 API
- 从配置文件读取 LLM 和项目设置
- 处理单个数据文件
- 完整的细胞类型注释流程
- 输出分析结果和 Token 统计信息

### 示例代码结构

```python
from agentype.api.main_workflow import process_workflow_sync

# 1. 加载配置
config = load_config("./agentype_config.json")

# 2. 调用完整工作流
result = process_workflow_sync(
    input_data="your_data.rds",
    tissue_type="PBMC",
    cluster_column="seurat_clusters",
    api_key=config["llm"]["api_key"],
    api_base=config["llm"]["api_base"],
    model=config["llm"]["model"],
    output_dir="./outputs",
    language=config["project"]["language"],
    enable_streaming=config["project"]["enable_streaming"],
    enable_llm_logging=config["project"]["enable_logging"]
)

# 3. 处理结果
if result['success']:
    print(f"Session ID: {result['session_id']}")
    print(f"结果文件: {result['result_file']}")
```

---

## 配置说明

### 配置文件

所有示例都使用 `agentype_config.json` 配置文件（位于项目根目录）：

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

**创建配置**:
```bash
cp agentype_config.example.json agentype_config.json
# 然后编辑 agentype_config.json，填入您的 API key
```

### 环境变量（可选）

也可以使用环境变量配置：

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_API_BASE="https://api.openai.com/v1"
export OPENAI_MODEL="gpt-4o"
```

---

## 输出文件

所有结果保存在 `outputs/` 目录：

```
outputs/
├── cache/          # 缓存数据库文件
├── logs/           # 运行日志
├── results/        # 分析结果（JSON, CSV 等）
└── downloads/      # 下载的参考数据
```

---

## 测试数据

由于文件大小限制，测试数据不包含在仓库中。您可以：

1. **使用自己的数据**（推荐）
   - 支持格式：RDS, H5AD, H5, CSV, JSON
   - 确保数据包含聚类信息（如 `seurat_clusters` 列）

2. **下载公开数据集**:
   - [10X Genomics 数据](https://www.10xgenomics.com/resources/datasets)
   - [Scanpy 内置数据](https://scanpy.readthedocs.io/en/stable/api.html#module-scanpy.datasets)

---

## 使用建议

1. **首次使用**: 先用小数据集测试（如 1000 个细胞）
2. **批量处理**: 参考示例代码，添加循环处理多个文件
3. **自定义参数**: 根据您的数据调整 `tissue_type` 和 `cluster_column`

---

## 常见问题

**Q: 如何处理多个文件？**

A: 在示例代码基础上添加循环：
```python
files = ["data1.rds", "data2.rds", "data3.rds"]
for file in files:
    result = process_workflow_sync(input_data=file, ...)
```

**Q: 如何更改输出目录？**

A: 修改 `output_dir` 参数：
```python
result = process_workflow_sync(..., output_dir="/path/to/outputs")
```

**Q: 遇到错误怎么办？**

A:
1. 查看 `outputs/logs/` 目录的日志文件
2. 确认配置文件格式正确
3. 检查 API key 是否有效
4. 参考项目根目录的 `README.md`
