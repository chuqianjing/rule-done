# 架构设计

本文档介绍「入档·党员发展档案材料填写与生成工具」的技术架构和核心模块设计。

---

## 整体架构

系统采用经典的三层架构设计：

```
┌─────────────────────────────────────────────────────────────┐
│                        UI 层 (src/ui/)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  主窗口      │  │  页面组件   │  │  对话框/小部件       │  │
│  │ MainWindow  │  │  *_page.py  │  │  widgets/, dialogs  │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Business 层 (src/business/)                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐  │
│  │  DataManager    │  │ TemplateEngine  │  │ Permission  │  │
│  │  数据管理        │  │ 模板引擎        │   │ Controller  │  │
│  └─────────────────┘  └─────────────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Data 层 (src/data/)                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ ConfigMgr   │  │  InfoMgr    │  │ TemplateMgr/FieldMgr│  │
│  │ 管理员配置   │  │  成员信息    │  │ 模板/字段定义        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      存储层 (data/, resources/)              │
│  ┌────────────────────┐  ┌────────────────────────────────┐ │
│  │ JSON 数据文件       │  │ Word 模板文件 (.docx)          │ │
│  │ admin_config.json  │  │ resources/templates/*.docx     │ │
│  │ member_info.json   │  │                                │ │
│  └────────────────────┘  └────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 核心模块

### 1. UI 层 (`src/ui/`)

负责用户界面展示和交互。

#### 主窗口 (`main_window.py`)

- 管理整体布局：侧边导航栏 + 内容区域
- 使用 `QStackedWidget` 实现页面切换
- 维护两套页面缓存（管理员/成员模式）
- 处理模式切换、配置同步、密码验证

#### 页面组件

| 文件 | 管理员模式 | 成员模式 | 功能 |
|------|-----------|---------|------|
| `*_home_page.py` | AdminHomePage | MemberHomePage | 基本信息编辑 |
| `*_list_page.py` | AdminListPage | MemberListPage | 模板列表展示 |
| `*_template_page.py` | AdminTemplatePage | MemberTemplatePage | 模板详情/填写 |
| `*_settings_page.py` | AdminSettingsPage | MemberSettingsPage | 系统设置 |

#### 通用组件 (`src/ui/widgets/`)

- `toast.py` - 消息提示
- `progress_dialog.py` - 进度对话框

### 2. Business 层 (`src/business/`)

封装核心业务逻辑。

#### DataManager (`data_manager.py`)

数据管理的统一入口，协调各个 Manager 的操作：

```python
class DataManager:
    def __init__(self):
        self.config_manager = ConfigManager()    # 管理员配置
        self.info_manager = InfoManager()        # 成员信息
        self.template_manager = TemplateManager()# 模板管理
        self.field_manager = FieldManager()      # 字段定义
        self.settings_manager = SettingsManager()# 系统设置
```

核心职责：
- 统一的数据读写接口
- 配置导入/导出/同步
- 密码验证与加密管理
- 数据校验

#### TemplateEngine (`template_engine.py`)

模板处理引擎，负责：

- 读取 Word 模板文件
- 解析模板中的占位符
- 管理占位符到数据字段的映射
- 使用 `docxtpl` 进行模板渲染
- 生成最终的 Word 文档

```python
# 占位符映射示例
placeholder_mapping = {
    "出生年月": "出生日期",
    "出生年月份": "出生日期",
    "生年月": "出生日期",
}
```

#### PermissionController (`permission_controller.py`)

权限控制，管理运行模式：

- `user` - 用户模式（可自由切换）
- `admin` - 管理员模式
- `member` - 成员模式

### 3. Data 层 (`src/data/`)

负责数据持久化和访问。

#### ConfigManager (`config_manager.py`)

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

#### InfoManager (`info_manager.py`)

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

#### FieldManager (`field_manager.py`)

读取 `fields_definition.json`，提供字段定义信息：

- 管理员字段（admin_fields）
- 成员字段（member_fields）
- 模板字段（template_fields）

#### TemplateManager (`template_manager.py`)

管理 Word 模板文件，提供模板列表和元信息。

---

## 数据流向

### 1. 管理员配置流程

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

### 2. 成员填写流程

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

### 3. 文档生成流程

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

### 4. 配置同步流程

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
      ├── 比对版本号
      ├── 如有更新，覆盖本地配置
      │
      ▼
通知 UI 刷新
```

---

## 设计决策

### 1. 为什么使用双角色模式？

**问题**：党员发展涉及支部统一配置和个人信息，两者来源不同。

**方案**：
- 管理员端：配置支部公共信息，导出给成员
- 成员端：只填写个人信息，复用支部配置
- 好处：配置一处修改全员生效，减少重复工作

### 2. 为什么使用 JSON 存储？

**考量**：
- 数据量小，不需要数据库
- JSON 可读性好，便于调试和备份
- 跨平台兼容性好
- 易于导入导出和网络传输

### 3. 为什么使用 docxtpl？

**对比**：
- `python-docx`：适合从零创建文档，但模板替换能力弱
- `docxtpl`：基于 Jinja2 语法，支持复杂的模板逻辑（循环、条件等）

### 4. 加密方案选择

```
用户密码
    │
    ▼
Argon2 密钥派生（防暴力破解）
    │
    ▼
AES-GCM 加密数据（认证加密）
    │
    ▼
加密后的 JSON 文件
```

- Argon2：抵抗 GPU/ASIC 攻击
- AES-GCM：提供加密 + 完整性验证

---

## 目录结构

```
party-dev-system/
├── main.py                     # 程序入口
├── requirements.txt            # 依赖清单
│
├── src/
│   ├── business/               # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── data_manager.py     # 数据管理器（门面类）
│   │   ├── template_engine.py  # 模板引擎
│   │   └── permission_controller.py  # 权限控制
│   │
│   ├── data/                   # 数据访问层
│   │   ├── __init__.py
│   │   ├── config_manager.py   # 管理员配置管理
│   │   ├── info_manager.py     # 成员信息管理
│   │   ├── template_manager.py # 模板文件管理
│   │   ├── field_manager.py    # 字段定义管理
│   │   └── settings_manager.py # 系统设置管理
│   │
│   ├── ui/                     # 界面层
│   │   ├── __init__.py
│   │   ├── main_window.py      # 主窗口
│   │   ├── styles.py           # 样式定义
│   │   ├── admin_*.py          # 管理员模式页面
│   │   ├── member_*.py         # 成员模式页面
│   │   ├── *_page.py           # 通用页面基类
│   │   ├── export_dialog.py    # 导出对话框
│   │   ├── password_dialog.py  # 密码对话框
│   │   ├── config_sync_thread.py  # 配置同步线程
│   │   └── widgets/            # 通用小部件
│   │
│   └── utils/                  # 工具模块
│       └── encryption.py       # 加密工具
│
├── resources/
│   ├── fields_definition.json  # 字段定义
│   └── templates/              # Word 模板文件
│       ├── template_001_入党申请书.docx
│       ├── template_002_*.docx
│       └── ...
│
├── data/                       # 运行时数据（gitignore）
│   ├── admin_config.json
│   ├── member_info.json
│   └── system_settings.json
│
└── exports/                    # 导出文件目录（gitignore）
```

---

## 扩展指南

### 添加新的模板类型

1. 将新模板放入 `resources/templates/`
2. 命名格式：`template_XXX_模板名称.docx`
3. 在模板中使用 `{{ 字段名 }}` 占位符
4. 如需特殊字段映射，在 `template_engine.py` 的 `placeholder_mapping` 中添加

### 添加新的数据字段

1. 在 `resources/fields_definition.json` 中添加字段定义
2. 区分 `admin_fields`（管理员字段）和 `member_fields`（成员字段）
3. UI 会自动根据字段定义生成表单
