import os
import datetime
import threading
import json
from flask import Blueprint, request
from zPerseusLogger import logger
from zMainHandler import run_alas_mumu_check ,handlerun,Handlepush
import zAlas
import zMumu
import zPGRJZ
from zBarkCustom import PerseusErrorMsg, PerseusNotifyMsg
import zQbotApi

main_loop_bp = Blueprint("main_loop_bp", __name__)

# 定时器相关全局状态控制
timer_thread = None
timer_event = threading.Event()
timer_counter = 15
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
        logger.warning(f"⚠️ 保存统计数据失败: {e}")

def increment_stat(key, amount=1):
    with stats_lock:
        stats = load_stats()
        if key in stats:
            stats[key] += amount
            save_stats(stats)

def set_global_states(hp, fs, qbs):
    global HANDLEPUSH, FORCESTOP
    HANDLEPUSH = hp
    FORCESTOP = fs
    zQbotApi.QBOTSTOP = qbs

def stop_timer(timeout=10):
    """停止后台定时检查线程，并等待线程退出"""
    global timer_thread, timer_event

    with timer_lock:
        event = timer_event
        thread = timer_thread

        if event:
            event.set()

    if thread and thread.is_alive():
        if thread is not threading.current_thread():
            thread.join(timeout=timeout)

    if thread and thread.is_alive():
        logger.warning("⚠️ 定时器线程仍在运行，可能正在执行任务")
        return False

    with timer_lock:
        if timer_thread is thread:
            timer_thread = None

    logger.info("定时器线程已停止")
    return True

def start_alas_mumu_check_timer():
    """启动/重启后台定时任务线程"""
    global timer_thread, timer_event,HANDLEPUSH,FORCESTOP

    if FORCESTOP :
        return False

    # 先停止旧线程
    if not stop_timer(timeout=10):
        logger.error("旧定时器尚未退出，取消本次启动")
        return False

    with timer_lock:
        stop_event = threading.Event()
        timer_event = stop_event

        def timer_loop(stop_event):
            global timer_counter,HANDLEPUSH,FORCESTOP

            while not stop_event.is_set():

                # 等待120秒，支持随时响应停止信号
                if stop_event.wait(120):
                    break
                if not HANDLEPUSH:
                    logger.warning("HANDLEPUSH已关闭但仍在执行循环")
                    continue
                try:
                    logger.info(f"⏰ 触发定时任务: {timer_counter},handp{HANDLEPUSH},fstop{FORCESTOP}")
                    if timer_counter < 0:
                        timer_counter = 0
                    elif timer_counter < 15:
                        zMumu.once_hidemumu()
                        zAlas.once_hidealas()
                        timer_counter += 1
                        logger.success("已完成常规隐藏任务 {}", timer_counter)
                    else:
                        response = run_alas_mumu_check(stop_event=stop_event)
                        if response:
                            logger.success("自动化检查成功，返回为 {}", response)
                        else:
                            HANDLEPUSH = False
                            logger.error("自动化检查报错, HANDLEPUSH已设置为 {}", HANDLEPUSH)
                        timer_counter = 0
                        logger.success("已完成完整检查任务")

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
                                if not zQbotApi.QBOTSTOP:
                                    logger.info("执行Qbot重启")
                                    zQbotApi.start_qbot_process()
                                    logger.info("正在处理自动化签到")
                                zPGRJZ.run(headless=True)
                            except Exception as e:
                                logger.warning("自动签到异常: {}", e)
                            with open(log_path, 'w', encoding='utf-8') as f:
                                f.write(today_str)
                except Exception as e:
                    logger.error("⚠️ 定时运行 alas_mumu_check 出现异常: {}", e)
                    PerseusErrorMsg("定时运行 alas_mumu_check 出现异常", str(e))
                    
        timer_thread = threading.Thread(
            target=timer_loop,
            args=(stop_event,),
            name="AlasMumuCheckTimer",
            daemon=True
        )

        timer_thread.start()

    logger.success("后台定时器已启动")
    return True

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
        logger.error("zAlas.cleanup() 失败: {}", e)
    try:
        zMumu.mumu_kill()
    except Exception as e:
        logger.error("zMumu.mumu_kill() 失败: {}", e)
    try:
        zAlas.once_hidealas()
        zMumu.once_hidemumu()
    except Exception as e:
        logger.error("兜底窗口隐藏失败: {}", e)

def format_response(data, status_code=200):
    return data, status_code

@main_loop_bp.route("/stop", methods=["GET", "POST"])
@main_loop_bp.route("/main/stop", methods=["GET", "POST"])
def handle_stop():
    global HANDLEPUSH
    HANDLEPUSH = False
    enter_standby()
    stop_timer()
    PerseusNotifyMsg(str({"status": "ok", "message": "服务已进入待机状态"}), "")
    return format_response({"status": "ok", "message": "服务已进入待机状态"}, 200)

@main_loop_bp.route("/forcestop", methods=["GET", "POST"])
@main_loop_bp.route("/main/forcestop", methods=["GET", "POST"])
def force_stop():
    global FORCESTOP,HANDLEPUSH
    enter_standby()
    stop_timer()
    FORCESTOP = True
    HANDLEPUSH = False
    PerseusNotifyMsg(str({"status": "ok", "message": "服务已进入待机状态"}), "")
    return format_response({"status": "ok", "message": "服务已进入待机状态"}, 200)

@main_loop_bp.route("/forcestart", methods=["GET", "POST"])
@main_loop_bp.route("/main/forcestart", methods=["GET", "POST"])
def force_start():
    global FORCESTOP,HANDLEPUSH
    enter_standby()
    FORCESTOP = False
    HANDLEPUSH = True
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

# 推送接收接口
@main_loop_bp.route("/push", methods=["GET", "POST"])
def receive_push():
    msg_dict = {}
    msg_dict.update(request.args.to_dict())
    msg_dict.update(request.form.to_dict())
    if request.is_json:
        json_data = request.get_json(silent=True)
        if json_data:
            msg_dict.update(json_data)

    logger.info("\n========================================")
    logger.info(f"【新OnePush推送】时间：{str(request.args)}")
    logger.info("消息完整字典：")
    print(json.dumps(msg_dict, ensure_ascii=False, indent=4))
    logger.info("========================================\n")
    with stats_lock:
        stats = load_stats()
        stats["push_handle_count"] += 1
        save_stats(stats)
    logger.info("⏱️ [统计模块] push处理次数+1")

    if HANDLEPUSH:
        push_res = Handlepush(msg_dict)
        if not push_res:
            logger.error("❌ Handlepush 处理失败，进入待机状态...")
            if main_enabled:
                enter_standby()
            
            PerseusErrorMsg(
                "Handlepush 处理失败", 
                "Push 消息处理异常，服务已自动进入待机状态并清理进程！"
            )
            
            fail_resp = push_res if push_res is not None else {
                "status": "error",
                "code": 500,
                "message": "推送处理失败，服务已转入待机状态",
                "data": msg_dict
            }
            return format_response(fail_resp, 500)
        # 成功分支，返回标准成功结构，不再返回 push_res（bool）
        ok_resp = {
            "status": "ok",
            "code": 200,
            "message": "Handlepush 处理成功",
            "data": msg_dict
        }
        return format_response(ok_resp, 200)

    title = msg_dict.get("title", "")
    body = msg_dict.get("body", "")
    PerseusNotifyMsg(title, body)

    default_resp = {
        "status": "ok",
        "code": 200,
        "message": "消息已转发（处于待机状态，未开启 Handlepush）",
        "data": msg_dict
    }
    return format_response(default_resp, 200)

@main_loop_bp.route("/run", methods=["GET", "POST"])
def handle_run():
    req_data = {}
    req_data.update(request.args.to_dict())
    req_data.update(request.form.to_dict())
    if request.is_json:
        json_data = request.get_json(silent=True)
        if json_data:
            req_data.update(json_data)

    print("\n========================================")
    print("【/run 收到消息】内容：")
    print(json.dumps(req_data, ensure_ascii=False, indent=4))
    print("========================================\n")

    run_result = handlerun(req_data)
    PerseusNotifyMsg(str(run_result),"")
    return format_response(run_result, 200)