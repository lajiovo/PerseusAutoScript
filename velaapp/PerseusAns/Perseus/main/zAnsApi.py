import os
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from zAns import ZAnsProcessor

app = Flask(__name__, static_folder="webassets")
CORS(app)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "servercache", "watchans")
os.makedirs(CACHE_DIR, exist_ok=True)

TASKS_FILE = os.path.join(CACHE_DIR, "tasks.json")

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

@app.route("/")
def index():
    return send_from_directory("webassets", "watchans.html")

@app.route("/watch/ans/tasks", methods=["GET"])
def get_tasks():
    tasks = load_tasks()
    return jsonify({"status": "success", "tasks": tasks})

@app.route("/watch/ans/task/ack", methods=["POST"])
def ack_task():
    data = request.json or {}
    task_id = data.get("task_id")
    tasks = load_tasks()
    new_tasks = [t for t in tasks if t.get("id") != task_id]
    save_tasks(new_tasks)
    return jsonify({"status": "success", "remaining_tasks": len(new_tasks)})

@app.route("/watch/ans/get/<ans_id>", methods=["GET"])
def get_ans(ans_id):
    cache_path = os.path.join(CACHE_DIR, f"{ans_id}.json")
    if os.path.exists(cache_path):
        with open(cache_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return jsonify({"status": "success", "source": "cache", "data": data})
    return jsonify({"status": "error", "message": "Solution not found"}), 404

@app.route("/watch/ans/upload", methods=["POST"])
def upload_ans():
    data = request.json or {}
    raw_text = data.get("raw_text", "")
    title = data.get("title", "未命名题目")
    category = data.get("category", "数学")

    if not raw_text:
        return jsonify({"status": "error", "message": "raw_text cannot be empty"}), 400

    # 处理并转 AST
    result = ZAnsProcessor.process_content(raw_text, title=title, category=category)
    ans_id = result["ans_id"]

    # 持久化缓存到 servercache/watchans
    cache_path = os.path.join(CACHE_DIR, f"{ans_id}.json")
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 自动生成同步任务
    tasks = load_tasks()
    # 检查是否已存在该 ans_id 的 download 任务
    tasks = [t for t in tasks if t.get("ans_id") != ans_id]
    new_task = {
        "id": f"task_{ans_id}_{int(os.path.getmtime(cache_path) if os.path.exists(cache_path) else 0)}",
        "action": "download",
        "ans_id": ans_id,
        "title": title,
        "category": category
    }
    tasks.append(new_task)
    save_tasks(tasks)

    return jsonify({"status": "success", "ans_id": ans_id, "result": result})

@app.route("/watch/ans/list", methods=["GET"])
def list_ans():
    items = []
    if os.path.exists(CACHE_DIR):
        for fname in os.listdir(CACHE_DIR):
            if fname.endswith(".json") and fname != "tasks.json":
                fpath = os.path.join(CACHE_DIR, fname)
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        d = json.load(f)
                        items.append({
                            "ans_id": d.get("ans_id"),
                            "title": d.get("title"),
                            "category": d.get("category"),
                            "total_pages": d.get("total_pages")
                        })
                except:
                    pass
    return jsonify({"status": "success", "items": items})

# 管理后台：题目与任务管理 API
@app.route("/watch/ans/manage/delete/<ans_id>", methods=["DELETE", "POST"])
def delete_ans(ans_id):
    cache_path = os.path.join(CACHE_DIR, f"{ans_id}.json")
    if os.path.exists(cache_path):
        os.remove(cache_path)
    # 同时从任务中移除
    tasks = load_tasks()
    tasks = [t for t in tasks if t.get("ans_id") != ans_id]
    save_tasks(tasks)
    return jsonify({"status": "success", "deleted": ans_id})

@app.route("/watch/ans/manage/tasks/add", methods=["POST"])
def add_task_manual():
    data = request.json or {}
    tasks = load_tasks()
    task_id = f"task_manual_{len(tasks)+1}"
    new_task = {
        "id": task_id,
        "action": data.get("action", "download"),
        "ans_id": data.get("ans_id", ""),
        "title": data.get("title", "手动任务"),
        "category": data.get("category", "综合")
    }
    tasks.append(new_task)
    save_tasks(tasks)
    return jsonify({"status": "success", "task": new_task})

@app.route("/watch/ans/manage/tasks/clear", methods=["POST", "DELETE"])
def clear_tasks():
    save_tasks([])
    return jsonify({"status": "success", "message": "Task queue cleared"})

@app.route("/watch/ans/manage/tasks/delete/<task_id>", methods=["DELETE", "POST"])
def delete_task_item(task_id):
    tasks = load_tasks()
    tasks = [t for t in tasks if t.get("id") != task_id]
    save_tasks(tasks)
    return jsonify({"status": "success", "deleted_task_id": task_id})


if __name__ == "__main__":
    print("Starting ZAns API Server on port 25566...")
    app.run(host="0.0.0.0", port=25566, debug=True)
