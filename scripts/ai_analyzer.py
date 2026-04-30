#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 章节分析器 - 自动调用 AI 模型分析章节

使用方式：
    python ai_analyzer.py <分章MD目录> [--model kimi-k2.5]
    
示例：
    python ai_analyzer.py "D:/Mylibrary/书籍总结/我的书"
    python ai_analyzer.py "D:/Mylibrary/书籍总结/我的书" --range 1-10
"""
import sys
import re
import json
from pathlib import Path
from typing import Dict, List, Optional
import argparse
from datetime import datetime


# 综合章节分析提示词（精简版，减少 Token 消耗）
ANALYSIS_PROMPT = """请分析以下章节，生成结构化总结：

【章节】第{index}章 {title}

【内容】
{content}

【要求】生成包含以下4部分的Markdown：

## 一、章节概述
- **主旨**：一句话概括（20-50字）
- **核心要点**：3-5条，每条用**加粗**标关键词
- **内容概述**：2-3段描述主要内容
- **章节定位**：在全书中的作用

## 二、知识要素
- **核心概念**：重要概念及定义
- **关键要素**：用表格整理（要素|说明|重要性）
- **重要数据/金句**：引用格式标注
- **相关理论/模型**：如有则列出

## 三、案例分析
- **主要案例**：1-3个，含背景/问题/方案/结果/启示
- **次要案例**：简要列出
- **论据/故事**：支撑论点的事例

## 四、应用拓展
- **实际应用方法**：场景+步骤+效果
- **不同领域应用**：用表格（领域|场景|做法）
- **注意事项**：常见误区及避免方法
- **实践练习**：1-2个练习任务

【规则】
- 基于实际内容，不编造
- 每个部分必须有实质内容
- 使用清晰Markdown层级
"""


def extract_content_from_md(md_content: str) -> tuple:
    """从Markdown内容中提取标题和正文"""
    lines = md_content.split('\n')
    
    # 提取标题
    title = "未命名章节"
    if lines and lines[0].startswith('# '):
        title = lines[0][2:].strip()
    
    # 提取正文
    content_lines = []
    in_content = False
    
    for line in lines:
        if line.startswith('# ') and not in_content:
            continue
        
        if line.strip() == '---' and not in_content:
            in_content = True
            continue
        
        if line.strip() == '---' and in_content:
            in_content = False
            continue
        
        if in_content and (line.startswith('**章节') or line.startswith('**字数') or 
                          line.startswith('**生成时间') or line.startswith('**章节层级')):
            continue
        
        if in_content and not line.strip():
            continue
        
        if in_content and line.strip():
            in_content = "collecting"
        
        if in_content == "collecting":
            content_lines.append(line)
    
    content = '\n'.join(content_lines).strip()
    
    if '*由 FastSecond Read 自动生成*' in content:
        content = content.split('*由 FastSecond Read 自动生成*')[0].strip()
    
    return title, content


def truncate_content(content: str, max_chars: int = 3000) -> str:
    """智能截断内容"""
    if len(content) <= max_chars:
        return content
    
    truncated = content[:max_chars]
    
    # 在句子边界截断
    for sep in ['。', '？', '！', '. ', '? ', '! ']:
        last_sep = truncated.rfind(sep)
        if last_sep > max_chars * 0.7:
            return truncated[:last_sep + 1]
    
    # 在段落边界截断
    last_para = truncated.rfind('\n\n')
    if last_para > max_chars * 0.7:
        return truncated[:last_para]
    
    return truncated


def prepare_analysis_task(chapter_file: Path) -> Optional[Dict]:
    """
    准备分析任务
    
    返回：
        {
            'index': int,
            'title': str,
            'content': str,
            'prompt': str,
            'word_count': int
        }
    """
    md_content = chapter_file.read_text(encoding='utf-8')
    title, content = extract_content_from_md(md_content)
    
    match = re.match(r'(\d+)_.*\.md', chapter_file.name)
    index = int(match.group(1)) if match else 0
    
    if not content.strip():
        return None
    
    # 截断内容
    content_truncated = truncate_content(content, 3000)
    
    # 生成提示词
    prompt = ANALYSIS_PROMPT.format(
        title=title,
        index=index,
        content=content_truncated
    )
    
    return {
        'index': index,
        'title': title,
        'content': content,
        'prompt': prompt,
        'word_count': len(content)
    }


def save_analysis_result(task: Dict, analysis_result: str, output_dir: Path):
    """保存分析结果"""
    safe_title = re.sub(r'[<>:"/\\|?*]', '_', task['title']).strip('. ')[:80] or 'untitled'
    chapter_dir = output_dir / f"第{task['index']:02d}章_{safe_title}"
    chapter_dir.mkdir(parents=True, exist_ok=True)
    
    # 构建完整的分析文档
    analysis_doc = f"""# 第{task['index']}章 {task['title']} - 章节分析

---

**章节序号**：第{task['index']}章  
**原始字数**：{task['word_count']} 字  
**分析字数**：{len(task['content'][:3000])} 字  
**生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M')}  

---

{analysis_result}

---

*由 AI 分析生成*
"""
    
    analysis_file = chapter_dir / "章节分析.md"
    with open(analysis_file, 'w', encoding='utf-8') as f:
        f.write(analysis_doc)
    
    return str(analysis_file)


def create_analysis_plan(input_dir: Path, output_dir: Path, range_str: Optional[str] = None) -> List[Dict]:
    """
    创建分析计划
    
    返回任务列表，每个任务包含分析所需的所有信息
    """
    md_files = sorted(input_dir.glob('*.md'))
    
    if not md_files:
        return []
    
    # 解析范围
    if range_str:
        indices = set()
        for part in range_str.split(','):
            part = part.strip()
            if '-' in part:
                start, end = part.split('-')
                indices.update(range(int(start), int(end) + 1))
            else:
                indices.add(int(part))
        md_files = [f for f in md_files if int(re.match(r'(\d+)_.*', f.name).group(1)) in indices]
    
    # 准备任务
    tasks = []
    for chapter_file in md_files:
        task = prepare_analysis_task(chapter_file)
        if task:
            tasks.append(task)
    
    return tasks


def save_plan_json(tasks: List[Dict], output_dir: Path):
    """保存分析计划为JSON"""
    plan = {
        'created_at': datetime.now().isoformat(),
        'total_chapters': len(tasks),
        'tasks': [
            {
                'index': t['index'],
                'title': t['title'],
                'word_count': t['word_count'],
                'prompt_length': len(t['prompt'])
            }
            for t in tasks
        ]
    }
    
    plan_file = output_dir / '.analysis_plan.json'
    with open(plan_file, 'w', encoding='utf-8') as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    
    return str(plan_file)


def main():
    parser = argparse.ArgumentParser(description='AI 章节分析器')
    parser.add_argument('input_dir', help='分章MD文件所在目录')
    parser.add_argument('--output-dir', '-o', help='输出目录')
    parser.add_argument('--range', '-r', help='章节范围，如 "1-10" 或 "1,3,5"')
    parser.add_argument('--plan-only', '-p', action='store_true', help='只生成分析计划')
    
    args = parser.parse_args()
    
    input_dir = Path(args.input_dir)
    
    if not input_dir.exists():
        print(f"[ERROR] 目录不存在: {input_dir}")
        sys.exit(1)
    
    # 确定输出目录
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        output_dir = Path(f"{input_dir}_全书分析_{timestamp}")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 70)
    print("AI 章节分析器")
    print("=" * 70)
    print()
    
    # 创建分析计划
    print("[INFO] 创建分析计划...")
    tasks = create_analysis_plan(input_dir, output_dir, args.range)
    
    if not tasks:
        print("[ERROR] 未找到有效的章节文件")
        print("[INFO] 请先使用 book_processor.py 处理书籍文件")
        sys.exit(1)
    
    print(f"[INFO] 找到 {len(tasks)} 个章节待分析")
    print(f"[INFO] 输出目录: {output_dir}")
    
    # 保存计划
    plan_file = save_plan_json(tasks, output_dir)
    print(f"[INFO] 分析计划已保存: {plan_file}")
    
    if args.plan_only:
        print()
        print("[INFO] 计划模式，不执行实际分析")
        print("[INFO] 每个章节的分析任务已准备就绪")
        print()
        print("执行方式：")
        print("  1. 读取 .analysis_plan.json 获取任务列表")
        print("  2. 对每个任务，使用 'prompt' 字段调用 AI 模型")
        print("  3. 将 AI 返回的内容保存到对应章节的 章节分析.md 文件")
        return
    
    print()
    print("=" * 70)
    print("开始分析")
    print("=" * 70)
    print()
    print("[提示] 当前脚本只准备分析任务，需要 AI 模型执行实际分析")
    print("[提示] 每个章节已生成对应的提示词，可以批量发送给 AI 模型")
    print()
    
    # 显示任务摘要
    total_words = sum(t['word_count'] for t in tasks)
    print(f"任务摘要:")
    print(f"  章节数: {len(tasks)}")
    print(f"  总字数: {total_words:,}")
    print(f"  平均每章: {total_words // len(tasks):,} 字")
    print()
    
    # 生成提示词文件（供批量使用）
    prompts_file = output_dir / '.all_prompts.txt'
    with open(prompts_file, 'w', encoding='utf-8') as f:
        for task in tasks:
            f.write(f"\n{'='*70}\n")
            f.write(f"第{task['index']}章: {task['title']}\n")
            f.write(f"{'='*70}\n\n")
            f.write(task['prompt'])
            f.write("\n\n")
    
    print(f"[INFO] 所有提示词已保存: {prompts_file}")
    print()
    print("=" * 70)
    print("使用建议")
    print("=" * 70)
    print()
    print("方式1 - AI 自动处理（推荐）:")
    print("  让 AI 读取 .analysis_plan.json，然后批量处理每个任务")
    print()
    print("方式2 - 手动分批处理:")
    print("  打开 .all_prompts.txt，分批复制提示词给 AI 分析")
    print()
    print("方式3 - 单章处理:")
    print("  进入每个章节目录，手动调用 AI 分析")
    print()


if __name__ == '__main__':
    main()
