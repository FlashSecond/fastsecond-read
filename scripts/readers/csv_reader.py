"""
CSV/TSV文件读取器 - 输出JSON结构化文档
"""
from .base import FileReader
from pathlib import Path
from core.document import Document, Chapter, ContentBlock, ContentType, TextStyle
import csv
import io


class CSVReader(FileReader):
    """CSV/TSV文件读取器 - 保留表格结构"""
    
    SUPPORTED_EXTS = ['.csv', '.tsv', '.tab']
    
    def supports(self, file_path: str) -> bool:
        ext = Path(file_path).suffix.lower()
        return ext in self.SUPPORTED_EXTS
    
    def read(self, file_path: str) -> Document:
        """读取CSV/TSV文件，返回结构化文档"""
        file_info = self.get_file_info(file_path)
        
        doc = Document(
            file_path=file_info["path"],
            file_name=file_info["name"],
            file_format="csv"
        )
        
        try:
            ext = Path(file_path).suffix.lower()
            
            # 确定分隔符
            if ext == '.tsv' or ext == '.tab':
                delimiter = '\t'
            else:
                delimiter = ','
            
            # 尝试检测编码
            encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']
            content = None
            used_encoding = 'utf-8'
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding, newline='') as f:
                        content = f.read()
                    used_encoding = encoding
                    break
                except UnicodeDecodeError:
                    continue
            
            if content is None:
                print(f"Could not decode {file_path} with any supported encoding")
                return doc
            
            # 解析CSV
            lines = content.split('\n')
            reader = csv.reader(lines, delimiter=delimiter)
            rows = list(reader)
            
            if not rows:
                return doc
            
            # 第一行作为表头
            headers = rows[0] if rows else []
            data_rows = rows[1:] if len(rows) > 1 else []
            
            # 创建章节结构
            # 第一章：表头信息
            chapter_idx = 0
            
            # 表头章节
            chapter_idx += 1
            header_chapter = Chapter(
                index=chapter_idx,
                title="表头信息",
                level=1
            )
            
            header_text = f"列数: {len(headers)}\n列名: {', '.join(headers)}"
            header_chapter.content_blocks.append(ContentBlock(
                type=ContentType.PARAGRAPH,
                text=header_text
            ))
            header_chapter.word_count = len(header_text)
            header_chapter.paragraph_count = 1
            doc.chapters.append(header_chapter)
            
            # 数据章节 - 每10行作为一个章节
            chunk_size = 10
            for i in range(0, len(data_rows), chunk_size):
                chunk = data_rows[i:i+chunk_size]
                chapter_idx += 1
                
                chapter = Chapter(
                    index=chapter_idx,
                    title=f"数据行 {i+1}-{min(i+chunk_size, len(data_rows))}",
                    level=1
                )
                
                # 创建表格内容块
                table_data = [headers] + chunk
                
                # 同时添加文本描述
                texts = []
                for row in chunk:
                    if row:  # 跳过空行
                        row_dict = dict(zip(headers, row))
                        row_text = '; '.join([f"{k}={v}" for k, v in row_dict.items()])
                        texts.append(row_text)
                
                text_content = '\n'.join(texts)
                
                chapter.content_blocks.append(ContentBlock(
                    type=ContentType.TABLE,
                    text=f"表格数据 ({len(chunk)} 行)",
                    table_data=table_data
                ))
                
                chapter.content_blocks.append(ContentBlock(
                    type=ContentType.PARAGRAPH,
                    text=text_content
                ))
                
                chapter.word_count = len(text_content)
                chapter.paragraph_count = len(chunk)
                doc.chapters.append(chapter)
            
            # 更新统计
            doc.total_chapters = len(doc.chapters)
            doc.total_words = sum(ch.word_count for ch in doc.chapters)
            
            return doc
            
        except Exception as e:
            print(f"Error reading CSV {file_path}: {e}")
            import traceback
            traceback.print_exc()
            return doc
