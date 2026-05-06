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
chapters = reader._build_chapters_from_detection(result['chapters'], file_contents)

print(f'构建的章节数: {len(chapters)}')
for i, ch in enumerate(chapters, 1):
    print(f'{i}. {ch.title} (level={ch.level}, words={ch.word_count})')
