import os
import glob
from flask import Blueprint, request, jsonify
from zConfig import get_config

# 创建日志查看蓝图，统一前缀 /logapi
log_bp = Blueprint('log_bp', __name__, url_prefix='/logapi')

def get_path_metadata(path_str):
    """
    识别路径特征并返回标签和分类
    要求：
    - 调整路径判定顺序：先判定 yunzai，再判定 Perseus/logs、AzurPilot、Perseus/QBot/log、Perseus/QBot。
    - 确保返回的 metadata 中带有准确的分类名称。
    """
    normalized = path_str.replace("\\", "/")
    tags = []
    category = "other"
    
    # 按照最新精细化要求调整后的优先级判定顺序：
    # 1. yunzai
    # 2. Perseus/logs (主服务日志)
    # 3. AzurPilot (Azurpilot日志)
    # 4. Perseus/QBot/log (机器人日志)
    # 5. Perseus/QBot (QBotSDK日志)
    
    if "yunzai" in normalized.lower():
        tags.append("云崽日志")
        category = "yunzai"
    elif "perseus/logs" in normalized.lower() or normalized.lower().endswith("perseus/logs") or ("/logs" in normalized.lower() and "perseus" in normalized.lower() and "qbot" not in normalized.lower()):
        tags.append("主服务日志")
        category = "perseus_logs"
    elif "azurpilot" in normalized.lower():
        tags.append("Azurpilot日志")
        category = "azurpilot"
    elif "perseus/qbot/log" in normalized.lower():
        tags.append("机器人日志")
        category = "qbot_log"
    elif "perseus/qbot" in normalized.lower():
        tags.append("QBotSDK日志")
        category = "qbot_sdk"
    else:
        tags.append("其他日志")
        category = "other"
        
    return tags, category

def get_valid_log_paths():
    """
    1. 读取配置 PRESET_LOG_PATHS = zConfig.get_config("bot.opcmd.preset_log_paths")
    （若为空或未配置可提供默认路径列表如 ["logs", "."]）。
    """
    paths = get_config("bot.opcmd.preset_log_paths")
    if not paths or not isinstance(paths, list):
        paths = ["logs", ".", "main/logs", "QBot/logs"]
    
    valid_dirs = []
    for p in paths:
        # 转为绝对路径或相对于工作区的安全路径
        if not os.path.isabs(p):
            abs_p = os.path.abspath(p)
        else:
            abs_p = p
            
        if os.path.exists(abs_p) and os.path.isdir(abs_p):
            tags, category = get_path_metadata(abs_p)
            valid_dirs.append({
                "path": abs_p,
                "name": os.path.basename(abs_p) or abs_p,
                "tags": tags,
                "category": category
            })
    
    # 确保至少有当前目录或默认目录
    if not valid_dirs:
        current_dir = os.path.abspath(".")
        tags, category = get_path_metadata(current_dir)
        valid_dirs.append({
            "path": current_dir,
            "name": os.path.basename(current_dir) or "root",
            "tags": tags,
            "category": category
        })
        
    return valid_dirs

@log_bp.route("/folders", methods=["GET"])
def api_get_folders():
    """
    GET /logapi/folders: 返回预设的文件夹列表（从 PRESET_LOG_PATHS 中解析出的有效目录）。
    """
    try:
        folders = get_valid_log_paths()
        return jsonify({
            "status": "success",
            "folders": folders
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@log_bp.route("/files", methods=["GET"])
def api_get_files():
    """
    GET /logapi/files?folder=<folder_path>: 返回指定文件夹下的日志文件列表。
    过滤条件：
    1. 过滤掉所有 .json 文件。
    2. 支持滚动日志文件命名（例如 app.log.1, log.txt.2 等，即文件名包含 .log 或 .txt 或以数字后缀结尾的日志，或无后缀/常见日志后缀）。
    """
    folder_path = request.args.get("folder", "")
    if not folder_path or not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        return jsonify({
            "status": "error",
            "message": "Invalid or missing folder path"
        }), 400

    try:
        files = []
        for item in os.listdir(folder_path):
            full_path = os.path.join(folder_path, item)
            if os.path.isfile(full_path):
                lower_item = item.lower()
                
                # 1. 明确过滤掉所有 .json 文件
                if lower_item.endswith(".json"):
                    continue
                
                # 2. 支持滚动日志文件命名及标准日志格式判断
                # 条件：包含 .log 或 .txt 或以数字后缀结尾（如 .1, .2）或无后缀/其他常见日志后缀（.out, .err）
                is_valid_log = False
                if ".log" in lower_item or ".txt" in lower_item:
                    is_valid_log = True
                elif lower_item.endswith((".out", ".err")):
                    is_valid_log = True
                elif "." in lower_item:
                    # 检查是否为滚动日志后缀，例如 .log.1 或 .txt.2 或 .1, .2 等数字后缀
                    parts = lower_item.split(".")
                    if parts[-1].isdigit():
                        is_valid_log = True
                else:
                    # 无后缀文件，如果大小大于0且可能是日志，也可以酌情收录（或者只收录包含log/txt的）
                    # 按照之前逻辑，"."" not in item 也算，但为了严谨，这里对常见的日志做匹配
                    is_valid_log = True
                
                if is_valid_log:
                    stat = os.stat(full_path)
                    files.append({
                        "name": item,
                        "size": stat.st_size,
                        "mtime": stat.st_mtime
                    })
        
        # 按修改时间降序排序（最新的排在前面）
        files.sort(key=lambda x: x["mtime"], reverse=True)
        
        return jsonify({
            "status": "success",
            "folder": folder_path,
            "files": files
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@log_bp.route("/content", methods=["GET"])
def api_get_content():
    """
    GET /logapi/content?folder=<folder_path>&file=<file_name>&lines=100&filter_http=true/false: 
    返回指定文件的最新内容（支持服务端过滤 HTTP 访问/静态请求及回溯满指定行数）。
    """
    folder_path = request.args.get("folder", "")
    file_name = request.args.get("file", "")
    lines_param = request.args.get("lines", "100")
    filter_http_param = request.args.get("filter_http", "true").lower()
    filter_http = filter_http_param in ("true", "1", "yes")
    
    if not folder_path or not file_name:
        return jsonify({
            "status": "error",
            "message": "Missing folder or file parameter"
        }), 400

    # 安全检查，防止路径穿越
    safe_folder = os.path.abspath(folder_path)
    file_path = os.path.abspath(os.path.join(safe_folder, file_name))
    
    if not file_path.startswith(safe_folder) or not os.path.exists(file_path) or not os.path.isfile(file_path):
        return jsonify({
            "status": "error",
            "message": "File not found or access denied"
        }, 404)

    try:
        try:
            num_lines = int(lines_param)
        except ValueError:
            num_lines = 100

        file_size = os.path.getsize(file_path)
        
        # 定义过滤 HTTP/静态请求的判断函数
        def is_http_noise(line):
            if not filter_http:
                return False
            lower = line.lower()
            # 特征匹配：
            # 1. 包含 " - - [" 或 "HTTP/1." 或请求方法 GET/POST/PUT/DELETE
            # 2. 包含状态码或状态段 "304 -"、"404 -"、"200 -"、"500 -" 等
            # 3. 静态资源常见后缀
            if (
                " - - [" in line or
                "http/1." in lower or
                "get /" in lower or
                "post /" in lower or
                "put /" in lower or
                "delete /" in lower or
                " - 304 -" in line or
                " - 404 -" in line or
                " - 200 -" in line or
                " - 500 -" in line or
                '" 304 -' in line or
                '" 404 -' in line or
                '" 200 -' in line or
                '" 500 -' in line or
                r'\.(js|css|ico|png|jpg|jpeg|gif|svg|woff|woff2|ttf|map)(\?.*)?["\s]' in lower
            ):
                return True
            return False

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()

        if num_lines <= 0:
            # 全文过滤
            filtered_lines = [l for l in all_lines if not is_http_noise(l)]
            content = "".join(filtered_lines)
        else:
            # 回溯查找：从文件末尾向前扫描，直到收集到指定数量的有效非噪音日志行
            valid_lines = []
            idx = len(all_lines) - 1
            while idx >= 0 and len(valid_lines) < num_lines:
                line = all_lines[idx]
                if not is_http_noise(line):
                    valid_lines.insert(0, line)
                idx -= 1
            content = "".join(valid_lines)

        return jsonify({
            "status": "success",
            "file": file_name,
            "size": file_size,
            "content": content
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
