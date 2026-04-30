#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
章节分析器 - 自动为每个章节生成综合分析文件

使用方式：
    python chapter_analyzer.py <分章MD目录> [--model kimi-k2.5]
    
示例：
    python chapter_analyzer.py "D:/Mylibrary/书籍总结/我的书"
"""
import sys
import re
from pathlib import Path
from typing import Dict, List, Optional
import argparse


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


def extract_content_from_md(md_content: str) -> tuple:
    """
    从Markdown内容中提取标题和正文
    
    Args:
        md_content: Markdown文件内容
    
    Returns:
        (title, content) 元组
    """
    lines = md_content.split('\n')
    
    # 提取标题（第一行的一级标题）
    title = "未命名章节"
    if lines and lines[0].startswith('# '):
        title = lines[0][2:].strip()
    
    # 提取正文（去掉头部信息和尾部信息）
    content_lines = []
    in_content = False
    
    for line in lines:
        # 跳过标题行
        if line.startswith('# ') and not in_content:
            continue
        
        # 遇到第一个 --- 开始正文
        if line.strip() == '---' and not in_content:
            in_content = True
            continue
        
        # 遇到第二个 --- 结束头部信息区域
        if line.strip() == '---' and in_content:
            in_content = False
            # 再跳过一个空行
            continue
        
        # 遇到尾部的 --- 结束正文
        if line.strip() == '---' and not in_content:
            break
        
        # 跳过元信息行
        if in_content and (line.startswith('**章节') or line.startswith('**字数') or 
                          line.startswith('**生成时间') or line.startswith('**章节层级')):
            continue
        
        # 跳过空行（头部和正文之间的）
        if in_content and not line.strip():
            continue
        
        # 开始收集正文
        if in_content and line.strip():
            in_content = "collecting"  # 标记为正在收集正文
        
        if in_content == "collecting":
            content_lines.append(line)
    
    content = '\n'.join(content_lines).strip()
    
    # 去掉尾部的自动生成标记
    if '*由 FastSecond Read 自动生成*' in content:
        content = content.split('*由 FastSecond Read 自动生成*')[0].strip()
    
    return title, content


def analyze_chapter(chapter_file: Path, output_dir: Path, model: str = "kimi-k2.5") -> Dict:
    """
    分析单个章节，生成综合分析文件
    
    Args:
        chapter_file: 章节MD文件路径
        output_dir: 输出目录
        model: 使用的AI模型
    
    Returns:
        处理结果字典
    """
    # 读取章节内容
    md_content = chapter_file.read_text(encoding='utf-8')
    
    # 提取标题和正文
    title, content = extract_content_from_md(md_content)
    
    # 从文件名提取序号
    match = re.match(r'(\d+)_.*\.md', chapter_file.name)
    index = int(match.group(1)) if match else 0
    
    if not content.strip():
        return {
            'success': False,
            'chapter': title,
            'error': '章节内容为空'
        }
    
    # 创建章节输出目录
    safe_title = _sanitize_filename(title)
    chapter_dir = output_dir / f"第{index:02d}章_{safe_title}"
    chapter_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n[INFO] 分析第{index}章: {title[:40]}...")
    
    # 生成综合分析文件
    print("  -> 生成章节分析...")
    analysis_content = _generate_analysis(
        title=title,
        index=index,
        content=content,
        model=model
    )
    
    analysis_file = chapter_dir / "章节分析.md"
    _write_md_file(analysis_file, analysis_content)
    
    return {
        'success': True,
        'chapter': title,
        'chapter_dir': str(chapter_dir),
        'file': str(analysis_file)
    }


def _generate_analysis(title: str, index: int, content: str, model: str) -> str:
    """
    调用AI模型生成分析内容
    
    注意：这里使用模拟实现，实际使用时需要接入真实的LLM API
    """
    # 截取内容避免超出上下文限制
    content_truncated = content[:4000] if len(content) > 4000 else content
    
    prompt = CHAPTER_ANALYSIS_PROMPT.format(
        title=title,
        index=index,
        content=content_truncated
    )
    
    # TODO: 接入真实的LLM API
    # 这里返回一个占位符，表示需要AI分析
    return f"""# 第{index}章 {title} - 章节分析

---

## 待AI分析

**提示词已准备就绪，请使用以下提示词调用AI模型进行分析：**

---

{prompt}

---

**建议**：使用 `{model}` 模型进行分析，可获得最佳效果。

**章节原始内容字数**：{len(content)} 字
"""


def _write_md_file(filepath: Path, content: str):
    """写入Markdown文件"""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


def _sanitize_filename(name: str) -> str:
    """清理文件名中的非法字符"""
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = name.strip('. ')
    if len(name) > 80:
        name = name[:80]
    return name or 'untitled'


def main():
    parser = argparse.ArgumentParser(description='章节分析器 - 自动为每个章节生成综合分析文件')
    parser.add_argument('input_dir', help='分章MD文件所在目录')
    parser.add_argument('--output-dir', '-o', help='输出目录（默认：输入目录_analysis_日期）')
    parser.add_argument('--model', '-m', default='kimi-k2.5', help='使用的AI模型')
    parser.add_argument('--range', '-r', help='章节范围，如 "1-10" 或 "1,3,5"')
    
    args = parser.parse_args()
    
    input_dir = Path(args.input_dir)
    
    if not input_dir.exists():
        print(f"[ERROR] 目录不存在: {input_dir}")
        sys.exit(1)
    
    # 查找所有MD文件
    md_files = sorted(input_dir.glob('*.md'))
    
    if not md_files:
        print(f"[ERROR] 未找到MD文件: {input_dir}")
        print("[INFO] 请先使用 book_processor.py 处理书籍文件")
        sys.exit(1)
    
    # 确定输出目录
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        output_dir = Path(f"{input_dir}_全书分析_{timestamp}")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"[INFO] 找到 {len(md_files)} 个章节文件")
    print(f"[INFO] 输出目录: {output_dir}")
    print(f"[INFO] 使用模型: {args.model}")
    print(f"[INFO] 输出格式: 每个章节 1 个综合分析文件（章节分析.md）")
    
    # 解析章节范围
    target_files = md_files
    if args.range:
        indices = _parse_range(args.range)
        target_files = [f for f in md_files if int(re.match(r'(\d+)_.*', f.name).group(1)) in indices]
        print(f"[INFO] 处理章节范围: {args.range} (共{len(target_files)}章)")
    
    # 处理每个章节
    success_count = 0
    fail_count = 0
    
    for chapter_file in target_files:
        result = analyze_chapter(chapter_file, output_dir, args.model)
        
        if result['success']:
            success_count += 1
        else:
            print(f"[WARN] 分析失败: {result.get('error', '未知错误')}")
            fail_count += 1
    
    print(f"\n[INFO] 处理完成!")
    print(f"  成功: {success_count} 章")
    print(f"  失败: {fail_count} 章")
    print(f"  输出目录: {output_dir}")


def _parse_range(range_str: str) -> set:
    """解析章节范围"""
    indices = set()
    
    for part in range_str.split(','):
        part = part.strip()
        if '-' in part:
            start, end = part.split('-')
            indices.update(range(int(start), int(end) + 1))
        else:
            indices.add(int(part))
    
    return indices


if __name__ == '__main__':
    main()
