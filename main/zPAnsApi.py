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
    # 检查请求是否带有非手表标记（例如来自网页端控制台的调用）
    # 兼容 request.args 以及任何形式的 client 参数
    try:
        if request.args.get("client") == "web":
            return
        if request.is_json and request.json and request.json.get("client") == "web":
            return
    except:
        pass

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

AST_TAGS = {"t", "txt", "r", "f", "sq", "sup_g", "sub_g", "sup", "sub", "vec", "chem_seq", "chem_a", "m", "paragraph", "h1", "h2", "h3", "c"}


def ast_to_content(ast_nodes):
    """把 zLatex 的 ['r', n1, n2] / 单节点 转成手表端可遍历的 children 列表。"""
    if ast_nodes is None:
        return []
    if isinstance(ast_nodes, list) and ast_nodes:
        head = ast_nodes[0]
        if head == "r":
            if len(ast_nodes) == 2 and isinstance(ast_nodes[1], list):
                inner = ast_nodes[1]
                if inner and isinstance(inner[0], str) and inner[0] in AST_TAGS:
                    return [inner]
                return inner
            return ast_nodes[1:]
        if isinstance(head, str) and head in AST_TAGS:
            return [ast_nodes]
        return ast_nodes
    return [ast_nodes]


def inspect_pages(pages):
    page_count = len(pages or [])
    block_count = 0
    ast_chars = 0
    for page in pages or []:
        blocks = page.get("blocks") if isinstance(page, dict) else page
        if not isinstance(blocks, list):
            continue
        block_count += len(blocks)
        for block in blocks:
            if isinstance(block, dict):
                ast_chars += len(str(block.get("raw") or ""))
            elif isinstance(block, list):
                ast_chars += 1
    return {
        "page_count": page_count,
        "block_count": block_count,
        "pages_empty": page_count == 0,
        "blocks_empty": block_count == 0,
        "ast_empty": ast_chars == 0,
    }


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
            content = ast_to_content(ast_nodes)
            blocks.append({
                "block_type": block_type,
                "type": block_type,
                "raw": line,
                "value": line,
                "ast": ast_nodes,
                "content": content,
                "children": content,
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
        summary = ""
        for block in blocks:
            if block.get("raw"):
                summary = block["raw"].replace("\n", " ").strip()[:24]
                break
        flags = inspect_pages(pages)
        result = {
            "ans_id": ans_id,
            "id": ans_id,
            "title": title or "未命名解析",
            "category": category,
            "summary": summary,
            "total_pages": len(pages),
            "pages": pages,
            "raw_text": raw_text,
            "pages_empty": flags["pages_empty"],
            "blocks_empty": flags["blocks_empty"],
            "raw_empty": not bool((raw_text or "").strip()),
            "block_count": flags["block_count"]
        }
        return result


def compact_ans_payload(data, ans_id):
    pages = data.get("pages") or []
    flags = inspect_pages(pages)
    summary = data.get("summary") or (data.get("raw_text") or "").replace("\n", " ").strip()[:24]
    return {
        "ans_id": data.get("ans_id") or ans_id,
        "id": data.get("id") or data.get("ans_id") or ans_id,
        "title": data.get("title") or "未命名解析",
        "category": data.get("category") or "数学",
        "summary": summary,
        "total_pages": data.get("total_pages") or len(pages),
        "pages": pages,
        "pages_empty": flags["pages_empty"],
        "blocks_empty": flags["blocks_empty"],
        "raw_empty": not bool((data.get("raw_text") or "").strip()),
        "ast_empty": flags["ast_empty"],
        "block_count": flags["block_count"],
        "has_raw": bool((data.get("raw_text") or "").strip())
    }

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
            if "ans_id" not in data:
                data["ans_id"] = ans_id
            compact = str(request.args.get("compact", "")).lower() in ("1", "true", "yes")
            payload = compact_ans_payload(data, ans_id) if compact else data
            return jsonify({"status": "success", "source": "cache", "data": payload})
    return jsonify({"status": "error", "message": "Solution not found"}), 404

@p_ans_bp.route("/watch/pans/upload", methods=["POST"])
def upload_pans_ans():
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
    log_api_request("/watch/pans/list", dict(request.args))
    items = []
    if os.path.exists(CACHE_DIR):
        for fname in os.listdir(CACHE_DIR):
            if fname.endswith(".json") and fname not in ["tasks.json", "recent_api_logs.json"]:
                fpath = os.path.join(CACHE_DIR, fname)
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        d = json.load(f)
                        flags = inspect_pages(d.get("pages") or [])
                        items.append({
                            "ans_id": d.get("ans_id"),
                            "id": d.get("ans_id") or d.get("id"),
                            "title": d.get("title"),
                            "category": d.get("category", "数学"),
                            "total_pages": d.get("total_pages"),
                            "summary": d.get("summary") or "",
                            "pages_empty": flags["pages_empty"],
                            "blocks_empty": flags["blocks_empty"],
                            "raw_empty": not bool((d.get("raw_text") or "").strip()),
                            "block_count": flags["block_count"]
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
    log_api_request("/watch/pans/sync_status", dict(request.args))
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
                        flags = inspect_pages(d.get("pages") or [])
                        items.append({
                            "ans_id": ans_id,
                            "title": d.get("title"),
                            "category": d.get("category", "数学"),
                            "synced": is_synced,
                            "summary": d.get("summary") or "",
                            "pages_empty": flags["pages_empty"],
                            "blocks_empty": flags["blocks_empty"],
                            "raw_empty": not bool((d.get("raw_text") or "").strip()),
                            "block_count": flags["block_count"]
                        })
                except:
                    pass
    return jsonify({"status": "success", "pending_tasks_count": len(tasks), "items": items})
