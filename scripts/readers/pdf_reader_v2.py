"""
PDF文件读取器 V2 - 基于 PyMuPDF 的智能分章
使用文本位置、字体大小、水平对齐等特征进行章节识别

智能分章规则：
1. 章节标题：水平居中、字体显著大于正文、单独成行
2. 章节内小标题：数字列表格式（如"1. 标题"），字号略大于或等于正文
3. 正文：靠左对齐、字体统一、连续段落
4. 内容归属：章节标题后的所有内容（包括小标题和正文）归属于该章节
"""
import re
import fitz  # PyMuPDF
from .base import FileReader
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from core.document import Document, Chapter, ContentBlock, ContentType, TextStyle


class PDFReaderV2(FileReader):
    """
    PDF文件读取器 V2
    
    基于版面特征的智能分章：
    - 章节标题：水平居中、字体显著大于正文
    - 章节内小标题：数字列表格式，字号略大或等于正文
    - 正文：靠左对齐、字体统一
    """
    
    def supports(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() == '.pdf'
    
    def read(self, file_path: str) -> Document:
        """读取PDF并返回结构化文档"""
        file_info = self.get_file_info(file_path)
        
        doc = Document(
            file_path=file_info["path"],
            file_name=file_info["name"],
            file_format="pdf"
        )
        
        all_blocks = []
        
        with fitz.open(file_path) as pdf:
            doc.total_pages = len(pdf)
            
            for page_num in range(len(pdf)):
                page = pdf[page_num]
                page_blocks = self._extract_page_blocks(page, page_num + 1)
                all_blocks.extend(page_blocks)
        
        # 分析全局字体统计
        font_stats = self._analyze_font_stats(all_blocks)
        
        # 标记每个块的类型（章节标题/小标题/正文）
        self._classify_blocks(all_blocks, font_stats)
        
        # 合并同一标题下的连续内容
        merged_blocks = self._merge_paragraphs(all_blocks)
        
        # 检测章节边界（仅章节标题开始新章节）
        doc.chapters = self._detect_chapters(merged_blocks)
        doc.total_chapters = len(doc.chapters)
        doc.total_words = sum(len(b["text"]) for b in merged_blocks)
        
        return doc
    
    def _extract_page_blocks(self, page: fitz.Page, page_num: int) -> List[Dict]:
        """提取页面的文本块，包含位置和样式信息"""
        blocks = []
        
        # 获取页面尺寸
        page_rect = page.rect
        page_width = page_rect.width
        page_height = page_rect.height
        
        # 提取文本块（带格式）
        text_dict = page.get_text("dict")
        
        for block in text_dict.get("blocks", []):
            if "lines" not in block:
                continue
            
            for line in block["lines"]:
                # 计算行的整体信息
                line_text = ""
                line_font_sizes = []
                line_fonts = []
                line_bboxes = []
                
                for span in line["spans"]:
                    text = span.get("text", "")
                    if text.strip():
                        line_text += text
                        line_font_sizes.append(span.get("size", 12))
                        line_fonts.append(span.get("font", ""))
                        line_bboxes.append(span["bbox"])
                
                if not line_text.strip():
                    continue
                
                # 计算行的边界框
                if line_bboxes:
                    x0 = min(b[0] for b in line_bboxes)
                    y0 = min(b[1] for b in line_bboxes)
                    x1 = max(b[2] for b in line_bboxes)
                    y1 = max(b[3] for b in line_bboxes)
                else:
                    continue
                
                # 计算平均字体大小
                avg_font_size = sum(line_font_sizes) / len(line_font_sizes) if line_font_sizes else 12
                
                # 判断是否粗体
                is_bold = any("bold" in f.lower() or "黑体" in f or "Bold" in f for f in line_fonts)
                
                # 计算水平位置特征
                line_width = x1 - x0
                left_margin = x0
                right_margin = page_width - x1
                
                # 判断是否居中（左右边距差小于行宽的20%）
                is_centered = abs(left_margin - right_margin) < line_width * 0.2
                
                # 判断是否靠左（左边距小于右边距的一半）
                is_left_aligned = left_margin < right_margin * 0.5
                
                # 计算行中心位置（用于后续段落合并）
                center_x = (x0 + x1) / 2
                
                blocks.append({
                    "text": line_text.strip(),
                    "font_size": avg_font_size,
                    "is_bold": is_bold,
                    "bbox": (x0, y0, x1, y1),
                    "page_num": page_num,
                    "line_width": line_width,
                    "left_margin": left_margin,
                    "right_margin": right_margin,
                    "is_centered": is_centered,
                    "is_left_aligned": is_left_aligned,
                    "center_x": center_x,
                    "page_width": page_width,
                    "page_height": page_height
                })
        
        return blocks
    
    def _analyze_font_stats(self, blocks: List[Dict]) -> Dict:
        """分析全局字体统计信息"""
        if not blocks:
            return {}
        
        font_sizes = [b["font_size"] for b in blocks]
        font_sizes.sort()
        
        n = len(font_sizes)
        
        return {
            "min_size": font_sizes[0],
            "max_size": font_sizes[-1],
            "median_size": font_sizes[n // 2],
            "mean_size": sum(font_sizes) / n,
            "q1_size": font_sizes[n // 4],  # 25%分位数
            "q3_size": font_sizes[3 * n // 4],  # 75%分位数
        }
    
    def _classify_blocks(self, blocks: List[Dict], font_stats: Dict):
        """
        根据版面特征分类文本块
        
        分类体系：
        - 章节标题 (is_chapter_title): 居中 + 字号显著大于正文 → 开始新章节
        - 小标题 (is_subheading): 数字列表格式 → 归属于当前章节
        - 正文 (is_body): 其他内容 → 归属于当前章节
        """
        if not font_stats:
            return
        
        median_size = font_stats.get("median_size", 12)
        q3_size = font_stats.get("q3_size", 12)
        mean_size = font_stats.get("mean_size", 12)
        
        for block in blocks:
            font_size = block["font_size"]
            is_centered = block["is_centered"]
            is_bold = block["is_bold"]
            text = block["text"]
            text_len = len(text)
            
            # 初始化
            is_chapter_title = False
            is_subheading = False
            subheading_level = 0
            
            # ========== 章节标题判定 ==========
            # 必须同时满足：居中 + 字号显著大于正文 + 短文本
            if font_size > q3_size * 1.2 and is_centered and text_len < 50:
                is_chapter_title = True
            # 或者：粗体 + 居中 + 短文本
            elif is_bold and is_centered and text_len < 40 and font_size >= median_size:
                is_chapter_title = True
            
            # ========== 小标题判定（章节内） ==========
            # 数字列表格式，字号略大于或等于正文，不作为章节标题
            if not is_chapter_title and self._is_numbered_subheading(text):
                # 字号条件：略大于正文（1.05-1.3倍）或等于正文
                if median_size * 1.05 <= font_size <= median_size * 1.3:
                    is_subheading = True
                    subheading_level = 2
                # 或者粗体 + 短文本
                elif is_bold and text_len < 50:
                    is_subheading = True
                    subheading_level = 3
            
            # ========== 正文判定 ==========
            is_body = (
                not is_chapter_title and 
                not is_subheading and
                font_size >= median_size * 0.85 and 
                font_size <= median_size * 1.3
            )
            
            block["is_chapter_title"] = is_chapter_title
            block["is_subheading"] = is_subheading
            block["is_body"] = is_body
            block["subheading_level"] = subheading_level
    
    def _is_numbered_subheading(self, text: str) -> bool:
        """
        判断是否为数字编号的小标题（章节内）
        
        特征：
        - 阿拉伯数字或中文数字开头
        - 后跟标点或空格
        - 短文本（通常 < 50 字符）
        """
        # 清理文本
        text = text.strip()
        
        # 数字列表模式
        patterns = [
            r'^\d{1,3}[\.\、\s]\s*',           # 1.  1、  1 
            r'^\d{2,3}\s+',                     # 01  02
            r'^[（(]\d{1,3}[)）]\s*',           # (1)  （1）
            r'^[\u4e00-\u9fa5]{1,3}[、\.\s]',   # 一、  二.  三 
            r'^[（(][\u4e00-\u9fa5]{1,3}[)）]', # （一） （二）
        ]
        
        for pattern in patterns:
            if re.match(pattern, text):
                return True
        return False
    
    def _merge_paragraphs(self, blocks: List[Dict]) -> List[Dict]:
        """
        合并同一正文段落内的连续行
        
        规则：
        - 章节标题和小标题不合并
        - 连续的正文行（靠左对齐）
        - 字号相近（差异 < 15%）
        - 水平位置相近（中心点差异 < 20%页面宽度）
        """
        if not blocks:
            return blocks
        
        merged = []
        current_para = None
        
        for block in blocks:
            # 标题不合并
            if block.get("is_chapter_title") or block.get("is_subheading"):
                if current_para:
                    merged.append(current_para)
                    current_para = None
                merged.append(block)
                continue
            
            # 尝试合并到当前段落
            if current_para is None:
                current_para = block.copy()
            else:
                # 检查是否可以合并
                font_size_diff = abs(block["font_size"] - current_para["font_size"]) / current_para["font_size"]
                center_diff = abs(block["center_x"] - current_para["center_x"]) / block["page_width"]
                
                # 合并条件：字号相近、位置相近、都是正文
                if (font_size_diff < 0.15 and 
                    center_diff < 0.2 and 
                    block.get("is_body") and 
                    current_para.get("is_body")):
                    # 合并文本
                    current_para["text"] += " " + block["text"]
                    # 更新边界框
                    current_para["bbox"] = (
                        min(current_para["bbox"][0], block["bbox"][0]),
                        min(current_para["bbox"][1], block["bbox"][1]),
                        max(current_para["bbox"][2], block["bbox"][2]),
                        max(current_para["bbox"][3], block["bbox"][3])
                    )
                else:
                    # 不能合并，保存当前段落
                    merged.append(current_para)
                    current_para = block.copy()
        
        # 保存最后一个段落
        if current_para:
            merged.append(current_para)
        
        return merged
    
    def _detect_chapters(self, blocks: List[Dict]) -> List[Chapter]:
        """
        根据章节标题检测章节边界
        
        规则：
        - 只有 is_chapter_title 开始新章节
        - 小标题和正文都归属于当前章节
        - 遇到下一个章节标题时结束当前章节
        """
        chapters = []
        current_chapter_blocks = []
        chapter_index = 0
        current_title = None
        
        for block in blocks:
            if block.get("is_chapter_title"):
                # 保存上一个章节
                if current_chapter_blocks and current_title:
                    chapter = self._create_chapter(
                        chapter_index, 
                        current_title, 
                        current_chapter_blocks
                    )
                    if chapter:
                        chapters.append(chapter)
                        chapter_index += 1
                
                # 开始新章节
                current_title = block["text"]
                current_chapter_blocks = [block]
            else:
                # 归属于当前章节（包括小标题和正文）
                current_chapter_blocks.append(block)
        
        # 保存最后一个章节
        if current_chapter_blocks and current_title:
            chapter = self._create_chapter(
                chapter_index,
                current_title,
                current_chapter_blocks
            )
            if chapter:
                chapters.append(chapter)
        
        # 如果没有检测到章节，将所有内容作为一个章节
        if not chapters and blocks:
            # 尝试找到第一个非空行作为标题
            title = "正文"
            for b in blocks[:5]:
                if b["text"] and len(b["text"]) < 100:
                    title = b["text"][:50]
                    break
            
            chapter = self._create_chapter(0, title, blocks)
            if chapter:
                chapters.append(chapter)
        
        return chapters
    
    def _create_chapter(self, index: int, title: str, blocks: List[Dict]) -> Chapter:
        """从文本块创建章节"""
        if not blocks:
            return None
        
        # 将块转换为 ContentBlock
        content_blocks = []
        
        # 第一个块是章节标题，跳过
        body_blocks = blocks[1:] if len(blocks) > 1 else blocks
        
        for block in body_blocks:
            if not block.get("text"):
                continue
            
            # 确定内容类型
            if block.get("is_subheading"):
                content_type = ContentType.HEADING
                level = block.get("subheading_level", 2)
            elif block.get("is_body"):
                content_type = ContentType.PARAGRAPH
                level = 0
            else:
                content_type = ContentType.PARAGRAPH
                level = 0
            
            content_block = ContentBlock(
                type=content_type,
                text=block["text"],
                level=level,
                style=TextStyle(
                    bold=block.get("is_bold", False),
                    font_size=block.get("font_size")
                ),
                page_number=block.get("page_num", 1),
                bbox=block.get("bbox")
            )
            content_blocks.append(content_block)
        
        # 计算统计信息
        word_count = sum(len(b.text) for b in content_blocks)
        paragraph_count = sum(
            1 for b in content_blocks 
            if b.type == ContentType.PARAGRAPH
        )
        
        return Chapter(
            index=index + 1,
            title=title[:100],  # 限制标题长度
            level=1,
            content_blocks=content_blocks,
            word_count=word_count,
            paragraph_count=paragraph_count
        )
