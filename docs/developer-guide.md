# 开发者文档


本文档介绍 **「入档 • 党员发展档案管理工具」** 的技术架构和开发说明，帮助开发者参与项目开发。

---

## 目录

- [部署项目](#部署项目)
- [整体结构](#整体结构)
- [模块设计](#模块设计)
- [开发工作](#开发工作)
- [获取帮助](#获取帮助)

---


## 部署项目

### 环境要求
- **Python**: = 3.10
- **操作系统**: Windows 10/11、macOS 10.15+、Linux（推荐 Ubuntu 20.04+）
- **IDE**: 依个人习惯

### 快速开始

#### 1. 克隆仓库

```bash
git clone https://github.com/chuqianjing/rule-done.git
cd rule-done
```

#### 2. 配置环境

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

# 安装依赖
pip install -r requirements.txt
```

#### 4. 运行程序

```bash
python main.py
```

---

## 整体结构

### 架构设计

系统采用经典的三层架构设计：

```
┌─────────────────────────────────────────────────────────────┐
│                        UI 层 (src/ui/)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  主窗口      │  │  页面组件   │  │      对话框部件      │  │
│  │ MainWindow  │  │  *_page.py  │  │      *_dialog       │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  应用层 (src/application/)                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐  │
│  │  DataManager    │  │ TemplateEngine  │  │ Permission  │  │
│  │  数据管理        │  │    模板引擎     │   │ Controller  │  │
│  └─────────────────┘  └─────────────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   持久层 (src/persistence/)                  │
│  ┌──────────────────────┐  ┌─────────────┐  ┌────────────┐  │
│  │ArX/Config/Info/SetMgr│  │ Fiel/TplMgr │  │ SyncMgr    │  │
│  │      用户数据         │  │   资源数据  │  │  网络数据   │  │
│  └──────────────────────┘  └─────────────┘  └────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      存储层 (data/, resources/)              │
│  ┌───────────────────────────┐  ┌─────────────────────────┐ │
│  │ data/                     │  │ resources/              │ │
│  │ 用户json数据               │  │ 字段规则定义             │ │
│  │ archive_images/ 档案图片   │  │ Word 模板文件 (.docx)   │ │
│  └───────────────────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```


### 目录结构

```
party-dev-system/
├── main.py                     # 程序入口
├── requirements.txt            # 依赖清单
│
├── src/
│   ├── application/            # 应用逻辑层
│   │   ├── __init__.py
│   │   ├── data_manager.py     # 数据管理器（门面类）
│   │   ├── template_engine.py  # 模板引擎
│   │   └── permission_controller.py  # 权限控制
│   │
│   ├── persistence/            # 数据持久层
│   │   ├── __init__.py
│   │   ├── config_manager.py   # 管理员配置管理
│   │   ├── info_manager.py     # 成员信息管理
│   │   ├── template_manager.py # 模板文件管理
│   │   ├── field_manager.py    # 字段定义管理
│   │   ├── settings_manager.py # 系统设置管理
│   │   ├── archive_manager.py  # 档案管理
│   │   └── sync_manager.py     # 同步管理
│   │
│   ├── ui/                     # 界面展示层
│   │   ├── __init__.py
│   │   ├── main_window.py      # 主窗口
│   │   ├── admin_home_page.py  # 管理员首页
│   │   ├── admin_list_page.py  # 管理员列表
│   │   ├── admin_template_page.py  # 管理员模板页
│   │   ├── admin_settings_page.py  # 管理员设置页
│   │   ├── member_home_page.py # 成员首页
│   │   ├── member_list_page.py # 成员列表
│   │   ├── member_template_page.py  # 成员模板页
│   │   ├── member_settings_page.py  # 成员设置页
│   │   ├── export_dialog.py    # 导出对话框
│   │   ├── password_dialog.py  # 密码对话框
│   │   └── list_page.py        # 列表页面基类
│   │
│   └── utils/                  # 工具模块
│       ├── __init__.py
│       ├── crypto_storage.py   # 加密存储
│       ├── json_storage.py     # JSON 存储
│       ├── styles.py           # 样式定义
│       ├── validators.py       # 验证器
│       ├── widget_binding.py   # 组件绑定
│       └── config_sync_thread.py  # 配置同步线程
│
├── resources/
│   ├── schema/
│   │   └── fields_definition.json  # 字段定义
│   ├── templates/              # Word 模板文件
│   │   ├── template_001_入党申请书.docx
│   │   ├── template_002_*.docx
│   │   └── ...
│   ├── icons/                  # 图标资源
│   └── images/                 # 图片资源
│
├── data/                       # 运行时数据（gitignore）
│   ├── admin_config.json
│   ├── member_info.json
│   ├── system_settings.json
│   └── archive_images/         # 归档图片
│
└── exports/                    # 导出文件目录（gitignore）
```

---

## 模块设计

### 核心模块

#### 1. UI 层 (`src/ui/`)

负责用户界面展示和交互。

**主窗口** (`main_window.py`)

- 管理整体布局：侧边导航栏 + 内容区域
- 使用 `QStackedWidget` 实现页面切换
- 维护所有页面实例的缓存（管理员/成员模式）
- 处理模式切换、配置同步、密码验证

**页面组件**

| 文件 | 管理员模式 | 成员模式 | 功能 |
|------|-----------|---------|------|
| `*_home_page.py` | AdminHomePage | MemberHomePage | 基本信息编辑 |
| `*_list_page.py` | AdminListPage | MemberListPage | 模板列表展示 |
| `*_template_page.py` | AdminTemplatePage | MemberTemplatePage | 模板详情/填写 |
| `*_settings_page.py` | AdminSettingsPage | MemberSettingsPage | 通用设置 |

#### 2. 应用层 (`src/application/`)

封装核心业务逻辑。

**DataManager** (`data_manager.py`)

数据管理的统一入口，协调各个 Manager 的操作：

```python
class DataManager:
    def __init__(self):
        self.config_manager = ConfigManager()    # 管理员配置
        self.info_manager = InfoManager()        # 成员信息
        self.template_manager = TemplateManager()# 模板管理
        self.field_manager = FieldManager()      # 字段定义
        self.settings_manager = SettingsManager()# 系统设置
        self.image_manager = ArchiveManager()    # 存档管理
      self.sync_manager = SyncManager() # 同步管理
```

#### 飞书多维表格同步（成员端）

当前版本已支持成员基本信息同步至飞书多维表格，采用客户端直连 API：

- 配置落点：`system_settings.info_sync.feishu`
- 敏感字段：`app_secret` 使用 `enc::` 前缀加密存储
- 同步策略：按 `id_field`（默认「身份证号」）执行 upsert（先查后更 / 无则创建）
- 线程模型：通过 `InfoSyncThread` 异步执行，避免 UI 阻塞

关键代码位置：

- `src/persistence/sync_manager.py`
      - `test_info_sync_connection(provider, info_sync_config)`
      - `upload_member_basic_data(provider, basic_data, info_sync_config)`
- `src/application/data_manager.py`
      - `save_info_sync_provider_settings(provider, provider_config)`
      - `test_info_sync_connection(provider)`
      - `push_member_basic_data_to_remote(provider)`
- `src/ui/member_home_page.py`
      - 手动同步按钮
      - 保存后自动同步

排障建议：

- 401/403：优先检查飞书应用权限和 `app_secret` 是否正确。
- 404：检查 `app_token` 与 `table_id` 是否匹配同一多维表。
- 查询不到记录：确认唯一标识字段名与飞书列名一致（包括中文全角字符）。
- 429：飞书限流，建议在 UI 端提示稍后重试。

核心职责：提供除模板文件操作外的几乎所有数据操作的接口，并进行必要的处理。

**TemplateEngine** (`template_engine.py`)

模板处理引擎，负责：

- 解析 Word 模板中的占位符，并为其匹配合适的字段定义
- 管理占位符到数据源的映射 `mapping`
- 使用 `docxtpl` 进行模板渲染，生成最终的 Word 文档

其中，占位符到其数据源的映射 `mapping` 字典，是成员端「模板详情」页中字段信息呈现、文档占位符填充、以及实现配置快照机制的核心数据结构。其结构如下：

```python
mapping[placeholder] = {
      "source": "admin_basic_data",   # 必选键值：数据源
      "key": placeholder,             # 可选键值：其值可不必为 placeholder
      "is_tip": True,                 # 可选键值
      }
```

**PermissionController** (`permission_controller.py`)

权限控制，管理运行模式：

- `user` - 用户模式（可自由切换）
- `admin` - 管理员模式
- `member` - 成员模式

#### 3. 持久层 (`src/persistence/`)

负责数据持久化和访问。

**ConfigManager** (`config_manager.py`)

管理 `admin_config.json`：

```json
{
  "version": "1.0.0",
  "basic_data": {
    "支部信息": { "支部名称": "...", "支部书记": "..." },
    "上级党委信息": { ... },
    "公共字段": { ... },
    "交互设置": { ... }
  },
  "template_data": {
    "template_001": { ... },
    "template_002": { ... }
  }
}
```

**InfoManager** (`info_manager.py`)

管理 `member_info.json`：

```json
{
  "version": "1.0.0",
  "basic_data": {
    "姓名": "...",
    "性别": "...",
    "出生日期": "..."
  },
  "template_data": {
    "template_001": { "locked": false, "fields": { ... } },
    "template_002": { ... }
  }
}
```

**FieldManager** (`field_manager.py`)

读取 `fields_definition.json`，提供字段定义信息：

- 管理员字段（admin_fields）
- 成员字段（member_fields）
- 模板字段（template_fields）

**TemplateManager** (`template_manager.py`)

管理 Word 模板文件，提供模板列表和元信息。

**ArchiveManager** (`archive_manager.py`)

存档图片的本地存储：

- 图片格式校验（支持 JPG/JPEG/PNG/BMP/WEBP）
- 目录管理与文件复制
- 同名冲突处理（自动重命名）

**SyncManager** (`sync_manager.py`)

支持管理员配置的远程同步：

- 支持 GitHub 和阿里云 OSS 两种云端存储仓库
- 配置上传、下载、连接测试
- 敏感字段的加密/解密

**SettingsManager** (`sync_manager.py`)

管理系统设置的相关信息。

### 数据流向

#### 1. 管理员配置流程

```
管理员填写表单
      │
      ▼
AdminHomePage / AdminTemplatePage
      │
      ▼
DataManager.save_admin_config()
      │
      ▼
ConfigManager.save()
      │
      ▼
admin_config.json (可选加密)
```

#### 2. 成员填写流程

```
成员填写表单
      │
      ▼
MemberHomePage / MemberTemplatePage
      │
      ▼
DataManager.save_member_info()
      │
      ▼
InfoManager.save()
      │
      ▼
member_info.json (可选加密)
```

#### 3. 文档生成流程

```
用户点击导出
      │
      ▼
TemplateEngine.render_template()
      │
      ├── 读取 Word 模板
      ├── 合并管理员配置 + 成员信息
      ├── 应用占位符映射
      ├── 使用 docxtpl 渲染
      │
      ▼
生成 .docx 文件
```

#### 4. 配置同步流程

```
程序启动（成员模式）
      │
      ▼
检查 admin_config 中的同步 URL
      │
      ▼
ConfigSyncThread（后台线程）
      │
      ├── 请求远程配置
      ├── 比对文件时效性
      ├── 如有更新，覆盖本地配置
      │
      ▼
通知 UI 刷新
```
---

## 开发工作

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
chore: 杂项
```

### 常用开发任务

#### 添加新页面

2. 在 `src/ui/` 创建新的页面文件：

```python
# src/ui/new_page.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

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

#### 配置远程同步

使用 `SyncManager` 配置远程同步，目前支持 GitHub 和阿里云 OSS，可增加更多云存储方式。

```python
# 1. 在 SyncManager 的 get_default_config 方法中增加新方式的默认配置
"new_one": {
    "...": "...",
    ......
    },

# 2. 在 SyncManager 的编写上传本地json至远程仓库的方法
def _upload_to_new(self, *args):
    pass

# 3. 在 admin_settings_page.py 编写相关组件
......
```

---

## 获取帮助

- 查看 [贡献指南](../CONTRIBUTING.md) 了解如何提交代码
- 在 GitHub 提交 Issue 或 Discussion
