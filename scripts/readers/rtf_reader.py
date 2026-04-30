"""
RTF文件读取器 - 输出JSON结构化文档
"""
from .base import FileReader
from pathlib import Path
from core.document import Document, Chapter, ContentBlock, ContentType, TextStyle
import re


class RTFReader(FileReader):
    """RTF文件读取器 - 提取纯文本内容"""
    
    SUPPORTED_EXTS = ['.rtf']
    
    def supports(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in self.SUPPORTED_EXTS
    
    def read(self, file_path: str) -> Document:
        """读取RTF文件，返回结构化文档"""
        file_info = self.get_file_info(file_path)
        
        doc = Document(
            file_path=file_info["path"],
            file_name=file_info["name"],
            file_format="rtf"
        )
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # 移除RTF控制字
            content = re.sub(r'\{\\rtf1[^}]*\}', '', content)
            content = re.sub(r'\\[a-z]+\d*\s?', ' ', content)
            content = re.sub(r'\\\*\\[^\s{}]+', ' ', content)
            content = re.sub(r'\\\'([0-9a-fA-F]{2})', self._decode_hex, content)
            content = re.sub(r'[{}]', '', content)
            content = re.sub(r'\s+', ' ', content).strip()
            
            # 尝试检测章节标题
            lines = content.split('\n')
            chapter_idx = 0
            current_chapter = None
            current_blocks = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # 检测可能的章节标题
                is_chapter = re.match(r'^(CHAPTER|SECTION|PART|第[一二三四五六七八九十\d]+章)', line, re.IGNORECASE)
                
                if is_chapter:
                    # 保存之前的章节
                    if current_chapter:
                        current_chapter.content_blocks = current_blocks
                        current_chapter.word_count = sum(len(b.text) for b in current_blocks)
                        current_chapter.paragraph_count = len(current_blocks)
                        doc.chapters.append(current_chapter)
                    
                    # 创建新章节
                    chapter_idx += 1
                    current_chapter = Chapter(
                        index=chapter_idx,
                        title=line,
                        level=1
                    )
                    current_blocks = []
                else:
                    # 添加内容块
                    current_blocks.append(ContentBlock(
                        type=ContentType.PARAGRAPH,
                        text=line
                    ))
            
            # 保存最后一个章节
            if current_chapter:
                current_chapter.content_blocks = current_blocks
                current_chapter.word_count = sum(len(b.text) for b in current_blocks)
                current_chapter.paragraph_count = len(current_blocks)
                doc.chapters.append(current_chapter)
            
            # 如果没有章节，将整个内容作为一个章节
            if not doc.chapters:
                doc.chapters.append(Chapter(
                    index=1,
                    title="全文",
                    level=1,
                    content_blocks=[ContentBlock(
                        type=ContentType.PARAGRAPH,
                        text=content
                    )],
                    word_count=len(content),
                    paragraph_count=content.count('\n\n') + 1
                ))
            
            # 更新统计
            doc.total_chapters = len(doc.chapters)
            doc.total_words = sum(ch.word_count for ch in doc.chapters)
            
            return doc
            
        except Exception as e:
            print(f"Error reading RTF {file_path}: {e}")
            return doc
    
    def _decode_hex(self, match):
        """解码RTF十六进制字符"""
        try:
            return bytes.fromhex(match.group(1)).decode('latin-1')
        except:
            return '?'
