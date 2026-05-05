#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os

# 读取示例文件
folder = r'D:\Mylibrary\书籍总结\刻意练习：如何从新手到大师 - 安德斯·艾利克森（Anders Ericsson） & 罗伯特·普尔（Robert Pool）\03_第1章　有目的的练习'

files = ['01_章节概述.md', '02_知识要素.md', '05_思维导图.md', '06_知识提问.md']

for filename in files:
    filepath = os.path.join(folder, filename)
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        print(f"\n{'='*70}")
        print(f"文件: {filename}")
        print('='*70)
        print(content[:1500])
        print("...")
