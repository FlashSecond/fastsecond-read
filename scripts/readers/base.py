"""
文件读取器基类 - 支持JSON结构化输出
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union
from core.document import Document


class FileReader(ABC):
    """文件读取器抽象基类"""
    
    @abstractmethod
    def read(self, file_path: str) -> Document:
        """
        读取文件并返回结构化文档对象
        
        Args:
            file_path: 文件路径
            
        Returns:
            Document: 结构化文档对象
        """
        pass
    
    @abstractmethod
    def supports(self, file_path: str) -> bool:
        """检查是否支持该文件类型"""
        pass
    
    def get_file_info(self, file_path: str) -> dict:
        """获取文件基本信息"""
        path = Path(file_path)
        return {
            "path": str(path.absolute()),
            "name": path.name,
            "format": path.suffix.lower().lstrip('.'),
            "size": path.stat().st_size if path.exists() else 0
        }
