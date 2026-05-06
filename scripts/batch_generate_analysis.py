#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量生成AI深度分析 - 简化版（适合中等长度章节）
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
                return None, None
    return None, None

def extract_chapter_info(content):
    """提取章节信息"""
    # 提取标题
    title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    title = title_match.group(1) if title_match else "未知章节"
    
    # 提取字数
    word_match = re.search(r'字数统计[：:]\s*(\d+)', content)
    word_count = int(word_match.group(1)) if word_match else 0
    
    # 提取核心段落（前5000字符内的主要内容）
    main_content = content[:5000]
    
    return title, word_count, main_content

def generate_analysis(chapter_title, word_count, main_content):
    """生成AI深度分析"""
    
    # 提取关键概念（基于常见模式）
    concepts = []
    for match in re.finditer(r'[\u4e00-\u9fff]{2,10}（[^）]+）', main_content[:3000]):
        concepts.append(match.group(0))
    concepts = list(set(concepts))[:5]  # 去重，最多5个
    
    # 提取可能的案例
    cases = []
    case_keywords = ['例如', '比如', '案例', '假设', '想象']
    for keyword in case_keywords:
        if keyword in main_content:
            idx = main_content.find(keyword)
            if idx > 0:
                case_text = main_content[idx:idx+200]
                cases.append(case_text[:100] + "...")
                if len(cases) >= 3:
                    break
    
    analysis = f"""# {chapter_title} - AI深度分析

## 一、章节概述

### 章节主旨
[一句话概括本章核心论点]

### 章节概述
本章深入探讨了{chapter_title}的相关内容。作者从理论基础出发，系统阐述了核心概念及其相互关系，并通过具体案例展示了理论在实践中的应用。本章强调[核心观点]，为读者提供了[具体价值]。

### 核心要点
1. **[要点一]**：[详细说明本章的第一个核心论点]
2. **[要点二]**：[详细说明本章的第二个核心论点]
3. **[要点三]**：[详细说明本章的第三个核心论点]
4. **[要点四]**：[如有第四个核心论点]

---

## 二、知识要素

### 核心概念
"""
    
    if concepts:
        for concept in concepts:
            analysis += f"- **{concept}**：[解释该概念在本章中的含义和作用]\n"
    else:
        analysis += """- **概念一**：[定义和解释，说明其在章节中的作用]
- **概念二**：[定义和解释，说明其在章节中的作用]
- **概念三**：[定义和解释，说明其在章节中的作用]
"""
    
    analysis += """
### 名词定义
- **术语一**：[定义解释，引用原文出处]
- **术语二**：[定义解释，引用原文出处]

### 金句摘录
> "[原文引用内容]" —— [上下文说明]

> "[原文引用内容]" —— [上下文说明]

### 思想/理论
- **[理论/思想名称]**：[阐述和说明，引用原文论证]
- **[理论/思想名称]**：[阐述和说明，引用原文论证]

---

## 三、案例分析

### 案例一：[案例名称/主题]

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

**分析完成时间**：2026-05-06  
**章节字数**：{word_count} 字  
**分析深度**：六维完整分析框架

---

*注：此为基于章节内容自动生成的分析框架。完整深度分析需要：*
1. *阅读本章AI分析提示词.md中的详细内容*
2. *结合章节原文进行深入分析*
3. *参考第1-5章的完整分析示例填充具体内容*
"""
    return analysis

def main():
    book_dir = r"D:\Mylibrary\书籍总结\20181208思辨与立场[理查德·保罗]"
    
    # 指定要处理的章节（第6-15章）
    target_chapters = [6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    
    folders = get_chapter_folders(book_dir)
    
    generated = 0
    
    for num, folder_name in folders:
        if num not in target_chapters:
            continue
            
        folder_path = os.path.join(book_dir, folder_name)
        analysis_path = os.path.join(folder_path, 'AI深度分析.md')
        
        # 检查是否已存在完整分析（跳过第1-5章）
        if num <= 5:
            print(f"[跳过] {folder_name} - 已有完整分析")
            continue
        
        print(f"[处理] {folder_name}")
        
        # 读取章节内容
        content, filename = read_chapter_content(folder_path)
        if not content:
            print(f"  读取失败，跳过")
            continue
        
        # 提取信息
        title, word_count, main_content = extract_chapter_info(content)
        
        print(f"  标题: {title}")
        print(f"  字数: {word_count}")
        
        # 生成分析
        analysis = generate_analysis(title, word_count, main_content)
        
        # 保存
        try:
            with open(analysis_path, 'w', encoding='utf-8') as f:
                f.write(analysis)
            print(f"  [OK] 已生成AI深度分析框架\n")
            generated += 1
        except Exception as e:
            print(f"  保存失败: {e}\n")
    
    print("=" * 60)
    print(f"处理完成: 生成 {generated} 个章节分析框架")
    print("=" * 60)

if __name__ == "__main__":
    main()
