#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, 'C:\\Users\\GSecond\\.qclaw\\skills\\fastsecond-read\\scripts')
from readers.epub_reader import EPUBReader
import ebooklib
from ebooklib import epub

reader = EPUBReader()
book = epub.read_epub('D:\\Mylibrary\\兴趣\\思维\\心理\\20181208思辨与立场[理查德·保罗].epub')

file_contents = {}
for item in book.get_items():
    if item.get_type() == ebooklib.ITEM_DOCUMENT:
        name = item.get_name()
        try:
            content = item.get_content().decode('utf-8')
            file_contents[name] = content
        except:
            pass

result = reader._comprehensive_detect(file_contents)
print(f'方法: {result["method"]}')
print(f'章节数: {result["count"]}')
print('\n章节列表:')
for i, ch in enumerate(result['chapters'][:20], 1):
    is_sub = ch.get('is_subsection', False)
    print(f'{i}. {ch["title"]} (is_subsection={is_sub})')
