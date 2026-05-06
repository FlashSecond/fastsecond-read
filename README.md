# FastSecond-Read 智能书籍阅读与分析工具

> 智能分章节、提取内容、生成深度AI分析

## 功能特性

- **智能分章**: 自动识别书籍章节结构，按序号分文件夹存储
- **多格式支持**: 支持 PDF、EPUB、DOCX、Markdown、TXT、HTML 等格式
- **AI深度分析**: 为每章生成六维深度分析（概述、论点、概念、案例、框架、批判思考）
- **批量处理**: 支持批量处理多本书籍
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
python scripts/book_processor.py --input "书籍.pdf" --output "./output"

# 批量处理
python scripts/book_processor.py --input "./books/" --output "./output" --batch
```

### 3. 生成AI分析

```bash
# 为分章后的书籍生成AI深度分析
python scripts/ai_analyze_chapters.py --book-dir "./output/书籍名"
```

## 目录结构

```
fastsecond-read/
├── scripts/
│   ├── book_processor.py          # 书籍处理主脚本
│   ├── ai_analyze_chapters.py     # AI深度分析脚本
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
└── SKILL.md                        # 技能详细文档
```

## AI深度分析维度

每章生成以下六维分析：

1. **章节概述** - 核心内容摘要
2. **核心论点解析** - 主要观点深度解读
3. **关键概念与术语** - 重要概念解释
4. **案例分析** - 案例深度剖析
5. **理论框架与论证逻辑** - 理论结构分析
6. **批判性思考** - 多角度批判分析

## 输出格式

### 分章输出

```
output/
└── 书籍名/
    ├── 01_第一章标题/
    │   ├── 01_第一章标题.md          # 章节原文
    │   └── 01_第一章标题_AI深度分析.md  # AI分析
    ├── 02_第二章标题/
    │   ├── 02_第二章标题.md
    │   └── 02_第二章标题_AI深度分析.md
    └── ...
```

### AI分析文件格式

```markdown
# 第一章标题 - AI深度分析

## 一、章节概述
...

## 二、核心论点解析
...

## 三、关键概念与术语
...

## 四、案例分析
...

## 五、理论框架与论证逻辑
...

## 六、批判性思考
...

## 七、思维导图
```mermaid
...
```

## 九、知识提问
...
```

## 配置选项

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `OPENAI_API_KEY` | OpenAI API密钥 | - |
| `OPENAI_BASE_URL` | API基础URL | https://api.openai.com |
| `DEFAULT_MODEL` | 默认AI模型 | gpt-4 |

### 命令行参数

#### book_processor.py

| 参数 | 说明 | 示例 |
|------|------|------|
| `--input`, `-i` | 输入文件或目录 | `--input "book.pdf"` |
| `--output`, `-o` | 输出目录 | `--output "./output"` |
| `--batch`, `-b` | 批量模式 | `--batch` |
| `--format`, `-f` | 输出格式 | `--format md` |

#### ai_analyze_chapters.py

| 参数 | 说明 | 示例 |
|------|------|------|
| `--book-dir`, `-d` | 书籍目录 | `--book-dir "./output/书籍名"` |
| `--chapters`, `-c` | 指定章节 | `--chapters 1,2,3` |
| `--model`, `-m` | AI模型 | `--model gpt-4` |

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

## 常见问题

### Q: 如何处理扫描版PDF？
A: 使用 OCR 读取器，需要安装 Tesseract OCR 引擎。

### Q: 支持哪些AI模型？
A: 支持所有 OpenAI 兼容的 API，包括 GPT-4、GPT-3.5、Claude 等。

### Q: 如何调整分析深度？
A: 修改 `ai_analyze_chapters.py` 中的提示词模板。

## 依赖要求

- Python 3.8+
- 详见 `requirements.txt`

## 许可证

MIT License

## 贡献指南

欢迎提交 Issue 和 Pull Request！

## 更新日志

### v1.0.0 (2026-05-06)
- ✅ 初始版本发布
- ✅ 支持15种文件格式
- ✅ 实现AI深度分析功能
- ✅ 清理临时脚本，优化代码结构

---

**维护者**: FastSecond  
**项目地址**: `C:\Users\GSecond\.qclaw\skills\fastsecond-read`
