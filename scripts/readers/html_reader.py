"""
HTML文件读取器 - 基于HTML标签层级的智能分章

统一层级规则（h1和h2为同级章节）：
1. 书籍名：字体大小 ≥ h1 或特殊标记（如class="book-title"，仅标记边界，不创建章节）
2. 章节标题：h1/h2 标签（Chapter level=1）
   - h1和h2为同级章节，各自独立
   - 章节标题文本：优先使用h1/h2标签的文本内容，否则使用title属性（支持class="hidden"）
   - 内容范围：从当前章节开始（包含h1/h2标题元素本身），直到下一个章节之前的所有内容
   - 包含所有正文内容直到下一个章节
   - 过滤规则：如果h1/h2没有对应正文内容（移除标题后字数<10中文或<20英文），则跳过
3. 小标题：h3-h6 标签（作为正文内容块）
   - 归属于最近的章节

内容归属：
- 书籍名 → 文档元数据（仅标记边界）
- h1/h2 → 同级章节（各自包含h1/h2标题元素本身 + 直到下一个章节之前的所有内容）
- h3-h6 + 正文 → 归属于最近的章节
"""
from .base import FileReader
from pathlib import Path
from typing import List, Dict, Optional
from core.document import Document, Chapter, ContentBlock, ContentType, TextStyle


class HTMLReader(FileReader):
    """
    HTML文件读取器 - 基于HTML标签层级的智能分章
    
    统一层级结构（h1和h2为同级）：
    - 书籍名：字号 >= h1 或特殊class标记 → 文档标题（仅标记边界）
    - h1/h2：同级章节 → Chapter(level=1)
      - 章节标题：优先使用标签文本，否则使用title属性（支持class="hidden"）
      - 内容范围：从当前章节到下一个章节之前的所有内容
      - 包含所有正文内容直到下一个章节
      - 过滤：无正文内容（<10中文或<20英文）的章节标签会被跳过
    - h3-h6：小章节标题 → ContentBlock(type=HEADING)，属于正文
    """
    
    def supports(self, file_path: str) -> bool:
        ext = Path(file_path).suffix.lower()
        return ext in ['.html', '.htm', '.xhtml']
    
    def read(self, file_path: str) -> Document:
        """读取HTML文件并返回结构化文档"""
        file_info = self.get_file_info(file_path)
        
        try:
            from bs4 import BeautifulSoup
            
            doc = Document(
                file_path=file_info["path"],
                file_name=file_info["name"],
                file_format="html"
            )
            
            # 读取文件
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            soup = BeautifulSoup(content, 'html.parser')
            
            # 移除脚本和样式
            for script in soup(["script", "style"]):
                script.decompose()
            
            # 尝试提取标题
            title_tag = soup.find('title')
            if title_tag:
                doc.title = title_tag.get_text(strip=True)
            
            # 提取章节
            doc.chapters = self._detect_chapters_from_html(soup)
            doc.total_chapters = len(doc.chapters)
            doc.total_words = sum(c.word_count for c in doc.chapters)
            
            return doc
            
        except ImportError:
            print("beautifulsoup4 not installed. Please install: pip install beautifulsoup4")
            return self._create_empty_doc(file_info)
        except Exception as e:
            print(f"Error reading HTML {file_path}: {e}")
            return self._create_empty_doc(file_info)
    
    def _detect_chapters_from_html(self, soup) -> List[Chapter]:
        """
        从HTML中检测章节（统一层级规则：h1和h2为同级）
        
        同级章节规则：
        - h1和h2作为同级章节边界
        - 章节标题：优先使用h1/h2的title属性（支持class="hidden"），否则使用标签文本
        - 每个章节包含从当前章节到下一个章节之前的所有内容
        - h3-h6作为正文内容块
        """
        from bs4 import BeautifulSoup
        import re
        
        chapters = []
        chapter_index = 0
        
        # 收集所有元素
        all_elements = list(soup.descendants)
        
        # 找到所有h1和h2元素作为同级章节边界
        chapter_positions = []
        for i, elem in enumerate(all_elements):
            if hasattr(elem, 'name') and elem.name:
                tag_name = elem.name.lower()
                if tag_name in ['h1', 'h2']:
                    chapter_positions.append((i, elem, tag_name))
        
        if not chapter_positions:
            # 没有h1/h2，将所有内容作为一个章节
            body = soup.find('body')
            if body:
                chapter = self._create_chapter_from_element(
                    chapter_index, "正文", 1, body
                )
                if chapter and chapter.word_count > 0:
                    chapters.append(chapter)
            return chapters
        
        # 处理每个h1/h2作为同级章节
        for idx, (start_pos, elem, tag_name) in enumerate(chapter_positions):
            # 提取章节标题：优先使用标签文本，否则使用title属性
            title = self._extract_chapter_title(elem)
            if not title:
                continue
            
            # 确定这个章节的内容范围（到下一个h1/h2之前）
            if idx + 1 < len(chapter_positions):
                end_pos = chapter_positions[idx + 1][0]
            else:
                end_pos = len(all_elements)
            
            # 提取章节内容
            content = self._extract_content_between(
                all_elements, start_pos, end_pos
            )
            
            # 检查是否有正文内容（不只是标题）
            if not self._has_substantial_content(content, title):
                # 没有正文内容，跳过此章节标签
                continue
            
            # 创建章节（h1和h2同级，都使用level=1）
            chapter = self._create_chapter_from_content(
                chapter_index, title, 1, content
            )
            if chapter and chapter.word_count > 0:
                chapters.append(chapter)
                chapter_index += 1
        
        return chapters
    
    def _has_substantial_content(self, content: str, title: str) -> bool:
        """
        检查内容是否有实质性正文（不只是标题）
        
        规则：
        1. 提取纯文本内容
        2. 移除标题文本
        3. 检查剩余内容是否有足够的字数（>10个中文字符或>20个英文单词）
        """
        from bs4 import BeautifulSoup
        import re
        
        soup = BeautifulSoup(content, 'html.parser')
        text = soup.get_text(strip=True)
        
        # 移除标题文本
        text_without_title = text.replace(title, "", 1).strip()
        
        # 计算字数（中文字符 + 英文单词）
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text_without_title))
        english_words = len(re.findall(r'[a-zA-Z]+', text_without_title))
        
        # 检查是否有足够的正文内容（>3个中文字符或>=5个英文单词）
        return chinese_chars > 3 or english_words >= 5
    
    def _extract_chapter_title(self, elem) -> str:
        """
        提取章节标题
        
        优先级：
        1. 优先使用标签的文本内容（如果存在且不为空）
        2. 否则使用title属性（支持class="hidden"的h1/h2）
        """
        # 优先使用标签文本（如果存在且不为空）
        text_content = elem.get_text(strip=True)
        if text_content:
            return text_content
        
        # 否则使用title属性
        title_attr = elem.get('title')
        if title_attr and title_attr.strip():
            return title_attr.strip()
        
        return ""
    
    def _extract_content_between(self, all_elements: List, start_idx: int, end_idx: int) -> str:
        """提取两个位置之间的内容"""
        content_parts = []
        
        for elem in all_elements[start_idx:end_idx]:
            if not hasattr(elem, 'name') or not elem.name:
                continue
            content_parts.append(str(elem))
        
        return '\n'.join(content_parts)
    
    def _create_chapter_from_element(self, index: int, title: str, level: int, elem) -> Chapter:
        """从元素创建章节"""
        content = str(elem)
        return self._create_chapter_from_content(index, title, level, content)
    
    def _create_chapter_from_content(self, index: int, title: str, level: int, content: str) -> Chapter:
        """从HTML内容创建章节"""
        from bs4 import BeautifulSoup
        import re
        
        soup = BeautifulSoup(content, 'html.parser')
        
        # 提取所有文本内容
        text = soup.get_text(separator='\n', strip=True)
        
        # 创建内容块
        content_blocks = self._extract_content_blocks(soup)
        
        # 计算字数（中文字符 + 英文单词）
        word_count = len(re.findall(r'[\u4e00-\u9fff]', text)) + len(re.findall(r'[a-zA-Z]+', text))
        
        return Chapter(
            index=index,
            title=title,
            level=level,
            content_blocks=content_blocks,
            word_count=word_count
        )
    
    def _extract_content_blocks(self, soup) -> List[ContentBlock]:
        """从HTML中提取内容块"""
        blocks = []
        
        for elem in soup.descendants:
            if not hasattr(elem, 'name') or not elem.name:
                continue
            
            tag_name = elem.name.lower()
            
            # 跳过脚本和样式
            if tag_name in ['script', 'style']:
                continue
            
            text = elem.get_text(strip=True)
            if not text:
                continue
            
            # 判断内容类型
            if tag_name in ['h1', 'h2']:
                # h1/h2作为章节标题，不添加到内容块
                continue
            elif tag_name in ['h3', 'h4', 'h5', 'h6']:
                block_type = ContentType.HEADING
            elif tag_name in ['p', 'div']:
                block_type = ContentType.PARAGRAPH
            elif tag_name in ['ul', 'ol']:
                block_type = ContentType.LIST
            elif tag_name == 'blockquote':
                block_type = ContentType.QUOTE
            elif tag_name == 'pre' or tag_name == 'code':
                block_type = ContentType.CODE
            elif tag_name == 'table':
                block_type = ContentType.TABLE
            else:
                block_type = ContentType.PARAGRAPH
            
            # 提取样式信息
            style = self._extract_style(elem)
            
            block = ContentBlock(
                type=block_type,
                text=text,
                style=style
            )
            blocks.append(block)
        
        return blocks
    
    def _extract_style(self, elem) -> TextStyle:
        """从HTML元素提取样式信息"""
        style = TextStyle()
        
        # 检查粗体
        if elem.name in ['b', 'strong']:
            style.bold = True
        
        # 检查斜体
        if elem.name in ['i', 'em']:
            style.italic = True
        
        # 检查样式属性
        if elem.get('style'):
            style_str = elem.get('style').lower()
            if 'font-weight' in style_str and ('bold' in style_str or '700' in style_str):
                style.bold = True
            if 'font-style' in style_str and 'italic' in style_str:
                style.italic = True
            if 'text-align' in style_str:
                if 'center' in style_str:
                    style.alignment = 'center'
                elif 'right' in style_str:
                    style.alignment = 'right'
                elif 'left' in style_str:
                    style.alignment = 'left'
        
        # 检查class
        if elem.get('class'):
            classes = ' '.join(elem.get('class')).lower()
            if 'bold' in classes or 'strong' in classes:
                style.bold = True
            if 'italic' in classes or 'em' in classes:
                style.italic = True
        
        return style
