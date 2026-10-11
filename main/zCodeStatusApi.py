import os
import pathspec
from flask import Blueprint, jsonify, request, send_from_directory
from zConfig import get_config

codestatus_bp = Blueprint('codestatus', __name__, url_prefix='/codestatus')

# 默认忽略的目录及文件
DEFAULT_IGNORED_DIRS = {
    '.git', '.svn', '.hg', '__pycache__', 'node_modules', 'venv', '.venv',
    'env', 'dist', 'build', '.idea', '.vscode', 'servercache', 'target', 'bin', 'obj'
}
DEFAULT_IGNORED_FILES = {
    '.DS_Store', 'Thumbs.db', 'desktop.ini'
}

# 语言映射及统计分类
LANG_EXT_MAP = {
    'Python': ['.py', '.pyw'],
    'JavaScript': ['.js', '.mjs', '.cjs'],
    'TypeScript': ['.ts', '.tsx'],
    'HTML': ['.html', '.htm'],
    'CSS': ['.css', '.scss', '.sass', '.less'],
    'Markdown': ['.md', '.markdown'],
    'JSON': ['.json'],
    'YAML': ['.yaml', '.yml'],
    'C/C++': ['.c', '.cpp', '.h', '.hpp'],
    'Java': ['.java'],
    'Go': ['.go'],
    'Rust': ['.rs'],
    'Shell': ['.sh', '.bat', '.cmd', '.ps1'],
}

def get_target_directory():
    """
    从 zConfig.get_config("codestatus.dir") 获取目标目录，
    若未配置或为空则默认取项目根目录。
    """
    configured_dir = get_config("codestatus.dir")
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    
    if configured_dir and isinstance(configured_dir, str):
        if os.path.isabs(configured_dir):
            target = configured_dir
        else:
            target = os.path.normpath(os.path.join(root_dir, configured_dir))
        if os.path.exists(target) and os.path.isdir(target):
            return target
            
    return root_dir

def load_gitignore_spec(target_dir):
    """
    自动读取目标目录下的 .gitignore 文件，结合默认忽略项构建 pathspec 匹配规则
    """
    patterns = []
    
    # 加入默认忽略目录和文件
    for d in DEFAULT_IGNORED_DIRS:
        patterns.append(f"/{d}/")
        patterns.append(f"{d}/")
        patterns.append(d)
    for f in DEFAULT_IGNORED_FILES:
        patterns.append(f)
        
    gitignore_path = os.path.join(target_dir, ".gitignore")
    if os.path.exists(gitignore_path) and os.path.isfile(gitignore_path):
        try:
            with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        patterns.append(line)
        except Exception:
            pass
            
    return pathspec.PathSpec.from_lines('gitwildmatch', patterns)

def detect_language(filename):
    ext = os.path.splitext(filename)[1].lower()
    for lang, exts in LANG_EXT_MAP.items():
        if ext in exts:
            return lang
    return 'Other'

@codestatus_bp.route('/api/stats', methods=['GET'])
def get_code_stats():
    """
    返回 JSON 格式的统计数据：总文件数、总字符数、总代码行数、各语言文件数与行数统计、文件列表及详细信息。
    """
    target_dir = get_target_directory()
    spec = load_gitignore_spec(target_dir)
    
    total_files = 0
    total_chars = 0
    total_lines = 0
    lang_stats = {}
    file_details = []
    
    root_abs = os.path.abspath(target_dir)
    
    for root, dirs, files in os.walk(root_abs):
        # 计算相对于 target_dir 的路径，用于 gitignore 匹配
        rel_root = os.path.relpath(root, root_abs)
        
        # 过滤目录
        dirs[:] = [
            d for d in dirs 
            if d not in DEFAULT_IGNORED_DIRS and 
            not spec.match_file(os.path.join(rel_root, d) if rel_root != '.' else d)
        ]
        
        for file in files:
            if file in DEFAULT_IGNORED_FILES:
                continue
                
            rel_file_path = os.path.join(rel_root, file) if rel_root != '.' else file
            
            # 使用 pathspec 校验是否被忽略
            if spec.match_file(rel_file_path):
                continue
                
            abs_file_path = os.path.join(root, file)
            
            # 尝试读取文件统计行数、字符数
            try:
                # 忽略过大的文件（例如 > 5MB）
                if os.path.getsize(abs_file_path) > 5 * 1024 * 1024:
                    continue
                    
                with open(abs_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                continue
                
            chars = len(content)
            lines = content.count('\n') + (1 if content and not content.endswith('\n') else 0)
            lang = detect_language(file)
            
            total_files += 1
            total_chars += chars
            total_lines += lines
            
            # 统计各语言
            if lang not in lang_stats:
                lang_stats[lang] = {'files': 0, 'lines': 0, 'chars': 0}
            lang_stats[lang]['files'] += 1
            lang_stats[lang]['lines'] += lines
            lang_stats[lang]['chars'] += chars
            
            file_details.append({
                'path': rel_file_path.replace('\\', '/'),
                'name': file,
                'language': lang,
                'lines': lines,
                'chars': chars,
                'size': os.path.getsize(abs_file_path)
            })
            
    # 按行数降序对文件列表排序
    file_details.sort(key=lambda x: x['lines'], reverse=True)
    
    return jsonify({
        'status': 'success',
        'target_directory': root_abs,
        'total_files': total_files,
        'total_chars': total_chars,
        'total_lines': total_lines,
        'languages': lang_stats,
        'files': file_details
    })

@codestatus_bp.route('/', defaults={'filename': 'codestatus.html'}, methods=['GET'])
@codestatus_bp.route('/<path:filename>', methods=['GET'])
def serve_ui(filename):
    """
    提供静态页面访问路由（如 /codestatus/ 或 /codestatus/ui 等渲染 codestatus.html）
    """
    webassets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "webassets"))
    if not filename:
        filename = 'codestatus.html'
    target = os.path.join(webassets_dir, filename)
    if os.path.exists(target) and os.path.isfile(target):
        return send_from_directory(webassets_dir, filename)
    return send_from_directory(webassets_dir, 'codestatus.html')
