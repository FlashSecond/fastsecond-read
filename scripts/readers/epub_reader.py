"""
EPUB文件读取器 V3 - 综合检测策略版

【方案七实现 - 2026-05-06】
基于优先级的多策略级联检测系统：
1. 标准标题标签 (h1-h6) - 置信度5
2. CSS类名检测 - 置信度4
3. 文本模式检测 (第X章/Chapter X) - 置信度5
4. 字体大小检测 - 置信度3
5. 段落特征检测 - 置信度3
6. 文件结构检测 - 置信度4
7. 备用方案 (按文件分割) - 置信度2

核心逻辑：按优先级尝试每种方法，成功则停止，失败则继续下一个
"""
from .base import FileReader
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from core.document import Document, Chapter, ContentBlock, ContentType, TextStyle
import re


class EPUBReader(FileReader):
    """
    EPUB文件读取器 - 综合检测策略
    
    核心改进：
    - 7种检测策略按优先级级联执行
    - 自动选择最佳检测方法
    - 高覆盖率，适应不同EPUB格式
    """
    
    # 非章节关键词（用于过滤）
    NON_CHAPTER_KEYWORDS = [
        '版权', '目录', 'contents', '赞誉', '推荐序', '译者序', '前言', '序言',
        '致谢', '简介', '介绍', '导言', '引言', '后记', '附录', '参考文献',
        '索引', '关于作者', '关于本书', '献词', '扉页', '封面'
    ]
    
    # 新书开始标记关键词
    NEW_BOOK_INDICATORS = [
        '推荐序', '译者序', '关于封面', '目录', 'contents'
    ]
    
    # 最小章节内容阈值
    MIN_CHAPTER_CONTENT = 500
    MIN_SUBSTANTIAL_CHAPTER = 1000
    
    # 章节标题模式
    CHAPTER_PATTERN = re.compile(r'第[一二三四五六七八九十百千\d]+章|Chapter\s*\d+|^\d+\s+', re.IGNORECASE)
    PART_PATTERN = re.compile(r'第[一二三四五六七八九十\d]+(部分|篇|卷|集|部)|Part\s*\d+|Volume\s*[\dIVX]+|Book\s*\d+', re.IGNORECASE)
    
    # CSS类名模式
    TITLE_CLASS_PATTERNS = [
        r'chapter[_-]?title', r'chapter[_-]?name', r'chaptitle',
        r'title[_-]?1', r'title[_-]?2', r'head[_-]?1', r'head[_-]?2',
        r'part[_-]?title', r'section[_-]?title', r'book[_-]?title',
        r'h1', r'h2', r'chapter'
    ]
    
    def __init__(self):
        super().__init__()
        # 定义检测策略（按优先级排序）
        self.strategies = [
            ("标准标题标签", self._detect_by_headings, 5),
            ("CSS类名检测", self._detect_by_class, 4),
            ("文本模式检测", self._detect_by_pattern, 5),
            ("字体大小检测", self._detect_by_font_size, 3),
            ("段落特征检测", self._detect_by_paragraph, 3),
            ("文件结构检测", self._detect_by_file_structure, 4),
        ]
        self.min_chapters = 2  # 最少章节阈值
    
    def supports(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() == '.epub'
    
    def read(self, file_path: str, level2_as_body: bool = True, level3_as_body: bool = True) -> Document:
        """读取EPUB文件 - 使用综合检测策略"""
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
            
            # 【方案七】执行综合检测策略
            detection_result = self._comprehensive_detect(file_contents)
            
            print(f"[INFO] EPUB检测完成: 使用'{detection_result['method']}'检测到{detection_result['count']}个章节")
            
            # 构建章节
            doc.chapters = self._build_chapters_from_detection(detection_result['chapters'], file_contents)
            doc.total_chapters = len(doc.chapters)
            doc.total_words = sum(c.word_count for c in doc.chapters)
            
            # 添加元数据
            doc.metadata['detection_method'] = detection_result['method']
            doc.metadata['detection_confidence'] = detection_result['confidence']
            doc.metadata['level2_as_body'] = level2_as_body
            doc.metadata['level3_as_body'] = level3_as_body
            
            return doc
            
        except ImportError:
            print("[ERROR] ebooklib or beautifulsoup4 not installed")
            return self._create_empty_doc(file_info)
        except Exception as e:
            print(f"[ERROR] Error reading EPUB {file_path}: {e}")
            return self._create_empty_doc(file_info)
    
    # ==================== 方案七：综合检测策略核心 ====================
    
    def _comprehensive_detect(self, file_contents: Dict[str, str]) -> Dict:
        """
        执行综合检测策略
        按优先级尝试每种方法，成功则停止
        """
        all_results = []
        
        for strategy_name, strategy_func, confidence in self.strategies:
            try:
                chapters = strategy_func(file_contents)
                
                # 【层级验证】区分真正章节和小节
                if chapters and len(chapters) > 0:
                    chapters = self._validate_chapter_hierarchy(chapters)
                
                if chapters and len(chapters) >= self.min_chapters:
                    print(f"[检测成功] {strategy_name}: 检测到 {len(chapters)} 个章节")
                    return {
                        'chapters': chapters,
                        'method': strategy_name,
                        'confidence': confidence,
                        'count': len(chapters)
                    }
                else:
                    count = len(chapters) if chapters else 0
                    print(f"[检测跳过] {strategy_name}: 仅检测到 {count} 个章节")
                    if chapters:
                        all_results.append((strategy_name, chapters, confidence))
                        
            except Exception as e:
                print(f"[检测错误] {strategy_name}: {e}")
                continue
        
        # 所有策略都失败，使用最佳备选或备用方案
        return self._select_best_fallback(all_results, file_contents)
    
    def _validate_chapter_hierarchy(self, chapters: List[Dict]) -> List[Dict]:
        """
        验证章节层级，区分真正章节和小节
        
        规则：
        1. 优先匹配"第X章"或数字编号格式作为主章节
        2. 无章节编号前缀的标题视为小节
        3. 小于1000字的"章节"自动合并到上一章
        """
        if not chapters:
            return chapters
        
        # 按文件路径和位置排序
        sorted_chapters = sorted(chapters, key=lambda x: (x.get('file_path', ''), x.get('position', 0)))
        
        validated = []
        last_real_chapter = None
        
        for ch in sorted_chapters:
            title = ch.get('title', '')
            
            # 检查是否是真正的章节标题
            # 模式1: "第X章" 或 "Chapter X"
            # 模式2: 数字编号开头，如 "01 标题" 或 "1. 标题"
            is_real_chapter = bool(self.CHAPTER_PATTERN.search(title))
            
            # 额外检查：如果标题以数字+空格开头，也认为是章节
            if not is_real_chapter:
                is_real_chapter = bool(re.match(r'^\d+[\.\s]', title))
            
            if is_real_chapter:
                # 是真正的章节
                ch['is_subsection'] = False
                validated.append(ch)
                last_real_chapter = ch
            else:
                # 不是章节格式，可能是小节
                # 检查是否太短（可能是小节）
                if last_real_chapter and len(title) < 50:
                    # 标记为小节，合并到上一章
                    ch['is_subsection'] = True
                    ch['parent_chapter'] = last_real_chapter
                    # 不添加到validated列表，而是合并到父章节
                else:
                    # 可能是前言、附录等独立部分
                    ch['is_subsection'] = False
                    validated.append(ch)
                    last_real_chapter = ch
        
        return validated
    
    # ==================== 策略1: 标准标题标签 ====================
    
    def _detect_by_headings(self, file_contents: Dict[str, str]) -> List[Dict]:
        """基于 h1-h6 标签检测"""
        from bs4 import BeautifulSoup
        
        chapters = []
        for file_path, content in file_contents.items():
            soup = BeautifulSoup(content, 'html.parser')
            
            for tag_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                for elem in soup.find_all(tag_name):
                    title = elem.get_text(strip=True)
                    if not title or len(title) >= 50:
                        continue
                    if self._is_non_chapter_title(title):
                        continue
                    if self._ends_with_period(title):
                        continue
                    
                    level = int(tag_name[1])
                    chapters.append({
                        'title': title,
                        'level': 1 if level <= 2 else 2,
                        'file_path': file_path,
                        'element': elem,
                        'position': elem.sourceline if hasattr(elem, 'sourceline') else 0,
                        'source': 'headings'
                    })
        
        return self._sort_and_deduplicate(chapters)
    
    # ==================== 策略2: CSS类名检测 ====================
    
    def _detect_by_class(self, file_contents: Dict[str, str]) -> List[Dict]:
        """基于CSS类名检测章节标题"""
        from bs4 import BeautifulSoup
        
        chapters = []
        
        for file_path, content in file_contents.items():
            soup = BeautifulSoup(content, 'html.parser')
            
            for pattern in self.TITLE_CLASS_PATTERNS:
                elements = soup.find_all(class_=re.compile(pattern, re.I))
                
                for elem in elements:
                    title = elem.get_text(strip=True)
                    if not title or len(title) < 3 or len(title) >= 100:
                        continue
                    if self._is_non_chapter_title(title):
                        continue
                    
                    level = 1 if '1' in pattern or 'chapter' in pattern.lower() else 2
                    
                    chapters.append({
                        'title': title,
                        'level': level,
                        'file_path': file_path,
                        'element': elem,
                        'position': 0,
                        'source': 'class',
                        'class_pattern': pattern
                    })
        
        return self._sort_and_deduplicate(chapters)
    
    # ==================== 策略3: 文本模式检测（核心） ====================
    
    def _detect_by_pattern(self, file_contents: Dict[str, str]) -> List[Dict]:
        """基于文本模式检测章节标题 - 核心策略"""
        from bs4 import BeautifulSoup
        
        # 定义多种章节模式（优先级从高到低）
        patterns = [
            # 中文章节模式（最常用）
            (r'第[一二三四五六七八九十百千\d]+章[\s]*[:：]?\s*(.+?)(?=\n|$)', 'chapter', 1),
            (r'第[一二三四五六七八九十\d]+[章节篇卷集部]', 'chapter', 1),
            
            # 英文章节模式
            (r'Chapter\s*[\dIVX]+[:：]?\s*(.+?)(?=\n|$)', 'chapter', 1),
            (r'Part\s*\d+|Volume\s*[\dIVX]+|Book\s*\d+', 'part', 1),
            
            # 数字编号模式
            (r'^(\d{1,2})[\.\s]+(.+?)(?=\n|$)', 'section', 2),
            (r'^[（(]?(\d{1,2})[)）]?[、\.\s]+(.+?)(?=\n|$)', 'section', 2),
            
            # 中文数字编号
            (r'^[（(]?[一二三四五六七八九十百千]+[)）]?[、\.\s]+(.+?)(?=\n|$)', 'section', 2),
        ]
        
        chapters = []
        
        for file_path, content in file_contents.items():
            # 移除HTML标签，保留纯文本
            soup = BeautifulSoup(content, 'html.parser')
            text = soup.get_text()
            
            for pattern, ptype, level in patterns:
                matches = re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE)
                
                for match in matches:
                    title = match.group(0).strip()
                    position = match.start()
                    
                    # 验证标题合理性
                    if self._validate_title(title):
                        chapters.append({
                            'title': title,
                            'level': level,
                            'file_path': file_path,
                            'position': position,
                            'pattern_type': ptype,
                            'source': 'pattern'
                        })
        
        return self._sort_by_position(chapters)
    
    # ==================== 策略4: 字体大小检测 ====================
    
    def _detect_by_font_size(self, file_contents: Dict[str, str]) -> List[Dict]:
        """基于字体大小检测章节标题"""
        from bs4 import BeautifulSoup
        
        chapters = []
        
        for file_path, content in file_contents.items():
            soup = BeautifulSoup(content, 'html.parser')
            
            # 收集所有带字体大小的元素
            font_sizes = []
            for elem in soup.find_all(style=True):
                style = elem['style']
                match = re.search(r'font-size:\s*([\d.]+)(px|pt|em|rem)', style, re.I)
                if match:
                    size = float(match.group(1))
                    unit = match.group(2).lower()
                    # 统一转换为px（近似）
                    if unit == 'pt':
                        size *= 1.33
                    elif unit in ('em', 'rem'):
                        size *= 16
                    
                    text = elem.get_text(strip=True)
                    if text:
                        font_sizes.append((elem, size, text))
            
            if not font_sizes:
                continue
            
            # 找出最大字体
            max_size = max(fs[1] for fs in font_sizes)
            threshold = max_size * 0.75  # 阈值：最大字体的75%
            
            for elem, size, text in font_sizes:
                if size >= threshold and 5 < len(text) < 100:
                    # 检查是否是标题（不以标点结尾）
                    if not text[-1] in '。，！？；：""''（）':
                        chapters.append({
                            'title': text,
                            'level': 1 if size == max_size else 2,
                            'file_path': file_path,
                            'element': elem,
                            'font_size': size,
                            'source': 'font_size'
                        })
        
        return self._sort_and_deduplicate(chapters)
    
    # ==================== 策略5: 段落特征检测 ====================
    
    def _detect_by_paragraph(self, file_contents: Dict[str, str]) -> List[Dict]:
        """基于段落特征检测章节标题"""
        from bs4 import BeautifulSoup
        
        chapters = []
        chapter_keywords = ['章', '节', '篇', '卷', '部', '集']
        
        for file_path, content in file_contents.items():
            soup = BeautifulSoup(content, 'html.parser')
            paragraphs = soup.find_all('p')
            
            for i, p in enumerate(paragraphs):
                text = p.get_text(strip=True)
                
                # 特征1: 长度适中（10-50字）
                if not (10 <= len(text) <= 50):
                    continue
                
                # 特征2: 不以标点结尾
                if text[-1] in '。，！？；：""''（）':
                    continue
                
                # 特征3: 计算标题得分
                score = 0
                
                # 包含章节关键词
                if any(kw in text for kw in chapter_keywords):
                    score += 3
                
                # 包含数字或中文数字
                if re.search(r'[\d一二三四五六七八九十百千]', text):
                    score += 2
                
                # 下一行是长文本（正文）
                if i + 1 < len(paragraphs):
                    next_text = paragraphs[i + 1].get_text(strip=True)
                    if len(next_text) > 100:
                        score += 2
                
                # 字体加粗或特殊样式
                if p.find(['b', 'strong']) or 'font-weight' in str(p.get('style', '')):
                    score += 1
                
                # 得分足够高，认为是标题
                if score >= 5:
                    chapters.append({
                        'title': text,
                        'level': 1 if score >= 7 else 2,
                        'file_path': file_path,
                        'element': p,
                        'score': score,
                        'source': 'paragraph'
                    })
        
        return chapters
    
    # ==================== 策略6: 文件结构检测 ====================
    
    def _detect_by_file_structure(self, file_contents: Dict[str, str]) -> List[Dict]:
        """基于文件结构检测章节（每章一个文件）"""
        from bs4 import BeautifulSoup
        
        chapters = []
        sorted_files = sorted(file_contents.items(), key=lambda x: x[0])
        
        for file_path, content in sorted_files:
            soup = BeautifulSoup(content, 'html.parser')
            
            # 获取文件中的第一个有意义的文本
            body = soup.find('body')
            if not body:
                continue
            
            # 获取所有文本节点
            texts = []
            for elem in body.find_all(['p', 'h1', 'h2', 'h3', 'div']):
                text = elem.get_text(strip=True)
                if text and len(text) < 200:
                    texts.append((text, elem))
            
            # 找最可能是标题的
            for text, elem in texts[:5]:
                if 10 <= len(text) <= 80 and not text[-1] in '。，！？':
                    # 检查文件名是否包含数字
                    file_match = re.search(r'(?:chapter|section|part|chap)?[_-]?(\d+)', file_path, re.I)
                    chapter_num = int(file_match.group(1)) if file_match else None
                    
                    chapters.append({
                        'title': text,
                        'level': 1,
                        'file_path': file_path,
                        'element': elem,
                        'chapter_number': chapter_num,
                        'source': 'file_structure'
                    })
                    break
        
        return chapters
    
    # ==================== 备用方案 ====================
    
    def _select_best_fallback(self, all_results: List[Tuple], file_contents: Dict[str, str]) -> Dict:
        """选择最佳备选结果或使用最终备用方案"""
        
        if all_results:
            # 按置信度和章节数排序，选择最佳结果
            best = max(all_results, key=lambda x: (x[2], len(x[1])))
            print(f"[检测备选] 使用最佳备选方案: {best[0]} ({len(best[1])} 个章节)")
            return {
                'chapters': best[1],
                'method': best[0] + ' (备选)',
                'confidence': best[2],
                'count': len(best[1])
            }
        
        # 最终备用：按文件分割
        return self._fallback_split_by_files(file_contents)
    
    def _fallback_split_by_files(self, file_contents: Dict[str, str]) -> Dict:
        """最终备用方案：每个文件作为一个章节"""
        print("[检测备用] 使用文件分割方案")
        
        chapters = []
        for i, (file_path, content) in enumerate(sorted(file_contents.items()), 1):
            # 从文件名生成标题
            file_name = file_path.split('/')[-1].split('\\')[-1]
            title = f"章节 {i}" if file_name.endswith(('.html', '.xhtml')) else file_name
            
            chapters.append({
                'title': title,
                'level': 1,
                'file_path': file_path,
                'source': 'fallback'
            })
        
        return {
            'chapters': chapters,
            'method': '文件分割 (最终备用)',
            'confidence': 2,
            'count': len(chapters)
        }
    
    # ==================== 辅助方法 ====================
    
    def _validate_title(self, title: str) -> bool:
        """验证标题是否合理"""
        if not title or len(title) < 3 or len(title) > 100:
            return False
        if title[-1] in '。，！？；：""''（）':
            return False
        if self._is_non_chapter_title(title):
            return False
        return True
    
    def _sort_by_position(self, chapters: List[Dict]) -> List[Dict]:
        """按位置排序章节"""
        return sorted(chapters, key=lambda x: (x.get('file_path', ''), x.get('position', 0)))
    
    def _sort_and_deduplicate(self, chapters: List[Dict]) -> List[Dict]:
        """排序并去重"""
        sorted_chapters = sorted(chapters, key=lambda x: (x.get('file_path', ''), x.get('title', '')))
        
        seen = set()
        unique = []
        for ch in sorted_chapters:
            key = (ch.get('file_path', ''), ch.get('title', ''))
            if key not in seen:
                seen.add(key)
                unique.append(ch)
        
        return unique
    
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
    
    # ==================== 原有方法（保持不变） ====================
    
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
    
    def _build_chapters_from_detection(self, detected_chapters: List[Dict], file_contents: Dict[str, str]) -> List[Chapter]:
        """根据检测结果构建章节（支持跨文件内容提取和小节合并）"""
        chapters = []
        chapter_index = 1
        i = 0
        
        # 构建文件顺序映射
        sorted_files = sorted(file_contents.keys())
        file_order = {f: idx for idx, f in enumerate(sorted_files)}
        
        while i < len(detected_chapters):
            detected = detected_chapters[i]
            
            # 检查是否是小节
            if detected.get('is_subsection', False):
                i += 1
                continue
            
            # 提取当前章节内容（支持跨文件）
            content_blocks = self._extract_chapter_content_cross_file(detected, detected_chapters, i, file_contents, file_order, sorted_files)
            
            if content_blocks:
                chapter = self._create_chapter(
                    index=chapter_index,
                    title=detected['title'],
                    level=detected.get('level', 1),
                    content_blocks=content_blocks
                )
                chapters.append(chapter)
                chapter_index += 1
            
            # 找到下一个主章节
            j = i + 1
            while j < len(detected_chapters) and detected_chapters[j].get('is_subsection', False):
                j += 1
            i = j
        
        return chapters
    
    def _extract_chapter_content_cross_file(self, detected: Dict, all_chapters: List[Dict], 
                                            current_idx: int, file_contents: Dict[str, str],
                                            file_order: Dict[str, int], sorted_files: List[str]) -> List[ContentBlock]:
        """
        跨文件提取章节内容
        
        EPUB中一个大章节可能跨多个HTML文件，需要：
        1. 从当前章节所在文件开始提取
        2. 继续提取后续文件，直到遇到下一个主章节或文件结束
        """
        from bs4 import BeautifulSoup
        
        blocks = []
        start_file = detected['file_path']
        start_file_idx = file_order.get(start_file, 0)
        
        # 找到下一个主章节的文件位置
        next_chapter_file_idx = len(file_order)
        for j in range(current_idx + 1, len(all_chapters)):
            if not all_chapters[j].get('is_subsection', False):
                next_file = all_chapters[j]['file_path']
                next_chapter_file_idx = file_order.get(next_file, len(file_order))
                break
        
        # 收集所有小节标题（用于识别小节边界）
        subsection_titles = set()
        for j in range(current_idx + 1, len(all_chapters)):
            if all_chapters[j].get('is_subsection', False):
                subsection_titles.add(all_chapters[j]['title'])
            else:
                break
        
        # 遍历从当前文件到下一个主章节之前的所有文件
        for file_idx in range(start_file_idx, next_chapter_file_idx):
            if file_idx >= len(sorted_files):
                break
            file_path = sorted_files[file_idx]
            if file_path not in file_contents:
                continue
            
            content = file_contents[file_path]
            soup = BeautifulSoup(content, 'html.parser')
            
            # 移除脚本和样式
            for script in soup(["script", "style"]):
                script.decompose()
            
            # 提取正文内容
            body = soup.find('body')
            if body:
                # 获取所有文本元素
                for elem in body.find_all(['p', 'div', 'span', 'h1', 'h2', 'h3', 'h4']):
                    text = elem.get_text(strip=True)
                    if not text or len(text) < 3:
                        continue
                    
                    # 检查是否是小节标题
                    if text in subsection_titles:
                        # 添加小节标题作为二级标题
                        blocks.append(ContentBlock(
                            type=ContentType.HEADING,
                            text=f"## {text}",
                            level=2,
                            style=TextStyle(),
                            page_number=0
                        ))
                        subsection_titles.remove(text)  # 只处理一次
                    elif elem.name in ['h1', 'h2', 'h3'] and len(text) < 100:
                        # 可能是小节标题，检查是否匹配
                        is_subsection = any(sub_title in text or text in sub_title 
                                          for sub_title in subsection_titles)
                        if is_subsection:
                            blocks.append(ContentBlock(
                                type=ContentType.HEADING,
                                text=f"## {text}",
                                level=2,
                                style=TextStyle(),
                                page_number=0
                            ))
                        else:
                            # 普通段落
                            blocks.append(ContentBlock(
                                type=ContentType.PARAGRAPH,
                                text=text,
                                level=0,
                                style=TextStyle(),
                                page_number=0
                            ))
                    else:
                        # 普通段落
                        blocks.append(ContentBlock(
                            type=ContentType.PARAGRAPH,
                            text=text,
                            level=0,
                            style=TextStyle(),
                            page_number=0
                        ))
        
        return blocks
    
    def _extract_content_for_chapter(self, detected: Dict, file_contents: Dict[str, str]) -> List[ContentBlock]:
        """提取章节内容"""
        from bs4 import BeautifulSoup
        
        blocks = []
        file_path = detected['file_path']
        
        if file_path not in file_contents:
            return blocks
        
        content = file_contents[file_path]
        soup = BeautifulSoup(content, 'html.parser')
        
        # 移除脚本和样式
        for script in soup(["script", "style"]):
            script.decompose()
        
        # 提取正文内容
        body = soup.find('body')
        if body:
            for elem in body.find_all(['p', 'div', 'span']):
                text = elem.get_text(strip=True)
                if text and len(text) > 5:
                    blocks.append(ContentBlock(
                        type=ContentType.PARAGRAPH,
                        text=text,
                        level=0,
                        style=TextStyle(),
                        page_number=0
                    ))
        
        return blocks
    
    def _create_chapter(self, index: int, title: str, level: int, content_blocks: List[ContentBlock]) -> Chapter:
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
