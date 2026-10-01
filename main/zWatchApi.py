import os
import json
import datetime
from flask import Blueprint, request, jsonify
import zBarkCustom

# 创建 watch_bp 蓝图
watch_bp = Blueprint('watch_bp', __name__)

# 数据存储路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_CACHE_DIR = os.path.join(BASE_DIR, "servercache", "watch")
os.makedirs(SERVER_CACHE_DIR, exist_ok=True)

DATA_FILE = os.path.join(SERVER_CACHE_DIR, "study_records.json")
WEIGHTS_FILE = os.path.join(SERVER_CACHE_DIR, "subject_weights.json")

# 默认权重配置（语文1.7、英语1.5、数学1.2、化学1.2、生物1.1、物理1.0）
DEFAULT_WEIGHTS = {
    "语文": 1.7,
    "英语": 1.5,
    "数学": 1.2,
    "化学": 1.2,
    "生物": 1.1,
    "物理": 1.0,
    "综合科目": 1.0
}

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

def generate_record_fingerprint(record):
    """
    基于唯一记录指纹生成：subject + dateStr/date + minutes (或 timestamp)
    用于自动去重机制
    """
    subject = record.get("subject") or record.get("subjectName") or "综合科目"
    minutes = record.get("minutes") or round(float(record.get("duration", 0)) / 60, 2)
    timestamp = record.get("timestamp") or 0
    date_str = record.get("dateStr") or record.get("date") or ""
    # 如果有精确timestamp，取整到秒或分钟粒度防止重复提交，或者组合唯一指纹
    if timestamp:
        # 允许相同时间戳或1秒内去重
        return f"{subject}_{minutes}_{int(timestamp / 1000)}"
    return f"{subject}_{minutes}_{date_str}"

@watch_bp.route("/vela/sync", methods=["POST", "GET"])
def vela_sync():
    """
    接收来自手表端或批量同步的学习时间数据，增加强大的自动去重机制。
    """
    if request.method == "GET":
        return jsonify({"status": "ok", "message": "zWatchApi sync endpoint is active with auto-deduplication"})

    try:
        data = {}
        if request.is_json:
            data = request.get_json(silent=True) or {}
        if not data:
            data = request.form.to_dict() or request.args.to_dict()

        if not data:
            return jsonify({"status": "error", "message": "No data received"}), 400

        existing_records = load_json(DATA_FILE, [])
        
        # 建立现有记录的指纹集合用于去重
        fingerprints = set()
        for r in existing_records:
            fingerprints.add(generate_record_fingerprint(r))

        incoming_records = []
        if "records" in data and isinstance(data["records"], list):
            incoming_records = data["records"]
        else:
            incoming_records = [data]

        added_count = 0
        duplicate_count = 0

        for item in incoming_records:
            subject = item.get("subject") or item.get("subjectName") or "综合科目"
            minutes = float(item.get("minutes") or (float(item.get("duration", 0)) / 60))
            timestamp = int(item.get("timestamp", datetime.datetime.now().timestamp() * 1000))
            date_str = item.get("dateStr") or item.get("date") or datetime.datetime.now().strftime("%Y-%m-%d")
            note = item.get("note", "")

            normalized_item = {
                "id": timestamp,
                "subject": subject,
                "minutes": minutes,
                "duration": minutes * 60,
                "timestamp": timestamp,
                "dateStr": date_str,
                "note": note,
                "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            fp = generate_record_fingerprint(normalized_item)
            if fp in fingerprints:
                duplicate_count += 1
            else:
                fingerprints.add(fp)
                existing_records.append(normalized_item)
                added_count += 1

        save_json(DATA_FILE, existing_records)

        zBarkCustom.PerseusNotifyMsg("vela_sync()",str({
            "status": "success",
            "message": f"同步完成：新增 {added_count} 条记录，自动过滤重复 {duplicate_count} 条",
            "added_count": added_count,
            "duplicate_count": duplicate_count,
            "total_records": len(existing_records)
        }))

        return jsonify({
            "status": "success",
            "message": f"同步完成：新增 {added_count} 条记录，自动过滤重复 {duplicate_count} 条",
            "added_count": added_count,
            "duplicate_count": duplicate_count,
            "total_records": len(existing_records)
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@watch_bp.route("/vela/api/stats", methods=["GET"])
def vela_stats():
    """
    提供多天、多周、多科综合视图与统计图表 API，包含精确权重与加权分析。
    """
    try:
        records = load_json(DATA_FILE, [])
        weights = load_json(WEIGHTS_FILE, DEFAULT_WEIGHTS)

        subject_stats = {}
        daily_stats = {}
        weekly_stats = {}
        total_duration_minutes = 0
        total_weighted_score = 0

        for r in records:
            sub = r.get("subject") or r.get("subjectName") or "综合科目"
            mins = float(r.get("minutes") or (float(r.get("duration", 0)) / 60))
            total_duration_minutes += mins

            # 日期归类
            date_str = r.get("dateStr") or r.get("date")
            if not date_str and r.get("timestamp"):
                dt = datetime.datetime.fromtimestamp(r.get("timestamp") / 1000)
                date_str = dt.strftime("%Y-%m-%d")
            if not date_str:
                date_str = datetime.datetime.now().strftime("%Y-%m-%d")

            # 统计科目
            w = weights.get(sub, 1.0)
            if sub not in subject_stats:
                subject_stats[sub] = {
                    "subject": sub,
                    "minutes": 0,
                    "count": 0,
                    "weight": w,
                    "weighted_score": 0
                }
            subject_stats[sub]["minutes"] += mins
            subject_stats[sub]["count"] += 1

            # 统计每日
            if date_str not in daily_stats:
                daily_stats[date_str] = 0
            daily_stats[date_str] += mins

        # 计算加权分值
        analyzed_subjects = []
        for sub, info in subject_stats.items():
            w = info["weight"]
            mins = info["minutes"]
            weighted_val = mins * w
            total_weighted_score += weighted_val
            analyzed_subjects.append({
                "subject": sub,
                "minutes": round(mins, 1),
                "hours": round(mins / 60, 2),
                "count": info["count"],
                "weight": w,
                "weighted_score": round(weighted_val, 1)
            })

        # 整理多天趋势（按日期升序排序）
        sorted_daily = [{"date": d, "minutes": m} for d, m in sorted(daily_stats.items())]

        return jsonify({
            "status": "success",
            "total_records": len(records),
            "total_duration_minutes": round(total_duration_minutes, 1),
            "total_duration_hours": round(total_duration_minutes / 60, 2),
            "total_weighted_score": round(total_weighted_score, 1),
            "subjects": analyzed_subjects,
            "daily_trend": sorted_daily,
            "weights": weights,
            "records": records[-100:]  # 最近100条
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@watch_bp.route("/vela/api/weights", methods=["POST", "GET"])
def vela_weights():
    """
    获取或更新科目投入权重配置。
    """
    if request.method == "GET":
        weights = load_json(WEIGHTS_FILE, DEFAULT_WEIGHTS)
        return jsonify({"status": "success", "weights": weights}), 200

    try:
        data = {}
        if request.is_json:
            data = request.get_json(silent=True) or {}
        if not data:
            data = request.form.to_dict() or request.args.to_dict()

        if not data:
            return jsonify({"status": "error", "message": "No weights data provided"}), 400

        weights = load_json(WEIGHTS_FILE, DEFAULT_WEIGHTS)
        for k, v in data.items():
            try:
                weights[str(k)] = float(v)
            except ValueError:
                pass

        save_json(WEIGHTS_FILE, weights)
        return jsonify({"status": "success", "message": "权重配置更新成功", "weights": weights}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@watch_bp.route("/vela/api/clear", methods=["POST"])
def vela_clear():
    """
    清空所有学习记录。
    """
    try:
        save_json(DATA_FILE, [])
        return jsonify({"status": "success", "message": "所有学习记录已清空"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
