#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量AI深度分析生成器
为多个章节快速生成AI深度分析文档
"""

import os
import re
from pathlib import Path

def get_chapter_info(book_dir):
    """获取所有章节信息"""
    chapters = []
    for item in sorted(os.listdir(book_dir)):
        item_path = os.path.join(book_dir, item)
        if os.path.isdir(item_path):
            match = re.match(r'^(\d+)_(.+)', item)
            if match:
                num = int(match.group(1))
                name = match.group(2)
                # 找到章节md文件
                md_file = None
                for f in os.listdir(item_path):
                    if f.endswith('.md') and not f.startswith('AI'):
                        md_file = os.path.join(item_path, f)
                        break
                if md_file:
                    chapters.append({
                        'num': num,
                        'folder': item,
                        'name': name,
                        'path': item_path,
                        'md_file': md_file
                    })
    return sorted(chapters, key=lambda x: x['num'])

def extract_chapter_summary(md_file):
    """提取章节核心内容摘要"""
    try:
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取标题
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1) if title_match else "未知章节"
        
        # 提取正文（去除元数据）
        parts = content.split('---')
        if len(parts) >= 3:
            body = parts[2].strip()
        else:
            body = content
        
        # 提取所有二级标题
        headers = re.findall(r'^##\s+(.+)$', body, re.MULTILINE)
        
        # 统计字数
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', body))
        
        return {
            'title': title,
            'headers': headers,
            'word_count': chinese_chars,
            'preview': body[:5000]  # 前5000字符作为预览
        }
    except Exception as e:
        print(f"  读取失败: {e}")
        return None

def generate_analysis_template(chapter_info, summary):
    """生成分析文档模板"""
    
    title = summary['title']
    headers_text = '\n'.join([f"- {h}" for h in summary['headers'][:10]])
    
    template = f"""# {title} - AI深度分析

## 一、章节概述

### 章节主旨
[一句话概括本章核心论点]

### 章节概述
本章{summary['word_count']}字，主要探讨：
{headers_text}

[根据上述标题，撰写200-300字的章节概述，说明本章的核心内容、论证逻辑和在全书中的位置]

### 核心要点
1. **要点一**：[根据章节内容提炼第一个核心要点]
2. **要点二**：[提炼第二个核心要点]
3. **要点三**：[提炼第三个核心要点]
4. **要点四**：[如有第四个要点]
5. **要点五**：[如有第五个要点]

---

## 二、知识要素

### 核心概念
- **概念一**：[定义和解释]
- **概念二**：[定义和解释]
- **概念三**：[定义和解释]

### 名词定义
- **术语一**：[定义]
- **术语二**：[定义]

### 金句摘录
> "[原文金句]" —— [上下文]

> "[原文金句]" —— [上下文]

### 思想/理论
- **[理论名称]**：[阐述和说明]

---

## 三、案例分析

### 案例一：[案例名称]

**案例内容**：
[简要描述案例内容]

**案例分析**：
- 案例背景
- 关键要素
- 发展过程

**理论印证**：
[该案例如何印证本章理论]

**启示意义**：
[案例的价值和启示]

---

### 案例二：[案例名称]

**案例内容**：
[简要描述案例内容]

**案例分析**：
- 案例背景
- 关键要素
- 发展过程

**理论印证**：
[该案例如何印证本章理论]

**启示意义**：
[案例的价值和启示]

---

## 四、应用拓展

### 实践方法
- **方法一**：[具体说明]
- **方法二**：[具体说明]

### 操作步骤
1. [步骤一]
2. [步骤二]
3. [步骤三]

### 行动策略
- [策略一]
- [策略二]

### 习惯养成
- [习惯一]
- [习惯二]

---

## 五、思维导图

```mermaid
mindmap
  root(({title}))
    [分支一]
      (子分支一)
      (子分支二)
    [分支二]
      (子分支一)
      (子分支二)
    [分支三]
      (子分支一)
      (子分支二)
```

---

## 六、知识提问

### 基础理解
1. **[问题一]**？[提示]
2. **[问题二]**？[提示]

### 深度思考
3. **[问题三]**？[提示]
4. **[问题四]**？[提示]

### 应用反思
5. **[问题五]**？[提示]
6. **[问题六]**？[提示]

### 拓展探索
7. **[问题七]**？[提示]

---

**分析完成时间**：2026-05-05  
**章节字数**：{summary['word_count']} 字  
**分析深度**：六维完整分析

---

## 待完善内容

> **注意**：本分析为快速模板，需要基于以下章节内容进行深度完善：

### 章节内容预览

```
{summary['preview'][:2000]}...
```

### 完善建议

1. **阅读完整章节内容**：查看原文件 `{os.path.basename(chapter_info['md_file'])}`
2. **提取核心论点**：根据内容提炼3-5个核心要点
3. **分析案例**：识别章节中的具体案例，进行深入分析
4. **提取金句**：找出有价值的原文引用
5. **生成思维导图**：根据章节结构绘制Mermaid图
6. **设计问题**：根据内容设计引导性问题

### 使用方法

1. 打开原章节文件阅读完整内容
2. 根据内容填充本模板中的 `[...]` 部分
3. 删除"待完善内容"章节
4. 保存为完整的AI深度分析文档
"""
    return template

def main():
    """主函数"""
    print("=" * 70)
    print("批量AI深度分析生成器")
    print("=" * 70)
    
    book_dir = r"D:\Mylibrary\书籍总结\刻意练习：如何从新手到大师 - 安德斯·艾利克森（Anders Ericsson） & 罗伯特·普尔（Robert Pool）"
    
    if not os.path.exists(book_dir):
        print(f"错误：书籍目录不存在")
        return
    
    # 获取章节信息
    chapters = get_chapter_info(book_dir)
    print(f"\n发现 {len(chapters)} 个章节\n")
    
    # 只处理第3-8章（索引2-7）
    target_chapters = [c for c in chapters if 5 <= c['num'] <= 10]
    print(f"将为 {len(target_chapters)} 个章节生成分析模板：")
    for ch in target_chapters:
        print(f"  - {ch['folder']}")
    print()
    
    for i, ch in enumerate(target_chapters, 1):
        print(f"[{i}/{len(target_chapters)}] 处理: {ch['folder']}")
        
        # 提取章节摘要
        summary = extract_chapter_summary(ch['md_file'])
        if not summary:
            print(f"  无法读取章节内容")
            continue
        
        print(f"  标题: {summary['title']}")
        print(f"  字数: {summary['word_count']}")
        print(f"  小节: {len(summary['headers'])}")
        
        # 生成分析模板
        analysis = generate_analysis_template(ch, summary)
        
        # 保存分析文件
        output_path = os.path.join(ch['path'], 'AI深度分析_模板.md')
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(analysis)
            print(f"  [OK] 已生成: AI深度分析_模板.md")
        except Exception as e:
            print(f"  [FAIL] 保存失败: {e}")
        
        print()
    
    print("=" * 70)
    print("模板生成完成！")
    print("=" * 70)
    print("\n说明：")
    print("- 生成的是分析模板，包含章节结构框架")
    print("- 需要根据原章节内容手动填充具体信息")
    print("- 建议结合 AI分析提示词.md 使用")

if __name__ == '__main__':
    main()
