"""
Markdown文件读取器 - 输出JSON结构化文档
"""
from .base import FileReader
from pathlib import Path
from core.document import Document, Chapter, ContentBlock, ContentType, TextStyle
import re


class MarkdownReader(FileReader):
    """Markdown文件读取器 - 保留标题标记用于分章节"""
    
    # 支持的Markdown扩展名
    SUPPORTED_EXTS = ['.md', '.markdown', '.mdown', '.mkd', '.mkdn']
    
    def supports(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in self.SUPPORTED_EXTS
    
    def read(self, file_path: str) -> Document:
        """读取Markdown文件，返回结构化文档"""
        file_info = self.get_file_info(file_path)
        
        doc = Document(
            file_path=file_info["path"],
            file_name=file_info["name"],
            file_format="markdown"
        )
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析Markdown结构
            lines = content.split('\n')
            current_chapter = None
            current_blocks = []
            chapter_idx = 0
            
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue
                
                # 检测一级标题 # 标题
                h1_match = re.match(r'^#\s+(.+)$', stripped)
                if h1_match:
                    # 保存之前的章节
                    if current_chapter:
                        current_chapter.content_blocks = current_blocks
                        current_chapter.word_count = sum(len(b.text) for b in current_blocks)
                        current_chapter.paragraph_count = len([b for b in current_blocks if b.type == ContentType.PARAGRAPH])
                        doc.chapters.append(current_chapter)
                    
                    # 创建新章节
                    chapter_idx += 1
                    title = h1_match.group(1).strip()
                    current_chapter = Chapter(
                        index=chapter_idx,
                        title=title,
                        level=1
                    )
                    current_blocks = []
                    
                    # 添加标题内容块
                    current_blocks.append(ContentBlock(
                        type=ContentType.HEADING,
                        text=title,
                        level=1,
                        style=TextStyle(bold=True)
                    ))
                    continue
                
                # 检测二级标题 ## 标题
                h2_match = re.match(r'^##\s+(.+)$', stripped)
                if h2_match:
                    title = h2_match.group(1).strip()
                    current_blocks.append(ContentBlock(
                        type=ContentType.HEADING,
                        text=title,
                        level=2,
                        style=TextStyle(bold=True)
                    ))
                    continue
                
                # 检测列表项
                list_match = re.match(r'^[\s]*[-*+]\s+(.+)$', stripped)
                if list_match:
                    current_blocks.append(ContentBlock(
                        type=ContentType.LIST,
                        text=list_match.group(1).strip(),
                        list_items=[list_match.group(1).strip()],
                        list_ordered=False
                    ))
                    continue
                
                # 检测有序列表
                ordered_match = re.match(r'^[\s]*\d+\.\s+(.+)$', stripped)
                if ordered_match:
                    current_blocks.append(ContentBlock(
                        type=ContentType.LIST,
                        text=ordered_match.group(1).strip(),
                        list_items=[ordered_match.group(1).strip()],
                        list_ordered=True
                    ))
                    continue
                
                # 检测代码块
                if stripped.startswith('```'):
                    # 代码块标记，跳过
                    continue
                
                # 检测引用
                if stripped.startswith('>'):
                    quote_text = stripped[1:].strip()
                    current_blocks.append(ContentBlock(
                        type=ContentType.QUOTE,
                        text=quote_text
                    ))
                    continue
                
                # 普通段落
                if stripped:
                    current_blocks.append(ContentBlock(
                        type=ContentType.PARAGRAPH,
                        text=stripped
                    ))
            
            # 保存最后一个章节
            if current_chapter:
                current_chapter.content_blocks = current_blocks
                current_chapter.word_count = sum(len(b.text) for b in current_blocks)
                current_chapter.paragraph_count = len([b for b in current_blocks if b.type == ContentType.PARAGRAPH])
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
            
        except UnicodeDecodeError:
            # 尝试其他编码
            for encoding in ['gbk', 'gb2312', 'latin-1']:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
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
                    doc.total_chapters = 1
                    doc.total_words = len(content)
                    return doc
                except:
                    continue
        except Exception as e:
            print(f"Error reading Markdown {file_path}: {e}")
        
        return doc
