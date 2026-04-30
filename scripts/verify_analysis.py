#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析结果验证工具 - 检查章节分析是否完整

使用方式：
    python verify_analysis.py <分析结果目录>
    
示例：
    python verify_analysis.py "D:/Mylibrary/书籍总结/我的书_全书分析_20240430"
"""
import sys
from pathlib import Path
from typing import Dict, List
import argparse


def verify_analysis(analysis_dir: str) -> Dict:
    """
    验证分析结果完整性
    
    Args:
        analysis_dir: 分析结果目录路径
    
    Returns:
        验证结果字典
    """
    analysis_path = Path(analysis_dir)
    
    if not analysis_path.exists():
        return {
            'success': False,
            'error': f'目录不存在: {analysis_dir}'
        }
    
    # 查找所有章节文件夹
    chapter_dirs = [d for d in analysis_path.iterdir() if d.is_dir() and d.name.startswith('第')]
    chapter_dirs.sort()
    
    if not chapter_dirs:
        return {
            'success': False,
            'error': '未找到章节文件夹（格式：第XX章_标题）'
        }
    
    print(f"[INFO] 找到 {len(chapter_dirs)} 个章节文件夹")
    print()
    
    # 检查每个章节
    complete_chapters = []
    incomplete_chapters = []
    empty_files = []
    
    expected_file = '章节分析.md'
    expected_sections = ['一、章节概述', '二、知识要素', '三、案例分析', '四、应用拓展']
    
    for chapter_dir in chapter_dirs:
        analysis_file = chapter_dir / expected_file
        
        # 检查文件是否存在
        if not analysis_file.exists():
            incomplete_chapters.append({
                'name': chapter_dir.name,
                'missing': [expected_file],
                'empty': [],
                'missing_sections': expected_sections
            })
            continue
        
        # 读取文件内容
        content = analysis_file.read_text(encoding='utf-8')
        
        # 检查是否是占位符文件
        is_placeholder = '待AI分析' in content or '提示词已准备就绪' in content or len(content) < 1000
        
        # 检查是否包含所有4个部分
        missing_sections = []
        for section in expected_sections:
            if section not in content:
                missing_sections.append(section)
        
        if is_placeholder or missing_sections:
            incomplete_chapters.append({
                'name': chapter_dir.name,
                'missing': [],
                'empty': [expected_file] if is_placeholder else [],
                'missing_sections': missing_sections
            })
            if is_placeholder:
                empty_files.append(f"{chapter_dir.name}/{expected_file}")
        else:
            complete_chapters.append(chapter_dir.name)
    
    # 打印结果
    print("=" * 60)
    print("验证结果")
    print("=" * 60)
    print()
    print(f"总章节数: {len(chapter_dirs)}")
    print(f"完整完成: {len(complete_chapters)} ({len(complete_chapters)/len(chapter_dirs)*100:.1f}%)")
    print(f"未完成: {len(incomplete_chapters)}")
    print()
    
    if complete_chapters:
        print("✅ 完整完成的章节:")
        for name in complete_chapters[:10]:  # 只显示前10个
            print(f"  ✓ {name}")
        if len(complete_chapters) > 10:
            print(f"  ... 还有 {len(complete_chapters) - 10} 个")
        print()
    
    if incomplete_chapters:
        print("❌ 未完成的章节:")
        for info in incomplete_chapters:
            print(f"  ✗ {info['name']}")
            if info['missing']:
                print(f"    缺少文件: {', '.join(info['missing'])}")
            if info['empty']:
                print(f"    空/模板文件: {', '.join(info['empty'])}")
            if info['missing_sections']:
                print(f"    缺少部分: {', '.join(info['missing_sections'])}")
        print()
    
    if empty_files:
        print("⚠️  需要AI分析的文件:")
        for f in empty_files[:10]:
            print(f"  ! {f}")
        if len(empty_files) > 10:
            print(f"  ... 还有 {len(empty_files) - 10} 个")
        print()
    
    # 返回结果
    return {
        'success': True,
        'total': len(chapter_dirs),
        'complete': len(complete_chapters),
        'incomplete': len(incomplete_chapters),
        'complete_rate': len(complete_chapters) / len(chapter_dirs) * 100 if chapter_dirs else 0,
        'incomplete_details': incomplete_chapters
    }


def main():
    parser = argparse.ArgumentParser(description='验证章节分析结果完整性')
    parser.add_argument('analysis_dir', help='分析结果目录路径')
    parser.add_argument('--fix', action='store_true', help='尝试修复问题（删除空文件）')
    
    args = parser.parse_args()
    
    result = verify_analysis(args.analysis_dir)
    
    if not result['success']:
        print(f"[ERROR] {result['error']}")
        sys.exit(1)
    
    print("=" * 60)
    print("总结")
    print("=" * 60)
    print(f"完成率: {result['complete_rate']:.1f}%")
    
    if result['complete_rate'] == 100:
        print("✅ 所有章节分析已完成！")
    elif result['complete_rate'] >= 80:
        print("⚠️  大部分已完成，还有少量需要处理")
    else:
        print("❌ 大量章节未完成，需要继续分析")
    
    # 修复模式
    if args.fix and result['incomplete_details']:
        print()
        print("[INFO] 修复模式：删除空文件...")
        for info in result['incomplete_details']:
            chapter_dir = Path(args.analysis_dir) / info['name']
            for empty_file in info.get('empty', []):
                filepath = chapter_dir / empty_file
                if filepath.exists():
                    print(f"  删除: {filepath}")
                    filepath.unlink()
        print("[INFO] 修复完成，请重新运行分析")


if __name__ == '__main__':
    main()
