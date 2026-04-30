"""
纯文本文件读取器 - 输出JSON结构化文档
"""
from .base import FileReader
from pathlib import Path
from core.document import Document, Chapter, ContentBlock, ContentType, TextStyle


class TxtReader(FileReader):
    """纯文本文件读取器 - 智能检测结构"""
    
    def supports(self, file_path: str) -> bool:
        ext = Path(file_path).suffix.lower()
        return ext in ['.txt', '.md', '.markdown']
    
    def read(self, file_path: str) -> Document:
        """
        读取纯文本文件并返回结构化文档
        
        智能检测：
        - Markdown标题（# ## ###）
        - 列表（- * 1.）
        - 代码块（```）
        - 引用（>）
        - 章节标题（第X章、Chapter X）
        """
        file_info = self.get_file_info(file_path)
        
        try:
            # 尝试多种编码
            content = self._read_with_encoding(file_path)
            
            if not content:
                return self._create_empty_doc(file_info)
            
            doc = Document(
                file_path=file_info["path"],
                file_name=file_info["name"],
                file_format=Path(file_path).suffix.lower().lstrip('.')
            )
            
            # 解析内容
            blocks = self._parse_content(content)
            
            # 章节分组
            doc.chapters = self._group_into_chapters(blocks)
            
            # 更新统计信息
            doc.total_chapters = len(doc.chapters)
            doc.total_words = sum(
                len(block.text) 
                for ch in doc.chapters 
                for block in ch.content_blocks
            )
            
            return doc
            
        except Exception as e:
            print(f"Error reading TXT {file_path}: {e}")
            return self._create_empty_doc(file_info)
    
    def _read_with_encoding(self, file_path: str) -> str:
        """尝试多种编码读取文件"""
        encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
            except Exception:
                continue
        
        return ""
    
    def _parse_content(self, content: str) -> list:
        """解析内容为结构化块"""
        import re
        
        blocks = []
        lines = content.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            if not stripped:
                i += 1
                continue
            
            # 检测代码块
            if stripped.startswith('```'):
                code_block, i = self._parse_code_block(lines, i)
                if code_block:
                    blocks.append(code_block)
                continue
            
            # 检测Markdown标题
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            if heading_match:
                level = len(heading_match.group(1))
                text = heading_match.group(2)
                blocks.append(ContentBlock(
                    type=ContentType.HEADING,
                    text=text,
                    level=level,
                    style=TextStyle(bold=True)
                ))
                i += 1
                continue
            
            # 检测列表
            list_match = re.match(r'^[\s]*([\-\*\+]|[\d]+[\.\)])\s+(.+)$', stripped)
            if list_match:
                list_block, i = self._parse_list(lines, i)
                if list_block:
                    blocks.append(list_block)
                continue
            
            # 检测引用
            if stripped.startswith('>'):
                quote_block, i = self._parse_quote(lines, i)
                if quote_block:
                    blocks.append(quote_block)
                continue
            
            # 检测章节标题（第X章、Chapter X）
            if self._is_chapter_heading(stripped):
                blocks.append(ContentBlock(
                    type=ContentType.HEADING,
                    text=stripped,
                    level=1,
                    style=TextStyle(bold=True)
                ))
                i += 1
                continue
            
            # 普通段落
            para_block, i = self._parse_paragraph(lines, i)
            if para_block:
                blocks.append(para_block)
        
        return blocks
    
    def _parse_code_block(self, lines: list, start: int) -> tuple:
        """解析代码块"""
        import re
        
        first_line = lines[start].strip()
        
        # 提取语言
        lang_match = re.match(r'^```(\w+)?$', first_line)
        language = lang_match.group(1) if lang_match and lang_match.group(1) else None
        
        code_lines = []
        i = start + 1
        
        while i < len(lines):
            if lines[i].strip() == '```':
                i += 1
                break
            code_lines.append(lines[i])
            i += 1
        
        code_text = '\n'.join(code_lines)
        
        block = ContentBlock(
            type=ContentType.CODE,
            text=code_text,
            level=0,
            style=TextStyle(),
            language=language
        )
        
        return block, i
    
    def _parse_list(self, lines: list, start: int) -> tuple:
        """解析列表"""
        import re
        
        list_items = []
        i = start
        is_ordered = False
        
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            if not stripped:
                i += 1
                continue
            
            # 检测列表项
            unordered_match = re.match(r'^[\s]*[\-\*\+]\s+(.+)$', stripped)
            ordered_match = re.match(r'^[\s]*[\d]+[\.\)]\s+(.+)$', stripped)
            
            if unordered_match:
                list_items.append(unordered_match.group(1))
                is_ordered = False
                i += 1
            elif ordered_match:
                list_items.append(ordered_match.group(1))
                is_ordered = True
                i += 1
            else:
                break
        
        if not list_items:
            return None, start + 1
        
        text = '\n'.join([f"{'1.' if is_ordered else '-'} {item}" for item in list_items])
        
        block = ContentBlock(
            type=ContentType.LIST,
            text=text,
            level=0,
            style=TextStyle(),
            list_items=list_items,
            list_ordered=is_ordered
        )
        
        return block, i
    
    def _parse_quote(self, lines: list, start: int) -> tuple:
        """解析引用块"""
        quote_lines = []
        i = start
        
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            if not stripped:
                i += 1
                continue
            
            if stripped.startswith('>'):
                quote_lines.append(stripped[1:].strip())
                i += 1
            else:
                break
        
        if not quote_lines:
            return None, start + 1
        
        text = '\n'.join(quote_lines)
        
        block = ContentBlock(
            type=ContentType.QUOTE,
            text=text,
            level=0,
            style=TextStyle(italic=True)
        )
        
        return block, i
    
    def _parse_paragraph(self, lines: list, start: int) -> tuple:
        """解析段落"""
        para_lines = []
        i = start
        
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            if not stripped:
                break
            
            # 检测是否为其他类型
            if stripped.startswith('#') or stripped.startswith('>') or \
               stripped.startswith('-') or stripped.startswith('*') or \
               stripped.startswith('```') or self._is_chapter_heading(stripped):
                break
            
            para_lines.append(stripped)
            i += 1
        
        if not para_lines:
            return None, start + 1
        
        text = ' '.join(para_lines)
        
        block = ContentBlock(
            type=ContentType.PARAGRAPH,
            text=text,
            level=0,
            style=TextStyle()
        )
        
        return block, i
    
    def _is_chapter_heading(self, text: str) -> bool:
        """检测是否为章节标题"""
        import re
        
        chapter_patterns = [
            r'^[第][\d一二三四五六七八九十百千万]+[章节篇回]',
            r'^Chapter\s+\d+',
            r'^Part\s+\d+',
        ]
        
        for pattern in chapter_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def _group_into_chapters(self, blocks: list) -> list:
        """将内容块分组为章节"""
        chapters = []
        current_chapter_blocks = []
        chapter_index = 0
        
        for block in blocks:
            # 检测章节标题
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
    
    def _is_chapter_title(self, block: ContentBlock) -> bool:
        """判断是否为章节标题"""
        if block.type != ContentType.HEADING:
            return False
        
        # 一级标题通常是章节标题
        if block.level == 1:
            return True
        
        text = block.text
        import re
        
        chapter_patterns = [
            r'^[第][\d一二三四五六七八九十百千万]+[章节篇回]',
            r'^Chapter\s+\d+',
            r'^Part\s+\d+',
        ]
        
        for pattern in chapter_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def _create_chapter(self, index: int, blocks: list) -> Chapter:
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
        ext = Path(file_info["path"]).suffix.lower().lstrip('.')
        return Document(
            file_path=file_info["path"],
            file_name=file_info["name"],
            file_format=ext
        )
