"""
XML文件读取器 - 输出JSON结构化文档
"""
from .base import FileReader
from pathlib import Path
from core.document import Document, Chapter, ContentBlock, ContentType, TextStyle
import re


class XMLReader(FileReader):
    """XML文件读取器 - 保留标签结构"""
    
    SUPPORTED_EXTS = ['.xml', '.xhtml', '.xht', '.rss', '.atom', '.opml']
    
    def supports(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in self.SUPPORTED_EXTS
    
    def read(self, file_path: str) -> Document:
        """读取XML文件，返回结构化文档"""
        file_info = self.get_file_info(file_path)
        
        doc = Document(
            file_path=file_info["path"],
            file_name=file_info["name"],
            file_format="xml"
        )
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 移除XML声明
            content = re.sub(r'<\?xml[^?]*\?>', '', content)
            
            # 提取章节相关的标签内容
            chapter_tags = ['chapter', 'section', 'part', 'book', 'article', 
                           'title', 'head', 'body', 'item', 'entry']
            
            chapter_idx = 0
            
            # 尝试提取带标签的内容
            for tag in chapter_tags:
                pattern = rf'<{tag}[^>]*>(.*?)</{tag}>'
                matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
                
                for match in matches:
                    chapter_idx += 1
                    # 清理内部标签
                    clean_text = re.sub(r'<[^>]+>', ' ', match)
                    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                    
                    if clean_text:
                        chapter = Chapter(
                            index=chapter_idx,
                            title=f"{tag.upper()}: {clean_text[:50]}",
                            level=1,
                            content_blocks=[ContentBlock(
                                type=ContentType.PARAGRAPH,
                                text=clean_text
                            )],
                            word_count=len(clean_text),
                            paragraph_count=clean_text.count('\n\n') + 1
                        )
                        doc.chapters.append(chapter)
            
            # 如果没有找到章节标签，将整个内容作为一个章节
            if not doc.chapters:
                text_only = re.sub(r'<[^>]+>', ' ', content)
                text_only = re.sub(r'\s+', '\n', text_only).strip()
                
                doc.chapters.append(Chapter(
                    index=1,
                    title="XML内容",
                    level=1,
                    content_blocks=[ContentBlock(
                        type=ContentType.PARAGRAPH,
                        text=text_only
                    )],
                    word_count=len(text_only),
                    paragraph_count=text_only.count('\n\n') + 1
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
                    # 重新处理
                    return self.read(file_path)
                except:
                    continue
            return doc
        except Exception as e:
            print(f"Error reading XML {file_path}: {e}")
            return doc
