"""
EPUB文件读取器 - 基于EPUB目录结构的智能分章
"""
from .base import FileReader
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from core.document import Document, Chapter, ContentBlock, ContentType, TextStyle
import re


def _info(msg: str):
    """打印信息日志"""
    print(f"[INFO] {msg}")


def _debug(msg: str):
    """打印调试日志"""
    print(f"[DEBUG] {msg}")


class EPUBReader(FileReader):
    """
    EPUB文件读取器 - 基于目录结构的智能分章
    
    核心逻辑：
    1. 读取EPUB目录(toc.ncx/nav.xhtml)获取章节结构
    2. 根据目录href提取各章节内容
    3. 一级章节包含直到下一个一级章节之前的所有内容
    4. 二级章节在一级章节内部，包含直到下一个二级章节之前的内容
    """
    
    def supports(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() == '.epub'
    
    def read(self, file_path: str) -> Document:
        """读取EPUB文件并返回结构化文档"""
        file_info = self.get_file_info(file_path)
        
        try:
            import ebooklib
            from ebooklib import epub
            from bs4 import BeautifulSoup
            
            doc = Document(
                file_path=file_info["path"],
                file_name=file_info["name"],
                file_format="epub"
            )
            
            book = epub.read_epub(file_path)
            
            # 提取元数据
            doc.title = self._get_metadata(book, 'title')
            doc.author = self._get_metadata(book, 'creator')
            doc.publisher = self._get_metadata(book, 'publisher')
            
            # 第一步：读取EPUB目录获取章节结构
            toc = self._extract_toc(book)
            
            # 第二步：构建文件内容映射
            file_contents = self._build_file_contents_map(book)
            
            # 第三步：根据目录结构创建章节
            if toc:
                # 使用目录结构
                doc.chapters = self._build_chapters_from_toc(toc, file_contents)
                
                # 检查目录提取是否成功（章节数是否过少或内容是否过少）
                if not self._validate_chapter_extraction(doc.chapters, file_contents):
                    _info("目录提取可能不完整，切换到HTML标签分析模式...")
                    html_chapters = self._extract_from_html_tags(file_contents)
                    # 如果标签提取的章节更多或内容更多，使用标签提取的结果
                    if len(html_chapters) > len(doc.chapters) or \
                       sum(c.word_count for c in html_chapters) > sum(c.word_count for c in doc.chapters) * 1.2:
                        _info(f"使用HTML标签提取: {len(html_chapters)}章 vs 目录提取: {len(doc.chapters)}章")
                        doc.chapters = html_chapters
            else:
                # 回退到HTML标签分析
                doc.chapters = self._extract_from_html_tags(file_contents)
            
            doc.total_chapters = len(doc.chapters)
            doc.total_words = sum(c.word_count for c in doc.chapters)
            
            return doc
            
        except ImportError:
            _info("ebooklib or beautifulsoup4 not installed. Please install: pip install ebooklib beautifulsoup4")
            return self._create_empty_doc(file_info)
        except Exception as e:
            _info(f"Error reading EPUB {file_path}: {e}")
            import traceback
            traceback.print_exc()
            return self._create_empty_doc(file_info)
    
    def _get_metadata(self, book, key: str) -> str:
        """获取EPUB元数据"""
        try:
            metadata = book.get_metadata('DC', key)
            if metadata:
                return metadata[0][0]
        except:
            pass
        return None
    
    def _extract_toc(self, book) -> List[Dict]:
        """
        从EPUB提取目录结构
        
        返回: [{'title': '章节名', 'href': '文件路径#锚点', 'level': 1}]
        level映射（统一层级规则，h1和h2为同级章节）：
        - level 1: 书籍名（字体大小 ≥ h1，仅标记边界）
        - level 2/3: 章节标题（h1/h2同级）→ Chapter(level=1)
        - level 4+: 小标题（h3-h6，作为正文内容块）
        
        同级章节规则：
        - h1和h2为同级章节，各自独立
        - 每个章节包含从当前章节开始，直到下一个章节之前的所有内容
        - 小标题和正文归属于最近的章节
        """
        toc = []
        
        try:
            # 尝试读取 toc.ncx (EPUB 2)
            for item in book.get_items():
                if item.get_name().endswith('.ncx'):
                    toc = self._parse_ncx(item.get_content().decode('utf-8'))
                    if toc:
                        return toc
        except:
            pass
        
        try:
            # 尝试读取 nav.xhtml (EPUB 3)
            for item in book.get_items():
                if item.get_name().endswith('nav.xhtml') or 'nav' in item.get_name().lower():
                    toc = self._parse_nav_xhtml(item.get_content().decode('utf-8'))
                    if toc:
                        return toc
        except:
            pass
        
        return toc
    
    def _parse_ncx(self, content: str) -> List[Dict]:
        """解析NCX目录文件"""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(content, 'xml')
        toc = []
        
        # 查找所有navPoint
        for nav_point in soup.find_all('navPoint'):
            title_elem = nav_point.find('text')
            content_elem = nav_point.find('content')
            
            if title_elem and content_elem:
                title = title_elem.get_text(strip=True)
                href = content_elem.get('src', '')
                
                # 计算层级（根据navPoint嵌套深度）
                level = 1
                parent = nav_point.parent
                while parent:
                    if parent.name == 'navPoint':
                        level += 1
                    parent = parent.parent
                
                toc.append({
                    'title': title,
                    'href': href,
                    'level': level
                })
        
        return toc
    
    def _parse_nav_xhtml(self, content: str) -> List[Dict]:
        """解析EPUB3导航文件"""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(content, 'html.parser')
        toc = []
        
        # 查找toc nav
        nav = soup.find('nav', {'epub:type': 'toc'})
        if not nav:
            nav = soup.find('nav')
        
        if nav:
            # 递归解析ol/li结构
            def parse_list(ol, level=1):
                items = []
                for li in ol.find_all('li', recursive=False):
                    a = li.find('a')
                    if a:
                        title = a.get_text(strip=True)
                        href = a.get('href', '')
                        items.append({
                            'title': title,
                            'href': href,
                            'level': level
                        })
                    
                    # 递归处理子列表
                    sub_ol = li.find('ol', recursive=False)
                    if sub_ol:
                        items.extend(parse_list(sub_ol, level + 1))
                
                return items
            
            ol = nav.find('ol')
            if ol:
                toc = parse_list(ol)
        
        return toc
    
    def _build_file_contents_map(self, book) -> Dict[str, str]:
        """构建文件路径到内容的映射"""
        import ebooklib
        
        file_contents = {}
        
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                name = item.get_name()
                try:
                    content = item.get_content().decode('utf-8')
                    file_contents[name] = content
                except:
                    pass
        
        return file_contents
    
    def _build_chapters_from_toc(self, toc: List[Dict], file_contents: Dict[str, str]) -> List[Chapter]:
        """
        根据目录结构创建章节（统一层级规则，h1和h2为同级）
        
        层级映射：
        - level 1: 书籍名（字体大小 ≥ h1，仅标记边界，不创建章节）
        - level 2/3: 章节标题（h1/h2同级）→ Chapter(level=1)
        - level 4+: 小标题（h3-h6）→ 作为正文内容块，归属于最近的章节
        
        同级章节规则：
        - h1和h2为同级章节，各自独立
        - 每个章节包含从当前章节开始，到下一个章节之前的所有内容
        - 小标题和正文归属于最近的章节
        """
        from bs4 import BeautifulSoup
        
        chapters = []
        chapter_index = 0
        
        for i, toc_item in enumerate(toc):
            title = toc_item['title']
            href = toc_item['href']
            toc_level = toc_item.get('level', 1)
            
            # 解析href
            if '#' in href:
                file_path, anchor = href.split('#', 1)
            else:
                file_path, anchor = href, None
            
            # 获取文件内容
            content = file_contents.get(file_path, '')
            if not content:
                continue
            
            # 提取章节内容（传递当前文件路径用于锚点判断）
            chapter_content = self._extract_chapter_content(content, anchor, toc, i, file_path)
            
            # 检查内容是否为空
            temp_soup = BeautifulSoup(chapter_content, 'html.parser')
            text_content = temp_soup.get_text(strip=True)
            
            # 根据目录层级处理（统一层级规则：level 2/3 为同级章节）
            if toc_level == 1:
                # Level 1: 书籍名，仅标记边界，不创建章节
                continue
            
            elif toc_level in [2, 3]:
                # Level 2/3: 章节标题（h1/h2同级）
                if len(text_content) < 10:
                    continue
                
                # h1和h2为同级，都使用 level=1
                chapter = self._create_chapter_from_content(
                    chapter_index, title, 1, chapter_content
                )
                chapters.append(chapter)
                chapter_index += 1
            
            else:
                # Level 4+: 小标题（h3-h6），作为独立章节
                if len(text_content) < 10:
                    continue
                
                chapter = self._create_chapter_from_content(
                    chapter_index, title, 1, chapter_content
                )
                chapters.append(chapter)
                chapter_index += 1
        
        return chapters
    
    def _extract_chapter_content(self, content: str, anchor: Optional[str], 
                                  toc: List[Dict], toc_index: int,
                                  current_file: str = None) -> str:
        """提取章节内容
        
        内容范围规则：
        - 从当前章节的锚点开始
        - 到下一个同级或更高级别章节之前
        - 如果下一个章节在不同文件，提取到当前文件末尾
        """
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(content, 'html.parser')
        
        # 移除脚本和样式
        for script in soup(["script", "style"]):
            script.decompose()
        
        if anchor:
            # 如果有锚点，从锚点开始提取
            start_elem = soup.find(id=anchor)
            if start_elem:
                return self._extract_from_element(start_elem, soup, toc, toc_index, current_file)
        
        # 没有锚点或找不到锚点，返回整个body内容
        body = soup.find('body')
        if body:
            return str(body)
        
        return str(soup)
    
    def _extract_from_element(self, start_elem, soup, toc: List[Dict], 
                              toc_index: int, current_file: str = None) -> str:
        """从指定元素开始提取内容
        
        提取范围：
        - 从 start_elem 开始
        - 到下一个同级或更高级别的章节锚点之前
        - 如果下一章节在不同文件，提取到当前文件末尾
        """
        content_parts = []
        
        # 收集所有元素
        all_elements = list(soup.descendants)
        
        # 找到起始元素的位置
        try:
            start_idx = all_elements.index(start_elem)
        except ValueError:
            return str(start_elem)
        
        # 获取当前章节的层级
        current_level = toc[toc_index].get('level', 2) if toc_index < len(toc) else 2
        
        # 查找下一个同级或更高级别章节的锚点（只在同一文件内）
        stop_anchor = None
        if toc_index + 1 < len(toc):
            for next_idx in range(toc_index + 1, len(toc)):
                next_item = toc[next_idx]
                next_href = next_item['href']
                next_level = next_item.get('level', 2)
                next_file = next_href.split('#')[0] if '#' in next_href else next_href
                
                # 只检查同一文件内的章节
                if current_file and next_file != current_file:
                    continue
                
                # 找到同级或更高级别的章节
                if next_level <= current_level:
                    if '#' in next_href:
                        _, stop_anchor = next_href.split('#', 1)
                    break
        
        # 收集内容直到停止锚点
        for elem in all_elements[start_idx:]:
            # 跳过字符串节点
            if not hasattr(elem, 'name') or not elem.name:
                continue
            
            # 检查是否到达停止锚点
            if stop_anchor and elem.get('id') == stop_anchor:
                break
            
            content_parts.append(str(elem))
        
        return '\n'.join(content_parts) if content_parts else str(start_elem)
    
    def _create_chapter_from_content(self, index: int, title: str, level: int, 
                                     content: str) -> Chapter:
        """从HTML内容创建章节"""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(content, 'html.parser')
        
        # 提取所有文本内容
        text = soup.get_text(separator='\n', strip=True)
        
        # 检查是否有隐藏的h1/h2标签，优先使用其title属性
        # 这用于处理class="hidden"的标题标签
        enhanced_title = self._extract_hidden_title(soup, title)
        
        # 创建内容块 - 保持原有结构
        content_blocks = self._extract_content_blocks(soup)
        
        # 计算字数（中文字符 + 英文单词）
        word_count = self._count_words(text)
        
        return Chapter(
            index=index,
            title=enhanced_title,
            level=level,
            content_blocks=content_blocks,
            word_count=word_count
        )
    
    def _extract_hidden_title(self, soup, default_title: str) -> str:
        """
        提取章节标题（处理h1/h2标签）
        
        优先级：
        1. 优先使用h1/h2标签的文本内容（如果存在且不为空）
        2. 否则使用title属性（支持class="hidden"的h1/h2）
        3. 最后使用默认标题（目录标题）
        """
        # 查找h1/h2标签
        for tag_name in ['h1', 'h2']:
            elem = soup.find(tag_name)
            if elem:
                # 优先使用标签文本（如果存在且不为空）
                text_content = elem.get_text(strip=True)
                if text_content:
                    return text_content
                
                # 否则使用title属性
                title_attr = elem.get('title')
                if title_attr and title_attr.strip():
                    return title_attr.strip()
        
        # 返回默认标题
        return default_title
    
    def _extract_content_blocks(self, soup) -> List[ContentBlock]:
        """提取内容块，保持HTML结构"""
        blocks = []
        
        for elem in soup.descendants:
            if not hasattr(elem, 'name') or not elem.name:
                continue
            
            block_type = self._get_block_type(elem)
            if block_type:
                text = elem.get_text(strip=True)
                if text:
                    style = self._extract_style(elem)
                    blocks.append(ContentBlock(
                        type=block_type,
                        text=text,
                        style=style
                    ))
        
        return blocks
    
    def _get_block_type(self, elem) -> Optional[ContentType]:
        """根据HTML标签判断内容块类型"""
        tag = elem.name.lower()
        
        if tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            return ContentType.HEADING
        elif tag == 'p':
            return ContentType.PARAGRAPH
        elif tag in ['ul', 'ol']:
            return ContentType.LIST
        elif tag == 'blockquote':
            return ContentType.QUOTE
        elif tag == 'pre' or tag == 'code':
            return ContentType.CODE
        elif tag == 'table':
            return ContentType.TABLE
        elif tag == 'img':
            return ContentType.IMAGE
        
        return None
    
    def _extract_style(self, elem) -> TextStyle:
        """提取文本样式"""
        style = TextStyle()
        
        # 检查标签类型
        tag = elem.name.lower()
        if tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            style.heading_level = int(tag[1])
        
        # 检查样式类
        class_list = elem.get('class', [])
        if isinstance(class_list, str):
            class_list = class_list.split()
        
        # 检查粗体
        if tag in ['strong', 'b'] or 'bold' in class_list:
            style.bold = True
        
        # 检查斜体
        if tag in ['em', 'i'] or 'italic' in class_list:
            style.italic = True
        
        return style
    
    def _count_words(self, text: str) -> int:
        """计算字数"""
        if not text:
            return 0
        
        # 中文字符计数
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        # 英文单词计数
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        
        return chinese_chars + english_words
    
    def _validate_chapter_extraction(self, chapters: List[Chapter], file_contents: Dict[str, str]) -> bool:
        """
        验证章节提取是否成功
        
        检查指标：
        1. 章节数是否过少（少于文件中h1/h2标签数的50%）
        2. 总内容字数是否过少（少于所有文件总文本的30%）
        3. 是否存在大量空章节
        
        返回: True 如果提取看起来正常，False 如果可能有问题
        """
        from bs4 import BeautifulSoup
        
        if not chapters:
            return False
        
        # 统计文件中的h1/h2标签数
        total_headings = 0
        total_text_length = 0
        
        for content in file_contents.values():
            soup = BeautifulSoup(content, 'html.parser')
            # 移除脚本和样式
            for script in soup(["script", "style"]):
                script.decompose()
            
            # 统计h1/h2标签
            h1_count = len(soup.find_all('h1'))
            h2_count = len(soup.find_all('h2'))
            total_headings += h1_count + h2_count
            
            # 统计总文本长度
            text = soup.get_text(strip=True)
            total_text_length += len(text)
        
        # 检查1：章节数是否过少
        extracted_chapters = len(chapters)
        if total_headings > 0 and extracted_chapters < total_headings * 0.5:
            print(f"章节数过少: 提取了{extracted_chapters}章，但检测到{total_headings}个h1/h2标签")
            return False
        
        # 检查2：总字数是否过少
        extracted_words = sum(c.word_count for c in chapters)
        if total_text_length > 0 and extracted_words < total_text_length * 0.3:
            print(f"内容字数过少: 提取了{extracted_words}字，但文件总文本约{total_text_length}字")
            return False
        
        # 检查3：空章节比例
        empty_chapters = sum(1 for c in chapters if c.word_count < 10)
        if len(chapters) > 0 and empty_chapters / len(chapters) > 0.3:
            print(f"空章节过多: {empty_chapters}/{len(chapters)}章内容少于10字")
            return False
        
        return True
    
    def _extract_from_html_tags(self, file_contents: Dict[str, str]) -> List[Chapter]:
        """
        基于HTML标签(h1/h2)提取章节
        
        统一层级规则（h1和h2为同级章节）：
        - h1和h2都作为一级章节边界
        - 每个章节包含从当前h1/h2到下一个h1/h2之前的内容
        """
        from bs4 import BeautifulSoup
        
        chapters = []
        chapter_index = 0
        
        for file_path, content in file_contents.items():
            soup = BeautifulSoup(content, 'html.parser')
            
            # 移除脚本和样式
            for script in soup(["script", "style"]):
                script.decompose()
            
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
                # 没有h1/h2，将整个文件作为一个章节
                body = soup.find('body')
                if body:
                    chapter = self._create_chapter_from_content(
                        chapter_index, file_path, 1, str(body)
                    )
                    if chapter.word_count > 0:
                        chapters.append(chapter)
                        chapter_index += 1
                continue
            
            # 处理每个h1/h2作为同级章节
            for idx, (start_pos, elem, tag_name) in enumerate(chapter_positions):
                # 提取章节标题：优先使用标签文本，否则使用title属性
                title = self._extract_chapter_title_from_elem(elem)
                if not title:
                    continue
                
                # 确定这个章节的内容范围（到下一个h1/h2之前）
                if idx + 1 < len(chapter_positions):
                    end_pos = chapter_positions[idx + 1][0]
                else:
                    end_pos = len(all_elements)
                
                # 提取章节内容
                content_parts = []
                for e in all_elements[start_pos:end_pos]:
                    if hasattr(e, 'name') and e.name:
                        content_parts.append(str(e))
                
                chapter_content = '\n'.join(content_parts)
                
                # 检查是否有正文内容（不只是标题）
                temp_soup = BeautifulSoup(chapter_content, 'html.parser')
                text = temp_soup.get_text(strip=True)
                
                # 移除标题后检查剩余内容
                title_len = len(title)
                remaining_text = text[title_len:].strip()
                
                # 过滤规则：中文字符≤3或英文单词<5
                chinese_chars = len(__import__('re').findall(r'[\u4e00-\u9fff]', remaining_text))
                english_words = len(__import__('re').findall(r'[a-zA-Z]+', remaining_text))
                
                if chinese_chars <= 3 and english_words < 5:
                    # 没有正文内容，跳过此章节标签
                    continue
                
                # 创建章节（h1和h2同级，都使用level=1）
                chapter = self._create_chapter_from_content(
                    chapter_index, title, 1, chapter_content
                )
                
                if chapter.word_count > 0:
                    chapters.append(chapter)
                    chapter_index += 1
        
        return chapters
    
    def _extract_chapter_title_from_elem(self, elem) -> str:
        """从h1/h2元素提取章节标题"""
        # 优先使用标签文本
        text_content = elem.get_text(strip=True)
        if text_content:
            return text_content
        
        # 否则使用title属性
        title_attr = elem.get('title')
        if title_attr and title_attr.strip():
            return title_attr.strip()
        
        return None
    
    def _fallback_to_html_analysis(self, file_contents: Dict[str, str]) -> List[Chapter]:
        """当目录不可用时，回退到HTML标签分析"""
        from bs4 import BeautifulSoup
        
        chapters = []
        chapter_index = 0
        
        for file_path, content in file_contents.items():
            soup = BeautifulSoup(content, 'html.parser')
            
            # 移除脚本和样式
            for script in soup(["script", "style"]):
                script.decompose()
            
            # 查找所有h1标签作为一级章节
            h1_elements = soup.find_all('h1')
            
            for h1 in h1_elements:
                title = h1.get_text(strip=True)
                if not title:
                    continue
                
                # 提取从h1开始到下一个h1之前的内容
                chapter_content = self._extract_until_next_heading(h1, soup, 'h1')
                
                chapter = self._create_chapter_from_content(
                    chapter_index, title, 1, chapter_content
                )
                
                if chapter.word_count > 0:
                    chapters.append(chapter)
                    chapter_index += 1
        
        return chapters
    
    def _extract_until_next_heading(self, start_elem, soup, heading_tag: str) -> str:
        """提取从起始元素到下一个同级标题之前的内容"""
        content_parts = []
        
        all_elements = list(soup.descendants)
        
        try:
            start_idx = all_elements.index(start_elem)
        except ValueError:
            return str(start_elem)
        
        for elem in all_elements[start_idx:]:
            if not hasattr(elem, 'name') or not elem.name:
                continue
            
            # 如果遇到下一个同级标题，停止
            if elem.name.lower() == heading_tag and elem != start_elem:
                break
            
            content_parts.append(str(elem))
        
        return '\n'.join(content_parts) if content_parts else str(start_elem)
    
    def _create_empty_doc(self, file_info: dict) -> Document:
        """创建空文档"""
        return Document(
            file_path=file_info["path"],
            file_name=file_info["name"],
            file_format="epub",
            title="",
            author="",
            chapters=[],
            total_chapters=0,
            total_words=0
        )
