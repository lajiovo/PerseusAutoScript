import os
import json
import datetime
from flask import Blueprint, request, jsonify

# 创建 watch_bp 蓝图
watch_bp = Blueprint('watch_bp', __name__)

# 数据存储路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_CACHE_DIR = os.path.join(BASE_DIR, "servercache", "watch")
os.makedirs(SERVER_CACHE_DIR, exist_ok=True)

DATA_FILE = os.path.join(SERVER_CACHE_DIR, "study_records.json")
WEIGHTS_FILE = os.path.join(SERVER_CACHE_DIR, "subject_weights.json")

def load_json(file_path, default_val):
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default_val

def save_json(file_path, data):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@watch_bp.route("/vela/sync", methods=["POST", "GET"])
def vela_sync():
    """
    接收来自手表端（192.168.10.3:25566/vela/sync）的学习时间同步数据。
    支持 JSON 或表单提交。
    数据结构示例:
    {
      "subject": "数学",
      "duration": 1800,  # 秒
      "timestamp": 1775000000000,
      "date": "2026-09-30",
      "note": "复习微积分"
    }
    """
    if request.method == "GET":
        return jsonify({"status": "ok", "message": "zWatchApi sync endpoint is ready (GET)"})

    try:
        data = {}
        if request.is_json:
            data = request.get_json(silent=True) or {}
        if not data:
            data = request.form.to_dict() or request.args.to_dict()

        if not data:
            return jsonify({"status": "error", "message": "No data received"}), 400

        subject = data.get("subject", "综合科目").strip()
        duration = float(data.get("duration", 0))
        timestamp = int(data.get("timestamp", datetime.datetime.now().timestamp() * 1000))
        date_str = data.get("date", datetime.datetime.now().strftime("%Y-%m-%d"))
        note = data.get("note", "")

        record = {
            "id": int(datetime.datetime.now().timestamp() * 1000),
            "subject": subject,
            "duration": duration,
            "timestamp": timestamp,
            "date": date_str,
            "note": note,
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # 存储记录
        records = load_json(DATA_FILE, [])
        records.append(record)
        save_json(DATA_FILE, records)

        return jsonify({
            "status": "success",
            "message": "学习数据同步成功并已存储",
            "data": record
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@watch_bp.route("/vela/api/stats", methods=["GET"])
def vela_stats():
    """
    提供学习统计分析 API，包含加权分析。
    """
    try:
        records = load_json(DATA_FILE, [])
        weights = load_json(WEIGHTS_FILE, {
            "数学": 1.5,
            "英语": 1.2,
            "专业课": 2.0,
            "政治": 1.0,
            "综合科目": 1.0
        })

        subject_stats = {}
        total_duration = 0
        total_weighted_score = 0

        for r in records:
            sub = r.get("subject", "综合科目")
            dur = float(r.get("duration", 0))
            total_duration += dur
            
            if sub not in subject_stats:
                subject_stats[sub] = {
                    "duration": 0,
                    "count": 0,
                    "weight": weights.get(sub, 1.0)
                }
            subject_stats[sub]["duration"] += dur
            subject_stats[sub]["count"] += 1

        # 计算加权得分与占比
        analyzed_subjects = []
        for sub, info in subject_stats.items():
            w = info["weight"]
            dur = info["duration"]
            weighted_val = dur * w
            total_weighted_score += weighted_val
            analyzed_subjects.append({
                "subject": sub,
                "duration": dur,
                "duration_minutes": round(dur / 60, 2),
                "duration_hours": round(dur / 3600, 2),
                "count": info["count"],
                "weight": w,
                "weighted_score": weighted_val
            })

        return jsonify({
            "status": "success",
            "total_records": len(records),
            "total_duration_seconds": total_duration,
            "total_duration_hours": round(total_duration / 3600, 2),
            "total_weighted_score": total_weighted_score,
            "subjects": analyzed_subjects,
            "weights": weights,
            "raw_records": records[-50:]  # 最近50条
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@watch_bp.route("/vela/api/weights", methods=["POST", "GET"])
def vela_weights():
    """
    获取或更新科目投入权重配置。
    """
    if request.method == "GET":
        weights = load_json(WEIGHTS_FILE, {
            "数学": 1.5,
            "英语": 1.2,
            "专业课": 2.0,
            "政治": 1.0,
            "综合科目": 1.0
        })
        return jsonify({"status": "success", "weights": weights}), 200

    try:
        data = {}
        if request.is_json:
            data = request.get_json(silent=True) or {}
        if not data:
            data = request.form.to_dict() or request.args.to_dict()

        if not data:
            return jsonify({"status": "error", "message": "No weights data provided"}), 400

        weights = load_json(WEIGHTS_FILE, {})
        for k, v in data.items():
            try:
                weights[str(k)] = float(v)
            except ValueError:
                pass

        save_json(WEIGHTS_FILE, weights)
        return jsonify({"status": "success", "message": "权重配置更新成功", "weights": weights}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
