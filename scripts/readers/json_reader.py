"""
JSON文件读取器 - 输出JSON结构化文档
"""
from .base import FileReader
from pathlib import Path
from core.document import Document, Chapter, ContentBlock, ContentType, TextStyle
import json


class JSONReader(FileReader):
    """JSON文件读取器 - 从JSON结构中提取文本"""
    
    SUPPORTED_EXTS = ['.json', '.jsonl']
    
    def supports(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in self.SUPPORTED_EXTS
    
    def read(self, file_path: str) -> Document:
        """读取JSON文件，返回结构化文档"""
        file_info = self.get_file_info(file_path)
        
        doc = Document(
            file_path=file_info["path"],
            file_name=file_info["name"],
            file_format="json"
        )
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 尝试解析JSON
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                # 可能是JSONL格式（每行一个JSON对象）
                lines = content.strip().split('\n')
                data = [json.loads(line) for line in lines if line.strip()]
            
            # 从JSON提取章节
            chapters = self._extract_chapters(data)
            
            if chapters:
                doc.chapters = chapters
            else:
                # 如果没有提取到章节，将整个JSON作为一个章节
                doc.chapters.append(Chapter(
                    index=1,
                    title="JSON内容",
                    level=1,
                    content_blocks=[ContentBlock(
                        type=ContentType.CODE,
                        text=content,
                        language="json"
                    )],
                    word_count=len(content),
                    paragraph_count=1
                ))
            
            # 更新统计
            doc.total_chapters = len(doc.chapters)
            doc.total_words = sum(ch.word_count for ch in doc.chapters)
            
            return doc
            
        except Exception as e:
            print(f"Error reading JSON {file_path}: {e}")
            # 返回包含原始内容的文档
            doc.chapters.append(Chapter(
                index=1,
                title="JSON内容",
                level=1,
                content_blocks=[ContentBlock(
                    type=ContentType.CODE,
                    text=content if 'content' in dir() else "",
                    language="json"
                )],
                word_count=len(content) if 'content' in dir() else 0,
                paragraph_count=1
            ))
            doc.total_chapters = 1
            doc.total_words = doc.chapters[0].word_count
            return doc
    
    def _extract_chapters(self, data) -> list:
        """从JSON数据中提取章节"""
        chapters = []
        chapter_idx = 0
        
        if isinstance(data, dict):
            # 如果是字典，每个键值对作为一个章节
            for key, value in data.items():
                chapter_idx += 1
                
                # 提取文本内容
                text_content = self._value_to_text(value)
                
                chapter = Chapter(
                    index=chapter_idx,
                    title=str(key),
                    level=1,
                    content_blocks=[ContentBlock(
                        type=ContentType.PARAGRAPH,
                        text=text_content
                    )],
                    word_count=len(text_content),
                    paragraph_count=text_content.count('\n\n') + 1
                )
                chapters.append(chapter)
                
        elif isinstance(data, list):
            # 如果是列表，每个元素作为一个章节
            for i, item in enumerate(data):
                chapter_idx += 1
                
                # 提取标题
                title = self._extract_title(item) or f"第{i+1}项"
                
                # 提取文本内容
                text_content = self._value_to_text(item)
                
                chapter = Chapter(
                    index=chapter_idx,
                    title=title,
                    level=1,
                    content_blocks=[ContentBlock(
                        type=ContentType.PARAGRAPH,
                        text=text_content
                    )],
                    word_count=len(text_content),
                    paragraph_count=text_content.count('\n\n') + 1
                )
                chapters.append(chapter)
        
        return chapters
    
    def _extract_title(self, item) -> str:
        """从JSON项中提取标题"""
        if isinstance(item, dict):
            # 优先使用常见标题字段
            title_fields = ['title', 'name', 'chapter', 'section', 'heading', 'topic']
            for field in title_fields:
                if field in item:
                    return str(item[field])
        return ""
    
    def _value_to_text(self, value) -> str:
        """将JSON值转换为文本"""
        if isinstance(value, str):
            return value
        elif isinstance(value, (int, float, bool)):
            return str(value)
        elif isinstance(value, dict):
            # 递归处理字典
            texts = []
            for k, v in value.items():
                texts.append(f"{k}: {self._value_to_text(v)}")
            return '\n'.join(texts)
        elif isinstance(value, list):
            # 递归处理列表
            texts = []
            for i, item in enumerate(value):
                texts.append(f"[{i+1}] {self._value_to_text(item)}")
            return '\n'.join(texts)
        else:
            return str(value)
