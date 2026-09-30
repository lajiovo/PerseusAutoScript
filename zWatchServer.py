import os
import json
import datetime
from flask import Blueprint, request, jsonify, send_from_directory

# 兼容命名 zWatchServer 作为独立模块或蓝图挂载入口
# 如果直接作为独立脚本运行，可以提供完整的 Flask 实例或 Blueprint
zWatchServer_bp = Blueprint('zWatchServer_bp', __name__)

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

@zWatchServer_bp.route("/api/watch/stats", methods=["GET"])
def api_watch_stats():
    """
    提供网页阅览和统计分析所需的 API 接口：获取学习统计与加权分析数据
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
            "records": list(reversed(records))  # 最新排在前
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@zWatchServer_bp.route("/api/watch/weights", methods=["POST", "GET"])
def api_watch_weights():
    """
    科目投入权重规划与调整接口
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
            return jsonify({"status": "error", "message": "No weights provided"}), 400

        weights = load_json(WEIGHTS_FILE, {})
        for k, v in data.items():
            try:
                weights[str(k)] = float(v)
            except ValueError:
                pass

        save_json(WEIGHTS_FILE, weights)
        return jsonify({"status": "success", "message": "科目权重已成功更新", "weights": weights}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@zWatchServer_bp.route("/api/watch/clear", methods=["POST", "GET"])
def api_watch_clear():
    """
    清空所有学习记录数据
    """
    try:
        save_json(DATA_FILE, [])
        return jsonify({"status": "success", "message": "所有学习记录已清空"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
