# FastSecond Read - 智能书籍分章工具

> 智能分章节、提取内容，支持 PDF、EPUB、Word 等 20+ 种格式

## 功能特性

- **智能分章**: 自动识别书籍章节结构，按层级分文件夹存储
- **多格式支持**: 支持 PDF、EPUB、DOCX、Markdown、TXT、HTML 等 20+ 种格式
- **Markdown 输出**: 每个章节保存为排版好的 Markdown 文件
- **层级标记**: 使用标准 `#` 标记标识标题层级
- **可扩展架构**: 模块化设计，易于添加新的读取器

## 支持的文件格式

| 格式 | 扩展名 | 状态 |
|------|--------|------|
| PDF | `.pdf` | ✅ 支持 |
| EPUB | `.epub` | ✅ 支持 |
| Word | `.docx` | ✅ 支持 |
| Markdown | `.md` | ✅ 支持 |
| 纯文本 | `.txt` | ✅ 支持 |
| HTML | `.html`, `.htm` | ✅ 支持 |
| JSON | `.json` | ✅ 支持 |
| CSV | `.csv` | ✅ 支持 |
| XML | `.xml` | ✅ 支持 |
| RTF | `.rtf` | ✅ 支持 |
| 代码文件 | `.py`, `.js`, etc. | ✅ 支持 |
| OCR | 图片 | ✅ 支持 |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 处理书籍

```bash
# 处理单本书籍
python scripts/book_processor.py "书籍.pdf"

# 指定输出目录
python scripts/book_processor.py "书籍.pdf" "D:/我的总结"
```



## 目录结构

```
fastsecond-read/
├── scripts/
│   ├── book_processor.py          # 书籍处理主脚本
│   ├── ai_analyze_chapters.py     # AI分析提示词生成脚本
│   ├── core/
│   │   └── document.py             # 文档处理核心模块
│   └── readers/
│       ├── base.py                 # 读取器基类
│       ├── factory.py              # 读取器工厂
│       ├── pdf_reader.py           # PDF读取器
│       ├── epub_reader.py          # EPUB读取器
│       ├── docx_reader.py          # DOCX读取器
│       └── ...                     # 其他格式读取器
├── requirements.txt                # Python依赖
├── README.md                       # 本文件
├── SKILL.md                        # 技能详细文档
├── PDF_RULES.md                    # PDF/EPUB分章规则详解
└── MEMORY.md                       # 更新历史
```

## 输出格式

### 分章输出

```
书籍总结/我的书/
├── 01_第1章_标题.md              # 一级标题（章）
├── 01_1_第1节_标题.md            # 二级标题（节）
├── 01_1_1_第1小节_标题.md        # 三级标题（小节）
├── 02_第2章_标题.md
└── ...
```

### 文件内容格式

```markdown
# 第1章 标题

---

**章节序号**：第1章  
**章节层级**：1 【章】  
**层级路径**：1  
**字数统计**：3500 字  
**生成时间**：2026-05-16 11:30  

---

## 第一节 小节标题

正文内容...

### 一、要点标题

详细内容...

---

*由 FastSecond Read 自动生成*
```

## 配置选项

### 控制参数

```python
# PDF/EPUB 读取器支持以下参数
reader.read(file_path, level2_as_body=True, level3_as_body=True)
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `level2_as_body` | True | 二级标题视为正文（不创建独立章节） |
| `level3_as_body` | True | 三级标题视为正文（不创建独立章节） |

## 分章规则

### PDF 分章规则

使用**自适应两轮检测算法**：

1. **第一轮**：固定比率粗筛（一级≥1.4倍，二级/三级>1.0且<1.4倍）
2. **第二轮**：自适应阈值计算（取前两位最大字号平均）
3. **第三轮**：标题分类（一级≥自适应比率，二级/三级通过x0位置区分）

**字数限制规则**（2026-05-16更新）：
- 一级/二级标题：无字数限制
- 三级标题：< 50字（仅对三级标题生效）

### EPUB 分章规则

- **h1**: 一级标题
- **h2**: 二级标题（默认为是正文）
- **h3-h6**: 三级标题（默认为是正文）

详细规则参见 `PDF_RULES.md`

## 扩展开发

### 添加新的读取器

1. 在 `scripts/readers/` 目录下创建新的读取器文件
2. 继承 `BaseReader` 基类
3. 实现 `read()` 方法
4. 在 `factory.py` 中注册

示例：

```python
# scripts/readers/my_format_reader.py
from .base import BaseReader

class MyFormatReader(BaseReader):
    def read(self, file_path):
        # 实现读取逻辑
        return content
```

## 依赖要求

- Python 3.8+
- 详见 `requirements.txt`

## 许可证

MIT License

---

**维护者**: FastSecond  
**项目地址**: `C:\Users\GSecond\.qclaw\skills\fastsecond-read`
