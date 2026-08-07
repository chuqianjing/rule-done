# 开发者文档

本文档介绍 **「入档 • 党员发展档案管理工具」** 的技术架构和开发说明，帮助开发者参与项目开发。

---


## 目录

- [部署项目](#部署项目)
- [整体结构](#整体结构)
- [模块设计](#模块设计)
- [数据文件与运行时目录](#数据文件与运行时目录)
- [同步机制](#同步机制)
- [开发工作](#开发工作)
- [获取帮助](#获取帮助)

---

## 部署项目

### 环境要求
- **Python**: = 3.10
- **操作系统**: Windows 10/11、macOS 10.15+
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

#### 3. 运行程序

```bash
python main.py
```

> 程序首次启动时会自动在用户可写目录创建运行时数据（详见「[数据文件与运行时目录](#数据文件与运行时目录)」）。

---

## 整体结构

### 架构设计

系统采用「UI 层 → 应用层 → 持久层 → 存储层」的分层架构：

```
┌─────────────────────────────────────────────────────────────┐
│                        UI 层 (src/ui/)                      │
│  MainWindow + 各 *_page.py 页面 + *_dialog.py 对话框       │
└─────────────────────────────────────────────────────────────┘
                              │  仅通过 DataManager 访问数据
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  应用层 (src/application/)                   │
│  DataManager（门面） · TemplateEngine（模板引擎）           │
│  PermissionController（角色权限）                           │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   持久层 (src/persistence/)                  │
│  本地数据：Config / Info / Settings / Field / Template /    │
│            Archive                                         │
│  网络同步：SyncManagerBase（基类）                           │
│            ConfigSync / ResourceSync / InfoSync / SyncCrypto│
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│            存储层（运行时目录 + 内置只读资源）                │
│  <user_data_root>/data · exports · resources                │
│  项目内 resources/（随包分发的内置资源）                     │
└─────────────────────────────────────────────────────────────┘
```

**分层约定**

- UI 层**不得直接访问** `persistence` 中的各个 Manager，必须通过 `DataManager` 的方法访问数据；需要新能力时在 `data_manager.py` 中增加薄封装。
- 持久层负责数据读写与远程交互，不依赖 UI。
- 运行时目录由 `src/utils/file_path.py` 统一解析（详见「[数据文件与运行时目录](#数据文件与运行时目录)」）。

### 目录结构

```
rule-done/
├── main.py                     # 程序入口（QApplication、主题、主窗口）
├── main.spec                   # PyInstaller 打包配置
├── installer.iss               # Inno Setup 安装包脚本（CI 传入版本号）
├── requirements.txt            # 依赖清单
│
├── src/
│   ├── application/            # 应用逻辑层
│   │   ├── data_manager.py     # DataManager：UI 唯一数据入口（门面）
│   │   ├── template_engine.py  # TemplateEngine：占位符映射 + docx 渲染
│   │   └── permission_controller.py  # 角色模式管理（admin/member）
│   │
│   ├── persistence/            # 数据持久层
│   │   ├── config_manager.py   # 管理员配置（admin_config.json）
│   │   ├── info_manager.py     # 成员信息（member_info.json）
│   │   ├── settings_manager.py # 系统设置（system_settings.json）
│   │   ├── field_manager.py    # 字段定义（fields_definition.json）
│   │   ├── template_manager.py # 模板发现与元信息（templates_config.json）
│   │   ├── archive_manager.py  # 档案图片本地存储
│   │   ├── sync_base.py        # SyncManagerBase：同步基类
│   │   ├── config_sync_manager.py   # 配置远程同步（GitHub/OSS）
│   │   ├── resource_sync_manager.py # 模板/字段资源打包与同步
│   │   ├── info_sync_manager.py     # 成员信息同步（飞书/腾讯/WPS）
│   │   └── sync_crypto_helper.py    # 同步凭据加解密
│   │
│   ├── ui/                     # 界面展示层
│   │   ├── main_window.py      # 主窗口（导航、页面切换、启动流程）
│   │   ├── admin_home_page.py / member_home_page.py       # 基本信息页
│   │   ├── admin_list_page.py / member_list_page.py       # 模板列表页
│   │   ├── admin_template_page.py / member_template_page.py # 模板填写页
│   │   ├── admin_settings_page.py / member_settings_page.py # 设置页
│   │   ├── list_page.py / template_page.py                # 页面基类
│   │   ├── export_dialog.py / password_dialog.py          # 导出/密码对话框
│   │   └── credentials_dialog.py  # 同步凭据对话框（双端共享）
│   │
│   └── utils/                  # 工具模块
│       ├── file_path.py        # 运行时路径解析（user_data_root 等）
│       ├── crypto_storage.py   # Argon2 + AES-GCM 加密存储
│       ├── json_storage.py     # JSON 读写/备份/加密
│       ├── validators.py       # 字段校验（文本/日期/身份证/逻辑关系）
│       ├── widget_binding.py   # 表单控件与数据绑定
│       ├── styles.py           # 样式定义
│       ├── sync_thread.py      # 后台同步线程
│       └── update_check_thread.py  # 更新检查线程
│
├── resources/                  # 内置只读资源（随包分发）
│   ├── schema/fields_definition.json  # 字段定义
│   ├── templates/              # 示例 Word 模板 + templates_config.json
│   ├── icons/                  # 图标（logo.ico / logo.icns）
│   └── images/                 # 文档配图
│
├── docs/                       # 文档
│   ├── user-guide.md           # 用户手册
│   ├── sync_guide.md           # 同步设置指南
│   └── developer-guide.md      # 本文档
│
└── assets/                     # 项目资源（README 配图、logo 等）
```

---

## 模块设计

### 1. UI 层 (`src/ui/`)

负责界面展示与交互。所有页面通过 `DataManager` 获取/保存数据。

**主窗口** (`main_window.py`)

- 布局：左侧导航栏 + `QStackedWidget` 内容区，按角色（管理员/成员）缓存页面实例
- 启动流程：密码验证 → 角色检测 → 配置就绪检查（导入/拉取/解密密钥）→ 配置同步 → 资源同步 → 信息同步 → 更新检查与公告
- 关键入口：`show_admin_*` / `show_member_*` 系列、`open_*_template_page`、`check_config_sync_on_startup`、`check_resource_sync_on_startup`、`check_updates_on_startup`

**页面组件**

| 文件 | 管理员模式 | 成员模式 | 功能 |
|------|-----------|---------|------|
| `*_home_page.py` | AdminHomePage | MemberHomePage | 基本信息填写 |
| `*_list_page.py` | AdminListPage | MemberListPage | 模板列表（按阶段分组） |
| `*_template_page.py` | AdminTemplatePage | MemberTemplatePage | 模板详情/字段填写/锁定 |
| `*_settings_page.py` | AdminSettingsPage | MemberSettingsPage | 通用设置与同步配置 |

**对话框**

- `export_dialog.py`：批量导出 Word 文档
- `password_dialog.py`：设置/验证本地密码
- `credentials_dialog.py`：配置远程同步凭据（GitHub 令牌 / OSS 子账号 / 解密密钥），双端共享，打开时预填已保存值

### 2. 应用层 (`src/application/`)

封装核心业务逻辑。

**DataManager** (`data_manager.py`)

UI 层唯一的数据入口（门面），聚合持久层各 Manager 并统一提供方法，主要分组：

- 基础：`get_fields`、`get_user_data_root` / `update_user_data_root`
- 管理员配置：`get_admin_config` / `save_admin_config` / `export_admin_config` / `import_admin_config` / `lock_admin_config` / `unlock_admin_config`
- 成员信息：`get_member_info` / `save_member_info` / `lock_member_template` / 档案图片 `save/get/remove_member_archive_image` / `export_member_info` / `import_member_info`
- 加密：`has_password` / `verify_password` / `set_password` / `enable_encryption` / `change_password` / `disable_encryption`
- 配置同步（发布）：`get/save_remote_settings`、`get/save_config_push_settings`、`push_admin_config_to_remote`（强制加密）、`test_config_sync_connection`
- 配置同步（拉取）：`pull_admin_config_from_remote`、`get/save_config_decrypt_key`、`get/save_config_access_token`、`get/save_config_oss_credentials`
- 资源同步（发布/拉取）：`publish_resources_to_remote`、`pull_resources_from_remote`、`get_resources_dir`、`refresh_template_cache`
- 成员信息同步：`get/save_info_sync_settings`、`test_info_sync_connection`、`push_member_basic_data_to_remote`
- 进度与提醒：`calculate_actual_progress`、`get/save_progress_reminder`
- 系统设置：`get/save_system_settings`、`get/set_ignored_update_version`、`get/set_dismissed_announcement_id`

`DataManager.__init__` 内部持有持久层各 Manager（UI 只能经 `DataManager` 方法间接使用）：

```python
self.config_manager        # ConfigManager
self.info_manager          # InfoManager
self.settings_manager      # SettingsManager
self.field_manager         # FieldManager
self.template_manager      # TemplateManager
self.archive_manager       # ArchiveManager
self.config_sync_manager   # ConfigSyncManager
self.resource_sync_manager # ResourceSyncManager
self.info_sync_manager     # InfoSyncManager
self.sync_crypto_helper    # SyncCryptoHelper
```

**TemplateEngine** (`template_engine.py`)

- 解析 Word 模板占位符并匹配字段定义
- 维护占位符 → 数据源映射 `mapping`，是模板详情呈现、文档填充与配置快照的核心数据结构：

```python
mapping[placeholder] = {
    "source": "admin_basic_data",   # 必选：数据源（admin/member/template 等）
    "key": placeholder,             # 可选：映射到数据中的键名
    "is_tip": True,                 # 可选：是否提示项
}
```

- 主要方法：`get_templates` / `get_templates_grouped_by_stage` / `get_placeholders` / `map_placeholders_to_data` / `merge_data_for_template` / `generate_document`（docxtpl 渲染）

**PermissionController** (`permission_controller.py`)

管理运行模式（数据存于 `system_settings.mode`）：

- `admin` - 管理员模式
- `member` - 成员模式
- `detect_mode` / `save_mode` / `switch_to_admin_mode` / `switch_to_member_mode`

### 3. 持久层 (`src/persistence/`)

负责数据持久化与远程交互。

**ConfigManager** (`config_manager.py`) — 管理 `admin_config.json`

```json
{
  "version": "0.1.0",
  "configured": true,
  "basic_data": {
    "支部信息": { "支部名称": "...", "支部书记": "..." },
    "上级党委信息": { ... },
    "公共字段": { ... },
    "交互设置": { ... }
  },
  "template_data": { "template_001": { ... } },
  "last_modified": "2026-08-07T...",
  "synced_at": "...",
  "sync_source": "..."
}
```

- 支持密码加密（AES-GCM）、锁定/解锁、配置校验
- 关键方法：`load_config` / `save_config` / `lock_config` / `unlock_config` / `enable_encryption` / `disable_encryption`

**InfoManager** (`info_manager.py`) — 管理 `member_info.json`

```json
{
  "created_at": "2026-08-07T...",
  "basic_data": { "姓名": "...", "性别": "...", "出生日期": "..." },
  "template_data": { "template_001": { "locked": false, "fields": { ... } } },
  "last_modified": "2026-08-07T..."
}
```

**SettingsManager** (`settings_manager.py`) — 管理 `system_settings.json`

提供各同步块的默认值与「默认 + 用户值」合并方法：`merge_remote_settings` / `merge_remote_pull_settings` / `merge_config_push_settings` / `merge_config_pull_settings` / `merge_resource_push_settings` / `merge_resource_pull_settings` / `merge_info_sync_settings`。

**FieldManager** (`field_manager.py`) — 读取 `resources/schema/fields_definition.json`，提供管理员字段（`admin_fields`）/ 成员字段（`member_fields`）/ 模板字段（`template_fields`）定义。

**TemplateManager** (`template_manager.py`) — 管理模板元信息：

- 读取 `resources/templates/templates_config.json`，也可从文件系统发现模板（模板 ID 基于文件名）
- 按发展阶段分组（申请入党 → … → 归档）、提供模板文件路径、`validate_config` 校验

**ArchiveManager** (`archive_manager.py`) — 档案图片本地存储：

- 图片格式校验（JPG/JPEG/PNG/BMP/WEBP）、目录管理、同名冲突自动重命名

**同步相关模块**

| 模块 | 类 | 职责 |
|------|----|----|
| `sync_base.py` | `SyncManagerBase` | 网络同步基类（超时等公共能力） |
| `config_sync_manager.py` | `ConfigSyncManager` | 管理员配置上传/下载、连接测试；GitHub / 阿里云 OSS；原始文件上传下载；Bearer 令牌与 OSS 凭据下载 |
| `resource_sync_manager.py` | `ResourceSyncManager` | 资源打包（zip）、manifest 生成、发布、更新检查、应用与备份回滚 |
| `info_sync_manager.py` | `InfoSyncManager` | 成员基本信息同步至在线表格（飞书/腾讯/WPS），按唯一标识 upsert、本地缺失回填 |
| `sync_crypto_helper.py` | `SyncCryptoHelper` | 同步场景下的文本/载荷加解密（安装 ID 派生密钥） |

### 数据流向

#### 1. 管理员配置（本地）

```
管理员填写表单（AdminHomePage / AdminTemplatePage）
      │
      ▼
DataManager.save_admin_config()
      │
      ▼
ConfigManager.save_config()
      │
      ▼
admin_config.json（可选加密）
```

#### 2. 成员填写（本地）

```
成员填写表单（MemberHomePage / MemberTemplatePage）
      │
      ▼
DataManager.save_member_info()
      │
      ▼
InfoManager.save_data()
      │
      ▼
member_info.json（可选加密）
```

#### 3. 文档生成

```
用户点击导出
      │
      ▼
TemplateEngine.generate_document()
      ├── 读取 Word 模板（TemplateManager）
      ├── 合并管理员配置 + 成员信息 + 模板专有字段
      ├── 应用占位符映射 mapping
      └── docxtpl 渲染
      ▼
生成 .docx 到导出目录
```

#### 4. 管理员配置发布（管理员端 → 远程）

```
AdminSettingsPage 填写远程仓库信息
      │
      ▼
DataManager.push_admin_config_to_remote()   # encrypt_key 为空则拒绝发布
      │
      ▼
ConfigSyncManager.upload_admin_config()
      ├── GitHub：api.github.com（Bearer Token）
      └── 阿里云 OSS：oss2 签名上传
      ▼
远程仓库 admin_config.json（已加密）
```

#### 5. 成员端启动拉取（成员端 ← 远程）

```
程序启动（成员模式）
      │
      ▼
DataManager.pull_admin_config_from_remote()
      │
      ▼
ConfigSyncManager.download_admin_config()
      ├── GitHub：带 PAT（Authorization: Bearer）
      └── OSS：带只读子账号凭据（oss2 get_object）
      ├── 无凭据则匿名 GET，403 时提示配置凭据
      ▼
比对时效 → 覆盖本地 → 通知 UI 刷新
```

#### 6. 资源同步（模板/字段定义）

```
管理员端：ResourceSyncManager.build_resources_pack() → publish_resources() → 远程
成员端：  ResourceSyncManager.check_resources_update(manifest_url)
          ├── 有新版本 → apply_resources_pack()（先备份，失败回滚）
          └── 无更新 → 跳过
```

#### 7. 成员信息同步（成员端 → 在线汇总表）

```
成员保存/手动触发
      │
      ▼
DataManager.push_member_basic_data_to_remote()
      │
      ▼
InfoSyncManager.upload_member_basic_data_with_config()
      ├── 飞书多维表格 / 腾讯智能表格 / WPS 多维表格
      └── 按 id_field upsert（先查后更 / 无则创建），本地缺失值回填
```

---

## 数据文件与运行时目录

### 运行时根目录

- 由 `src/utils/file_path.py` 统一解析，默认 `<系统用户数据目录>/RuleDone`（Windows 为 `%APPDATA%\RuleDone`）
- 可通过 `bootstrap_settings.json` 中的 `user_data_root` 覆盖，切换时自动迁移数据与资源

```
<user_data_root>/
├── data/                      # 业务数据
│   ├── admin_config.json      # 管理员配置
│   ├── member_info.json       # 成员信息
│   ├── system_settings.json   # 系统设置
│   └── archive_images/        # 档案图片
├── exports/                   # 导出文档默认落点
└── resources/                 # 运行时资源（首次启用时从内置资源复制）
    ├── schema/fields_definition.json
    └── templates/*.docx + templates_config.json
```

- 项目内 `resources/` 为**内置只读资源**，随安装包分发；管理员可在运行时 `resources/` 上定制后发布给成员端
- 主入口启动时调用 `ensure_runtime_directories()` 创建目录

### 关键文件一览

| 文件 | 写入方 | 说明 |
|------|--------|------|
| `admin_config.json` | ConfigManager | 管理员配置（支部/党委/公共字段/模板数据），可加密、可锁定 |
| `member_info.json` | InfoManager | 成员个人信息与各模板填写数据，可加密 |
| `system_settings.json` | SettingsManager | 导出路径、角色模式、同步配置 |
| `fields_definition.json` | FieldManager（只读） | 字段定义（管理员/成员/模板字段） |
| `templates_config.json` | TemplateManager（只读） | 模板阶段与模板元信息 |

### 版本管理

- 版本号唯一真相源：`src/__init__.py` 的 `__version__`，UI 中以 `v{__version__}` 显示
- 注意区分：字段定义 schema 版本、模板格式版本、加密存储格式版本、安装包版本各自独立管理

---

## 同步机制

### 支持平台

| 用途 | 平台 | 说明 |
|------|------|------|
| 配置发布/拉取 | GitHub、阿里云 OSS | 私有仓库/私有读 + 长期凭据 |
| 成员信息同步 | 飞书多维表格、腾讯智能表格、WPS 多维表格 | 客户端直连 API，upsert |

### 安全模型

- **发布强制加密**：管理员发布配置时 `encrypt_key` 为空则拒绝（UI 有预检提示）
- **成员只读凭据**：GitHub 只读 fine-grained PAT（Contents: Read）或 OSS 只读子账号（仅 `oss:GetObject`）
- **凭据加密存储**：`system_settings` 中的敏感字段经 `SyncCryptoHelper` 加密（`enc::` 前缀），页面不落明文
- **连接配置与内容解耦**：push 方向共享 `remote_push`（写凭据），pull 方向共享 `remote_pull`（只读凭据）

### 排障建议

- **401/403**：检查平台应用权限、令牌/子账号权限与凭据是否正确
- **404**：检查 `app_token` / `table_id` 或仓库路径/对象 key 是否匹配
- **查询不到记录**：确认唯一标识字段名与在线表列名一致（含中文全角字符）
- **429**：平台限流，提示稍后重试
- **下载失败**：无凭据时成员端可能被 403 拒绝，需在「同步凭据」对话框中配置

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

1. 在 `src/ui/` 创建页面文件（可继承 `list_page.py` / `template_page.py` 基类）：

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

2. 在 `main_window.py` 中注册页面（参考 `show_member_list_page` 等做法，按角色缓存实例）：

```python
from src.ui.new_page import NewPage

# 在 MainWindow 类中添加
def show_new_page(self):
    if self.new_page is None:
        self.new_page = NewPage()
        self.stacked_widget.addWidget(self.new_page)
    self.stacked_widget.setCurrentWidget(self.new_page)
```

#### 新增同步平台

**配置/资源同步**（GitHub / OSS 已实现，可按同模式扩展）：

1. 在 `SettingsManager` 中增加新平台的默认配置与合并方法（如 `merge_remote_settings` 中加一项）
2. 在 `ConfigSyncManager` / `ResourceSyncManager` 中实现对应平台的上传/下载方法（参考 `_upload_to_github` / `_upload_to_oss`）
3. 在 `admin_settings_page.py` 中编写对应配置组件

**成员信息同步**（飞书 / 腾讯 / WPS 已实现）：

1. 在 `InfoSyncManager` 中实现 `_validate_<平台>`、`_get_<平台>_access_token`、查询/获取、`_create_record` / `_update_record` 等
2. 在 `DataManager` 增加对应配置读取与上传入口
3. 在 `member_home_page.py` / `member_settings_page.py` 增加配置与触发入口

#### 新增字段/模板

- 字段：编辑 `resources/schema/fields_definition.json`（及运行时资源副本），管理员端发布资源同步给成员
- 模板：向 `resources/templates/` 添加 `.docx` 并在 `templates_config.json` 登记，占位符格式见 `TemplateEngine`

---

## 获取帮助

- 查看 [贡献指南](../CONTRIBUTING.md) 了解如何提交代码
- 查看 [用户手册](user-guide.md) 与 [同步指南](sync_guide.md)
- 在 GitHub 提交 Issue 或 Discussion
