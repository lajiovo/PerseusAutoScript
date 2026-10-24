import os
import json
import time
from flask import Blueprint, request, jsonify
from zAns import process_markdown_and_latex

ans_bp = Blueprint("ans_bp", __name__)

DATA_FILE = os.path.join(os.path.dirname(__file__), "ans_data.json")
TASKS_FILE = os.path.join(os.path.dirname(__file__), "ans_tasks.json")

def _load_data():
    if not os.path.exists(DATA_FILE):
        return {"answers": [], "next_id": 1}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"answers": [], "next_id": 1}

def _save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _load_tasks():
    if not os.path.exists(TASKS_FILE):
        return []
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def _save_tasks(tasks):
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)

def add_task(action, ans_id, target_title=""):
    tasks = _load_tasks()
    task_id = int(time.time() * 1000)
    tasks.append({
        "task_id": task_id,
        "action": action, # "download" or "delete"
        "ans_id": ans_id,
        "title": target_title
    })
    _save_tasks(tasks)

@ans_bp.route("/watch/ans/tasks", methods=["GET"])
def get_watch_tasks():
    tasks = _load_tasks()
    return jsonify({
        "status": "success",
        "tasks": tasks
    })

@ans_bp.route("/watch/ans/task/ack", methods=["POST"])
def ack_watch_task():
    req = request.get_json(silent=True) or {}
    task_id = req.get("task_id")
    if not task_id:
        return jsonify({"status": "error", "message": "missing task_id"}), 400
    
    tasks = _load_tasks()
    tasks = [t for t in tasks if t.get("task_id") != task_id]
    _save_tasks(tasks)
    return jsonify({"status": "success", "remaining": len(tasks)})

@ans_bp.route("/watch/ans/get/<int:ans_id>", methods=["GET"])
def get_ans_detail(ans_id):
    data = _load_data()
    for item in data.get("answers", []):
        if item.get("id") == ans_id:
            return jsonify({"status": "success", "data": item})
    return jsonify({"status": "error", "message": "not found"}), 404

@ans_bp.route("/watch/ans/upload", methods=["POST"])
def upload_ans():
    req = request.get_json(silent=True) or {}
    title = req.get("title", "未命名题目")
    category = req.get("category", "数学")
    raw_markdown = req.get("markdown", "")
    
    parsed_result = process_markdown_and_latex(raw_markdown)
    
    data = _load_data()
    ans_id = data.get("next_id", 1)
    data["next_id"] = ans_id + 1
    
    new_item = {
        "id": ans_id,
        "title": title,
        "category": category,
        "summary": raw_markdown[:60] + ("..." if len(raw_markdown) > 60 else ""),
        "total_pages": parsed_result["total_pages"],
        "pages": parsed_result["pages"]
    }
    
    data["answers"].append(new_item)
    _save_data(data)
    
    # 添加入口同步任务
    add_task("download", ans_id, title)
    
    return jsonify({"status": "success", "id": ans_id})

@ans_bp.route("/watch/ans/list", methods=["GET"])
def list_ans():
    category = request.args.get("category")
    data = _load_data()
    answers = data.get("answers", [])
    if category and category != "全部":
        answers = [a for a in answers if a.get("category") == category]
    
    # 返回简要列表供管理端/手表端展示
    summary_list = [{
        "id": a["id"],
        "title": a["title"],
        "category": a["category"],
        "summary": a["summary"],
        "total_pages": a["total_pages"]
    } for a in answers]
    
    return jsonify({"status": "success", "list": summary_list})
