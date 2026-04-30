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


def format_chapter_content(doc_chapter, index: int) -> str:
    """
    将章节内容格式化为美观的Markdown
    
    Args:
        doc_chapter: 章节对象
        index: 章节序号
    
    Returns:
        格式化后的Markdown内容
    """
    title = doc_chapter.title or f"第{index}章"
    
    # 提取正文内容
    content_parts = []
    for block in doc_chapter.content_blocks:
        if block.text:
            text = block.text.strip()
            if text:
                content_parts.append(text)
    
    content = '\n\n'.join(content_parts)
    word_count = len(content)
    
    # 构建Markdown文档
    md_lines = []
    
    # 文档头部信息
    md_lines.append(f"# {title}")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")
    md_lines.append(f"**章节序号**：第{index}章  ")
    md_lines.append(f"**章节层级**：{doc_chapter.level}  ")
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
    
    # 保存每个章节
    chapter_files = []
    
    for idx, doc_chapter in enumerate(document.chapters, 1):
        # 格式化章节内容为Markdown
        md_content = format_chapter_content(doc_chapter, idx)
        
        # 保存MD文件
        safe_title = _sanitize_filename(doc_chapter.title or f"chapter_{idx}")
        filename = f"{idx:02d}_{safe_title}.md"
        filepath = output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        chapter_files.append(str(filepath))
        
        # 统计字数
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
