#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastSecond Read - 智能书籍分章工具

只做一件事：分章节，把每个章节的内容提取出来保存为排版好的MD文件

使用方式：
    from book_processor import process_book
    result = process_book("书籍.epub", "输出目录")
    
    或命令行：
    python book_processor.py "书籍.epub"
"""
import sys
import re
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from readers.factory import ReaderFactory


def format_chapter_content(doc_chapter, index: int, hierarchy_path: str = "") -> str:
    """
    将章节内容格式化为美观的Markdown，并在内容中标记一级、二级、三级标题
    
    Args:
        doc_chapter: 章节对象
        index: 章节序号
        hierarchy_path: 层级路径（如 "1.2.3" 表示第1章第2节第3小节）
    
    Returns:
        格式化后的Markdown内容
    """
    title = doc_chapter.title or f"第{index}章"
    level = doc_chapter.level
    
    # 根据层级确定标题前缀 (# ## ###)
    heading_prefix = "#" * level
    
    # 层级标记符号
    level_markers = {1: "【章】", 2: "【节】", 3: "【小节】"}
    level_marker = level_markers.get(level, f"【层级{level}】")
    
    # 提取并标记正文内容中的标题层级
    content_parts = []
    for block in doc_chapter.content_blocks:
        if block.text:
            text = block.text.strip()
            if text:
                # 根据内容块类型和层级添加标记
                marked_text = _mark_heading_level(block, text)
                content_parts.append(marked_text)
    
    content = '\n\n'.join(content_parts)
    word_count = len(content)
    
    # 构建Markdown文档
    md_lines = []
    
    # 文档头部信息
    md_lines.append(f"{heading_prefix} {title}")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")
    md_lines.append(f"**章节序号**：第{index}章  ")
    md_lines.append(f"**章节层级**：{level} {level_marker}  ")
    md_lines.append(f"**层级路径**：{hierarchy_path or str(index)}  ")
    md_lines.append(f"**字数统计**：{word_count} 字  ")
    md_lines.append(f"**生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M')}  ")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")
    
    # 正文内容
    if content:
        md_lines.append(content)
    else:
        md_lines.append("*（本章内容为空）*")
    
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")
    md_lines.append("*由 FastSecond Read 自动生成*")
    
    return '\n'.join(md_lines)


def process_book(file_path: str, output_dir: Optional[str] = None) -> Dict:
    """
    处理书籍文件，分章节提取内容为排版好的MD文件
    
    Args:
        file_path: 书籍文件路径
        output_dir: 输出目录（可选，默认 D:/Mylibrary/书籍总结）
    
    Returns:
        {
            'success': bool,
            'file': str,
            'chapters': int,
            'output_dir': str,
            'chapter_files': List[str]
        }
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        return {'success': False, 'error': f'文件不存在: {file_path}'}
    
    # 读取文件
    print(f"[INFO] 读取文件: {file_path}")
    document = ReaderFactory.read_file(str(file_path))
    
    if not document or not document.chapters:
        return {'success': False, 'error': '无法提取文件内容'}
    
    # 创建输出目录
    if output_dir is None:
        output_dir = Path('D:/Mylibrary/书籍总结') / file_path.stem.strip()
    else:
        output_dir = Path(output_dir) / file_path.stem.strip()
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存每个章节（支持层级结构）
    chapter_files = []
    
    def process_chapter(chapter, index: int, parent_path: str = "") -> str:
        """递归处理章节，返回层级路径"""
        # 构建层级路径
        if parent_path:
            hierarchy_path = f"{parent_path}.{index}"
        else:
            hierarchy_path = str(index)
        
        # 格式化章节内容为Markdown
        md_content = format_chapter_content(chapter, index, hierarchy_path)
        
        # 保存MD文件
        safe_title = _sanitize_filename(chapter.title or f"chapter_{index}")
        filename = f"{hierarchy_path.replace('.', '_')}_{safe_title}.md"
        filepath = output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        chapter_files.append(str(filepath))
        
        # 统计字数
        word_count = len([c for c in md_content if '\u4e00' <= c <= '\u9fff']) + len(md_content.split())
        safe_title = chapter.title[:40].replace('\xa0', ' ').replace('\u3000', ' ')
        # 安全编码处理
        try:
            safe_title_display = safe_title.encode('gbk', errors='ignore').decode('gbk')
        except:
            safe_title_display = f"Chapter_{index}"
        
        level_marker = {1: "【章】", 2: "【节】", 3: "【小节】"}.get(chapter.level, "")
        print(f"[INFO] 保存 {level_marker} {hierarchy_path}: {safe_title_display}... ({word_count} 字)")
        
        # 递归处理子章节
        if hasattr(chapter, 'sub_chapters') and chapter.sub_chapters:
            for sub_idx, sub_chapter in enumerate(chapter.sub_chapters, 1):
                process_chapter(sub_chapter, sub_idx, hierarchy_path)
        
        return hierarchy_path
    
    # 处理所有顶级章节
    for idx, doc_chapter in enumerate(document.chapters, 1):
        process_chapter(doc_chapter, idx)
    
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


def _mark_heading_level(block, text: str) -> str:
    """
    根据内容块类型标记标题层级，使用 # 标记
    
    Args:
        block: 内容块对象
        text: 文本内容
    
    Returns:
        带层级标记的文本（使用 # ## ### 格式）
    """
    from core.document import ContentType
    
    # 如果是标题类型，根据层级添加 # 标记
    if block.type == ContentType.TITLE or block.type == ContentType.HEADING:
        level = block.level
        # 限制 level 在 1-6 范围内
        if level < 1:
            level = 1
        if level > 6:
            level = 6
        # 使用 # 标记，例如：## 二级标题
        prefix = "#" * level
        return f"{prefix} {text}"
    
    return text


def _sanitize_filename(name: str) -> str:
    """清理文件名中的非法字符"""
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = name.strip('. ')
    if len(name) > 80:
        name = name[:80]
    return name or 'untitled'


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("=" * 60)
        print("FastSecond Read - 智能书籍分章工具")
        print("=" * 60)
        print()
        print("用法: python book_processor.py <文件路径> [输出目录]")
        print()
        print("示例:")
        print("  python book_processor.py '书籍.epub'")
        print("  python book_processor.py '书籍.pdf' 'D:/我的总结'")
        print()
        print("输出: 每个章节一个排版好的 Markdown 文件")
        print("=" * 60)
        sys.exit(1)
    
    file_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    result = process_book(file_path, output_dir)
    
    if not result['success']:
        print(f"[ERROR] {result.get('error', '处理失败')}")
        sys.exit(1)
