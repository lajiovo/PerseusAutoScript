import os
import datetime
import threading
import json
from flask import Blueprint, request
from zPerseusLogger import logger
from zMainHandler import run_alas_mumu_check
import zAlas
import zMumu
import zPGRJZ
from zBarkCustom import PerseusErrorMsg, PerseusNotifyMsg

main_loop_bp = Blueprint("main_loop_bp", __name__)

# 定时器相关全局状态控制
timer_thread = None
timer_event = threading.Event()
timer_counter = 0
timer_lock = threading.Lock()

# 全局状态引用
HANDLEPUSH = True
FORCESTOP = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATS_FILE = os.path.join(BASE_DIR, "servercache", "stats.json")
stats_lock = threading.Lock()

def load_stats():
    os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return {
                        "auto_check_count": int(data.get("auto_check_count", 0)),
                        "push_handle_count": int(data.get("push_handle_count", 0)),
                        "total_runtime_seconds": float(data.get("total_runtime_seconds", 0.0))
                    }
        except Exception:
            pass
    return {
        "auto_check_count": 0,
        "push_handle_count": 0,
        "total_runtime_seconds": 0.0
    }

def save_stats(stats):
    os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ 保存统计数据失败: {e}")

def increment_stat(key, amount=1):
    with stats_lock:
        stats = load_stats()
        if key in stats:
            stats[key] += amount
            save_stats(stats)

def set_global_states(hp, fs, qbs):
    global HANDLEPUSH, FORCESTOP, QBOTSTOP
    HANDLEPUSH = hp
    FORCESTOP = fs
    QBOTSTOP = qbs

def stop_timer():
    """停止后台定时检查线程"""
    global timer_event
    timer_event.set()

def start_alas_mumu_check_timer():
    """启动/重启后台定时任务线程：自动执行alas_mumu_check以及Alas/Mumu相关维护"""
    global timer_thread, timer_event
    stop_timer()
    
    timer_event = threading.Event()
    
    def timer_loop():
        global timer_counter
        while not timer_event.is_set():
            if timer_event.wait(120):
                break
            try:
                logger.info("⏰ 触发定时任务: {}", timer_counter)
                if timer_counter < 0:
                    timer_counter = 0
                elif timer_counter < 15:
                    zMumu.once_hidemumu()
                    zAlas.once_hidealas()
                    timer_counter += 1
                    logger.info("已完成常规隐藏任务 {}", timer_counter)
                else:
                    response = run_alas_mumu_check()
                    if response:
                        logger.info("自动化检查成功，返回为 {}", response)
                    else:
                        global HANDLEPUSH
                        HANDLEPUSH = False
                        logger.warning("自动化检查报错, HANDLEPUSH已设置为 {}", HANDLEPUSH)
                    timer_counter = 0
                    logger.info("已完成完整检查任务")

                    # 尝试调用 zOnepush 中的 _load_stats/_save_stats
                    try:
                        import zOnepush
                        if hasattr(zOnepush, "_load_stats") and hasattr(zOnepush, "_save_stats"):
                            stats = zOnepush._load_stats()
                            stats["auto_check_count"] += 1
                            zOnepush._save_stats(stats)
                    except Exception as ex:
                        logger.warning("更新统计数据异常: {}", ex)

                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    log_path = str(os.path.join(current_dir, 'last_checkin.txt'))
                    today_str = datetime.date.today().isoformat()

                    if not os.path.exists(log_path):
                        with open(log_path, 'w', encoding='utf-8') as f:
                            pass
                        last_date = ''
                    else:
                        with open(log_path, 'r', encoding='utf-8') as f:
                            last_date = f.read().strip()

                    if last_date != today_str:
                        try:
                            if not QBOTSTOP:
                                logger.info("正在处理自动化签到")
                            zPGRJZ.run(headless=True)
                        except Exception as e:
                            logger.error("自动签到异常: {}", e)
                        with open(log_path, 'w', encoding='utf-8') as f:
                            f.write(today_str)
            except Exception as e:
                logger.error("⚠️ 定时运行 alas_mumu_check 出现异常: {}", e)
                PerseusErrorMsg("定时运行 alas_mumu_check 出现异常", str(e))

    timer_thread = threading.Thread(target=timer_loop, daemon=True)
    timer_thread.start()

def enter_standby():
    """进入待机状态：停止 loop 并清理进程"""
    global HANDLEPUSH
    HANDLEPUSH = False
    stop_timer()
    try:
        import zOnepush
        if hasattr(zOnepush, "enter_standby"):
            pass
    except Exception:
        pass

    try:
        zAlas.cleanup()
    except Exception as e:
        logger.warning("zAlas.cleanup() 失败: {}", e)
    try:
        zMumu.mumu_kill()
    except Exception as e:
        logger.warning("zMumu.mumu_kill() 失败: {}", e)
    try:
        zAlas.once_hidealas()
        zMumu.once_hidemumu()
    except Exception as e:
        logger.warning("兜底窗口隐藏失败: {}", e)

def format_response(data, status_code=200):
    return data, status_code

@main_loop_bp.route("/stop", methods=["GET", "POST"])
@main_loop_bp.route("/main/stop", methods=["GET", "POST"])
def handle_stop():
    enter_standby()
    stop_timer()
    PerseusNotifyMsg(str({"status": "ok", "message": "服务已进入待机状态"}), "")
    return format_response({"status": "ok", "message": "服务已进入待机状态"}, 200)

@main_loop_bp.route("/forcestop", methods=["GET", "POST"])
@main_loop_bp.route("/main/forcestop", methods=["GET", "POST"])
def force_stop():
    global FORCESTOP
    enter_standby()
    stop_timer()
    FORCESTOP = True
    PerseusNotifyMsg(str({"status": "ok", "message": "服务已进入待机状态"}), "")
    return format_response({"status": "ok", "message": "服务已进入待机状态"}, 200)

@main_loop_bp.route("/forcestart", methods=["GET", "POST"])
@main_loop_bp.route("/main/forcestart", methods=["GET", "POST"])
def force_start():
    global FORCESTOP
    enter_standby()
    FORCESTOP = False
    try:
        zMumu.hidemumu()
        zAlas.start()
        run_alas_mumu_check()
    except Exception as e:
        logger.error("force_start 异常: {}", e)
    start_alas_mumu_check_timer()
    PerseusNotifyMsg(str({"status": "ok", "message": "服务已恢复"}), "")
    return format_response({"status": "ok", "message": "服务已恢复"}, 200)

@main_loop_bp.route("/start", methods=["GET", "POST"])
@main_loop_bp.route("/main/start", methods=["GET", "POST"])
def handle_start():
    global HANDLEPUSH, FORCESTOP
    if FORCESTOP:
        return format_response({"status": "error", "message": "服务已被强制禁用"}, 200)
    else:
        HANDLEPUSH = True
        try:
            zMumu.hidemumu()
            zAlas.start()
            run_alas_mumu_check()
        except Exception as e:
            logger.error("handle_start 异常: {}", e)
        start_alas_mumu_check_timer()
        PerseusNotifyMsg(str({"status": "ok", "message": "服务已重新启动并恢复处理"}), "")
        return format_response({"status": "ok", "message": "服务已重新启动并恢复处理"}, 200)
