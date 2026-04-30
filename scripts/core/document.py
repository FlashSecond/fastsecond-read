"""
文档结构定义 - JSON结构化文档模型

定义文章的结构化表示，包含：
- 文档元信息
- 章节结构树
- 段落级内容块
- 格式标记
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum


class ContentType(Enum):
    """内容类型枚举"""
    TITLE = "title"           # 标题
    HEADING = "heading"       # 小标题
    PARAGRAPH = "paragraph"   # 段落
    LIST = "list"             # 列表
    CODE = "code"             # 代码块
    QUOTE = "quote"           # 引用
    TABLE = "table"           # 表格
    IMAGE = "image"           # 图片
    FORMULA = "formula"       # 公式
    FOOTNOTE = "footnote"     # 脚注
    PAGE_BREAK = "page_break" # 分页符


class ModuleType(Enum):
    """正文模块类型枚举"""
    DEFINITION = "definition"     # 定义/背景模块
    CASE = "case"                 # 案例模块
    ARGUMENT = "argument"         # 分论点模块
    QUOTE_CITATION = "quote"      # 引用论证模块
    CONCLUSION = "conclusion"     # 结论/过渡模块
    UNKNOWN = "unknown"           # 未知类型


@dataclass
class TextStyle:
    """文本样式信息"""
    bold: bool = False
    italic: bool = False
    underline: bool = False
    font_size: Optional[float] = None  # 字号（磅）
    font_name: Optional[str] = None    # 字体名
    color: Optional[str] = None        # 颜色（十六进制）
    alignment: Optional[str] = None    # 对齐方式


@dataclass
class ContentBlock:
    """内容块 - 文档的基本组成单元"""
    type: ContentType
    text: str
    level: int = 0                     # 层级（用于标题）
    style: TextStyle = field(default_factory=TextStyle)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 模块类型（由分析器填充）
    module_type: Optional[ModuleType] = None
    
    # 列表特有
    list_items: List[str] = field(default_factory=list)
    list_ordered: bool = False
    
    # 代码特有
    language: Optional[str] = None
    
    # 表格特有
    table_data: List[List[str]] = field(default_factory=list)
    
    # 图片特有
    image_path: Optional[str] = None
    image_caption: Optional[str] = None
    
    # 位置信息（PDF等格式）
    page_number: Optional[int] = None
    bbox: Optional[tuple] = None  # (x0, y0, x1, y1)


@dataclass
class Chapter:
    """章节结构"""
    index: int
    title: str
    level: int = 1
    content_blocks: List[ContentBlock] = field(default_factory=list)
    sub_chapters: List['Chapter'] = field(default_factory=list)
    
    # 章节统计
    word_count: int = 0
    paragraph_count: int = 0
    
    # 章节元数据
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Document:
    """文档结构 - 完整的文章表示"""
    # 文档标识
    file_path: str
    file_name: str
    file_format: str
    
    # 文档元信息
    title: Optional[str] = None
    author: Optional[str] = None
    publisher: Optional[str] = None
    publish_date: Optional[str] = None
    isbn: Optional[str] = None
    language: Optional[str] = None
    
    # 文档统计
    total_pages: int = 0
    total_words: int = 0
    total_chapters: int = 0
    
    # 文档结构
    chapters: List[Chapter] = field(default_factory=list)
    
    # 原始内容（可选，用于调试）
    raw_content: Optional[str] = None
    
    # 处理元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "file_info": {
                "path": self.file_path,
                "name": self.file_name,
                "format": self.file_format
            },
            "metadata": {
                "title": self.title,
                "author": self.author,
                "publisher": self.publisher,
                "publish_date": self.publish_date,
                "isbn": self.isbn,
                "language": self.language
            },
            "statistics": {
                "total_pages": self.total_pages,
                "total_words": self.total_words,
                "total_chapters": self.total_chapters
            },
            "structure": [self._chapter_to_dict(ch) for ch in self.chapters]
        }
    
    def _chapter_to_dict(self, chapter: Chapter) -> Dict[str, Any]:
        """章节转字典"""
        return {
            "index": chapter.index,
            "title": chapter.title,
            "level": chapter.level,
            "statistics": {
                "word_count": chapter.word_count,
                "paragraph_count": chapter.paragraph_count
            },
            "content_blocks": [self._block_to_dict(b) for b in chapter.content_blocks],
            "sub_chapters": [self._chapter_to_dict(sub) for sub in chapter.sub_chapters]
        }
    
    def _block_to_dict(self, block: ContentBlock) -> Dict[str, Any]:
        """内容块转字典"""
        result = {
            "type": block.type.value,
            "text": block.text,
            "level": block.level,
            "module_type": block.module_type.value if block.module_type else None,
            "style": {
                "bold": block.style.bold,
                "italic": block.style.italic,
                "underline": block.style.underline,
                "font_size": block.style.font_size,
                "font_name": block.style.font_name,
                "color": block.style.color,
                "alignment": block.style.alignment
            }
        }
        
        # 添加可选字段
        if block.list_items:
            result["list_items"] = block.list_items
            result["list_ordered"] = block.list_ordered
        if block.language:
            result["language"] = block.language
        if block.table_data:
            result["table_data"] = block.table_data
        if block.image_path:
            result["image_path"] = block.image_path
            result["image_caption"] = block.image_caption
        if block.page_number:
            result["page_number"] = block.page_number
        if block.bbox:
            result["bbox"] = block.bbox
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Document':
        """从字典创建文档对象"""
        doc = cls(
            file_path=data["file_info"]["path"],
            file_name=data["file_info"]["name"],
            file_format=data["file_info"]["format"],
            title=data["metadata"].get("title"),
            author=data["metadata"].get("author"),
            publisher=data["metadata"].get("publisher"),
            publish_date=data["metadata"].get("publish_date"),
            isbn=data["metadata"].get("isbn"),
            language=data["metadata"].get("language"),
            total_pages=data["statistics"].get("total_pages", 0),
            total_words=data["statistics"].get("total_words", 0),
            total_chapters=data["statistics"].get("total_chapters", 0)
        )
        
        # 重建章节结构
        for ch_data in data.get("structure", []):
            doc.chapters.append(cls._dict_to_chapter(ch_data))
        
        return doc
    
    @classmethod
    def _dict_to_chapter(cls, data: Dict[str, Any]) -> Chapter:
        """从字典创建章节"""
        chapter = Chapter(
            index=data["index"],
            title=data["title"],
            level=data.get("level", 1),
            word_count=data.get("statistics", {}).get("word_count", 0),
            paragraph_count=data.get("statistics", {}).get("paragraph_count", 0)
        )
        
        # 重建内容块
        for block_data in data.get("content_blocks", []):
            chapter.content_blocks.append(cls._dict_to_block(block_data))
        
        # 重建子章节
        for sub_data in data.get("sub_chapters", []):
            chapter.sub_chapters.append(cls._dict_to_chapter(sub_data))
        
        return chapter
    
    @classmethod
    def _dict_to_block(cls, data: Dict[str, Any]) -> ContentBlock:
        """从字典创建内容块"""
        style_data = data.get("style", {})
        style = TextStyle(
            bold=style_data.get("bold", False),
            italic=style_data.get("italic", False),
            underline=style_data.get("underline", False),
            font_size=style_data.get("font_size"),
            font_name=style_data.get("font_name"),
            color=style_data.get("color"),
            alignment=style_data.get("alignment")
        )
        
        block = ContentBlock(
            type=ContentType(data["type"]),
            text=data["text"],
            level=data.get("level", 0),
            style=style,
            module_type=ModuleType(data["module_type"]) if data.get("module_type") else None,
            list_items=data.get("list_items", []),
            list_ordered=data.get("list_ordered", False),
            language=data.get("language"),
            table_data=data.get("table_data", []),
            image_path=data.get("image_path"),
            image_caption=data.get("image_caption"),
            page_number=data.get("page_number"),
            bbox=tuple(data["bbox"]) if data.get("bbox") else None
        )
        
        return block
