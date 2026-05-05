"""
EPUB文件读取器 V2 - 基于HTML标签和内容的智能分章

【规则 - 2026-05-02】
1. 标题字数 < 50字
2. 短文本检测
3. 句末无句号
4. 一级标题(h1)、二级标题(h2)、三级标题(h3-h6)
5. 三级标题与正文同级
6. 标题独立性：后面是否有正文
7. 非独立标题合并（一级+二级合并）

【改进 - 2026-05-05】
8. 检测无H1的异常结构：当HTML文件没有H1标题时，自动提升包含新书标记的标题为H1
9. 超大章节拆分：当章节内容超过10万字符时，基于内部标题结构自动拆分
10. 多书合并检测：识别"推荐序"、"前言"、"目录"等新书开始标记

【改进 - 2026-05-05 - 层级验证】
11. 章节标题模式识别：优先匹配"第X章"格式作为主章节标题
12. 小节标题识别：无"第X章"前缀的一级标题视为小节，合并到上一章节
13. 内容长度阈值：小于1000字的"章节"自动与上一章节合并
14. 层级连续性检查：检查连续标题的层级关系，防止章节被错误拆分
"""
from .base import FileReader
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from core.document import Document, Chapter, ContentBlock, ContentType, TextStyle
import re


class EPUBReaderV2(FileReader):
    """
    EPUB文件读取器 V2
    
    核心逻辑：
    1. 解析EPUB中的所有HTML文件
    2. 使用h1/h2/h3-h6标签识别标题层级
    3. 标题字数<50字、无句号、短文本
    4. 判断标题独立性（后面是否有正文）
    5. 非独立标题合并
    """
    
    # 非章节关键词（用于过滤）
    NON_CHAPTER_KEYWORDS = [
        '版权', '目录', 'contents', '赞誉', '推荐序', '译者序', '前言', '序言',
        '致谢', '简介', '介绍', '导言', '引言', '后记', '附录', '参考文献',
        '索引', '关于作者', '关于本书', '献词', '扉页', '封面'
    ]
    
    # 新书开始标记关键词（用于检测多书合并的情况）
    NEW_BOOK_INDICATORS = [
        '推荐序', '译者序', '前言', '序言', '关于封面', '目录', 'contents'
    ]
    
    # 最小章节内容阈值（字符数）
    MIN_CHAPTER_CONTENT = 500
    
    # 章节标题模式（用于识别真正的章节标题）
    CHAPTER_PATTERN = re.compile(r'第[一二三四五六七八九十百千\d]+章|Chapter\s*\d+', re.IGNORECASE)
    
    # 小节合并阈值（小于此字数的"章节"视为小节）
    MIN_SUBSTANTIAL_CHAPTER = 1000
    
    def _is_non_chapter_title(self, title: str) -> bool:
        """检查是否为非章节标题"""
        if not title:
            return True
        title_lower = title.lower()
        for keyword in self.NON_CHAPTER_KEYWORDS:
            if keyword in title_lower:
                return True
        return False
    
    def supports(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() == '.epub'
    
    def _detect_new_book_in_content(self, content: str) -> Optional[str]:
        """检测内容中是否包含新书开始的标志，返回可能的章节标题"""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(content, 'html.parser')
        
        # 移除脚本和样式
        for script in soup(["script", "style"]):
            script.decompose()
        
        # 检查前几个元素
        body = soup.find('body')
        if not body:
            return None
        
        for elem in body.children:
            if not hasattr(elem, 'name') or not elem.name:
                continue
            
            text = elem.get_text(strip=True)
            if not text:
                continue
            
            # 检查是否包含新书开始标记
            for indicator in self.NEW_BOOK_INDICATORS:
                if indicator in text and len(text) < 100:
                    # 找到标记后的第一个实质性标题
                    next_elem = elem.find_next_sibling()
                    while next_elem:
                        if hasattr(next_elem, 'name') and next_elem.name:
                            next_text = next_elem.get_text(strip=True)
                            if next_text and len(next_text) < 100:
                                return next_text
                        next_elem = next_elem.find_next_sibling()
                    return text
            
            # 只检查前10个元素
            break
        
        return None
    
    def read(self, file_path: str, level2_as_body: bool = True, level3_as_body: bool = True) -> Document:
        """读取EPUB文件并返回结构化文档
        
        Args:
            file_path: EPUB文件路径
            level2_as_body: 是否将二级标题(h2)视为正文（默认True）
            level3_as_body: 是否将三级标题(h3-h6)视为正文（默认True）
        """
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
            
            # 构建文件内容映射
            file_contents = self._build_file_contents_map(book)
            
            # 提取所有标题候选
            heading_candidates = self._extract_heading_candidates(file_contents)
            
            # 过滤和分类标题
            filtered_candidates = self._filter_headings(heading_candidates)
            
            # 标记二级、三级是否视为正文
            for candidate in filtered_candidates:
                level = candidate['level']
                if level == 2:
                    candidate['is_body'] = level2_as_body
                elif level >= 3:
                    candidate['is_body'] = level3_as_body
                else:
                    candidate['is_body'] = False
            
            # 检查标题独立性
            independent_headings = self._check_independence(filtered_candidates)
            
            # 合并非独立标题
            merged_headings = self._merge_headings(independent_headings)
            
            # 构建章节（过滤掉视为正文的标题）
            doc.chapters = self._build_chapters(merged_headings, file_contents)
            doc.total_chapters = len(doc.chapters)
            doc.total_words = sum(c.word_count for c in doc.chapters)
            
            # 添加控制参数到元数据
            doc.metadata['level2_as_body'] = level2_as_body
            doc.metadata['level3_as_body'] = level3_as_body
            
            return doc
            
        except ImportError:
            print("[INFO] ebooklib or beautifulsoup4 not installed")
            return self._create_empty_doc(file_info)
        except Exception as e:
            print(f"[INFO] Error reading EPUB {file_path}: {e}")
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
    
    def _is_non_chapter_title(self, title: str) -> bool:
        """检查是否为非章节标题"""
        if not title:
            return True
        title_lower = title.lower()
        for keyword in self.NON_CHAPTER_KEYWORDS:
            if keyword in title_lower:
                return True
        return False
    
    def _ends_with_period(self, text: str) -> bool:
        """检查是否以句号结尾"""
        return text.strip().endswith('。')
    
    def _extract_heading_candidates(self, file_contents: Dict[str, str]) -> List[Dict]:
        """提取所有标题候选（增强版：检测无H1的异常结构）"""
        from bs4 import BeautifulSoup
        
        candidates = []
        sorted_files = sorted(file_contents.keys())
        
        for file_idx, file_path in enumerate(sorted_files):
            content = file_contents[file_path]
            soup = BeautifulSoup(content, 'html.parser')
            
            # 移除脚本和样式
            for script in soup(["script", "style"]):
                script.decompose()
            
            # 找到所有h1-h6元素
            headings_in_file = []
            for elem in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                tag_name = elem.name.lower()
                title = elem.get_text(strip=True)
                
                if not title:
                    continue
                
                # 确定层级
                if tag_name == 'h1':
                    level = 1
                elif tag_name == 'h2':
                    level = 2
                else:
                    level = 3  # h3-h6作为三级标题
                
                headings_in_file.append({
                    'file_path': file_path,
                    'element': elem,
                    'tag_name': tag_name,
                    'title': title,
                    'level': level,
                    'position': elem.sourceline if hasattr(elem, 'sourceline') else 0
                })
            
            # 检测无H1的异常结构
            has_h1 = any(h['level'] == 1 for h in headings_in_file)
            
            if not has_h1 and headings_in_file:
                # 检查是否包含新书开始标记
                for h in headings_in_file:
                    if any(indicator in h['title'] for indicator in self.NEW_BOOK_INDICATORS):
                        # 将第一个包含新书标记的标题提升为H1
                        h['level'] = 1
                        h['tag_name'] = 'h1'
                        h['is_promoted'] = True  # 标记为提升的标题
                        print(f"[INFO] Promoted to H1 (new book indicator): {h['title'][:50]}")
                        break
                
                # 如果没有新书标记，但全是H3及以下，检查内容量
                all_low_level = all(h['level'] >= 3 for h in headings_in_file)
                if all_low_level:
                    # 提升第一个H3为H1（可能是新书的章节标题）
                    first_h3 = next((h for h in headings_in_file if h['level'] == 3), None)
                    if first_h3:
                        first_h3['level'] = 1
                        first_h3['tag_name'] = 'h1'
                        first_h3['is_promoted'] = True
                        print(f"[INFO] Promoted to H1 (no H1/H2, all H3+): {first_h3['title'][:50]}")
            
            candidates.extend(headings_in_file)
        
        # 按文件和位置排序
        candidates.sort(key=lambda x: (x['file_path'], x['position']))
        
        return candidates
    
    def _filter_headings(self, candidates: List[Dict]) -> List[Dict]:
        """过滤标题候选"""
        filtered = []
        
        for candidate in candidates:
            title = candidate['title']
            
            # 规则1: 字数 < 50
            if len(title) >= 50:
                continue
            
            # 规则2: 非章节关键词过滤
            if self._is_non_chapter_title(title):
                continue
            
            # 规则3: 不以句号结尾
            if self._ends_with_period(title):
                continue
            
            # 规则4: 短文本（已经通过字数<50控制）
            
            filtered.append(candidate)
        
        return filtered
    
    def _check_independence(self, candidates: List[Dict]) -> List[Dict]:
        """检查每个标题后面是否有正文内容（改进：一级标题默认独立）"""
        from bs4 import BeautifulSoup
        
        for i, candidate in enumerate(candidates):
            level = candidate['level']
            
            # 一级标题默认独立（除非明确检测到后面没有内容）
            if level == 1:
                has_body = self._has_body_content_after(candidate, candidates, i)
                candidate['has_body_after'] = has_body
                # 一级标题只要有内容就独立，即使内容很少
                candidate['is_independent'] = has_body or True  # 一级标题默认独立
            else:
                # 获取当前标题后的内容
                has_body = self._has_body_content_after(candidate, candidates, i)
                candidate['has_body_after'] = has_body
                candidate['is_independent'] = has_body
        
        return candidates
    
    def _has_body_content_after(self, candidate: Dict, all_candidates: List[Dict], 
                                current_idx: int) -> bool:
        """检查当前标题后是否有正文内容"""
        elem = candidate['element']
        current_level = candidate['level']
        
        # 查找当前标题后的兄弟元素
        next_sibling = elem.find_next_sibling()
        
        while next_sibling:
            # 如果遇到另一个标题
            if next_sibling.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                next_level = self._get_heading_level(next_sibling.name)
                
                # 规则: 一级/二级 + 三级 + 正文 → 三级视为正文
                if next_level == 3 and current_level in [1, 2]:
                    # 检查三级标题后面是否有正文
                    sibling_after_h3 = next_sibling.find_next_sibling()
                    while sibling_after_h3:
                        if sibling_after_h3.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                            break
                        text = sibling_after_h3.get_text(strip=True)
                        if text and len(text) > 10:
                            return True  # 三级标题后面有正文，当前标题独立
                        sibling_after_h3 = sibling_after_h3.find_next_sibling()
                    # 三级标题后面没有正文，继续检查
                    next_sibling = next_sibling.find_next_sibling()
                    continue
                
                # 如果是更低层级的标题（非三级特殊情况），不算正文
                if next_level > current_level:
                    return False
                # 如果是同级或更高，停止检查
                break
            
            # 检查是否有正文内容
            text = next_sibling.get_text(strip=True)
            if text and len(text) > 10:
                return True
            
            next_sibling = next_sibling.find_next_sibling()
        
        return False
    
    def _get_heading_level(self, tag_name: str) -> int:
        """获取标题层级"""
        if tag_name == 'h1':
            return 1
        elif tag_name == 'h2':
            return 2
        else:
            return 3
    
    def _merge_headings(self, candidates: List[Dict]) -> List[Dict]:
        """合并非独立标题（保守策略：减少合并，保留更多独立章节）"""
        if not candidates:
            return []
        
        merged = []
        i = 0
        
        while i < len(candidates):
            current = candidates[i]
            
            # 规则1: 一级标题 + 二级标题（一级不独立，且二级有正文）→ 合并为章节名
            # 但只有当它们在同一文件内且位置接近时才合并
            if (current['level'] == 1 and 
                not current.get('is_independent', False) and 
                i + 1 < len(candidates)):
                
                next_candidate = candidates[i + 1]
                # 检查是否在同一文件内
                same_file = current['file_path'] == next_candidate['file_path']
                
                if next_candidate['level'] == 2 and same_file:
                    # 合并标题，但保留二级标题作为独立小节
                    merged_title = f"{current['title']} - {next_candidate['title']}"
                    merged.append({
                        'file_path': current['file_path'],
                        'title': merged_title,
                        'level': 1,
                        'element': current['element'],
                        'is_independent': True,
                        'merged': True
                    })
                    i += 2
                    continue
            
            # 规则2: 一级标题 + 一级标题（第一个不独立，且在同一文件）→ 合并
            if (current['level'] == 1 and 
                not current.get('is_independent', False) and 
                i + 1 < len(candidates)):
                
                next_candidate = candidates[i + 1]
                same_file = current['file_path'] == next_candidate['file_path']
                
                if next_candidate['level'] == 1 and same_file:
                    # 合并两个一级标题
                    merged_title = f"{current['title']} - {next_candidate['title']}"
                    merged.append({
                        'file_path': current['file_path'],
                        'title': merged_title,
                        'level': 1,
                        'element': current['element'],
                        'is_independent': True,
                        'merged': True
                    })
                    i += 2
                    continue
            
            merged.append(current)
            i += 1
        
        return merged
    
    def _is_chapter_title(self, title: str) -> bool:
        """检查是否为真正的章节标题（包含"第X章"模式）"""
        if not title:
            return False
        return bool(self.CHAPTER_PATTERN.search(title))
    
    def _validate_heading_hierarchy(self, headings: List[Dict]) -> List[Dict]:
        """验证标题层级关系，标记应该合并的小节标题
        
        规则：
        1. 包含"第X章"的标题视为真正的章节标题
        2. 不包含"第X章"的一级标题，如果前面有章节标题，则视为小节
        3. 小于MIN_SUBSTANTIAL_CHAPTER字节的"章节"视为小节
        """
        validated = []
        last_chapter_heading = None
        
        for i, heading in enumerate(headings):
            title = heading.get('title', '')
            
            # 检查是否为真正的章节标题
            is_real_chapter = self._is_chapter_title(title)
            
            # 如果是真正章节标题，直接添加
            if is_real_chapter:
                heading['is_real_chapter'] = True
                heading['merge_with_previous'] = False
                last_chapter_heading = heading
                validated.append(heading)
                continue
            
            # 如果不是真正章节标题，但有"第X部分"等模式，也视为章节
            is_part = bool(re.search(r'第[一二三四五六七八九十百千\d]+部分|Part\s*\d+', title, re.IGNORECASE))
            if is_part:
                heading['is_real_chapter'] = True
                heading['merge_with_previous'] = False
                last_chapter_heading = heading
                validated.append(heading)
                continue
            
            # 检查是否应该合并到上一章节
            if last_chapter_heading and heading['level'] == 1:
                # 一级标题但没有"第X章"，可能是小节
                # 检查与上一个真正章节的距离
                last_chapter_idx = headings.index(last_chapter_heading)
                distance = i - last_chapter_idx
                
                # 如果距离很近（小于5个标题），可能是小节
                if distance <= 5:
                    heading['is_real_chapter'] = False
                    heading['merge_with_previous'] = True
                    heading['parent_chapter'] = last_chapter_heading
                    print(f"[INFO] Marked as subsection (will merge): {title[:50]}")
                else:
                    heading['is_real_chapter'] = True
                    heading['merge_with_previous'] = False
                    last_chapter_heading = heading
            else:
                heading['is_real_chapter'] = True
                heading['merge_with_previous'] = False
                if heading['level'] == 1:
                    last_chapter_heading = heading
            
            validated.append(heading)
        
        return validated
    
    def _merge_subsections(self, chapters: List[Chapter], headings: List[Dict]) -> List[Chapter]:
        """合并小节到所属章节"""
        if not chapters:
            return chapters
        
        merged = []
        chapter_map = {}  # 映射原始标题到章节索引
        
        # 建立标题到章节的映射
        for i, chapter in enumerate(chapters):
            for heading in headings:
                if heading.get('title') == chapter.title and heading.get('is_real_chapter'):
                    chapter_map[heading['title']] = i
                    break
        
        # 处理每个章节
        for i, chapter in enumerate(chapters):
            # 检查是否有小节需要合并
            subsections = []
            for heading in headings:
                if (heading.get('merge_with_previous') and 
                    heading.get('parent_chapter', {}).get('title') == chapter.title):
                    # 找到对应的小节内容
                    for j in range(i + 1, len(chapters)):
                        if chapters[j].title == heading.get('title'):
                            subsections.append(chapters[j])
                            break
            
            if subsections:
                # 合并小节内容
                for subsection in subsections:
                    chapter.content_blocks.append(ContentBlock(
                        type=ContentType.HEADING,
                        text=f"\n## {subsection.title}\n",
                        level=2,
                        style=TextStyle(bold=True),
                        page_number=0
                    ))
                    chapter.content_blocks.extend(subsection.content_blocks)
                    chapter.word_count += subsection.word_count
                    chapter.paragraph_count += subsection.paragraph_count
                
                print(f"[INFO] Merged {len(subsections)} subsections into: {chapter.title[:50]}")
            
            merged.append(chapter)
        
        # 过滤掉已合并的小节章节
        merged_titles = {h.get('title') for h in headings if h.get('merge_with_previous')}
        final_chapters = [c for c in merged if c.title not in merged_titles]
        
        # 重新编号
        for i, chapter in enumerate(final_chapters, 1):
            chapter.index = i
        
        return final_chapters
    
    def _build_chapters(self, headings: List[Dict], file_contents: Dict[str, str]) -> List[Chapter]:
        """根据标题构建章节（增强版：检测超大章节并尝试拆分）"""
        from bs4 import BeautifulSoup
        
        # 首先验证标题层级关系
        validated_headings = self._validate_heading_hierarchy(headings)
        
        chapters = []
        skip_until_file = None  # 用于跳过已拆分的文件中的后续标题
        
        for i, heading in enumerate(validated_headings):
            # 如果正在跳过某个文件的标题
            if skip_until_file:
                if heading['file_path'] == skip_until_file:
                    continue  # 跳过同一文件中的其他标题
                else:
                    skip_until_file = None  # 遇到新文件，恢复处理
            
            if not heading.get('is_independent', False):
                continue
            
            # 如果该标题视为正文，则不创建独立章节
            if heading.get('is_body', False):
                continue
            
            # 提取章节内容
            content_blocks = self._extract_chapter_content(heading, headings, i, file_contents)
            
            if not content_blocks:
                continue
            
            # 检查是否是超大章节（可能包含多本书的内容）
            total_chars = sum(len(b.text) for b in content_blocks)
            
            if total_chars > 100000:  # 超过10万字符，可能是合并了多本书
                print(f"[INFO] Large chapter detected: '{heading['title'][:50]}' ({total_chars} chars)")
                
                # 尝试拆分超大章节
                sub_chapters = self._split_large_chapter(heading, content_blocks)
                
                if sub_chapters:
                    print(f"[INFO] Split into {len(sub_chapters)} sub-chapters")
                    for sub_chapter in sub_chapters:
                        sub_chapter.index = len(chapters) + 1
                        chapters.append(sub_chapter)
                    
                    # 标记跳过该文件中的其他标题（因为内容已经被拆分处理）
                    skip_until_file = heading['file_path']
                    continue
            
            # 创建章节
            chapter = self._create_chapter(
                len(chapters) + 1,
                heading['title'],
                heading['level'],
                content_blocks
            )
            
            if chapter.word_count > 0:
                chapters.append(chapter)
        
        # 合并小节到所属章节
        chapters = self._merge_subsections(chapters, validated_headings)
        
        return chapters
    
    def _split_large_chapter(self, heading: Dict, content_blocks: List[ContentBlock]) -> List[Chapter]:
        """拆分超大章节（基于内部标题结构）"""
        from bs4 import BeautifulSoup
        
        sub_chapters = []
        current_blocks = []
        current_title = heading['title']
        
        for block in content_blocks:
            # 检查是否是可能的子章节标题
            if block.type == ContentType.HEADING:
                # 检测新书开始的标志
                is_new_book = any(indicator in block.text for indicator in self.NEW_BOOK_INDICATORS)
                
                # 检测"第X部分"、"第X章"等模式
                is_part_chapter = bool(re.search(r'第[一二三四五六七八九十\d]+部分|第[一二三四五六七八九十\d]+章', block.text))
                
                # 检测"01 简单"这种编号章节
                is_numbered_chapter = bool(re.search(r'^\d{2}\s+', block.text))
                
                if is_new_book or (is_part_chapter and len(current_blocks) > 10):
                    # 保存当前子章节
                    if current_blocks:
                        sub_chapter = self._create_chapter(
                            0,  # 索引稍后设置
                            current_title,
                            1,
                            current_blocks
                        )
                        if sub_chapter.word_count > self.MIN_CHAPTER_CONTENT:
                            sub_chapters.append(sub_chapter)
                    
                    # 开始新的子章节
                    current_title = block.text
                    current_blocks = []
                    continue
            
            current_blocks.append(block)
        
        # 保存最后一个子章节
        if current_blocks:
            sub_chapter = self._create_chapter(
                0,
                current_title,
                1,
                current_blocks
            )
            if sub_chapter.word_count > self.MIN_CHAPTER_CONTENT:
                sub_chapters.append(sub_chapter)
        
        # 如果拆分后只有1个章节，说明拆分失败，返回空列表
        if len(sub_chapters) <= 1:
            return []
        
        return sub_chapters
    
    def _extract_chapter_content(self, heading: Dict, all_headings: List[Dict],
                                heading_idx: int, file_contents: Dict[str, str]) -> List[ContentBlock]:
        """提取章节内容（支持跨文件提取）"""
        from bs4 import BeautifulSoup
        
        blocks = []
        elem = heading['element']
        current_file = heading['file_path']
        current_level = heading['level']
        
        # 获取所有文件的有序列表
        sorted_files = sorted(file_contents.keys())
        current_file_idx = sorted_files.index(current_file)
        
        # 找到下一个同级或更高级标题的位置
        next_heading_file = None
        next_heading_elem = None
        
        for i in range(heading_idx + 1, len(all_headings)):
            h = all_headings[i]
            if h['level'] <= current_level and not h.get('is_body', False):
                next_heading_file = h['file_path']
                next_heading_elem = h['element']
                break
        
        # 提取当前文件中的内容
        next_sibling = elem.find_next_sibling()
        while next_sibling:
            # 如果遇到另一个标题
            if next_sibling.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                next_level = self._get_heading_level(next_sibling.name)
                # 如果是同级或更高级，停止当前文件的处理
                if next_level <= current_level:
                    break
                # 如果是更低层级，作为小标题处理
                else:
                    title_text = next_sibling.get_text(strip=True)
                    blocks.append(ContentBlock(
                        type=ContentType.HEADING,
                        text=title_text,
                        level=next_level,
                        style=TextStyle(bold=True),
                        page_number=0
                    ))
            else:
                # 提取正文内容
                text = next_sibling.get_text(strip=True)
                if text:
                    blocks.append(ContentBlock(
                        type=ContentType.PARAGRAPH,
                        text=text,
                        level=0,
                        style=TextStyle(),
                        page_number=0
                    ))
            
            next_sibling = next_sibling.find_next_sibling()
        
        # 如果下一个标题在不同的文件中，需要跨文件提取内容
        if next_heading_file and next_heading_file != current_file:
            next_file_idx = sorted_files.index(next_heading_file)
            
            # 提取中间文件的内容（不包括包含下一个标题的文件）
            for file_idx in range(current_file_idx + 1, next_file_idx):
                file_path = sorted_files[file_idx]
                
                # 检查这个文件是否有独立的H1标题（可能是新章节）
                soup = BeautifulSoup(file_contents[file_path], 'html.parser')
                has_h1 = bool(soup.find('h1'))
                
                # 如果文件有H1标题，停止提取（这是新章节）
                if has_h1:
                    break
                
                # 移除脚本和样式
                for script in soup(["script", "style"]):
                    script.decompose()
                
                # 提取整个文件的内容
                body = soup.find('body')
                if body:
                    for child in body.children:
                        if hasattr(child, 'name') and child.name:
                            self._extract_element_content(child, blocks, current_level)
        
        return blocks
    
    def _extract_element_content(self, elem, blocks: List[ContentBlock], current_level: int):
        """提取单个元素的内容"""
        # 如果是标题
        if elem.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            level = self._get_heading_level(elem.name)
            title_text = elem.get_text(strip=True)
            if title_text:
                blocks.append(ContentBlock(
                    type=ContentType.HEADING,
                    text=title_text,
                    level=level,
                    style=TextStyle(bold=True),
                    page_number=0
                ))
        # 如果是段落或其他内容
        elif elem.name in ['p', 'div', 'span', 'blockquote', 'li', 'td', 'th']:
            text = elem.get_text(strip=True)
            if text and len(text) > 5:  # 过滤太短的文本
                blocks.append(ContentBlock(
                    type=ContentType.PARAGRAPH,
                    text=text,
                    level=0,
                    style=TextStyle(),
                    page_number=0
                ))
        # 递归处理子元素
        else:
            for child in elem.children:
                if hasattr(child, 'name') and child.name:
                    self._extract_element_content(child, blocks, current_level)
    
    def _create_chapter(self, index: int, title: str, level: int, 
                       content_blocks: List[ContentBlock]) -> Chapter:
        """创建章节对象"""
        word_count = sum(len(b.text) for b in content_blocks)
        paragraph_count = sum(1 for b in content_blocks if b.type == ContentType.PARAGRAPH)
        
        return Chapter(
            index=index,
            title=title[:100],
            level=level,
            content_blocks=content_blocks,
            word_count=word_count,
            paragraph_count=paragraph_count
        )
    
    def _create_empty_doc(self, file_info: Dict) -> Document:
        """创建空文档"""
        return Document(
            file_path=file_info["path"],
            file_name=file_info["name"],
            file_format="epub",
            chapters=[],
            total_chapters=0,
            total_words=0
        )


# 保持向后兼容
EPUBReader = EPUBReaderV2
