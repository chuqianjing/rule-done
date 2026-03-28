# 贡献指南

感谢你对「党员发展材料生成系统」的关注！我们欢迎任何形式的贡献，无论是报告 Bug、提出建议还是提交代码。

## 如何参与贡献

### 报告 Bug

如果你发现了 Bug，请通过 [Issue](../../issues/new?template=bug_report.md) 提交，并尽量提供以下信息：

- 问题的详细描述
- 复现步骤
- 预期行为与实际行为
- 运行环境（操作系统、Python 版本）
- 相关截图或日志（如有）

### 提出功能建议

如果你有新功能的想法，欢迎通过 [Issue](../../issues/new?template=feature_request.md) 提交。请描述：

- 功能的具体需求
- 使用场景
- 是否愿意参与实现

### 提交代码

#### 1. Fork 仓库

点击页面右上角的 Fork 按钮，将仓库复制到你的账户下。

#### 2. 克隆到本地

```bash
git clone https://github.com/chuqianjing/party-dev-system.git
cd party-dev-system
```

#### 3. 创建分支

请使用有意义的分支名：

```bash
# 功能开发
git checkout -b feature/add-export-pdf

# Bug 修复
git checkout -b fix/template-encoding-error

# 文档改进
git checkout -b docs/update-user-guide
```

#### 4. 搭建开发环境

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

详细的开发环境配置请参阅 [开发指南](docs/development.md)。

#### 5. 进行修改

- 确保代码风格与项目一致
- 添加必要的注释
- 如涉及新功能，请更新相关文档

#### 6. 提交更改

请使用清晰的 commit message：

```bash
# 格式：<type>: <description>
# type 可选值：feat, fix, docs, style, refactor, test, chore

git commit -m "feat: 添加 PDF 导出功能"
git commit -m "fix: 修复模板编码问题"
git commit -m "docs: 更新用户手册"
```

#### 7. 推送并创建 Pull Request

```bash
git push origin feature/add-export-pdf
```

然后在 GitHub 页面创建 Pull Request，请：

- 填写 PR 模板中的所有必要信息
- 关联相关的 Issue（如有）
- 等待代码审查

## 代码规范

### Python 代码风格

- 遵循 [PEP 8](https://pep8.org/) 规范
- 使用 4 空格缩进
- 类名使用 `PascalCase`
- 函数和变量使用 `snake_case`
- 常量使用 `UPPER_CASE`

### 文档字符串

使用 Google 风格的 docstring：

```python
def calculate_date(start_date: str, days: int) -> str:
    """计算指定天数后的日期。

    Args:
        start_date: 起始日期，格式为 'YYYY-MM-DD'
        days: 要增加的天数

    Returns:
        计算后的日期字符串

    Raises:
        ValueError: 如果日期格式不正确
    """
    pass
```

### 提交信息规范

| 类型 | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 文档更新 |
| `style` | 代码格式（不影响功能） |
| `refactor` | 重构（不是新功能也不是修复） |
| `test` | 测试相关 |
| `chore` | 构建过程或辅助工具变动 |

## 首次贡献

如果你是第一次参与开源项目，可以从带有 `good first issue` 标签的 Issue 开始。这些通常是相对简单且范围明确的任务。

## 行为准则

参与本项目即表示你同意遵守我们的 [行为准则](CODE_OF_CONDUCT.md)。

## 获取帮助

如果在贡献过程中遇到任何问题，欢迎：

- 在相关 Issue 中提问
- 发起 Discussion 讨论

再次感谢你的贡献！
