# Word 模板处理方案

## 一、模板占位符规范

### 1.1 占位符格式
**标准格式**：`{{变量名}}`

**示例**：
- `{{姓名}}`
- `{{支部名称}}`
- `{{出生年月}}`
- `{{入党时间}}`

### 1.2 占位符命名规范
- 使用中文名称，与字段定义中的 `key` 对应
- 支持嵌套路径，如 `{{上级党委.名称}}`
- 不支持空格，使用下划线或点号分隔

### 1.3 占位符位置
占位符可以出现在：
- 段落文本中
- 表格单元格中
- 页眉页脚中
- 文本框内

## 二、模板文件结构

### 2.1 模板目录结构
```
resources/
└── templates/
    ├── template_001_入党申请书.docx
    ├── template_002_转正申请书.docx
    └── template_003_思想汇报.docx
```

### 2.2 模板文件命名规范
- 格式：`template_{ID}_{名称}.docx`
- ID 与 `templates_config.json` 中的 `id` 对应

## 三、技术实现方案

### 3.1 方案选择：python-docx + docxtpl

**推荐使用 `docxtpl`**，原因：
- 基于 python-docx，功能强大
- 支持 Jinja2 语法，更灵活
- 自动处理格式保持
- 支持复杂模板逻辑

### 3.2 核心实现代码

#### 3.2.1 基础替换实现
```python
from docxtpl import DocxTemplate
import os

class WordGenerator:
    def __init__(self, template_dir="resources/templates"):
        self.template_dir = template_dir
    
    def generate_document(self, template_id, data, output_path):
        """
        生成 Word 文档
        
        Args:
            template_id: 模板ID
            data: 合并后的数据字典
            output_path: 输出文件路径
        """
        # 1. 获取模板文件路径
        template_path = self._get_template_path(template_id)
        
        # 2. 加载模板
        doc = DocxTemplate(template_path)
        
        # 3. 准备上下文数据
        context = self._prepare_context(data)
        
        # 4. 渲染模板
        doc.render(context)
        
        # 5. 保存文档
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        doc.save(output_path)
        
        return output_path
    
    def _get_template_path(self, template_id):
        """获取模板文件路径"""
        template_manager = TemplateManager()
        template_info = template_manager.get_template(template_id)
        return os.path.join(self.template_dir, template_info['file'])
    
    def _prepare_context(self, data):
        """准备模板上下文数据"""
        # 将数据转换为模板可用的格式
        context = {}
        for key, value in data.items():
            # 处理嵌套数据
            if isinstance(value, dict):
                context.update(value)
            else:
                context[key] = value
        return context
```

#### 3.2.2 高级功能：条件渲染
```python
# 模板中可以使用 Jinja2 语法
# 示例：{{% if 性别 == "男" %}}同志{{% endif %}}

def _prepare_context(self, data):
    """支持条件渲染的上下文准备"""
    context = data.copy()
    
    # 添加辅助函数
    context['format_date'] = self._format_date
    context['format_text'] = self._format_text
    
    return context

def _format_date(self, date_str, format_str="YYYY年MM月DD日"):
    """日期格式化函数"""
    # 实现日期格式化逻辑
    pass
```

### 3.3 纯 python-docx 实现（备选方案）

如果不想使用 docxtpl，可以使用纯 python-docx：

```python
from docx import Document
import re

class WordGeneratorBasic:
    def __init__(self):
        pass
    
    def generate_document(self, template_path, data, output_path):
        """使用纯 python-docx 生成文档"""
        doc = Document(template_path)
        
        # 替换段落中的占位符
        for paragraph in doc.paragraphs:
            self._replace_in_paragraph(paragraph, data)
        
        # 替换表格中的占位符
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    self._replace_in_cell(cell, data)
        
        # 替换页眉页脚
        for section in doc.sections:
            self._replace_in_header(section.header, data)
            self._replace_in_footer(section.footer, data)
        
        doc.save(output_path)
    
    def _replace_in_paragraph(self, paragraph, data):
        """在段落中替换占位符"""
        if not paragraph.text:
            return
        
        # 查找所有占位符
        placeholders = re.findall(r'\{\{(\w+)\}\}', paragraph.text)
        
        for placeholder in placeholders:
            value = data.get(placeholder, '')
            placeholder_full = f'{{{{{placeholder}}}}}'
            paragraph.text = paragraph.text.replace(placeholder_full, str(value))
    
    def _replace_in_cell(self, cell, data):
        """在单元格中替换占位符"""
        for paragraph in cell.paragraphs:
            self._replace_in_paragraph(paragraph, data)
    
    def _replace_in_header(self, header, data):
        """在页眉中替换占位符"""
        for paragraph in header.paragraphs:
            self._replace_in_paragraph(paragraph, data)
    
    def _replace_in_footer(self, footer, data):
        """在页脚中替换占位符"""
        for paragraph in footer.paragraphs:
            self._replace_in_paragraph(paragraph, data)
```

## 四、字段映射机制

### 4.1 映射配置
在 `templates_config.json` 中定义字段映射：

```json
{
  "template_001": {
    "field_mapping": {
      "{{姓名}}": {
        "source": "basic_info",
        "field": "姓名"
      },
      "{{支部名称}}": {
        "source": "admin_config",
        "path": "branch_info.branch_name"
      },
      "{{入党时间}}": {
        "source": "template_data",
        "template_id": "template_001",
        "field": "入党时间"
      }
    }
  }
}
```

### 4.2 映射解析实现
```python
class TemplateEngine:
    def merge_data_for_template(self, template_id):
        """合并数据用于模板生成"""
        # 1. 获取模板配置
        template_config = self.template_manager.get_template(template_id)
        field_mapping = template_config['field_mapping']
        
        # 2. 加载各类数据
        admin_config = self.data_manager.get_admin_config()
        member_info = self.data_manager.get_member_info()
        
        # 3. 构建数据字典
        merged_data = {}
        
        for placeholder, mapping in field_mapping.items():
            value = self._get_value_by_mapping(mapping, admin_config, member_info)
            # 移除 {{}} 作为 key
            key = placeholder.strip('{}')
            merged_data[key] = value
        
        return merged_data
    
    def _get_value_by_mapping(self, mapping, admin_config, member_info):
        """根据映射获取值"""
        source = mapping['source']
        
        if source == 'basic_info':
            return member_info['basic_info'].get(mapping['field'], '')
        
        elif source == 'admin_config':
            # 支持嵌套路径，如 "branch_info.branch_name"
            path = mapping['path'].split('.')
            value = admin_config
            for key in path:
                value = value.get(key, {})
            return value if isinstance(value, str) else ''
        
        elif source == 'template_data':
            template_id = mapping['template_id']
            field = mapping['field']
            return member_info['template_data'].get(template_id, {}).get(field, '')
        
        return ''
```

## 五、格式保持策略

### 5.1 使用 docxtpl 的优势
- **自动保持格式**：docxtpl 会自动保持原有格式
- **支持富文本**：可以保持字体、颜色、大小等

### 5.2 使用纯 python-docx 的格式保持
```python
def _replace_preserving_format(self, paragraph, placeholder, value):
    """保持格式的替换"""
    # 查找占位符位置
    text = paragraph.text
    start = text.find(placeholder)
    
    if start == -1:
        return
    
    # 获取占位符的格式
    runs = paragraph.runs
    placeholder_run = None
    
    for run in runs:
        if placeholder in run.text:
            placeholder_run = run
            break
    
    if placeholder_run:
        # 保持格式替换
        run.text = run.text.replace(placeholder, str(value))
        # 保持字体、大小等属性
        # run.font.name = placeholder_run.font.name
        # run.font.size = placeholder_run.font.size
```

## 六、模板验证

### 6.1 模板检查
```python
class TemplateValidator:
    def validate_template(self, template_path, field_mapping):
        """验证模板是否包含所有必需的占位符"""
        doc = Document(template_path)
        
        # 提取模板中的所有占位符
        template_placeholders = set()
        
        for paragraph in doc.paragraphs:
            placeholders = re.findall(r'\{\{(\w+)\}\}', paragraph.text)
            template_placeholders.update(placeholders)
        
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    placeholders = re.findall(r'\{\{(\w+)\}\}', cell.text)
                    template_placeholders.update(placeholders)
        
        # 检查映射配置
        mapped_placeholders = set()
        for placeholder in field_mapping.keys():
            key = placeholder.strip('{}')
            mapped_placeholders.add(key)
        
        # 找出缺失的占位符
        missing = template_placeholders - mapped_placeholders
        extra = mapped_placeholders - template_placeholders
        
        return {
            'valid': len(missing) == 0,
            'missing': list(missing),
            'extra': list(extra)
        }
```

## 七、批量生成

### 7.1 多模板批量生成
```python
def generate_multiple_documents(self, template_ids, output_dir):
    """批量生成多个文档"""
    results = []
    
    for template_id in template_ids:
        try:
            # 合并数据
            data = self.merge_data_for_template(template_id)
            
            # 生成文件名
            template_info = self.template_manager.get_template(template_id)
            filename = f"{template_info['name']}_{data.get('姓名', '')}.docx"
            output_path = os.path.join(output_dir, filename)
            
            # 生成文档
            self.generate_document(template_id, data, output_path)
            
            results.append({
                'template_id': template_id,
                'success': True,
                'path': output_path
            })
        except Exception as e:
            results.append({
                'template_id': template_id,
                'success': False,
                'error': str(e)
            })
    
    return results
```

## 八、错误处理

### 8.1 常见错误及处理
- **模板文件不存在**：提示用户检查模板文件
- **占位符未找到数据**：使用空字符串或提示
- **格式错误**：记录日志，尝试修复
- **保存失败**：检查文件权限，提示用户

### 8.2 错误处理实现
```python
def generate_document_safe(self, template_id, data, output_path):
    """安全的文档生成，包含错误处理"""
    try:
        # 验证模板存在
        if not self._template_exists(template_id):
            raise FileNotFoundError(f"模板 {template_id} 不存在")
        
        # 验证数据完整性
        missing_fields = self._check_required_fields(template_id, data)
        if missing_fields:
            logger.warning(f"缺少字段: {missing_fields}")
        
        # 生成文档
        return self.generate_document(template_id, data, output_path)
    
    except Exception as e:
        logger.error(f"生成文档失败: {e}", exc_info=True)
        raise
```

## 九、性能优化

### 9.1 模板缓存
```python
class TemplateCache:
    def __init__(self):
        self._cache = {}
    
    def get_template(self, template_id):
        """获取模板（带缓存）"""
        if template_id not in self._cache:
            template_path = self._get_template_path(template_id)
            self._cache[template_id] = DocxTemplate(template_path)
        return self._cache[template_id]
```

### 9.2 异步生成（可选）
对于大量文档生成，可以使用异步处理。

---

**文档版本**：v1.0  
**最后更新**：2024-01-01

