import os
import datetime
import json
import threading
from flask import Blueprint, request, jsonify, send_from_directory
from zPerseusLogger import logger

az_scheduler_bp = Blueprint("az_scheduler_bp", __name__, url_prefix="/schedule")

# 数据文件路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "servercache", "scheduler_config.json")
RUN_LOG_FILE = os.path.join(BASE_DIR, "servercache", "scheduler_run_log.json")
config_lock = threading.Lock()
log_lock = threading.Lock()

def get_default_config():
    return {
        "master_enabled": True,             # 总开关：任务规划功能开关
        "default_enabled": True,            # 默认安排开关：默认情况下是否允许运行
        "default_intervals": [              # 支持分时段任务：默认每日允许运行的时段列表
            {"start": "08:00", "end": "12:00"},
            {"start": "14:00", "end": "23:30"}
        ],
        "daily_limit_minutes": 300,         # 当日运行时间上限（分钟）
        "specific_dates": {}                # 近一个月的特殊情况配置
    }

def load_config():
    with config_lock:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        default = get_default_config()
                        for k, v in default.items():
                            if k not in data:
                                data[k] = v
                        if "default_start_time" in data and "default_intervals" not in data:
                            st = data.pop("default_start_time", "08:00")
                            et = data.pop("default_end_time", "23:30")
                            data["default_intervals"] = [{"start": st, "end": et}]
                        return data
            except Exception as e:
                logger.error(f"⚠️ 读取调度配置文件失败: {e}")
        cfg = get_default_config()
        save_config(cfg)
        return cfg

def save_config(cfg):
    with config_lock:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"⚠️ 保存调度配置文件失败: {e}")

def load_run_logs():
    with log_lock:
        os.makedirs(os.path.dirname(RUN_LOG_FILE), exist_ok=True)
        if os.path.exists(RUN_LOG_FILE):
            try:
                with open(RUN_LOG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
            except Exception as e:
                logger.error(f"⚠️ 读取任务运行日志失败: {e}")
        return []

def save_run_logs(logs):
    with log_lock:
        os.makedirs(os.path.dirname(RUN_LOG_FILE), exist_ok=True)
        try:
            with open(RUN_LOG_FILE, "w", encoding="utf-8") as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"⚠️ 保存任务运行日志失败: {e}")

def record_run_status(status_data):
    logs = load_run_logs()
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    date_str = status_data.get("date", today_str)
    
    found = False
    for item in logs:
        if item.get("date") == date_str:
            item.update(status_data)
            item["update_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            found = True
            break
    if not found:
        status_data["date"] = date_str
        status_data.setdefault("update_time", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        logs.append(status_data)
    
    logs.sort(key=lambda x: x.get("date", ""), reverse=True)
    save_run_logs(logs)

def check_can_run_now():
    """
    核心检查函数：
    参考当前时间、总开关、默认分时段、具体时间段开关、近一个月的特殊情况、当日运行时间上限。
    返回: (can_run: bool, reason: str)
    """
    cfg = load_config()
    if not cfg.get("master_enabled", True):
        return False, "任务规划总开关已关闭"
    
    now = datetime.datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    current_time_str = now.strftime("%H:%M")
    
    specific_dates = cfg.get("specific_dates", {})
    day_config = specific_dates.get(today_str)
    
    if day_config is not None:
        if not day_config.get("enabled", True):
            return False, f"今日 ({today_str}) 特殊设置为不运行"
        intervals = day_config.get("intervals", [])
        daily_limit = int(day_config.get("daily_limit_minutes", cfg.get("daily_limit_minutes", 300)))
    else:
        if not cfg.get("default_enabled", True):
            return False, "默认规划设置为不运行"
        intervals = cfg.get("default_intervals", [])
        daily_limit = int(cfg.get("daily_limit_minutes", 300))
        
    in_any_interval = False
    interval_desc = []
    for interval in intervals:
        st = interval.get("start", "00:00")
        et = interval.get("end", "23:59")
        interval_desc.append(f"{st}~{et}")
        if st <= current_time_str <= et:
            in_any_interval = True
            break
            
    if not intervals:
        in_any_interval = True
    elif not in_any_interval:
        return False, f"当前时间 {current_time_str} 不在允许运行的时段 [{', '.join(interval_desc)}] 内"
        
    logs = load_run_logs()
    today_log = next((item for item in logs if item.get("date") == today_str), None)
    accumulated_minutes = 0
    if today_log:
        accumulated_minutes = float(today_log.get("runtime_minutes", 0))
        
    if accumulated_minutes >= daily_limit:
        return False, f"已达到当日运行时间上限 ({accumulated_minutes:.1f}分钟 / 上限 {daily_limit}分钟)"
        
    return True, "允许运行"


# ==================== API 路由定义 ====================

@az_scheduler_bp.route("/config", methods=["GET"])
def api_get_config():
    cfg = load_config()
    return jsonify({"status": "success", "data": cfg})

@az_scheduler_bp.route("/config", methods=["POST"])
def api_save_config():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "error", "message": "无效的JSON数据"}), 400
    
    cfg = load_config()
    for key in ["master_enabled", "default_enabled", "default_intervals", "daily_limit_minutes", "specific_dates"]:
        if key in data:
            cfg[key] = data[key]
            
    save_config(cfg)
    logger.success("✅ 任务规划配置已更新: {}", cfg)
    return jsonify({"status": "success", "message": "配置保存成功", "data": cfg})

@az_scheduler_bp.route("/status", methods=["GET"])
def api_get_status():
    can_run, reason = check_can_run_now()
    cfg = load_config()
    logs = load_run_logs()
    
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    today_log = next((item for item in logs if item.get("date") == today_str), {"date": today_str, "runtime_minutes": 0, "status": "unknown"})
    
    return jsonify({
        "status": "success",
        "can_run": can_run,
        "reason": reason,
        "current_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "today_log": today_log,
        "config": cfg,
        "recent_logs": logs[:30]
    })

@az_scheduler_bp.route("/report", methods=["POST"])
def api_report_status():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "error", "message": "无效的JSON数据"}), 400
        
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    date_str = data.get("date", today_str)
    
    logs = load_run_logs()
    today_log = next((item for item in logs if item.get("date") == date_str), None)
    
    current_minutes = 0.0
    if today_log:
        current_minutes = float(today_log.get("runtime_minutes", 0.0))
        
    input_minutes = float(data.get("runtime_minutes", 0.0))
    if data.get("add_minutes", False):
        final_minutes = current_minutes + input_minutes
    else:
        final_minutes = input_minutes
        
    status_payload = {
        "date": date_str,
        "runtime_minutes": round(final_minutes, 2),
        "status": data.get("status", "running"),
        "message": data.get("message", "运行状态更新")
    }
    
    record_run_status(status_payload)
    logger.info("📈 [任务规划看板] 收到状态上报: {}", status_payload)
    return jsonify({"status": "success", "message": "运行状态已更新", "data": status_payload})

@az_scheduler_bp.route("/", defaults={"filename": "schedule.html"}, methods=["GET"])
@az_scheduler_bp.route("/<path:filename>", methods=["GET"])
def serve_scheduler_ui(filename):
    webassets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "webassets"))
    if not filename:
        filename = "schedule.html"
    target = os.path.join(webassets_dir, filename)
    if os.path.exists(target) and os.path.isfile(target):
        return send_from_directory(webassets_dir, filename)
    return jsonify({"status": "error", "message": f"文件 {filename} 不存在"}), 404
