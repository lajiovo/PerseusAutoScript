import os
import json
import hashlib
from flask import Blueprint, request, jsonify
from zLatex import LaTeXASTParser

p_ans_bp = Blueprint("p_ans_bp", __name__)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "servercache", "watchans")
os.makedirs(CACHE_DIR, exist_ok=True)

TASKS_FILE = os.path.join(CACHE_DIR, "tasks.json")
LOGS_FILE = os.path.join(CACHE_DIR, "recent_api_logs.json")

def load_tasks():
    if os.path.exists(TASKS_FILE):
        try:
            with open(TASKS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_tasks(tasks):
    with open(TASKS_FILE, 'w', encoding='utf-8') as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)

def log_api_request(endpoint, data):
    # 只记录来自手表的 API 请求（通过请求头或路径中确认手表标识，或者凡是 /watch/pans/ 且明确包含同步/获取/ack等操作）
    # 手表通常调用 /watch/pans/tasks, /watch/pans/get/, /watch/pans/task/ack
    logs = []
    if os.path.exists(LOGS_FILE):
        try:
            with open(LOGS_FILE, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        except:
            logs = []
    
    logs.insert(0, {
        "time": __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "endpoint": endpoint,
        "data": data
    })
    logs = logs[:50] # 保留最近50条
    with open(LOGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

class PAnsProcessor:
    @staticmethod
    def process_content(raw_text, title="", category="数学"):
        parser = LaTeXASTParser()
        lines = raw_text.split('\n')
        blocks = []
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith("%"):
                continue
            
            block_type = "paragraph"
            if line.startswith("# "):
                block_type = "h1"
                line = line[2:].strip()
            elif line.startswith("## "):
                block_type = "h2"
                line = line[3:].strip()
            elif line.startswith("### "):
                block_type = "h3"
                line = line[4:].strip()
            elif line.startswith("$$") and line.endswith("$$"):
                block_type = "block_math"
                line = line[2:-2].strip()

            ast_nodes = parser.parse_latex(line)
            blocks.append({
                "block_type": block_type,
                "raw": line,
                "ast": ast_nodes,
                "length": len(line)
            })

        pages = []
        current_page_blocks = []
        current_page_len = 0
        target_page_len = 350

        for block in blocks:
            b_len = block["length"]
            if current_page_len + b_len > target_page_len and current_page_blocks:
                pages.append({
                    "page_index": len(pages) + 1,
                    "blocks": current_page_blocks
                })
                current_page_blocks = [block]
                current_page_len = b_len
            else:
                current_page_blocks.append(block)
                current_page_len += b_len

        if current_page_blocks:
            pages.append({
                "page_index": len(pages) + 1,
                "blocks": current_page_blocks
            })

        if not pages:
            pages.append({"page_index": 1, "blocks": []})

        ans_id = hashlib.md5(raw_text.encode('utf-8')).hexdigest()[:8]
        result = {
            "ans_id": ans_id,
            "id": ans_id,
            "title": title or "未命名解析",
            "category": category,
            "total_pages": len(pages),
            "pages": pages,
            "raw_text": raw_text
        }
        return result

@p_ans_bp.route("/watch/pans/tasks", methods=["GET"])
def get_pans_tasks():
    log_api_request("/watch/pans/tasks", dict(request.args))
    tasks = load_tasks()
    return jsonify({"status": "success", "tasks": tasks})

@p_ans_bp.route("/watch/pans/task/ack", methods=["POST"])
def ack_pans_task():
    data = request.json or {}
    log_api_request("/watch/pans/task/ack", data)
    task_id = data.get("task_id") or data.get("id")
    tasks = load_tasks()
    new_tasks = [t for t in tasks if t.get("id") != task_id and t.get("task_id") != task_id]
    save_tasks(new_tasks)
    return jsonify({"status": "success", "remaining_tasks": len(new_tasks)})

@p_ans_bp.route("/watch/pans/get/<ans_id>", methods=["GET"])
def get_pans_ans(ans_id):
    log_api_request(f"/watch/pans/get/{ans_id}", dict(request.args))
    cache_path = os.path.join(CACHE_DIR, f"{ans_id}.json")
    if os.path.exists(cache_path):
        with open(cache_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if "id" not in data:
                data["id"] = ans_id
            return jsonify({"status": "success", "source": "cache", "data": data})
    return jsonify({"status": "error", "message": "Solution not found"}), 404

@p_ans_bp.route("/watch/pans/upload", methods=["POST"])
def upload_pans_ans():
    # 后台网页端上传不计入“手表API请求”
    data = request.json or {}
    raw_text = data.get("raw_text", "")
    title = data.get("title", "未命名题目")
    category = data.get("category", "数学")

    if not raw_text:
        return jsonify({"status": "error", "message": "raw_text cannot be empty"}), 400

    result = PAnsProcessor.process_content(raw_text, title=title, category=category)
    ans_id = result["ans_id"]

    cache_path = os.path.join(CACHE_DIR, f"{ans_id}.json")
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    tasks = load_tasks()
    tasks = [t for t in tasks if t.get("ans_id") != ans_id]
    task_id = f"task_{ans_id}_{int(os.path.getmtime(cache_path) if os.path.exists(cache_path) else 0)}"
    new_task = {
        "id": task_id,
        "task_id": task_id,
        "action": "download",
        "ans_id": ans_id,
        "title": title,
        "category": category
    }
    tasks.append(new_task)
    save_tasks(tasks)

    return jsonify({"status": "success", "ans_id": ans_id, "result": result})

@p_ans_bp.route("/watch/pans/list", methods=["GET"])
def list_pans_ans():
    items = []
    if os.path.exists(CACHE_DIR):
        for fname in os.listdir(CACHE_DIR):
            if fname.endswith(".json") and fname not in ["tasks.json", "recent_api_logs.json"]:
                fpath = os.path.join(CACHE_DIR, fname)
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        d = json.load(f)
                        items.append({
                            "ans_id": d.get("ans_id"),
                            "id": d.get("ans_id"),
                            "title": d.get("title"),
                            "category": d.get("category", "数学"),
                            "total_pages": d.get("total_pages")
                        })
                except:
                    pass
    return jsonify({"status": "success", "items": items})

@p_ans_bp.route("/watch/pans/delete/<ans_id>", methods=["DELETE", "POST"])
def delete_pans_ans(ans_id):
    cache_path = os.path.join(CACHE_DIR, f"{ans_id}.json")
    if os.path.exists(cache_path):
        os.remove(cache_path)
    tasks = load_tasks()
    tasks = [t for t in tasks if t.get("ans_id") != ans_id and t.get("id") != ans_id]
    save_tasks(tasks)
    return jsonify({"status": "success", "deleted": ans_id})

@p_ans_bp.route("/watch/pans/resync/<ans_id>", methods=["POST"])
def resync_pans_ans(ans_id):
    cache_path = os.path.join(CACHE_DIR, f"{ans_id}.json")
    if not os.path.exists(cache_path):
        return jsonify({"status": "error", "message": "Solution not found"}), 404
    
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            d = json.load(f)
            title = d.get("title", "未命名题目")
            category = d.get("category", "数学")
    except:
        title = "未命名题目"
        category = "数学"

    tasks = load_tasks()
    tasks = [t for t in tasks if t.get("ans_id") != ans_id]
    task_id = f"task_{ans_id}_{int(os.path.getmtime(cache_path) if os.path.exists(cache_path) else 0)}"
    new_task = {
        "id": task_id,
        "task_id": task_id,
        "action": "download",
        "ans_id": ans_id,
        "title": title,
        "category": category
    }
    tasks.append(new_task)
    save_tasks(tasks)
    return jsonify({"status": "success", "message": f"已重新加入同步队列: {title}", "task": new_task})

@p_ans_bp.route("/watch/pans/logs", methods=["GET"])
def get_recent_logs():
    logs = []
    if os.path.exists(LOGS_FILE):
        try:
            with open(LOGS_FILE, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        except:
            logs = []
    return jsonify({"status": "success", "logs": logs})

@p_ans_bp.route("/watch/pans/logs/clear", methods=["POST", "DELETE"])
def clear_recent_logs():
    if os.path.exists(LOGS_FILE):
        with open(LOGS_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)
    return jsonify({"status": "success", "message": "手表 API 请求日志已清空"})

@p_ans_bp.route("/watch/pans/sync_status", methods=["GET"])
def get_sync_status():
    tasks = load_tasks()
    items = []
    if os.path.exists(CACHE_DIR):
        for fname in os.listdir(CACHE_DIR):
            if fname.endswith(".json") and fname not in ["tasks.json", "recent_api_logs.json"]:
                fpath = os.path.join(CACHE_DIR, fname)
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        d = json.load(f)
                        ans_id = d.get("ans_id")
                        is_synced = not any(t.get("ans_id") == ans_id for t in tasks)
                        items.append({
                            "ans_id": ans_id,
                            "title": d.get("title"),
                            "category": d.get("category", "数学"),
                            "synced": is_synced
                        })
                except:
                    pass
    return jsonify({"status": "success", "pending_tasks_count": len(tasks), "items": items})
