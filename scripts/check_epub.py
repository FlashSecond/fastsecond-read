#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, 'C:\\Users\\GSecond\\.qclaw\\skills\\fastsecond-read\\scripts')
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import re

book = epub.read_epub('D:\\Mylibrary\\兴趣\\思维\\心理\\20181208思辨与立场[理查德·保罗].epub')

print("=== EPUB 文件结构 ===\n")

# 获取所有HTML文件
html_items = []
for item in book.get_items():
    if item.get_type() == ebooklib.ITEM_DOCUMENT:
        name = item.get_name()
        try:
            content = item.get_content().decode('utf-8')
            html_items.append((name, content))
        except:
            pass

# 按文件名排序
html_items.sort(key=lambda x: x[0])

# 提取每个文件的标题
chapter_pattern = re.compile(r'第[一二三四五六七八九十百千\d]+章|Chapter\s*\d+|^\d+\s+', re.IGNORECASE)

for name, content in html_items[:30]:  # 只看前30个文件
    soup = BeautifulSoup(content, 'html.parser')
    
    # 查找h1-h3标签
    headings = []
    for tag in ['h1', 'h2', 'h3']:
        for elem in soup.find_all(tag):
            text = elem.get_text(strip=True)
            if text and len(text) < 100:
                is_chapter = bool(chapter_pattern.search(text))
                headings.append((tag, text, is_chapter))
    
    if headings:
        print(f"\n文件: {name}")
        for tag, text, is_chapter in headings[:3]:  # 只显示前3个标题
            marker = "[章]" if is_chapter else ""
            print(f"  <{tag}> {text} {marker}")
