#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
合并所有章节分析文件为一个完整的深度分析文档
"""

import os
import re

BOOK_DIR = r"D:\Mylibrary\书籍总结\刻意练习：如何从新手到大师 - 安德斯·艾利克森（Anders Ericsson） & 罗伯特·普尔（Robert Pool）"
OUTPUT_FILE = r"D:\Mylibrary\书籍总结\刻意练习_全章节深度分析.md"

def get_chapter_folders():
    """获取所有章节文件夹，按序号排序"""
    folders = []
    for item in os.listdir(BOOK_DIR):
        item_path = os.path.join(BOOK_DIR, item)
        if os.path.isdir(item_path):
            # 提取序号
            match = re.match(r'^(\d+)_', item)
            if match:
                folders.append((int(match.group(1)), item))
    return [f[1] for f in sorted(folders)]

def read_file_if_exists(folder_path, filename):
    """读取文件，如果不存在返回None"""
    filepath = os.path.join(folder_path, filename)
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    return None

def extract_chapter_title(folder_name, folder_path):
    """提取章节标题"""
    # 从文件夹名提取
    match = re.match(r'^\d+_(.+)$', folder_name)
    if match:
        return match.group(1)
    return folder_name

def merge_chapter_analysis(folder_path, folder_name):
    """合并单个章节的所有分析文件"""
    chapter_title = extract_chapter_title(folder_name, folder_path)
    
    content = f"""# {chapter_title}

"""
    
    # 定义文件顺序和标题映射
    files_to_merge = [
        ('01_章节概述.md', '## 章节概述'),
        ('02_知识要素.md', '## 知识要素'),
        ('03_案例分析.md', '## 案例分析'),
        ('04_应用拓展.md', '## 应用拓展'),
        ('05_思维导图.md', '## 思维导图'),
        ('06_知识提问.md', '## 知识提问'),
        ('07_AI深度分析.md', '## AI深度分析'),
    ]
    
    has_content = False
    for filename, section_title in files_to_merge:
        file_content = read_file_if_exists(folder_path, filename)
        if file_content and file_content.strip():
            # 移除文件中原有的标题，使用统一的标题
            lines = file_content.split('\n')
            # 找到第一个非空行
            start_idx = 0
            for i, line in enumerate(lines):
                if line.strip():
                    # 如果是标题行，跳过
                    if line.startswith('#'):
                        start_idx = i + 1
                    break
            
            body = '\n'.join(lines[start_idx:]).strip()
            if body:
                content += f"""{section_title}

{body}

---

"""
                has_content = True
    
    return content if has_content else None

def generate_full_book_analysis():
    """生成全书合并分析"""
    
    # 构建文档头部
    full_content = """# 《刻意练习：如何从新手到大师》全章节深度分析

**作者**: 安德斯·艾利克森（Anders Ericsson） & 罗伯特·普尔（Robert Pool）  
**分析时间**: 2026-05-05  
**分析方式**: AI逐章深度解读

---

## 目录

"""
    
    folders = get_chapter_folders()
    
    # 生成目录
    for i, folder in enumerate(folders, 1):
        title = extract_chapter_title(folder, None)
        full_content += f"{i}. [{title}](#{i}-{title.replace(' ', '-').lower()})\n"
    
    full_content += "\n---\n\n"
    
    # 合并各章节
    for i, folder in enumerate(folders, 1):
        folder_path = os.path.join(BOOK_DIR, folder)
        print(f"处理: {folder}")
        
        chapter_content = merge_chapter_analysis(folder_path, folder)
        if chapter_content:
            # 添加章节锚点
            title = extract_chapter_title(folder, None)
            full_content += f"<a name=\"{i}-{title.replace(' ', '-').lower()}\"></a>\n\n"
            full_content += chapter_content
            full_content += "\n\n---\n\n"
    
    # 添加全书总结
    full_content += """# 全书总结

## 核心观点

1. **天才不是天生的**：所有杰出成就都来自刻意练习，而非天赋
2. **刻意练习 ≠ 普通练习**：需要明确目标、专注投入、及时反馈、走出舒适区
3. **心理表征是关键**：高手拥有更复杂、更结构化的心理表征
4. **黄金标准**：找到优秀导师 + 专注弱项 + 大量重复

## 实践框架

```
目标设定 → 专注练习 → 获取反馈 → 调整改进 → 突破舒适区
    ↑                                              ↓
    └────────────── 循环迭代 ←─────────────────────┘
```

## 应用领域

- **工作**：将工作本身变成练习场
- **生活**：在日常活动中融入刻意练习原则
- **教育**：培养孩子成为杰出人物的四阶段路线图

---

**文档生成时间**: 2026-05-05  
**分析工具**: fastsecond-read + AI深度分析
"""
    
    # 保存文件
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(full_content)
    
    print(f"\n[OK] 合并完成！")
    print(f"[FILE] 输出文件: {OUTPUT_FILE}")
    print(f"[SIZE] 文件大小: {os.path.getsize(OUTPUT_FILE) / 1024:.2f} KB")
    print(f"[COUNT] 章节数: {len(folders)}")

if __name__ == '__main__':
    generate_full_book_analysis()
