# -*- coding: utf-8 -*-
"""
PDF文件读取器 - 基于文本块属性的智能分章

核心规则：
1. 获取行宽度（页面内容区域）
2. 统计频率最高的字号作为正文基准字号
3. 提取文本块：内容、坐标(x0,y0,x1,y1)、字体名、字体大小

标题层级判定（基于字号比例 + x0位置）：
- 一级标题：字号≥1.4倍基准，x0远离正文(>10点)，垂直留白足够，短文本(<50字)，无句号
- 二级标题：字号1.1-1.4倍，x0远离正文(>10点)，留白足够，短文本(<50字)，无句号
- 三级标题：字号1.0-1.4倍，x0接近正文(≤10点)，留白足够，短文本(<40字)，无句号

关键区分点：
- 一级/二级/三级通过【字号比例】区分层级
- 二级/三级通过【x0与正文位置关系】区分（远离vs接近）

其他规则：
- 留白检测：句前+句后留白 > 行宽一半，且垂直留白足够
- 标签过滤：【章】【节】等标签不独立成章节
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
    
    def _estimate_heading_level(self, font_ratio: float, text: str = "") -> int:
        """根据字号比例和文本内容估算标题层级
        
        Args:
            font_ratio: 字号与基准字号的比例
            text: 文本内容（用于检测三级标题模式）
            
        Returns:
            估算的标题层级 (1-3)
        """
        # 常规判断（不再使用三级标题模式匹配）
        if font_ratio >= 1.4:
            return 1  # 一级标题
        elif font_ratio >= 1.1:
            return 2  # 二级标题
        elif font_ratio >= 1.0:
            return 3  # 三级标题（上限改为1.4，与二级标题上限一致）
        else:
            return 2  # 默认二级
    
    def read(self, file_path: str, level2_as_body: bool = True, level3_as_body: bool = True) -> Document:
        """读取PDF文件
        
        Args:
            file_path: PDF文件路径
            level2_as_body: 是否将二级标题视为正文（默认True）
            level3_as_body: 是否将三级标题视为正文（默认True）
        """
        path = Path(file_path)
        doc = fitz.open(file_path)
        
        # 提取所有文本块
        blocks = self._extract_blocks(doc)
        
        # 计算基准字号
        base_size = self._calculate_base_font_size(blocks)
        
        # 识别标题（每个标题会使用自己后面紧跟的正文x0来判断）
        headings = self._identify_headings(blocks, base_size, level2_as_body=level2_as_body, level3_as_body=level3_as_body)
        
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
                "level3_as_body": level3_as_body
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
    
    def _identify_headings(self, blocks: List[TextBlock], base_size: float,
                          level2_as_body: bool = True, level3_as_body: bool = True) -> List[HeadingInfo]:
        """识别所有标题
        
        Args:
            level2_as_body: 是否将二级标题视为正文（默认True）
            level3_as_body: 是否将三级标题视为正文（默认True）
        """
        headings = []
        
        for i, block in enumerate(blocks):
            prev_block = blocks[i-1] if i > 0 else None
            next_block = blocks[i+1] if i < len(blocks) - 1 else None
            
            # 获取该文本块后面紧跟的正文x0
            body_x0 = self._get_body_x0_after(blocks, i, base_size)
            
            level = self._classify_block(block, base_size, body_x0, prev_block, next_block)
            if level > 0:
                # 根据控制参数决定是否视为正文
                is_body = False
                if level == 2 and level2_as_body:
                    is_body = True
                elif level == 3 and level3_as_body:
                    is_body = True
                
                headings.append(HeadingInfo(block=block, level=level, is_body=is_body))
        
        return headings
    
    def _classify_block(self, block: TextBlock, base_size: float, 
                       body_x0: Optional[float],
                       prev_block: Optional[TextBlock] = None,
                       next_block: Optional[TextBlock] = None) -> int:
        """分类文本块，返回标题层级（0=正文，1=一级，2=二级，3=三级）"""
        text = block.text.strip()
        if len(text) < 2:
            return 0
        
        font_ratio = block.font_size / base_size if base_size > 0 else 1.0
        no_period = not block.ends_with_period
        
        # 获取行宽
        line_width = block.page_width
        
        # 检测留白
        has_large_margin = self._has_large_margin(block, prev_block, next_block, line_width)
        
        # 判断一级标题：字号≥1.4 + 垂直留白足够 + 短文本 + 无句号 + x0远离正文
        has_vertical_margin_only = self._has_vertical_margin_only(block, prev_block, next_block)
        if font_ratio >= 1.4 and has_vertical_margin_only and len(text) < 50 and no_period:
            if not (body_x0 and abs(block.bbox[0] - body_x0) <= 10):
                return 1
        
        # 判断二级标题：字号1.1-1.4 + 留白足够 + 短文本 + 无句号 + x0远离正文
        if 1.1 <= font_ratio < 1.4 and has_large_margin and len(text) < 50 and no_period:
            if not (body_x0 and abs(block.bbox[0] - body_x0) <= 10):
                return 2
        
        # 判断三级标题：字号1.0-1.4 + 留白足够 + 短文本 + 无句号 + x0接近正文
        if 1.0 <= font_ratio < 1.4 and has_large_margin and len(text) < 40 and no_period:
            if body_x0 and abs(block.bbox[0] - body_x0) <= 10:
                return 3
        
        return 0
    
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
        
        # 上方或下方留白超过行高
        return (margin_top > line_height) or (margin_bottom > line_height)
    
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
        
        for i, heading in enumerate(headings):
            if not heading.is_independent:
                continue
            
            # 如果该标题视为正文，则不创建独立章节
            if heading.is_body:
                continue
            
            start_idx = block_indices.get(id(heading.block), -1)
            if start_idx < 0:
                continue
            
            # 查找章节结束位置（遇到下一个不视为正文的标题）
            end_idx = len(blocks) - 1
            for j in range(i + 1, len(headings)):
                if not headings[j].is_body:
                    next_idx = block_indices.get(id(headings[j].block), -1)
                    if next_idx > 0:
                        end_idx = next_idx - 1
                    break
            
            # 提取章节内容
            content_blocks = []
            chapter_text = ""
            
            # 构建标题查找映射，用于判断内容块是否为标题及其层级
            heading_block_ids = {id(h.block): h.level for h in headings}
            
            for j in range(start_idx, min(end_idx + 1, len(blocks))):
                block = blocks[j]
                
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
                    is_body = (0.9 <= font_ratio <= 1.1) or block.ends_with_period
                    
                    if is_body:
                        content_type = ContentType.PARAGRAPH
                        content_level = 0
                    else:
                        # 可能是未识别的标题，根据字号和文本内容估算层级
                        content_type = ContentType.HEADING
                        content_level = self._estimate_heading_level(font_ratio, block.text)
                
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
