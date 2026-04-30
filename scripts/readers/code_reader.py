"""
代码文件读取器 - 输出JSON结构化文档
"""
from .base import FileReader
from pathlib import Path
from core.document import Document, Chapter, ContentBlock, ContentType, TextStyle


class CodeReader(FileReader):
    """代码文件读取器 - 支持常见编程语言"""
    
    # 支持的代码文件扩展名
    CODE_EXTENSIONS = [
        # Python
        '.py', '.pyw', '.pyi', '.pyc', '.pyo',
        # JavaScript/TypeScript
        '.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs',
        # Java
        '.java', '.class', '.jar',
        # C/C++
        '.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.hxx',
        # C#
        '.cs', '.csx',
        # Go
        '.go',
        # Rust
        '.rs', '.rlib',
        # Ruby
        '.rb', '.rbw',
        # PHP
        '.php', '.php3', '.php4', '.php5', '.phtml',
        # Swift
        '.swift',
        # Kotlin
        '.kt', '.kts',
        # Scala
        '.scala', '.sc',
        # Perl
        '.pl', '.pm',
        # Shell
        '.sh', '.bash', '.zsh', '.fish', '.ps1', '.psm1',
        # SQL
        '.sql',
        # Web
        '.css', '.scss', '.sass', '.less',
        # Config
        '.yaml', '.yml', '.toml', '.ini', '.conf', '.cfg',
        # Data
        '.properties', '.env',
    ]
    
    def supports(self, file_path: str) -> bool:
        ext = Path(file_path).suffix.lower()
        return ext in self.CODE_EXTENSIONS
    
    def read(self, file_path: str) -> Document:
        """读取代码文件，返回结构化文档"""
        file_info = self.get_file_info(file_path)
        ext = Path(file_path).suffix.lower()
        
        doc = Document(
            file_path=file_info["path"],
            file_name=file_info["name"],
            file_format=ext.lstrip('.')
        )
        
        try:
            # 尝试不同编码
            encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1', 'cp1252']
            content = None
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue
            
            if content is None:
                return doc
            
            lines = content.split('\n')
            
            # 创建主章节
            chapter = Chapter(
                index=1,
                title=f"代码: {file_info['name']}",
                level=1
            )
            
            # 添加文件信息
            chapter.content_blocks.append(ContentBlock(
                type=ContentType.PARAGRAPH,
                text=f"文件: {file_info['name']}\n语言: {self._get_language_name(ext)}"
            ))
            
            # 提取注释作为文档块
            comment_blocks = self._extract_comments(lines, ext)
            for comment in comment_blocks:
                chapter.content_blocks.append(ContentBlock(
                    type=ContentType.QUOTE,
                    text=comment
                ))
            
            # 添加完整代码
            chapter.content_blocks.append(ContentBlock(
                type=ContentType.CODE,
                text=content,
                language=self._get_language_name(ext)
            ))
            
            chapter.word_count = len(content)
            chapter.paragraph_count = len([l for l in lines if l.strip()])
            doc.chapters.append(chapter)
            
            # 更新统计
            doc.total_chapters = 1
            doc.total_words = chapter.word_count
            
            return doc
            
        except Exception as e:
            print(f"Error reading code file {file_path}: {e}")
            return doc
    
    def _extract_comments(self, lines: list, ext: str) -> list:
        """从代码中提取注释"""
        comments = []
        in_comment_block = False
        comment_lines = []
        
        for line in lines:
            stripped = line.strip()
            
            # Python/Shell/YAML 风格注释
            if ext in ['.py', '.pyw', '.sh', '.bash', '.yaml', '.yml', '.rb']:
                if stripped.startswith('#'):
                    comment_text = stripped[1:].strip()
                    if comment_text and not comment_text.startswith(('===', '---')):
                        comment_lines.append(comment_text)
                else:
                    if comment_lines:
                        comments.append(' '.join(comment_lines))
                        comment_lines = []
            
            # C/C++/Java/JavaScript 风格注释
            elif ext in ['.c', '.cpp', '.java', '.js', '.ts', '.cs', '.go', '.rs', '.swift', '.kt']:
                if stripped.startswith('//'):
                    comment_text = stripped[2:].strip()
                    if comment_text:
                        comment_lines.append(comment_text)
                elif stripped.startswith('/*') or stripped.startswith('/**'):
                    in_comment_block = True
                    comment_text = stripped[2:].strip()
                    if comment_text and not comment_text.startswith('*'):
                        comment_lines.append(comment_text)
                elif stripped.endswith('*/'):
                    in_comment_block = False
                    if comment_lines:
                        comments.append(' '.join(comment_lines))
                        comment_lines = []
                elif in_comment_block:
                    clean_line = stripped.lstrip('*').strip()
                    if clean_line:
                        comment_lines.append(clean_line)
                else:
                    if comment_lines:
                        comments.append(' '.join(comment_lines))
                        comment_lines = []
            
            # HTML/XML 风格注释
            elif ext in ['.html', '.htm', '.xml', '.css', '.scss']:
                if '<!--' in stripped:
                    start = stripped.find('<!--') + 4
                    end = stripped.find('-->') if '-->' in stripped else len(stripped)
                    comment_text = stripped[start:end].strip()
                    if comment_text:
                        comments.append(comment_text)
        
        # 处理剩余的注释行
        if comment_lines:
            comments.append(' '.join(comment_lines))
        
        return comments
    
    def _get_language_name(self, ext: str) -> str:
        """获取语言名称"""
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.java': 'java',
            '.c': 'c',
            '.cpp': 'cpp',
            '.cs': 'csharp',
            '.go': 'go',
            '.rs': 'rust',
            '.rb': 'ruby',
            '.php': 'php',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.sql': 'sql',
            '.sh': 'bash',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.json': 'json',
            '.css': 'css',
            '.scss': 'scss',
            '.html': 'html',
            '.xml': 'xml',
        }
        return language_map.get(ext, ext.lstrip('.'))
