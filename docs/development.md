# 开发指南

本文档帮助开发者搭建开发环境并参与项目开发。

---

## 环境要求

- **Python**: >= 3.10
- **操作系统**: Windows 10/11、macOS 10.15+、Linux（推荐 Ubuntu 20.04+）
- **IDE**: 推荐 VS Code 或 PyCharm

---

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/chuqianjing/party-dev-system.git
cd party-dev-system
```

### 2. 创建虚拟环境

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Windows (CMD)
venv\Scripts\activate.bat

# macOS / Linux
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 运行程序

```bash
python main.py
```

首次运行会进入开发者模式，可选择以管理员或成员身份体验。

---

## 项目结构

```
party-dev-system/
├── main.py                 # 程序入口
├── requirements.txt        # 依赖清单
├── src/
│   ├── business/           # 业务逻辑层
│   ├── data/               # 数据访问层
│   ├── ui/                 # 界面层
│   └── utils/              # 工具模块
├── resources/
│   ├── templates/          # Word 模板
│   └── fields_definition.json
├── data/                   # 运行时数据（不要提交）
├── exports/                # 导出目录（不要提交）
└── docs/                   # 文档
```

详细架构说明请参阅 [架构设计](architecture.md)。

---

## 开发配置

### VS Code 推荐配置

创建 `.vscode/settings.json`：

```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
    "python.formatting.provider": "black",
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "editor.formatOnSave": true,
    "editor.rulers": [100],
    "files.exclude": {
        "**/__pycache__": true,
        "**/*.pyc": true,
        ".venv": true,
        "venv": true
    }
}
```

### PyCharm 配置

1. 打开项目设置 (File → Settings)
2. 设置 Python Interpreter 为虚拟环境中的 Python
3. 启用 PEP 8 代码检查

---

## 开发工作流

### 分支命名规范

```bash
feature/xxx    # 新功能
fix/xxx        # Bug 修复
docs/xxx       # 文档更新
refactor/xxx   # 代码重构
```

### 提交信息规范

```bash
feat: 添加 PDF 导出功能
fix: 修复模板编码问题
docs: 更新用户手册
style: 格式化代码
refactor: 重构数据管理模块
test: 添加单元测试
chore: 更新依赖版本
```

---

## 常用开发任务

### 添加新页面

1. 在 `src/ui/` 创建新的页面文件：

```python
# src/ui/new_page.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

class NewPage(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.addWidget(QLabel("新页面"))
        self.setLayout(layout)
```

2. 在 `main_window.py` 中注册页面：

```python
from src.ui.new_page import NewPage

# 在 MainWindow 类中添加
def show_new_page(self):
    if self.new_page is None:
        self.new_page = NewPage()
        self.stacked_widget.addWidget(self.new_page)
    self.stacked_widget.setCurrentWidget(self.new_page)
```

### 添加新模板

1. 创建 Word 模板文件，使用 `{{ 字段名 }}` 占位符
2. 命名为 `template_XXX_模板名称.docx`
3. 放入 `resources/templates/` 目录
4. 重启程序后自动加载

### 添加新字段

编辑 `resources/fields_definition.json`：

```json
{
  "member_fields": [
    {
      "key": "新字段",
      "type": "text",
      "required": true,
      "display": {
        "label": "新字段",
        "order": 20
      }
    }
  ]
}
```

支持的字段类型：
- `text` - 单行文本
- `textarea` - 多行文本
- `select` - 下拉选择
- `date` - 日期选择
- `number` - 数字

---

## 调试技巧

### 启用调试日志

在代码中添加：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.debug("调试信息")
logger.info("一般信息")
logger.warning("警告信息")
logger.error("错误信息")
```

### 使用 Qt Designer

PyQt6 支持使用 Qt Designer 可视化设计界面：

```bash
pip install PyQt6-tools
pyqt6-tools designer
```

### 调试模板渲染

```python
from src.application.template_engine import TemplateEngine

engine = TemplateEngine()
# 查看模板中的占位符
placeholders = engine.get_placeholders("template_001")
print(placeholders)
```

---

## 测试

### 运行测试（待完善）

```bash
# 安装测试依赖
pip install pytest pytest-qt

# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_data_manager.py

# 运行并显示详细输出
pytest -v
```

### 编写测试

```python
# tests/test_data_manager.py
import pytest
from src.application.data_manager import DataManager

def test_save_and_load_config():
    dm = DataManager()
    dm.save_admin_config("basic_data", "支部信息", "支部名称", "测试支部")
    value = dm.get_admin_config("basic_data", "支部信息", "支部名称")
    assert value == "测试支部"
```

---

## 打包发布

### 使用 PyInstaller 打包

```bash
# 安装 PyInstaller
pip install pyinstaller

# 打包为单文件可执行程序
pyinstaller --onefile --windowed --name="党员材料系统" main.py

# 打包为目录形式
pyinstaller --onedir --windowed --name="党员材料系统" main.py
```

### 打包配置文件

创建 `party-dev-system.spec`：

```python
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('resources', 'resources'),
    ],
    hiddenimports=['PyQt6'],
    ...
)
```

然后运行：

```bash
pyinstaller party-dev-system.spec
```

---

## 常见问题

### Q: PyQt6 安装失败

A: 尝试：
```bash
pip install --upgrade pip
pip install PyQt6 --no-cache-dir
```

### Q: 运行时找不到模块

A: 确保：
1. 虚拟环境已激活
2. 依赖已安装：`pip install -r requirements.txt`
3. 从项目根目录运行：`python main.py`

### Q: 模板修改后不生效

A: 模板文件在程序启动时加载，修改后需要重启程序。

### Q: 如何重置所有数据

A: 删除 `data/` 目录下的所有 JSON 文件，然后重新启动程序。

---

## 获取帮助

- 阅读 [架构文档](architecture.md) 了解代码结构
- 查看 [贡献指南](../CONTRIBUTING.md) 了解如何提交代码
- 在 GitHub 提交 Issue 或 Discussion
