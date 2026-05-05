#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI深度分析脚本
读取分章后的书籍，为每章生成完整的六维AI分析
"""

import os
import re
from pathlib import Path

def get_chapter_folders(book_dir):
    """获取所有章节文件夹，按序号排序"""
    folders = []
    for item in os.listdir(book_dir):
        item_path = os.path.join(book_dir, item)
        if os.path.isdir(item_path):
            # 提取序号
            match = re.match(r'^(\d+)_', item)
            if match:
                folders.append((int(match.group(1)), item))
    return [f[1] for f in sorted(folders)]

def read_chapter_content(folder_path):
    """读取章节原文件内容"""
    for f in os.listdir(folder_path):
        if f.endswith('.md') and not f.startswith('0') and not f.startswith('AI'):
            filepath = os.path.join(folder_path, f)
            try:
                with open(filepath, 'r', encoding='utf-8') as file:
                    return file.read(), f
            except Exception as e:
                print(f"  读取失败: {e}")
                return None, None
    return None, None

def extract_headers(content):
    """提取多级标题结构"""
    headers = []
    for match in re.finditer(r'^(#{1,6})\s+(.+)$', content, re.MULTILINE):
        level = len(match.group(1))
        title = match.group(2).strip()
        headers.append((level, title))
    return headers

def extract_body_content(full_content):
    """提取正文内容（去除元数据）"""
    parts = full_content.split('---')
    if len(parts) >= 3:
        return parts[2].strip()
    return full_content

def count_words(content):
    """统计中文字数"""
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', content)
    return len(chinese_chars)

def generate_ai_prompt(chapter_title, headers, word_count, content_preview):
    """生成AI深度分析提示词"""
    
    # 构建标题结构描述
    header_structure = ""
    for level, title in headers[:15]:  # 限制前15个标题
        indent = "  " * (level - 1)
        header_structure += f"{indent}{'#' * level} {title}\n"
    
    prompt = f"""请对以下章节进行完整的AI深度分析，从六个维度输出结构化总结。

【章节信息】
- 章节标题：{chapter_title}
- 章节字数：{word_count} 字
- 标题结构：
{header_structure}

【分析维度】
1. 章节概述 - 主旨、脉络、核心要点
2. 知识要素 - 核心概念、名词定义、金句摘录
3. 案例分析 - 案例内容、分析、理论印证、启示
4. 应用拓展 - 实践方法、操作步骤、行动策略
5. 思维导图 - 章节结构（Mermaid格式）
6. 知识提问 - 基础理解、深度思考、应用反思

【分析原则】
- 基于原文：紧密贴合章节内容，准确引用关键论述
- 深度解读：揭示理论逻辑、概念关联、论证结构
- 结构化输出：按指定格式输出，保持清晰
- 字数要求：章节概述200-300字，每个要点详细说明

【章节内容】
{content_preview}

---

【输出格式】
# {chapter_title} - AI深度分析

## 一、章节概述

### 章节主旨
[一句话概括本章核心论点]

### 章节概述
[200-300字详细阐述：本章在全书中的位置和作用、主要论述的逻辑结构、核心问题的解决路径]

### 核心要点
1. **要点一**：[详细说明，包含关键论据]
2. **要点二**：[详细说明，包含关键论据]
3. **要点三**：[详细说明，包含关键论据]
4. **要点四**：[可选，如有]
5. **要点五**：[可选，如有]

---

## 二、知识要素

### 核心概念
- **概念名称**：[定义和解释，说明其在章节中的作用，引用原文]
- **概念名称**：[...]

### 名词定义
- **术语**：[定义解释，引用原文出处]

### 金句摘录
> "[原文引用内容]" —— [上下文说明]

### 思想/理论
- **[理论/思想名称]**：[阐述和说明，引用原文论证]

---

## 三、案例分析

### 案例一：[案例名称/主题]

**案例内容**：
[简要描述案例的具体内容，包含关键人物、时间、事件]

**案例分析**：
- 案例背景：[背景信息]
- 关键要素：[核心要素分析]
- 发展过程：[事件发展脉络]

**理论印证**：
[该案例如何印证或说明本章的理论观点，引用原文分析]

**启示意义**：
[案例的价值和启示，对读者的意义]

---

## 四、应用拓展

### 实践方法
- **方法名称**：[具体说明如何应用本章知识]

### 操作步骤
1. [步骤一：具体说明]
2. [步骤二：具体说明]
3. [步骤三：具体说明]

### 行动策略
- [策略一：具体说明]
- [策略二：具体说明]

### 习惯养成
- [建议培养的习惯，基于本章内容]

---

## 五、思维导图

```mermaid
mindmap
  root(({chapter_title}))
    [分支一：主要论点]
      (子分支一：论据)
      (子分支二：案例)
    [分支二：核心概念]
      (子分支一：定义)
      (子分支二：应用)
    [分支三：实践方法]
      (子分支一：步骤)
      (子分支二：策略)
```

---

## 六、知识提问

### 基础理解
1. **[问题一]**？[提示：引导回顾本章核心概念]

2. **[问题二]**？[提示：引导梳理本章主要内容]

### 深度思考
3. **[问题三]**？[提示：引导分析本章理论逻辑]

4. **[问题四]**？[提示：引导建立概念之间的联系]

### 应用反思
5. **[问题五]**？[提示：引导联系实际应用场景]

6. **[问题六]**？[提示：引导批判性思考本章观点]

### 拓展探索
7. **[问题七]**？[提示：引导进一步学习方向]

---

**分析完成时间**：自动生成  
**章节字数**：{word_count} 字  
**分析深度**：六维完整分析
"""
    return prompt

def save_analysis_prompt(folder_path, prompt_content):
    """保存AI分析提示词到文件"""
    output_path = os.path.join(folder_path, 'AI分析提示词.md')
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(prompt_content)
        return True
    except Exception as e:
        print(f"  保存失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 70)
    print("《刻意练习》AI深度分析 - 提示词生成器")
    print("=" * 70)
    
    # 书籍目录
    book_dir = r"D:\Mylibrary\书籍总结\刻意练习：如何从新手到大师 - 安德斯·艾利克森（Anders Ericsson） & 罗伯特·普尔（Robert Pool）"
    
    if not os.path.exists(book_dir):
        print(f"错误：书籍目录不存在: {book_dir}")
        return
    
    # 获取所有章节文件夹
    folders = get_chapter_folders(book_dir)
    print(f"\n发现 {len(folders)} 个章节\n")
    
    for i, folder in enumerate(folders, 1):
        folder_path = os.path.join(book_dir, folder)
        print(f"[{i}/{len(folders)}] 处理: {folder}")
        
        # 读取章节内容
        full_content, filename = read_chapter_content(folder_path)
        if not full_content:
            print(f"  无法读取章节内容")
            continue
        
        # 提取正文
        body = extract_body_content(full_content)
        
        # 统计字数
        word_count = count_words(body)
        
        # 提取标题
        headers = extract_headers(body)
        
        # 提取章节标题
        title_match = re.search(r'^#\s+(.+)$', full_content, re.MULTILINE)
        chapter_title = title_match.group(1) if title_match else folder
        
        print(f"  章节: {chapter_title}")
        print(f"  字数: {word_count}")
        print(f"  标题数: {len(headers)}")
        
        # 准备内容预览（前8000字符，约2000-3000字）
        content_preview = body[:8000]
        if len(body) > 8000:
            content_preview += "\n\n...[内容过长，已截取前8000字符]"
        
        # 生成AI提示词
        prompt = generate_ai_prompt(chapter_title, headers, word_count, content_preview)
        
        # 保存提示词文件
        if save_analysis_prompt(folder_path, prompt):
            print(f"  [OK] 已生成: AI分析提示词.md")
        else:
            print(f"  [FAIL] 生成失败")
        
        print()
    
    print("=" * 70)
    print("提示词生成完成！")
    print("=" * 70)
    print("\n使用方法：")
    print("1. 打开每个章节的 'AI分析提示词.md' 文件")
    print("2. 复制文件内容")
    print("3. 发送给AI（如ChatGPT、Claude等）")
    print("4. 将AI生成的分析保存为 'AI深度分析.md'")
    print("\n文件位置：")
    print(f"  {book_dir}")
    print("  └── [章节文件夹]/")
    print("      ├── [原章节].md")
    print("      ├── AI分析提示词.md  ← 生成的提示词")
    print("      └── AI深度分析.md    ← AI生成的分析（需手动保存）")

if __name__ == '__main__':
    main()
