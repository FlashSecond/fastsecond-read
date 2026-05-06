#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量生成AI深度分析
"""

import os
import sys
sys.path.insert(0, 'C:\\Users\\GSecond\\.qclaw\\skills\\fastsecond-read\\scripts')

from analyze_book import get_chapter_files, extract_headers, extract_body_content, count_words, generate_ai_analysis

def main():
    book_dir = r"D:\Mylibrary\书籍总结\20181208思辨与立场[理查德·保罗]"
    
    chapter_files = get_chapter_files(book_dir)
    total = len(chapter_files)
    
    print(f"共 {total} 个章节需要生成分析\n")
    
    for i, (num, chapter_file) in enumerate(chapter_files, 1):
        folder_name = chapter_file.replace('.md', '')
        chapter_folder = os.path.join(book_dir, folder_name)
        chapter_path = os.path.join(chapter_folder, chapter_file)
        analysis_path = os.path.join(chapter_folder, 'AI深度分析.md')
        
        # 检查是否已存在分析文件
        if os.path.exists(analysis_path):
            print(f"[{i}/{total}] {folder_name} - 已存在，跳过")
            continue
        
        print(f"[{i}/{total}] 生成分析: {folder_name}")
        
        # 读取章节内容
        try:
            with open(chapter_path, 'r', encoding='utf-8') as f:
                full_content = f.read()
        except Exception as e:
            print(f"  读取失败: {e}")
            continue
        
        # 提取信息
        headers = extract_headers(full_content)
        chapter_title = headers[0][1] if headers else folder_name
        word_count = count_words(full_content)
        
        print(f"  标题: {chapter_title}")
        print(f"  字数: {word_count}")
        
        # 生成分析（这里简化处理，实际应该调用AI）
        # 由于无法直接调用AI，我们生成提示词让用户自行处理
        print(f"  请使用 AI分析提示词.md 生成深度分析")
        print()

if __name__ == "__main__":
    main()
