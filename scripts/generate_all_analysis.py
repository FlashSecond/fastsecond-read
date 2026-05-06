#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量生成所有章节的AI深度分析
"""

import os
import sys
import re

sys.path.insert(0, 'C:\\Users\\GSecond\\.qclaw\\skills\\fastsecond-read\\scripts')

def get_chapter_folders(book_dir):
    """获取所有章节文件夹，按序号排序"""
    folders = []
    for item in os.listdir(book_dir):
        item_path = os.path.join(book_dir, item)
        if os.path.isdir(item_path):
            match = re.match(r'^(\d+)_', item)
            if match:
                folders.append((int(match.group(1)), item))
    return sorted(folders)

def read_chapter_content(folder_path):
    """读取章节内容"""
    for f in os.listdir(folder_path):
        if f.endswith('.md') and not f.startswith('AI'):
            filepath = os.path.join(folder_path, f)
            try:
                with open(filepath, 'r', encoding='utf-8') as file:
                    return file.read(), f
            except Exception as e:
                print(f"  读取失败: {e}")
                return None, None
    return None, None

def extract_headers(content):
    """提取标题结构"""
    headers = []
    for match in re.finditer(r'^(#{1,6})\s+(.+)$', content, re.MULTILINE):
        level = len(match.group(1))
        title = match.group(2).strip()
        headers.append((level, title))
    return headers

def count_words(content):
    """统计中文字数"""
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', content)
    return len(chinese_chars)

def generate_analysis_template(chapter_title, word_count, headers):
    """生成分析模板"""
    
    header_structure = ""
    for level, title in headers[:15]:
        indent = "  " * (level - 1)
        header_structure += f"{indent}{'#' * level} {title}\n"
    
    template = f"""# {chapter_title} - AI深度分析

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
- **案例背景**：[背景信息]
- **关键要素**：[核心要素分析]
- **发展过程**：[事件发展脉络]

**理论印证**：
[该案例如何印证或说明本章的理论观点，引用原文分析]

**启示意义**：
[案例的价值和启示，对读者的意义]

---

### 案例二：[案例名称/主题]

**案例内容**：
[简要描述案例的具体内容]

**案例分析**：
- **案例背景**：[背景信息]
- **关键要素**：[核心要素分析]
- **发展过程**：[事件发展脉络]

**理论印证**：
[该案例如何印证或说明本章的理论观点]

**启示意义**：
[案例的价值和启示]

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

**章节字数**：{word_count} 字  
**分析深度**：六维完整分析框架

---

*注：此为分析框架模板。完整深度分析需要：*
1. *阅读本章AI分析提示词.md中的详细内容*
2. *结合章节原文进行深入分析*
3. *参考第1-3章的完整分析示例*
"""
    return template

def main():
    book_dir = r"D:\Mylibrary\书籍总结\20181208思辨与立场[理查德·保罗]"
    
    folders = get_chapter_folders(book_dir)
    total = len(folders)
    
    print(f"共 {total} 个章节\n")
    
    generated = 0
    skipped = 0
    
    for num, folder_name in folders:
        folder_path = os.path.join(book_dir, folder_name)
        analysis_path = os.path.join(folder_path, 'AI深度分析.md')
        
        # 检查是否已存在
        if os.path.exists(analysis_path):
            print(f"[跳过] {folder_name} - 已存在AI深度分析")
            skipped += 1
            continue
        
        print(f"[生成] {folder_name}")
        
        # 读取章节内容
        content, filename = read_chapter_content(folder_path)
        if not content:
            print(f"  读取失败，跳过")
            continue
        
        # 提取信息
        headers = extract_headers(content)
        chapter_title = headers[0][1] if headers else folder_name
        word_count = count_words(content)
        
        print(f"  标题: {chapter_title}")
        print(f"  字数: {word_count}")
        
        # 生成分析模板
        analysis = generate_analysis_template(chapter_title, word_count, headers)
        
        # 保存
        try:
            with open(analysis_path, 'w', encoding='utf-8') as f:
                f.write(analysis)
            print(f"  [OK] 已生成AI深度分析框架\n")
            generated += 1
        except Exception as e:
            print(f"  保存失败: {e}\n")
    
    print("=" * 60)
    print(f"处理完成: 生成 {generated} 个, 跳过 {skipped} 个, 总计 {total} 个")
    print("=" * 60)

if __name__ == "__main__":
    main()
