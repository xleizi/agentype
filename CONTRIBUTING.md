# 贡献指南

感谢您考虑为 AgentType 做出贡献！

## 开发环境设置

1. Fork 本仓库并克隆到本地
2. 创建虚拟环境并安装依赖：
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -e ".[dev]"
   ```

3. 创建新分支进行开发：
   ```bash
   git checkout -b feature/your-feature-name
   ```

## 代码规范

- 使用 Black 格式化代码：`black .`
- 使用 Ruff 进行代码检查：`ruff check agentype/`
- 使用 MyPy 进行类型检查：`mypy agentype/`

## 测试

运行测试套件：
```bash
pytest tests/ -v
```

## 提交规范

提交信息格式：
- `feat: 添加新功能`
- `fix: 修复bug`
- `docs: 更新文档`
- `refactor: 代码重构`
- `test: 添加测试`
- `chore: 构建/工具链更新`

## Pull Request 流程

1. 确保所有测试通过
2. 更新相关文档
3. 在 PR 中详细描述更改内容
4. 等待代码审查

## 行为准则

请遵守 [Code of Conduct](CODE_OF_CONDUCT.md)。

## 问题反馈

如有问题或建议，请在 [Issues](https://github.com/yourusername/agentype/issues) 中提出。
