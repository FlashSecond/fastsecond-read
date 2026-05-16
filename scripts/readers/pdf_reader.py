# -*- coding: utf-8 -*-
"""
PDF文件读取器 - 基于字号统计的智能分章

核心规则：
1. 获取行宽度（页面内容区域）
2. 统计频率最高的字号作为正文基准字号
3. 提取文本块：内容、坐标(x0,y0,x1,y1)、字体名、字体大小

标题层级判定（自适应两轮检测算法）：

第一轮：固定比率粗筛
- 一级候选：字号 >= 基准 × 1.4
- 二级候选：字号 > 基准 × 1.0 且 < 基准 × 1.4
- 三级候选：字号 > 基准 × 1.0 且 < 基准 × 1.4
- 收集所有候选字号，去重

第二轮：自适应阈值计算
- 对去重后的候选字号排序，取前两位最大字号
- 计算自适应比率 = (第一大字号 + 第二大字号) / 2 / 基准字号

第三轮：标题分类（使用自适应比率）
- 一级标题：字号 >= 基准 × 自适应比率
  + 垂直留白足够 + 无句号 + (居中 或 x0远离正文)
- 二级标题：字号 > 基准 × 1.0 且 < 基准 × 自适应比率
  + 留白足够 + 无句号 + x0远离正文
- 三级标题：字号 > 基准 × 1.0 且 < 基准 × 自适应比率
  + 留白足够 + 短文本(<50字) + 无句号 + x0接近正文

关键区分点：
- 一级：字号 >= 自适应比率（由前两位最大字号平均计算）
- 二级/三级：字号范围相同（>1.0倍且<自适应比率），通过x0位置区分
  - 二级：x0远离正文（>10点）
  - 三级：x0接近正文（≤10点）
- 字数限制：仅对三级标题生效（<50字），一级/二级标题无字数限制

其他规则：
- 留白检测：句前+句后留白 > 行宽一半，且垂直留白足够
- 标签过滤：【章】【节】等标签不独立成章节
- 页眉页脚过滤：短文本(<30字)在页面顶部/底部6%区域内视为非标题
- 合并规则：一级+二级无正文间隔时合并；标签与标题合并

控制参数：
- level2_as_body: 二级标题是否视为正文（默认True）
- level3_as_body: 三级标题是否视为正文（默认True）
"""
import re
import fitz
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from collections import Counter

from .base import FileReader
from core.document import Document, Chapter, ContentBlock, ContentType, TextStyle


@dataclass
class TextBlock:
    """文本块数据类"""
    text: str
    font_size: float
    font_name: str
    bbox: Tuple[float, float, float, float]  # x0, y0, x1, y1
    page_num: int
    page_width: float
    page_height: float
    ends_with_period: bool = False
    
    @property
    def line_width(self) -> float:
        return self.bbox[2] - self.bbox[0]


@dataclass
class HeadingInfo:
    """标题信息"""
    block: TextBlock
    level: int  # 1, 2, 3
    is_body: bool = False  # 是否视为正文
    is_independent: bool = False
    merged_title: str = ""


class PDFReader(FileReader):
    """PDF文件读取器"""
    
    # 页眉页脚位置阈值（距离页面顶部/底部的距离比例）
    HEADER_FOOTER_MARGIN_RATIO = 0.06  # 页面高度的6%以内视为页眉页脚区域
    
    def supports(self, file_path: str) -> bool:
        """检查是否支持该文件类型"""
        return file_path.lower().endswith('.pdf')
    
    # 标签模式（如【章】【节】等，这类标签不应该独立成章节）
    LABEL_PATTERNS = [
        r'^【[章节篇卷部]】$',
        r'^\[[章节篇卷部]\]$',
        r'^[（(][章节篇卷部][)）]$',
    ]
    

    
    def _is_label(self, text: str) -> bool:
        """检查文本是否为标签（如【章】【节】等）"""
        text = text.strip()
        for pattern in self.LABEL_PATTERNS:
            if re.match(pattern, text):
                return True
        return False
    
    # 注释章节标题模式
    NOTE_PATTERNS = [
        r'^注释\s*[-—–]',
        r'^注释\s*[:：]',
        r'^Notes?$',
        r'^注释$',
        r'^注\s*\d+',
        r'^\d+\s*注释',
    ]
    
    def _is_note_heading(self, text: str) -> bool:
        """检查文本是否为注释章节标题"""
        text = text.strip()
        for pattern in self.NOTE_PATTERNS:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        return False
    
    def _is_in_header_footer_area(self, block: TextBlock) -> bool:
        """检查文本块是否在页眉或页脚区域
        
        根据文本块的垂直位置判断是否在页眉（页面顶部）或页脚（页面底部）区域
        """
        page_height = block.page_height
        y0 = block.bbox[1]  # 上边界
        y1 = block.bbox[3]  # 下边界
        
        # 计算文本块中心位置
        center_y = (y0 + y1) / 2
        
        # 页眉区域：页面顶部6%以内
        header_threshold = page_height * self.HEADER_FOOTER_MARGIN_RATIO
        # 页脚区域：页面底部6%以内
        footer_threshold = page_height * (1 - self.HEADER_FOOTER_MARGIN_RATIO)
        
        return center_y < header_threshold or center_y > footer_threshold
    
    def _is_header_footer_content(self, text: str) -> bool:
        """检测文本是否为页眉页脚内容（基于内容特征）
        
        页眉页脚通常包含：
        - 网址 (http://, https://, www.)
        - 版权声明 (版权所有, 仅供学习, 严禁商业)
        - 页码 (纯数字)
        - 书名/章节名重复
        """
        text = text.strip()
        if not text:
            return False
        
        # 检测网址
        if 'http://' in text or 'https://' in text or 'www.' in text:
            return True
        
        # 检测版权相关关键词
        copyright_keywords = ['版权所有', '仅供学习', '严禁商业', '不得转载', '翻版必究']
        for keyword in copyright_keywords:
            if keyword in text:
                return True
        
        # 检测纯数字（页码）
        if text.isdigit():
            return True
        
        # 检测页码格式（如 "- 1 -" 或 "1 / 255"）
        import re
        if re.match(r'^[-\s]*\d+[-\s/]*$', text):
            return True
        
        return False
    
    def _collect_heading_candidates(self, blocks: List[TextBlock], base_size: float) -> List[Tuple[TextBlock, float]]:
        """收集所有可能的标题候选（第一轮：固定比率粗筛）
        
        规则：
        - 一级候选：字号 >= 基准 × 1.4
        - 二级候选：字号 > 基准 × 1.0 且 < 基准 × 1.4
        - 三级候选：字号 > 基准 × 1.0 且 < 基准 × 1.4
        
        注意：字数限制只在最终分类阶段对三级标题生效
        
        返回: [(block, font_ratio), ...]
        """
        candidates = []
        
        for i, block in enumerate(blocks):
            prev_block = blocks[i-1] if i > 0 else None
            next_block = blocks[i+1] if i < len(blocks) - 1 else None
            
            # 基本过滤：长度、位置
            text = block.text.strip()
            if len(text) < 2:  # 至少2个字符
                continue
            
            # 页眉页脚区域过滤
            if len(text) < 30 and self._is_in_header_footer_area(block):
                continue
            
            # 标签过滤
            if self._is_label(text):
                continue
            
            # 句号过滤：标题通常不以句号结尾
            if block.ends_with_period:
                continue
            
            # 计算字号比例
            font_ratio = block.font_size / base_size if base_size > 0 else 1.0
            
            # 第一轮固定比率粗筛：
            # 一级候选：>= 1.4倍（放宽留白检测，使用容差避免浮点精度问题）
            # 二级/三级候选：> 1.0倍 且 < 1.4倍（严格留白检测）
            if font_ratio <= 1.0:  # 必须大于1.0倍
                continue
            
            # 留白检测：根据字号比例使用不同标准
            line_width = block.page_width
            if font_ratio >= 1.39:  # 使用1.39作为阈值，避免浮点精度问题（如20.999998/15.0=1.399999...）
                # 一级候选：只需垂直留白足够
                has_margin = self._has_vertical_margin_only(block, prev_block, next_block)
            else:
                # 二级/三级候选：需要水平和垂直留白都足够
                has_margin = self._has_large_margin(block, prev_block, next_block, line_width)
            
            if not has_margin:
                continue
            
            candidates.append((block, font_ratio))
        
        return candidates
    
    def _calculate_heading_thresholds(self, candidates: List[Tuple[TextBlock, float]], base_size: float) -> Tuple[float, float]:
        """计算自适应字号阈值（第二轮：自适应阈值计算）
        
        规则：
        1. 统计候选标题字号的频率（不去重，每个候选都计数）
        2. 去掉频率最高的字号（通常是正文基准字号）
        3. 计算剩余字号的期望值作为自适应比率
        4. 一级阈值 = 期望值
        5. 二级阈值 = 期望值 × 0.8（如果没有则使用基准×1.1）
        
        返回: (level1_threshold, level2_threshold)
        """
        if not candidates:
            # 默认值：一级1.4倍，二级1.1倍
            return base_size * 1.4, base_size * 1.1
        
        # 统计字号频率（不去重，每个候选都计数）
        from collections import Counter
        size_counter = Counter()
        for block, ratio in candidates:
            # 使用原始字号，不四舍五入，保持精度
            size_counter[block.font_size] += 1
        
        if len(size_counter) == 0:
            return base_size * 1.4, base_size * 1.1
        
        # 找出频率最高的字号（通常是正文基准字号）
        max_freq_size = max(size_counter.keys(), key=lambda s: size_counter[s])
        max_freq = size_counter[max_freq_size]
        
        # 去掉频率最高的字号，计算剩余字号的期望值（加权平均）
        remaining_sizes = []
        total_weight = 0
        weighted_sum = 0.0
        
        for size, freq in size_counter.items():
            if size != max_freq_size:  # 去掉频率最高的字号
                remaining_sizes.append(size)
                weighted_sum += size * freq
                total_weight += freq
        
        # 如果没有剩余字号，使用默认阈值
        if total_weight == 0:
            return base_size * 1.4, base_size * 1.1
        
        # 计算期望值（加权平均）
        expected_size = weighted_sum / total_weight
        
        # 一级阈值 = 期望值
        level1_threshold = expected_size
        # 二级阈值 = 期望值的80%（或基准×1.1，取较大者）
        level2_threshold = max(expected_size * 0.8, base_size * 1.1)
        
        return level1_threshold, level2_threshold
    
    def _identify_headings_with_thresholds(self, blocks: List[TextBlock], base_size: float,
                                           level1_threshold: float, level2_threshold: float,
                                           level2_as_body: bool = True, level3_as_body: bool = True) -> List[HeadingInfo]:
        """使用确定的阈值识别标题
        
        Args:
            level1_threshold: 一级标题字号阈值
            level2_threshold: 二级标题字号阈值
            level2_as_body: 是否将二级标题视为正文
            level3_as_body: 是否将三级标题视为正文
        """
        headings = []
        
        for i, block in enumerate(blocks):
            prev_block = blocks[i-1] if i > 0 else None
            next_block = blocks[i+1] if i < len(blocks) - 1 else None
            
            # 获取该文本块后面紧跟的正文x0
            body_x0 = self._get_body_x0_after(blocks, i, base_size)
            
            level = self._classify_block_with_thresholds(
                block, base_size, body_x0, 
                level1_threshold, level2_threshold,
                prev_block, next_block
            )
            
            if level > 0:
                # 根据控制参数决定是否视为正文
                is_body = False
                if level == 2 and level2_as_body:
                    is_body = True
                elif level == 3 and level3_as_body:
                    is_body = True
                
                headings.append(HeadingInfo(block=block, level=level, is_body=is_body))
        
        return headings
    
    def _classify_block_with_thresholds(self, block: TextBlock, base_size: float,
                                        body_x0: Optional[float],
                                        level1_threshold: float, level2_threshold: float,
                                        prev_block: Optional[TextBlock] = None,
                                        next_block: Optional[TextBlock] = None) -> int:
        """使用阈值分类文本块
        
        返回标题层级（0=正文，1=一级，2=二级，3=三级）
        """
        text = block.text.strip()
        if len(text) < 2:
            return 0
        
        # 页眉页脚区域过滤
        if len(text) < 30 and self._is_in_header_footer_area(block):
            return 0
        
        # 标签过滤
        if self._is_label(text):
            return 0
        
        # 注释章节过滤
        if self._is_note_heading(text):
            return 0
        
        font_size = block.font_size
        no_period = not block.ends_with_period
        
        # 获取行宽
        line_width = block.page_width
        
        # 检测留白
        has_large_margin = self._has_large_margin(block, prev_block, next_block, line_width)
        
        # 检测是否居中
        is_centered = self._is_centered(block, block.page_width)
        
        # 第三轮：标题分类（使用自适应比率）
        # 使用更小的容差（1%或0.2），避免阈值接近时重叠
        tolerance = min(0.2, level1_threshold * 0.01)
        
        # 判断一级标题：字号 >= level1_threshold + 垂直留白足够 + 无句号
        # 一级标题无字数限制
        has_vertical_margin_only = self._has_vertical_margin_only(block, prev_block, next_block)
        if font_size >= level1_threshold - tolerance and has_vertical_margin_only and no_period:
            return 1
        
        # 判断二级/三级标题：字号 > base_size 且 < level1_threshold
        # 二级和三级字号范围相同，通过x0位置区分
        if base_size < font_size < level1_threshold - tolerance and has_large_margin and no_period:
            # x0远离正文 (>10点) = 二级
            # 二级标题无字数限制
            if not (body_x0 and abs(block.bbox[0] - body_x0) <= 10):
                return 2
            # x0接近正文 (<=10点) = 三级
            else:
                # 三级标题字数限制：<50字（仅对三级标题生效）
                if len(text) < 50:
                    return 3
        
        return 0
    
    def _estimate_heading_level(self, font_ratio: float, text: str = "") -> int:
        """根据字号比例和文本内容估算标题层级
        
        注意：此函数仅用于在_build_chapters中对未识别的标题进行估算。
        由于此时正文已经被过滤掉，这里的"标题"实际上是相对正文较大的文本。
        
        Args:
            font_ratio: 字号与基准字号的比例
            text: 文本内容（用于检测三级标题模式）
            
        Returns:
            估算的标题层级 (1-3)
        """
        # 提高阈值，避免小节标题被误判为章节标题
        # 基准字号14.8，倍率1.4=20.7，1.25=18.5，1.15=17.0
        if font_ratio >= 1.4:
            return 1  # 一级标题（字号显著大于正文）
        elif font_ratio >= 1.25:
            return 2  # 二级标题（字号明显大于正文）
        elif font_ratio >= 1.15:
            return 3  # 三级标题（字号略大于正文）
        else:
            return 0  # 视为正文（字号接近基准）
    
    def _extract_toc_structure(self, blocks: List[TextBlock]) -> List[Dict]:
        """从PDF目录页提取章节结构
        
        检测目录页（通常包含"目录"标题和章节列表），提取章节标题和层级关系。
        
        Returns:
            章节结构列表，每项包含：
            - title: 章节标题
            - level: 层级（1=章，2=节）
            - type: 类型（'part'=篇，'chapter'=章，'section'=节）
            - parent: 父章节标题（如果有）
        """
        toc_items = []
        current_part = None
        toc_start_page = None
        pages_processed = set()  # 已处理的页码
        
        for b in blocks:
            text = b.text.strip()
            
            # 检测目录开始（"目录"标题，大字号）
            if toc_start_page is None and text == "目录" and b.font_size >= 20:
                toc_start_page = b.page_num
                pages_processed.add(b.page_num)
                continue
            
            # 如果还没找到目录开始，跳过
            if toc_start_page is None:
                continue
            
            # 严格限制：目录最多2页（目录标题页 + 1页内容）
            if len(pages_processed) >= 2 and b.page_num not in pages_processed:
                break
            
            # 记录当前页
            pages_processed.add(b.page_num)
            
            # 如果页码跳跃超过1页，说明目录结束
            if b.page_num > toc_start_page + 1:
                break
            
            # 跳过空文本和"目录"本身
            if not text or text == "目录":
                continue
            
            # 过滤过长的文本（不是标题）- 目录中的标题通常较短
            if len(text) >= 50:
                continue
            
            # 根据字号判断层级（目录中的标题通常字号较大且一致）
            if b.font_size >= 19.0:  # 一级标题（章/篇）
                if "第" in text and "篇" in text:
                    current_part = text
                    toc_items.append({
                        'title': text,
                        'level': 1,
                        'type': 'part',
                        'parent': None
                    })
                else:
                    toc_items.append({
                        'title': text,
                        'level': 1,
                        'type': 'chapter',
                        'parent': current_part
                    })
            elif b.font_size >= 14.0:  # 二级标题（节）
                toc_items.append({
                    'title': text,
                    'level': 2,
                    'type': 'section',
                    'parent': current_part
                })
        
        return toc_items
    
    def _find_toc_in_content(self, toc_items: List[Dict], blocks: List[TextBlock]) -> List[Dict]:
        """在正文中查找目录标题的位置
        
        对于每个目录中的标题，在正文中查找其首次出现的位置。
        支持标题被分成多个文本块的情况（如"三大宗："和"酒精、烟草、咖啡因"）。
        过滤掉位置不合理的匹配（如出现在文档末尾的可能是注释）。
        
        Returns:
            添加了'found', 'index', 'page'字段的toc_items
        """
        # 找到正文开始的位置
        content_start_page = 1
        toc_start_page = None
        for b in blocks:
            if b.text.strip() == "目录" and b.font_size >= 20:
                toc_start_page = b.page_num
                break
        
        if toc_start_page:
            # 正文从目录开始页 + 2 开始（跳过目录标题页和目录内容页）
            content_start_page = toc_start_page + 2
        
        for idx, item in enumerate(toc_items):
            title = item['title']
            found = False
            
            for i, b in enumerate(blocks):
                # 跳过目录页（严格限制）
                if b.page_num < content_start_page:
                    continue
                
                # 尝试完全匹配
                if b.text.strip() == title:
                    doc_progress = i / len(blocks)
                    
                    if item['type'] == 'part':
                        break
                    elif item['type'] == 'chapter':
                        item['found'] = True
                        item['index'] = i
                        item['page'] = b.page_num
                        found = True
                        break
                    else:  # section
                        if doc_progress < 0.95:
                            item['found'] = True
                            item['index'] = i
                            item['page'] = b.page_num
                            found = True
                            break
                
                # 尝试部分匹配（标题可能被分成多个块）
                # 检查当前块是否包含标题的开头部分
                elif title.startswith(b.text.strip()) and len(b.text.strip()) >= 3:
                    # 可能是标题的第一部分，检查接下来的几个块
                    combined_text = b.text.strip()
                    combined_idx = i
                    for j in range(i + 1, min(i + 5, len(blocks))):
                        if blocks[j].page_num != b.page_num:
                            break  # 跨页了，停止组合
                        combined_text += blocks[j].text.strip()
                        # 使用归一化比较（忽略空格差异）
                        normalized_combined = combined_text.replace(" ", "").replace("\u3000", "")
                        normalized_title = title.replace(" ", "").replace("\u3000", "")
                        if normalized_combined == normalized_title or normalized_title in normalized_combined:
                            doc_progress = i / len(blocks)
                            
                            if item['type'] == 'part':
                                break
                            elif item['type'] == 'chapter':
                                item['found'] = True
                                item['index'] = combined_idx
                                item['page'] = b.page_num
                                found = True
                                break
                            else:  # section
                                if doc_progress < 0.95:
                                    item['found'] = True
                                    item['index'] = combined_idx
                                    item['page'] = b.page_num
                                    found = True
                                    break
                    
                    if found:
                        break
            
            if not found:
                item['found'] = False
        
        return toc_items
    
    def _build_chapters_from_toc(self, toc_items: List[Dict], blocks: List[TextBlock], 
                                  base_size: float) -> List[Chapter]:
        """基于目录结构构建章节
        
        只使用在正文中找到的目录标题作为分章依据。
        """
        chapters = []
        found_items = [item for item in toc_items if item.get('found') and item['type'] != 'part']
        
        for i, item in enumerate(found_items):
            title = item['title']
            start_idx = item['index']
            level = item['level']
            
            # 计算章节结束位置
            if i + 1 < len(found_items):
                end_idx = found_items[i + 1]['index']
            else:
                end_idx = len(blocks)
            
            # 提取内容块
            content_blocks = []
            chapter_text = ""
            
            for j in range(start_idx, min(end_idx, len(blocks))):
                block = blocks[j]
                
                # 跳过标题本身（只保留文本）
                if j == start_idx:
                    chapter_text += block.text + "\n\n"
                    continue
                
                # 判断内容类型
                font_ratio = block.font_size / base_size if base_size > 0 else 1.0
                is_body_text = (0.9 <= font_ratio <= 1.1) or block.ends_with_period
                
                if is_body_text:
                    content_type = ContentType.PARAGRAPH
                    content_level = 0
                else:
                    # 可能是子标题，估算层级
                    if font_ratio >= 1.4:
                        content_type = ContentType.HEADING
                        content_level = 1
                    elif font_ratio >= 1.25:
                        content_type = ContentType.HEADING
                        content_level = 2
                    elif font_ratio >= 1.15:
                        content_type = ContentType.HEADING
                        content_level = 3
                    else:
                        content_type = ContentType.PARAGRAPH
                        content_level = 0
                
                content_blocks.append(ContentBlock(
                    type=content_type,
                    text=block.text,
                    level=content_level,
                    style=TextStyle(
                        font_size=block.font_size,
                        bold=False
                    )
                ))
                
                chapter_text += block.text + "\n\n"
            
            chapters.append(Chapter(
                index=len(chapters) + 1,
                title=title,
                level=level,
                content_blocks=content_blocks,
                word_count=len(chapter_text.replace(" ", "").replace("\n", "")),
                paragraph_count=len([b for b in content_blocks if b.type == ContentType.PARAGRAPH])
            ))
        
        return chapters
    
    def read(self, file_path: str, level2_as_body: bool = True, level3_as_body: bool = True,
             use_toc: bool = True) -> Document:
        """读取PDF文件
        
        Args:
            file_path: PDF文件路径
            level2_as_body: 是否将二级标题视为正文（默认True，仅当use_toc=False时生效）
            level3_as_body: 是否将三级标题视为正文（默认True，仅当use_toc=False时生效）
            use_toc: 是否优先使用目录结构分章（默认True）
        """
        path = Path(file_path)
        doc = fitz.open(file_path)
        
        # 提取所有文本块
        blocks = self._extract_blocks(doc)
        
        # 计算基准字号
        base_size = self._calculate_base_font_size(blocks)
        
        chapters = []
        used_toc = False
        
        # 尝试使用目录结构分章
        if use_toc:
            try:
                # 提取目录结构
                toc_items = self._extract_toc_structure(blocks)
                
                if toc_items:
                    # 在正文中查找目录标题
                    toc_items = self._find_toc_in_content(toc_items, blocks)
                    found_count = sum(1 for item in toc_items if item.get('found'))
                    
                    # 如果找到足够多的章节（至少3个），使用目录分章
                    if found_count >= 3:
                        chapters = self._build_chapters_from_toc(toc_items, blocks, base_size)
                        used_toc = True
            except Exception:
                # 目录分章失败，回退到字号阈值方法
                pass
        
        # 如果目录分章未使用或失败，使用传统的字号阈值方法
        if not chapters:
            # 第一步：收集所有标题候选并统计字号
            heading_candidates = self._collect_heading_candidates(blocks, base_size)
            
            # 第二步：根据字号分布确定一级和二级标题阈值
            level1_threshold, level2_threshold = self._calculate_heading_thresholds(heading_candidates, base_size)
            
            # 第三步：使用阈值重新识别标题
            headings = self._identify_headings_with_thresholds(blocks, base_size, level1_threshold, level2_threshold, level2_as_body=level2_as_body, level3_as_body=level3_as_body)
            
            # 判断独立性
            headings = self._check_independence(headings, blocks, base_size)
            
            # 合并非独立标题
            headings = self._merge_headings(headings)
            
            # 构建章节
            chapters = self._build_chapters(headings, blocks, base_size)
        
        # 计算总字数
        total_words = sum(ch.word_count for ch in chapters)
        
        return Document(
            file_path=file_path,
            file_name=path.name,
            file_format="pdf",
            title=path.stem,
            chapters=chapters,
            total_pages=len(doc),
            total_words=total_words,
            metadata={
                "base_font_size": base_size,
                "level2_as_body": level2_as_body,
                "level3_as_body": level3_as_body,
                "used_toc": used_toc
            }
        )
    
    def _extract_blocks(self, doc: fitz.Document) -> List[TextBlock]:
        """提取所有文本块"""
        blocks = []
        
        for page_num, page in enumerate(doc, 1):
            text_dict = page.get_text("dict")
            
            for block in text_dict.get("blocks", []):
                if "lines" not in block:
                    continue
                
                for line in block["lines"]:
                    spans = line.get("spans", [])
                    if not spans:
                        continue
                    
                    # 合并同一行的所有span
                    texts = []
                    font_sizes = []
                    bboxes = []
                    
                    for span in spans:
                        text = span.get("text", "").strip()
                        if text:
                            texts.append(text)
                            font_sizes.append(span.get("size", 12))
                            bboxes.append(span["bbox"])
                    
                    if not texts:
                        continue
                    
                    full_text = "".join(texts)
                    if len(full_text) < 1:
                        continue
                    
                    avg_font_size = sum(font_sizes) / len(font_sizes)
                    x0 = min(b[0] for b in bboxes)
                    y0 = min(b[1] for b in bboxes)
                    x1 = max(b[2] for b in bboxes)
                    y1 = max(b[3] for b in bboxes)
                    
                    blocks.append(TextBlock(
                        text=full_text,
                        font_size=avg_font_size,
                        font_name=spans[0].get("font", ""),
                        bbox=(x0, y0, x1, y1),
                        page_num=page_num,
                        page_width=page.rect.width,
                        page_height=page.rect.height,
                        ends_with_period=full_text.endswith('。')
                    ))
        
        return blocks
    
    def _calculate_base_font_size(self, blocks: List[TextBlock]) -> float:
        """计算正文基准字号（频率最高）"""
        if not blocks:
            return 12.0
        
        font_sizes = [round(b.font_size) for b in blocks]
        size_counter = Counter(font_sizes)
        most_common = size_counter.most_common(1)
        return float(most_common[0][0]) if most_common else 12.0
    
    def _get_body_x0_after(self, blocks: List[TextBlock], start_idx: int, base_size: float) -> Optional[float]:
        """获取指定位置之后紧跟的正文第一行的左边界x0"""
        if not blocks or start_idx < 0 or start_idx >= len(blocks) or base_size <= 0:
            return None
        
        # 从start_idx之后开始查找正文
        for i in range(start_idx + 1, min(start_idx + 20, len(blocks))):
            block = blocks[i]
            font_ratio = block.font_size / base_size
            # 字号接近基准（0.9-1.1倍）且长度足够视为正文
            if 0.9 <= font_ratio <= 1.1 and len(block.text) > 10:
                return block.bbox[0]
        
        return None
    
    def _is_centered(self, block: TextBlock, page_width: float) -> bool:
        """检查文本块是否居中"""
        block_width = block.bbox[2] - block.bbox[0]
        x0 = block.bbox[0]
        x1 = block.bbox[2]
        
        # 计算左右边距
        left_margin = x0
        right_margin = page_width - x1
        
        # 如果左右边距相差不超过20%，视为居中
        if left_margin + right_margin > 0:
            margin_diff_ratio = abs(left_margin - right_margin) / (left_margin + right_margin)
            return margin_diff_ratio < 0.2
        return False
    
    def _has_large_margin(self, block: TextBlock, prev_block: Optional[TextBlock], 
                          next_block: Optional[TextBlock], line_width: float) -> bool:
        """检测留白是否超过行宽的一半"""
        block_width = block.bbox[2] - block.bbox[0]
        total_margin = line_width - block_width
        half_line_width = line_width * 0.5
        
        # 检查句前+句末留白是否超过行宽的一半
        has_horizontal_margin = total_margin > half_line_width
        
        # 检查句上句下留白
        line_height = block.bbox[3] - block.bbox[1]
        
        margin_top = 0.0
        margin_bottom = 0.0
        
        if prev_block and prev_block.page_num == block.page_num:
            margin_top = block.bbox[1] - prev_block.bbox[3]
        
        if next_block and next_block.page_num == block.page_num:
            margin_bottom = next_block.bbox[1] - block.bbox[3]
        
        has_vertical_margin = (margin_top > line_height) or (margin_bottom > line_height)
        
        return has_horizontal_margin and has_vertical_margin
    
    def _has_vertical_margin_only(self, block: TextBlock, prev_block: Optional[TextBlock], 
                                   next_block: Optional[TextBlock]) -> bool:
        """只检测垂直留白（用于一级标题）"""
        line_height = block.bbox[3] - block.bbox[1]
        
        margin_top = 0.0
        margin_bottom = 0.0
        
        if prev_block and prev_block.page_num == block.page_num:
            margin_top = block.bbox[1] - prev_block.bbox[3]
        
        if next_block and next_block.page_num == block.page_num:
            margin_bottom = next_block.bbox[1] - block.bbox[3]
        
        # 上方或下方留白超过行高的0.5倍（放宽条件，适应章标题紧凑排版）
        return (margin_top > line_height * 0.5) or (margin_bottom > line_height * 0.5)
    
    def _check_independence(self, headings: List[HeadingInfo], 
                           blocks: List[TextBlock], base_size: float) -> List[HeadingInfo]:
        """判断每个标题是否独立（后面是否有正文）"""
        block_indices = {id(b): i for i, b in enumerate(blocks)}
        
        for i, heading in enumerate(headings):
            block_idx = block_indices.get(id(heading.block), -1)
            if block_idx < 0:
                continue
            
            # 标签（如【章】【节】）不应该独立成章节
            if self._is_label(heading.block.text):
                heading.is_independent = False
                continue
            
            heading.is_independent = self._has_body_after(
                blocks, block_idx, headings, i, base_size
            )
        
        return headings
    
    def _has_body_after(self, blocks: List[TextBlock], current_idx: int,
                       headings: List[HeadingInfo], heading_idx: int, base_size: float) -> bool:
        """检查当前位置之后是否有正文内容"""
        current_heading = headings[heading_idx]
        
        for i in range(current_idx + 1, min(current_idx + 30, len(blocks))):
            block = blocks[i]
            
            # 检查是否是另一个标题
            is_other_heading = False
            for h in headings:
                if id(h.block) == id(block):
                    is_other_heading = True
                    
                    # 规则15: 一级/二级 + 三级 + 正文 → 三级视为正文
                    if h.level == 3 and current_heading.level in [1, 2]:
                        # 检查三级标题后面是否有正文
                        for j in range(i + 1, min(i + 10, len(blocks))):
                            next_block = blocks[j]
                            font_ratio = next_block.font_size / base_size if base_size > 0 else 1.0
                            if 0.9 <= font_ratio <= 1.1 and len(next_block.text) > 10:
                                return True
                            # 检查是否遇到其他标题
                            is_heading = False
                            for hh in headings:
                                if id(hh.block) == id(next_block):
                                    is_heading = True
                                    break
                            if is_heading:
                                break
                        break
                    
                    # 如果是更低层级的标题，不算作正文
                    if h.level > current_heading.level:
                        return False
                    break
            
            if is_other_heading:
                continue
            
            # 检查是否为正文
            font_ratio = block.font_size / base_size if base_size > 0 else 1.0
            if 0.9 <= font_ratio <= 1.1 and len(block.text) > 10:
                return True
            if block.ends_with_period and len(block.text) > 5:
                return True
        
        return False
    
    def _merge_headings(self, headings: List[HeadingInfo]) -> List[HeadingInfo]:
        """合并非独立标题"""
        if not headings:
            return []
        
        merged = []
        i = 0
        
        while i < len(headings):
            current = headings[i]
            
            # 规则12: 一级 + 任意下级标题（一级不独立）→ 合并
            # 修改：支持一级与二级、三级等任意下级标题合并
            if (current.level == 1 and 
                not current.is_independent and 
                i + 1 < len(headings)):
                
                next_heading = headings[i + 1]
                # 只要下一个标题层级更高（数字更大），就合并
                if next_heading.level > current.level:
                    merged_title = f"{current.block.text} - {next_heading.block.text}"
                    merged.append(HeadingInfo(
                        block=current.block,
                        level=1,
                        is_independent=True,
                        merged_title=merged_title
                    ))
                    i += 2
                    continue
            
            # 规则14: 一级 + 一级（第一个不独立）→ 合并
            if (current.level == 1 and 
                not current.is_independent and 
                i + 1 < len(headings)):
                
                next_heading = headings[i + 1]
                if next_heading.level == 1:
                    merged_title = f"{current.block.text} - {next_heading.block.text}"
                    merged.append(HeadingInfo(
                        block=current.block,
                        level=1,
                        is_independent=True,
                        merged_title=merged_title
                    ))
                    i += 2
                    continue
            
            merged.append(current)
            i += 1
        
        return merged
    
    def _build_chapters(self, headings: List[HeadingInfo], 
                       blocks: List[TextBlock], base_size: float) -> List[Chapter]:
        """构建章节列表"""
        if not headings:
            return []
        
        chapters = []
        block_indices = {id(b): i for i, b in enumerate(blocks)}
        
        # 首先，直接在blocks列表中找出所有注释标题及其内容范围
        # 注释标题包括："注释"、"注释 - 绪论"等
        # 注意：注释标题可能被标记为is_body=True，所以需要在blocks中直接查找
        note_ranges = []  # [(start_idx, end_idx), ...]
        
        i = 0
        while i < len(blocks):
            block = blocks[i]
            text = block.text.strip()
            
            # 检查是否是注释标题
            if self._is_note_heading(text):
                note_start_idx = i
                # 查找这个注释标题的结束位置
                # 注释内容通常持续到文档结束，或遇到下一个一级/二级标题
                note_end_idx = len(blocks) - 1
                
                for j in range(i + 1, len(blocks)):
                    next_block = blocks[j]
                    next_text = next_block.text.strip()
                    
                    # 如果遇到下一个非注释的一级标题，则注释结束
                    # 一级标题的特征：字号较大、短文本、无句号
                    font_ratio = next_block.font_size / base_size if base_size > 0 else 1.0
                    is_short = len(next_text) < 50 and not next_text.endswith((".", "。", "!", "！", "?", "？"))
                    is_large_font = font_ratio >= 1.4
                    
                    # 如果满足一级标题条件且不是注释标题，则注释结束
                    if is_large_font and is_short and not self._is_note_heading(next_text):
                        note_end_idx = j - 1
                        break
                
                note_ranges.append((note_start_idx, note_end_idx))
                i = note_end_idx + 1  # 跳过已处理的注释范围
            else:
                i += 1
        
        # 创建注释范围的快速查找集合
        note_block_indices = set()
        for start, end in note_ranges:
            for idx in range(start, end + 1):
                note_block_indices.add(idx)
        
        for i, heading in enumerate(headings):
            if not heading.is_independent:
                continue
            
            # 如果该标题视为正文，则不创建独立章节
            if heading.is_body:
                continue
            
            # 检查是否为注释标题，如果是则跳过（不构建章节）
            heading_text = heading.merged_title if heading.merged_title else heading.block.text
            if self._is_note_heading(heading_text):
                continue
            
            start_idx = block_indices.get(id(heading.block), -1)
            if start_idx < 0:
                continue
            
            # 检查当前标题是否在注释范围内（不应该发生，但以防万一）
            if start_idx in note_block_indices:
                continue
            
            # 查找章节结束位置（遇到下一个不视为正文的标题或注释标题）
            end_idx = len(blocks) - 1
            
            # 首先检查从start_idx之后是否有注释标题
            for j in range(start_idx + 1, len(blocks)):
                block = blocks[j]
                text = block.text.strip()
                if self._is_note_heading(text):
                    end_idx = j - 1
                    break
            
            # 然后在headings列表中查找下一个非正文标题
            for j in range(i + 1, len(headings)):
                next_heading = headings[j]
                if not next_heading.is_body:
                    next_idx = block_indices.get(id(next_heading.block), -1)
                    if next_idx > 0 and next_idx - 1 < end_idx:
                        end_idx = next_idx - 1
                    break
            
            # 提取章节内容
            content_blocks = []
            chapter_text = ""
            
            # 构建标题查找映射，用于判断内容块是否为标题及其层级
            heading_block_ids = {id(h.block): h.level for h in headings}
            
            for j in range(start_idx, min(end_idx + 1, len(blocks))):
                block = blocks[j]
                
                # 跳过注释范围内的内容块
                if j in note_block_indices:
                    continue
                
                # 跳过页眉页脚区域的内容
                text = block.text.strip()
                # 条件1：短文本在页眉页脚区域内
                if len(text) < 30 and self._is_in_header_footer_area(block):
                    continue
                # 条件2：包含网址或版权信息的文本（无论长度）
                if self._is_header_footer_content(text):
                    continue
                
                # 跳过标题本身（只保留文本）
                if j == start_idx:
                    chapter_text += block.text + "\n\n"
                    continue
                
                # 判断是否为标题及其层级
                block_id = id(block)
                if block_id in heading_block_ids:
                    # 这是一个标题，使用识别的层级
                    heading_level = heading_block_ids[block_id]
                    content_type = ContentType.HEADING
                    content_level = heading_level
                else:
                    # 判断是否为正文
                    font_ratio = block.font_size / base_size if base_size > 0 else 1.0
                    is_body_text = (0.9 <= font_ratio <= 1.1) or block.ends_with_period
                    
                    if is_body_text:
                        content_type = ContentType.PARAGRAPH
                        content_level = 0
                    else:
                        # 可能是未识别的标题，根据字号和文本内容估算层级
                        estimated_level = self._estimate_heading_level(font_ratio, block.text)
                        if estimated_level == 0:
                            # 字号接近基准，视为正文
                            content_type = ContentType.PARAGRAPH
                            content_level = 0
                        else:
                            content_type = ContentType.HEADING
                            content_level = estimated_level
                
                content_blocks.append(ContentBlock(
                    type=content_type,
                    text=block.text,
                    level=content_level,
                    style=TextStyle(
                        font_size=block.font_size,
                        bold=False
                    )
                ))
                
                chapter_text += block.text + "\n\n"
            
            title = heading.merged_title if heading.merged_title else heading.block.text
            
            chapters.append(Chapter(
                index=len(chapters) + 1,
                title=title,
                level=heading.level,
                content_blocks=content_blocks,
                word_count=len(chapter_text.replace(" ", "").replace("\n", "")),
                paragraph_count=len([b for b in content_blocks if b.type == ContentType.PARAGRAPH])
            ))
        
        return chapters
