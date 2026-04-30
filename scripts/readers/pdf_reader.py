"""
PDF文件读取器 - 输出JSON结构化文档
"""
import re
from .base import FileReader
from pathlib import Path
from core.document import Document, Chapter, ContentBlock, ContentType, TextStyle


class PDFReader(FileReader):
    """PDF文件读取器 - 保留格式信息的结构化读取"""
    
    def supports(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() == '.pdf'
    
    def read(self, file_path: str) -> Document:
        """
        读取PDF文件并返回结构化文档
        
        提取内容的同时保留：
        - 页面结构
        - 字体样式（粗体、字号）
        - 段落边界
        - 标题层级
        """
        file_info = self.get_file_info(file_path)
        
        try:
            import pdfplumber
            
            doc = Document(
                file_path=file_info["path"],
                file_name=file_info["name"],
                file_format="pdf"
            )
            
            all_content_blocks = []
            current_chapter_blocks = []
            chapter_index = 0
            
            with pdfplumber.open(file_path) as pdf:
                doc.total_pages = len(pdf.pages)
                
                for page_num, page in enumerate(pdf.pages, 1):
                    # 提取带格式的文本
                    words = page.extract_words(
                        keep_blank_chars=True,
                        x_tolerance=3,
                        y_tolerance=3
                    )
                    
                    if not words:
                        continue
                    
                    # 按行分组
                    lines = self._group_words_to_lines(words)
                    
                    for line_info in lines:
                        block = self._create_content_block(line_info, page_num)
                        
                        # 检测章节标题
                        if self._is_chapter_title(block):
                            # 保存上一个章节
                            if current_chapter_blocks:
                                chapter = self._create_chapter(
                                    chapter_index, 
                                    current_chapter_blocks
                                )
                                if chapter:
                                    doc.chapters.append(chapter)
                                    chapter_index += 1
                            
                            # 开始新章节
                            current_chapter_blocks = [block]
                        else:
                            current_chapter_blocks.append(block)
                        
                        all_content_blocks.append(block)
                
                # 保存最后一个章节
                if current_chapter_blocks:
                    chapter = self._create_chapter(
                        chapter_index, 
                        current_chapter_blocks
                    )
                    if chapter:
                        doc.chapters.append(chapter)
            
            # 如果没有检测到章节，将所有内容作为一个章节
            if not doc.chapters and all_content_blocks:
                doc.chapters.append(self._create_chapter(0, all_content_blocks))
            
            # 更新统计信息
            doc.total_chapters = len(doc.chapters)
            doc.total_words = sum(
                len(block.text) 
                for ch in doc.chapters 
                for block in ch.content_blocks
            )
            
            return doc
            
        except ImportError:
            print("pdfplumber not installed, trying PyMuPDF...")
            return self._read_with_pymupdf(file_path, file_info)
        except Exception as e:
            print(f"Error reading PDF {file_path}: {e}")
            return self._create_empty_doc(file_info)
    
    def _read_with_pymupdf(self, file_path: str, file_info: dict) -> Document:
        """使用PyMuPDF读取PDF"""
        try:
            import fitz
            
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
                    blocks = page.get_text("dict")["blocks"]
                    
                    for block in blocks:
                        if "lines" in block:
                            for line in block["lines"]:
                                for span in line["spans"]:
                                    text = span["text"].strip()
                                    if text:
                                        content_block = ContentBlock(
                                            type=ContentType.PARAGRAPH,
                                            text=text,
                                            style=TextStyle(
                                                bold=span.get("flags", 0) & 2 ** 4 != 0,
                                                font_size=span.get("size"),
                                                font_name=span.get("font")
                                            ),
                                            page_number=page_num + 1,
                                            bbox=(
                                                block["bbox"][0],
                                                block["bbox"][1],
                                                block["bbox"][2],
                                                block["bbox"][3]
                                            )
                                        )
                                        all_blocks.append(content_block)
            
            # 章节检测和分组
            doc.chapters = self._detect_chapters_from_blocks(all_blocks)
            doc.total_chapters = len(doc.chapters)
            doc.total_words = sum(
                len(block.text) for block in all_blocks
            )
            
            return doc
            
        except ImportError:
            print("PyMuPDF not installed. Please install: pip install pdfplumber PyMuPDF")
            return self._create_empty_doc(file_info)
    
    def _group_words_to_lines(self, words: list) -> list:
        """将单词按行分组"""
        if not words:
            return []
        
        lines = []
        current_line = [words[0]]
        current_y = words[0].get("top", 0)
        
        for word in words[1:]:
            word_y = word.get("top", 0)
            # y坐标接近则认为是同一行
            if abs(word_y - current_y) < 5:
                current_line.append(word)
            else:
                lines.append(self._merge_words_to_line(current_line))
                current_line = [word]
                current_y = word_y
        
        if current_line:
            lines.append(self._merge_words_to_line(current_line))
        
        return lines
    
    def _merge_words_to_line(self, words: list) -> dict:
        """合并单词为行信息"""
        text = " ".join(w.get("text", "") for w in words)
        
        # 计算平均字体大小
        sizes = [w.get("size", 12) for w in words if w.get("size")]
        avg_size = sum(sizes) / len(sizes) if sizes else 12
        
        # 检测粗体
        is_bold = any(
            w.get("fontname", "").lower().find("bold") >= 0 
            for w in words
        )
        
        return {
            "text": text,
            "size": avg_size,
            "bold": is_bold,
            "words": words
        }
    
    def _create_content_block(self, line_info: dict, page_num: int) -> ContentBlock:
        """创建内容块"""
        text = line_info["text"].strip()
        
        # 检测内容类型
        content_type = self._detect_content_type(text, line_info)
        
        # 检测标题层级
        level = self._detect_heading_level(text, line_info)
        
        return ContentBlock(
            type=content_type,
            text=text,
            level=level,
            style=TextStyle(
                bold=line_info.get("bold", False),
                font_size=line_info.get("size")
            ),
            page_number=page_num
        )
    
    def _detect_content_type(self, text: str, line_info: dict) -> ContentType:
        """检测内容类型"""
        # 代码块检测
        if text.startswith("    ") or text.startswith("\t"):
            return ContentType.CODE
        
        # 列表检测
        if re.match(r'^[\s]*[•\-\*\d]+[\.\)]?[\s]', text):
            return ContentType.LIST
        
        # 引用检测
        if text.startswith(">") or text.startswith("「"):
            return ContentType.QUOTE
        
        # 标题检测
        if self._is_heading(text, line_info):
            return ContentType.HEADING
        
        return ContentType.PARAGRAPH
    
    def _detect_heading_level(self, text: str, line_info: dict) -> int:
        """检测标题层级"""
        size = line_info.get("size", 12)
        
        # 根据字号判断层级
        if size >= 18:
            return 1
        elif size >= 14:
            return 2
        elif size >= 12:
            return 3
        
        # 根据格式判断
        if re.match(r'^[第]?[\d一二三四五六七八九十]+[章节篇回]', text):
            return 1
        # 数字列表标题（如"1. 标题"、"01 标题"）
        if re.match(r'^\d{1,3}[\.\、\s]+', text):
            return 2
        if re.match(r'^\d{2,3}\s+', text):
            return 2
        
        return 0
    
    def _is_heading(self, text: str, line_info: dict) -> bool:
        """判断是否为标题"""
        size = line_info.get("size", 12)
        is_bold = line_info.get("bold", False)
        
        # 字号较大或加粗
        if size >= 14 or is_bold:
            return True
        
        # 匹配标题格式
        heading_patterns = [
            r'^[第]?[\d一二三四五六七八九十]+[章节篇回]',
            r'^[\d一二三四五六七八九十]+[、\.\s]',
            r'^(?:摘要|前言|引言|结论|总结|附录)',
            # 数字列表标题（更宽松）
            r'^\d{1,3}[\.\、\s]+[\u4e00-\u9fa5]',  # 1. 中文
            r'^\d{2,3}\s+[\u4e00-\u9fa5]',        # 01 中文
        ]
        
        for pattern in heading_patterns:
            if re.match(pattern, text):
                return True
        
        return False
    
    def _is_chapter_title(self, block: ContentBlock) -> bool:
        """判断是否为章节标题"""
        text = block.text.strip()
        
        # 一级标题检测（传统章节）
        chapter_patterns = [
            r'^[第][\d一二三四五六七八九十百千万]+[章节篇回]',
            r'^Chapter\s+\d+',
            r'^Part\s+\d+',
        ]
        
        for pattern in chapter_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        
        # 数字列表标题检测（如"1. 思维模型名称"、"01 模型名称"）
        number_patterns = [
            r'^\d{1,3}[\.\、\s]+[\u4e00-\u9fa5]',  # 1. 中文标题、1、中文
            r'^\d{2,3}\s+[\u4e00-\u9fa5]',        # 01 中文标题
            r'^\d{1,3}\.[\s]*[A-Za-z]',          # 1. English
        ]
        
        for pattern in number_patterns:
            if re.match(pattern, text):
                # 额外检查：数字列表标题通常较短，或者是粗体/较大字号
                is_short = len(text) < 50
                is_styled = block.type == ContentType.HEADING or block.style.bold or (block.style.font_size and block.style.font_size >= 12)
                if is_short or is_styled:
                    return True
        
        # 根据样式判断（粗体大字号的一级标题）
        if block.type == ContentType.HEADING and block.level == 1 and block.style.bold:
            return True
        
        return False
    
    def _create_chapter(self, index: int, blocks: list) -> Chapter:
        """
        从内容块创建章节
        
        章节过滤规则：
        - 如果章节没有对应的正文内容（移除标题后字数≤3个中文字符或<5个英文单词），则跳过该章节
        """
        if not blocks:
            return None
        
        # 第一个块作为标题（如果是标题类型）
        title_block = blocks[0]
        if title_block.type == ContentType.HEADING:
            title = title_block.text
            content_blocks = blocks[1:]
        else:
            title = f"章节 {index + 1}"
            content_blocks = blocks
        
        # 计算统计信息
        word_count = sum(len(block.text) for block in content_blocks)
        paragraph_count = sum(
            1 for block in content_blocks 
            if block.type == ContentType.PARAGRAPH
        )
        
        # 章节过滤：检查是否有足够的正文内容
        all_content_text = ''.join(block.text for block in content_blocks)
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', all_content_text))
        english_words = len(re.findall(r'[a-zA-Z]+', all_content_text))
        
        # 如果正文内容过少（≤3个中文字符或<5个英文单词），跳过该章节
        if chinese_chars <= 3 and english_words < 5:
            return None
        
        return Chapter(
            index=index + 1,
            title=title,
            level=1,
            content_blocks=content_blocks,
            word_count=word_count,
            paragraph_count=paragraph_count
        )
    
    def _detect_chapters_from_blocks(self, blocks: list) -> list:
        """从内容块列表中检测章节"""
        chapters = []
        current_chapter_blocks = []
        chapter_index = 0
        
        for block in blocks:
            if self._is_chapter_title(block):
                # 保存上一个章节
                if current_chapter_blocks:
                    chapter = self._create_chapter(
                        chapter_index, 
                        current_chapter_blocks
                    )
                    if chapter:
                        chapters.append(chapter)
                        chapter_index += 1
                
                # 开始新章节
                current_chapter_blocks = [block]
            else:
                current_chapter_blocks.append(block)
        
        # 保存最后一个章节
        if current_chapter_blocks:
            chapter = self._create_chapter(chapter_index, current_chapter_blocks)
            if chapter:
                chapters.append(chapter)
        
        # 如果没有检测到章节，将所有内容作为一个章节
        if not chapters and blocks:
            chapters.append(self._create_chapter(0, blocks))
        
        return chapters
    
    def _create_empty_doc(self, file_info: dict) -> Document:
        """创建空文档"""
        return Document(
            file_path=file_info["path"],
            file_name=file_info["name"],
            file_format="pdf"
        )
