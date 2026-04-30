"""
OCR 读取器 - 用于图片版 PDF 和扫描文档
"""
import re
from pathlib import Path
from typing import List, Optional
from .base import FileReader
from core.document import Document, Chapter, ContentBlock, ContentType, TextStyle


class OCRReader(FileReader):
    """OCR 读取器 - 使用 PaddleOCR 识别图片中的文字"""
    
    def supports(self, file_path: str) -> bool:
        ext = Path(file_path).suffix.lower()
        return ext in ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.bmp']
    
    def read(self, file_path: str) -> Document:
        """
        使用 OCR 读取图片版 PDF 或图片文件
        
        返回结构化文档，包含识别的文字和章节信息
        """
        file_info = self.get_file_info(file_path)
        
        try:
            from paddleocr import PaddleOCR
            import fitz  # PyMuPDF for PDF page rendering
            
            # 初始化 OCR
            ocr = PaddleOCR(
                use_angle_cls=True,
                lang='ch',
                show_log=False
            )
            
            doc = Document(
                file_path=file_info["path"],
                file_name=file_info["name"],
                file_format=Path(file_path).suffix.lower().lstrip('.')
            )
            
            # 处理 PDF 或图片
            if file_path.lower().endswith('.pdf'):
                pages = self._process_pdf(file_path, ocr)
            else:
                pages = self._process_image(file_path, ocr)
            
            # 合并所有页面的内容块
            all_blocks = []
            for page_num, blocks in enumerate(pages, 1):
                for block in blocks:
                    block.page_number = page_num
                    all_blocks.append(block)
            
            doc.total_pages = len(pages)
            
            # 检测章节
            doc.chapters = self._detect_chapters_from_blocks(all_blocks)
            doc.total_chapters = len(doc.chapters)
            doc.total_words = sum(len(block.text) for block in all_blocks)
            
            return doc
            
        except ImportError as e:
            print(f"OCR 依赖未安装: {e}")
            print("请安装: pip install paddleocr paddlepaddle pymupdf")
            return self._create_empty_doc(file_info)
        except Exception as e:
            print(f"OCR 读取失败: {e}")
            return self._create_empty_doc(file_info)
    
    def _process_pdf(self, file_path: str, ocr) -> List[List[ContentBlock]]:
        """处理 PDF 的每一页"""
        import fitz
        import tempfile
        import numpy as np
        from PIL import Image
        
        pages = []
        
        with fitz.open(file_path) as pdf:
            for page_num in range(len(pdf)):
                page = pdf[page_num]
                
                # 渲染页面为图片
                mat = fitz.Matrix(2, 2)  # 2x 缩放以提高 OCR 精度
                pix = page.get_pixmap(matrix=mat)
                
                # 转换为 PIL Image
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                
                # 保存临时文件
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                    img.save(tmp.name)
                    tmp_path = tmp.name
                
                # OCR 识别
                result = ocr.ocr(tmp_path, cls=True)
                
                # 清理临时文件
                import os
                os.unlink(tmp_path)
                
                # 解析 OCR 结果
                blocks = self._parse_ocr_result(result, page_num + 1)
                pages.append(blocks)
        
        return pages
    
    def _process_image(self, file_path: str, ocr) -> List[List[ContentBlock]]:
        """处理单张图片"""
        result = ocr.ocr(file_path, cls=True)
        blocks = self._parse_ocr_result(result, 1)
        return [blocks]
    
    def _parse_ocr_result(self, result, page_num: int) -> List[ContentBlock]:
        """解析 OCR 结果为标准内容块"""
        blocks = []
        
        if not result or not result[0]:
            return blocks
        
        for line in result[0]:
            if line:
                # OCR 结果格式: [bbox, (text, confidence)]
                bbox = line[0]
                text = line[1][0]
                confidence = line[1][1]
                
                if text and confidence > 0.5:  # 只保留置信度 > 50% 的结果
                    # 检测内容类型
                    content_type = self._detect_content_type(text)
                    level = self._detect_heading_level(text)
                    
                    block = ContentBlock(
                        type=content_type,
                        text=text,
                        level=level,
                        style=TextStyle(
                            bold=False,
                            font_size=None
                        ),
                        page_number=page_num,
                        bbox=(bbox[0][0], bbox[0][1], bbox[2][0], bbox[2][1])
                    )
                    blocks.append(block)
        
        return blocks
    
    def _detect_content_type(self, text: str) -> ContentType:
        """检测内容类型"""
        text = text.strip()
        
        # 标题检测
        if self._is_heading(text):
            return ContentType.HEADING
        
        # 列表检测
        if re.match(r'^[\s]*[•\-\*\d]+[\.\)]?[\s]', text):
            return ContentType.LIST
        
        # 引用检测
        if text.startswith(">") or text.startswith("「"):
            return ContentType.QUOTE
        
        return ContentType.PARAGRAPH
    
    def _detect_heading_level(self, text: str) -> int:
        """检测标题层级"""
        text = text.strip()
        
        # 一级标题
        if re.match(r'^[第][\d一二三四五六七八九十百千万]+[章节篇回]', text):
            return 1
        if re.match(r'^Chapter\s+\d+', text, re.IGNORECASE):
            return 1
        
        # 二级标题（数字列表）
        if re.match(r'^[\d一二三四五六七八九十]+[、\.\s]', text):
            return 2
        
        # 三级标题
        if re.match(r'^[（(][\d一二三四五六七八九十]+[)）]', text):
            return 3
        
        return 0
    
    def _is_heading(self, text: str) -> bool:
        """判断是否为标题"""
        text = text.strip()
        
        # 短文本可能是标题
        if len(text) < 30:
            # 匹配标题格式
            heading_patterns = [
                r'^[第][\d一二三四五六七八九十百千万]+[章节篇回]',
                r'^Chapter\s+\d+',
                r'^Part\s+\d+',
                r'^[\d一二三四五六七八九十]+[、\.\s]',
                r'^(?:摘要|前言|引言|结论|总结|附录)',
            ]
            
            for pattern in heading_patterns:
                if re.match(pattern, text, re.IGNORECASE):
                    return True
        
        return False
    
    def _detect_chapters_from_blocks(self, blocks: List[ContentBlock]) -> List[Chapter]:
        """从内容块中检测章节"""
        chapters = []
        current_chapter_blocks = []
        chapter_index = 0
        
        for block in blocks:
            if self._is_chapter_title(block):
                # 保存上一个章节
                if current_chapter_blocks:
                    chapter = self._create_chapter(chapter_index, current_chapter_blocks)
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
    
    def _is_chapter_title(self, block: ContentBlock) -> bool:
        """判断是否为章节标题"""
        if block.type != ContentType.HEADING:
            return False
        
        text = block.text.strip()
        
        # 一级标题
        chapter_patterns = [
            r'^[第][\d一二三四五六七八九十百千万]+[章节篇回]',
            r'^Chapter\s+\d+',
            r'^Part\s+\d+',
        ]
        
        for pattern in chapter_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        
        # 数字列表标题（如"1. 思维模型"）
        number_patterns = [
            r'^\d{1,3}[\.\、\s]+[\u4e00-\u9fa5]',  # 1. 中文
            r'^\d{2,3}\s+[\u4e00-\u9fa5]',        # 01 中文
        ]
        
        for pattern in number_patterns:
            if re.match(pattern, text):
                return True
        
        return False
    
    def _create_chapter(self, index: int, blocks: List[ContentBlock]) -> Optional[Chapter]:
        """从内容块创建章节"""
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
        
        return Chapter(
            index=index + 1,
            title=title,
            level=1,
            content_blocks=content_blocks,
            word_count=word_count,
            paragraph_count=paragraph_count
        )
    
    def _create_empty_doc(self, file_info: dict) -> Document:
        """创建空文档"""
        return Document(
            file_path=file_info["path"],
            file_name=file_info["name"],
            file_format="pdf"
        )
