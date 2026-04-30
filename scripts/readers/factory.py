"""
文件读取器工厂 - 创建适当的读取器实例
"""
from pathlib import Path
from typing import List, Optional
from core.document import Document
from .base import FileReader
from .pdf_reader import PDFReader
from .pdf_reader_v2 import PDFReaderV2
from .epub_reader import EPUBReader
from .docx_reader import DocxReader
from .txt_reader import TxtReader
from .html_reader import HTMLReader
from .markdown_reader import MarkdownReader
from .json_reader import JSONReader
from .csv_reader import CSVReader
from .xml_reader import XMLReader
from .rtf_reader import RTFReader
from .code_reader import CodeReader
from .ocr_reader import OCRReader


def _info(msg: str):
    """打印信息日志"""
    print(f"[INFO] {msg}")


def _error(msg: str):
    """打印错误日志"""
    print(f"[ERROR] {msg}", file=__import__('sys').stderr)


class ReaderFactory:
    """读取器工厂类"""
    
    # 所有可用的读取器（按优先级排序）
    _readers: List[FileReader] = [
        PDFReaderV2(),    # 优先使用 V2 版本（基于 PyMuPDF 的智能分章）
        PDFReader(),      # 备选：pdfplumber 版本
        EPUBReader(),
        DocxReader(),
        HTMLReader(),
        MarkdownReader(),
        JSONReader(),
        CSVReader(),
        XMLReader(),
        RTFReader(),
        CodeReader(),
        TxtReader(),      # TxtReader作为兜底
    ]
    
    # OCR 读取器（用于图片版 PDF）
    _ocr_reader: Optional[OCRReader] = None
    
    @classmethod
    def get_reader(cls, file_path: str) -> Optional[FileReader]:
        """
        根据文件路径获取合适的读取器
        
        Args:
            file_path: 文件路径
            
        Returns:
            FileReader: 合适的读取器实例，如果没有则返回None
        """
        for reader in cls._readers:
            if reader.supports(file_path):
                return reader
        return None
    
    @classmethod
    def read_file(cls, file_path: str, use_ocr: bool = False, use_v2: bool = True) -> Document:
        """
        读取文件并返回结构化文档
        
        Args:
            file_path: 文件路径
            use_ocr: 是否强制使用 OCR（用于图片版 PDF）
            use_v2: 是否优先使用 PDF V2 读取器（基于版面特征的智能分章）
            
        Returns:
            Document: 结构化文档对象
        """
        # 如果强制使用 OCR
        if use_ocr and file_path.lower().endswith('.pdf'):
            return cls._read_with_ocr(file_path)
        
        # 如果禁用 V2，使用 V1
        if not use_v2 and file_path.lower().endswith('.pdf'):
            reader = PDFReader()
            doc = reader.read(file_path)
            
            # 自动检测：如果 PDF 内容太少，尝试 OCR
            if doc.total_words < 1000 and not use_ocr:
                _info(f"PDF 内容较少（{doc.total_words} 字），尝试 OCR 识别...")
                return cls._read_with_ocr(file_path)
            return doc
        
        reader = cls.get_reader(file_path)
        
        if reader is None:
            # 创建空文档
            path = Path(file_path)
            from core.document import Document
            return Document(
                file_path=str(path.absolute()),
                file_name=path.name,
                file_format=path.suffix.lower().lstrip('.')
            )
        
        doc = reader.read(file_path)
        
        # 自动检测：如果 PDF 内容太少，尝试 OCR
        if (file_path.lower().endswith('.pdf') and 
            doc.total_words < 1000 and 
            not use_ocr):
            _info(f"PDF 内容较少（{doc.total_words} 字），尝试 OCR 识别...")
            return cls._read_with_ocr(file_path)
        
        return doc
    
    @classmethod
    def _read_with_ocr(cls, file_path: str) -> Document:
        """使用 OCR 读取文件"""
        if cls._ocr_reader is None:
            cls._ocr_reader = OCRReader()
        
        return cls._ocr_reader.read(file_path)
    
    @classmethod
    def supports(cls, file_path: str) -> bool:
        """检查是否支持该文件类型"""
        return cls.get_reader(file_path) is not None
    
    @classmethod
    def get_supported_formats(cls) -> List[str]:
        """获取支持的文件格式列表"""
        return [
            # 文档格式
            '.pdf', '.epub', '.docx', '.doc', '.rtf',
            # 标记格式
            '.txt', '.md', '.markdown', '.html', '.htm',
            # 数据格式
            '.json', '.jsonl', '.csv', '.tsv', '.xml',
            # 代码格式（CodeReader支持20+种）
            '.py', '.js', '.ts', '.java', '.c', '.cpp', '.h', '.hpp',
            '.cs', '.go', '.rs', '.rb', '.php', '.swift', '.kt',
            '.scala', '.r', '.m', '.mm', '.sql', '.sh', '.ps1',
            '.yaml', '.yml', '.toml', '.ini', '.conf', '.cfg',
            '.css', '.scss', '.sass', '.less',
            '.vue', '.jsx', '.tsx', '.svelte'
        ]
