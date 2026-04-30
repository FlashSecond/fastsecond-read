#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全自动书籍处理 - 分章 + 分析一站式完成

使用方式：
    python auto_process.py <书籍文件> [--output-dir 输出目录] [--model kimi-k2.5]
    
示例：
    python auto_process.py "我的书.epub"
    python auto_process.py "我的书.pdf" -o "D:/总结" -m kimi-k2.5
"""
import sys
import re
from pathlib import Path
from typing import Dict, List, Optional
import argparse
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from readers.factory import ReaderFactory


# 综合章节分析提示词模板
CHAPTER_ANALYSIS_PROMPT = """请分析以下章节内容，生成【综合章节分析】：

## 输入信息
- 章节标题：{title}
- 章节序号：{index}
- 章节内容：

{content}

## 输出要求

请生成一个完整的 Markdown 文档，包含以下 4 个部分：

---

## 一、章节概述

### 章节主旨
用一句话概括本章的核心主题（20-50字）

### 核心要点
列出 3-5 个核心要点，每个要点：
- 用**加粗**标出关键词
- 简要说明该要点的意义
- 格式：1. **要点**：说明

### 内容概述
用 2-3 段话描述本章的主要内容：
- 第一段：本章讨论的核心问题/主题
- 第二段：主要论述逻辑和关键论据
- 第三段（可选）：本章的结论或启示

### 章节定位
说明本章在全书中的位置和作用：
- 是引言/基础/深入/总结？
- 与前后章节的关联
- 本章的独特价值

---

## 二、知识要素

### 核心概念
列出本章涉及的重要概念和定义：
- 概念名称（加粗）
- 简明定义（1-2句话）
- 如有分类，用子列表说明

格式示例：
- **概念名称**：定义说明
  - 类型A：说明
  - 类型B：说明

### 关键要素
用表格整理关键要素：

| 要素 | 说明 | 重要性 |
|------|------|--------|
| 要素1 | 简要说明 | 高/中/低 |
| 要素2 | 简要说明 | 高/中/低 |

### 重要数据/金句
提取本章的重要数据、统计数字或经典金句：
- 数据：用引用格式 > 标注来源
- 金句：用引用格式 > 并注明上下文

### 相关理论/模型
如有涉及的理论、模型、框架：
- 理论名称
- 简要说明
- 应用场景

---

## 三、案例分析

### 主要案例
详细描述本章涉及的主要案例（1-3个）：

每个案例包含：
- **背景**：时间、地点、主体
- **问题/挑战**：核心问题
- **解决方案/行动**：具体措施
- **结果**：成果或影响
- **启示/教训**：借鉴意义

### 次要案例
简要列出其他提及的案例

### 论据/故事
支撑论点的故事或事例

---

## 四、应用拓展

### 实际应用方法
场景 + 步骤 + 效果

### 在不同领域的应用
用表格：| 领域 | 应用场景 | 具体做法 |

### 注意事项
- 常见误区：说明 + 正确做法
- 避免方法：具体操作

### 实践练习
- 练习1：基础应用（任务/标准/时间）
- 练习2：进阶挑战（可选）

---

要求：
- 基于实际内容，不能编造
- 每个部分都有实质内容
- 使用清晰的 Markdown 层级
"""


def format_chapter_content(doc_chapter, index: int) -> str:
    """将章节内容格式化为美观的Markdown"""
    title = doc_chapter.title or f"第{index}章"
    
    content_parts = []
    for block in doc_chapter.content_blocks:
        if block.text:
            text = block.text.strip()
            if text:
                content_parts.append(text)
    
    content = '\n\n'.join(content_parts)
    word_count = len(content)
    
    md_lines = [
        f"# {title}",
        "",
        "---",
        "",
        f"**章节序号**：第{index}章  ",
        f"**章节层级**：{doc_chapter.level}  ",
        f"**字数统计**：{word_count} 字  ",
        f"**生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M')}  ",
        "",
        "---",
        "",
        content if content else "*（本章内容为空）*",
        "",
        "---",
        "",
        "*由 FastSecond Read 自动生成*"
    ]
    
    return '\n'.join(md_lines)


def extract_content_from_md(md_content: str) -> tuple:
    """从Markdown内容中提取标题和正文"""
    lines = md_content.split('\n')
    
    title = "未命名章节"
    if lines and lines[0].startswith('# '):
        title = lines[0][2:].strip()
    
    content_lines = []
    in_content = False
    
    for line in lines:
        if line.startswith('# ') and not in_content:
            continue
        
        if line.strip() == '---' and not in_content:
            in_content = True
            continue
        
        if line.strip() == '---' and in_content:
            in_content = False
            continue
        
        if in_content and (line.startswith('**章节') or line.startswith('**字数') or 
                          line.startswith('**生成时间') or line.startswith('**章节层级')):
            continue
        
        if in_content and not line.strip():
            continue
        
        if in_content and line.strip():
            in_content = "collecting"
        
        if in_content == "collecting":
            content_lines.append(line)
    
    content = '\n'.join(content_lines).strip()
    
    if '*由 FastSecond Read 自动生成*' in content:
        content = content.split('*由 FastSecond Read 自动生成*')[0].strip()
    
    return title, content


def _sanitize_filename(name: str) -> str:
    """清理文件名中的非法字符"""
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = name.strip('. ')
    if len(name) > 80:
        name = name[:80]
    return name or 'untitled'


def process_book(file_path: str, output_dir: Optional[str] = None) -> Dict:
    """处理书籍文件，分章节提取内容为排版好的MD文件"""
    file_path = Path(file_path)
    
    if not file_path.exists():
        return {'success': False, 'error': f'文件不存在: {file_path}'}
    
    print(f"[INFO] 读取文件: {file_path}")
    document = ReaderFactory.read_file(str(file_path))
    
    if not document or not document.chapters:
        return {'success': False, 'error': '无法提取文件内容'}
    
    if output_dir is None:
        output_dir = Path('D:/Mylibrary/书籍总结') / file_path.stem.strip()
    else:
        output_dir = Path(output_dir) / file_path.stem.strip()
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    chapter_files = []
    
    for idx, doc_chapter in enumerate(document.chapters, 1):
        md_content = format_chapter_content(doc_chapter, idx)
        
        safe_title = _sanitize_filename(doc_chapter.title or f"chapter_{idx}")
        filename = f"{idx:02d}_{safe_title}.md"
        filepath = output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        chapter_files.append(str(filepath))
        
        word_count = len([c for c in md_content if '\u4e00' <= c <= '\u9fff']) + len(md_content.split())
        print(f"[INFO] 保存章节 {idx}: {doc_chapter.title[:40]}... ({word_count} 字)")
    
    print(f"\n[INFO] 分章完成!")
    print(f"  章节数: {len(document.chapters)}")
    print(f"  输出目录: {output_dir}")
    print(f"  文件格式: Markdown (.md)")
    
    return {
        'success': True,
        'file': str(file_path),
        'chapters': len(document.chapters),
        'output_dir': str(output_dir),
        'chapter_files': chapter_files
    }


def analyze_chapter(chapter_file: Path, output_dir: Path, model: str = "kimi-k2.5") -> Dict:
    """分析单个章节，生成综合分析文件"""
    md_content = chapter_file.read_text(encoding='utf-8')
    title, content = extract_content_from_md(md_content)
    
    match = re.match(r'(\d+)_.*\.md', chapter_file.name)
    index = int(match.group(1)) if match else 0
    
    if not content.strip():
        return {'success': False, 'chapter': title, 'error': '章节内容为空'}
    
    safe_title = _sanitize_filename(title)
    chapter_dir = output_dir / f"第{index:02d}章_{safe_title}"
    chapter_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n[INFO] 分析第{index}章: {title[:40]}...")
    print("  -> 生成章节分析...")
    
    content_truncated = content[:4000] if len(content) > 4000 else content
    prompt = CHAPTER_ANALYSIS_PROMPT.format(title=title, index=index, content=content_truncated)
    
    analysis_content = f"""# 第{index}章 {title} - 章节分析

---

## 待AI分析

**提示词已准备就绪，请使用以下提示词调用AI模型进行分析：**

---

{prompt}

---

**建议**：使用 `{model}` 模型进行分析，可获得最佳效果。

**章节原始内容字数**：{len(content)} 字
"""
    
    analysis_file = chapter_dir / "章节分析.md"
    with open(analysis_file, 'w', encoding='utf-8') as f:
        f.write(analysis_content)
    
    return {
        'success': True,
        'chapter': title,
        'chapter_dir': str(chapter_dir),
        'file': str(analysis_file)
    }


def main():
    parser = argparse.ArgumentParser(description='全自动书籍处理 - 分章 + 分析')
    parser.add_argument('file_path', help='书籍文件路径')
    parser.add_argument('--output-dir', '-o', help='输出目录（默认：D:/Mylibrary/书籍总结）')
    parser.add_argument('--model', '-m', default='kimi-k2.5', help='使用的AI模型')
    parser.add_argument('--skip-split', action='store_true', help='跳过分章，只进行分析')
    parser.add_argument('--md-dir', help='MD文件目录（与--skip-split配合使用）')
    
    args = parser.parse_args()
    
    # 步骤1：分章
    if not args.skip_split:
        print("=" * 60)
        print("步骤 1/2: 分章处理")
        print("=" * 60)
        
        result = process_book(args.file_path, args.output_dir)
        
        if not result['success']:
            print(f"[ERROR] 分章失败: {result.get('error', '未知错误')}")
            sys.exit(1)
        
        md_dir = Path(result['output_dir'])
    else:
        if not args.md_dir:
            print("[ERROR] 使用--skip-split时必须指定--md-dir")
            sys.exit(1)
        md_dir = Path(args.md_dir)
    
    # 步骤2：章节分析
    print("\n" + "=" * 60)
    print("步骤 2/2: 章节分析")
    print("=" * 60)
    print("[INFO] 注意：此步骤需要AI模型参与分析")
    print("[INFO] 当前版本生成提示词文件，需要AI后续处理")
    print("[INFO] 输出格式：每个章节 1 个综合分析文件（章节分析.md）")
    
    md_files = sorted(md_dir.glob('*.md'))
    
    if not md_files:
        print(f"[ERROR] 未找到MD文件: {md_dir}")
        sys.exit(1)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    analysis_dir = Path(f"{md_dir}_全书分析_{timestamp}")
    analysis_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"[INFO] 分析输出目录: {analysis_dir}")
    print(f"[INFO] 总章节数: {len(md_files)}")
    
    success_count = 0
    fail_count = 0
    
    for chapter_file in md_files:
        result = analyze_chapter(chapter_file, analysis_dir, args.model)
        
        if result['success']:
            success_count += 1
        else:
            print(f"[WARN] 分析失败: {result.get('error', '未知错误')}")
            fail_count += 1
    
    print(f"\n" + "=" * 60)
    print("处理完成!")
    print("=" * 60)
    print(f"  分章文件: {md_dir}")
    print(f"  分析文件: {analysis_dir}")
    print(f"  成功: {success_count} 章")
    print(f"  失败: {fail_count} 章")
    print(f"\n[注意] 分析文件包含AI提示词，需要调用AI模型完成实际分析")


if __name__ == '__main__':
    main()
