import os
import time
import threading
from flask import Blueprint, jsonify, request, render_template_string
from zBNP import BNPController

bnp_bp = Blueprint("bnp_bp", __name__)

# 全局单例控制器及锁、定时器
_bnp_controller = None
_controller_lock = threading.Lock()
_waiting_timer = None
_recent_logs = []  # 内存日志缓冲区，用于前端实时查看
_logs_lock = threading.Lock()

def _add_log(msg):
    with _logs_lock:
        _recent_logs.append(msg)
        if len(_recent_logs) > 500:
            _recent_logs.pop(0)

def _auto_terminate_timeout():
    """如果处于 WAITING_URL 状态且无输入超过 30 分钟，自动结束实例"""
    global _bnp_controller, _waiting_timer
    with _controller_lock:
        if _bnp_controller and _bnp_controller.is_running:
            if _bnp_controller.current_state == "WAITING_URL":
                log_msg = "[BNP Api] 处于 WAITING_URL 状态无输入超过 30 分钟，自动终止实例。\n"
                print(log_msg.strip())
                _add_log(log_msg)
                _bnp_controller.terminate_process()
        _waiting_timer = None

def _reset_waiting_timer():
    """重置或启动 30 分钟定时器"""
    global _waiting_timer
    with _controller_lock:
        if _waiting_timer:
            _waiting_timer.cancel()
        # 30分钟 = 1800 秒
        _waiting_timer = threading.Timer(1800.0, _auto_terminate_timeout)
        _waiting_timer.daemon = True
        _waiting_timer.start()

def _cancel_waiting_timer():
    global _waiting_timer
    with _controller_lock:
        if _waiting_timer:
            _waiting_timer.cancel()
            _waiting_timer = None

def get_bnp_controller() -> BNPController:
    global _bnp_controller
    with _controller_lock:
        if _bnp_controller is None:
            def on_state_change(state, desc):
                log_msg = f"[状态改变] {state}: {desc}\n"
                _add_log(log_msg)
                # 如果进入 WAITING_URL，启动 30 分钟无输入超时计时
                if state == "WAITING_URL":
                    _reset_waiting_timer()
                else:
                    # 离开 WAITING_URL 则取消定时器
                    _cancel_waiting_timer()

            def on_stdout(msg):
                _add_log(msg)

            def on_log(msg):
                _add_log(msg)

            _bnp_controller = BNPController(
                on_log_callback=on_log,
                on_stdout_callback=on_stdout,
                on_state_change=on_state_change
            )
    return _bnp_controller

@bnp_bp.route("/bnp/status", methods=["GET"])
def api_bnp_status():
    ctrl = get_bnp_controller()
    info = ctrl.get_progress_info()
    return jsonify({"code": 200, "data": info})

@bnp_bp.route("/bnp/logs", methods=["GET"])
def api_bnp_logs():
    with _logs_lock:
        logs_copy = list(_recent_logs)
    return jsonify({"code": 200, "logs": logs_copy})

@bnp_bp.route("/bnp/start", methods=["POST", "GET"])
def api_bnp_start():
    ctrl = get_bnp_controller()
    success, msg = ctrl.start_process()
    if success:
        _add_log(f"[系统] {msg}\n")
        return jsonify({"code": 200, "message": msg})
    else:
        return jsonify({"code": 400, "message": msg}), 400

@bnp_bp.route("/bnp/stop", methods=["POST", "GET"])
def api_bnp_stop():
    ctrl = get_bnp_controller()
    _cancel_waiting_timer()
    ctrl.terminate_process()
    _add_log("[系统] 用户手动终止程序。\n")
    return jsonify({"code": 200, "message": "程序已停止"})

@bnp_bp.route("/bnp/input", methods=["POST"])
def api_bnp_input():
    data = request.get_json(silent=True) or request.form.to_dict() or request.args.to_dict()
    text = data.get("text", "")
    if not text:
        return jsonify({"code": 400, "message": "缺少输入文本 (text)"}), 400
    
    ctrl = get_bnp_controller()
    # 用户有输入，重置/取消 waiting 超时
    _cancel_waiting_timer()
    
    success, msg = ctrl.send_input(text)
    if success:
        _add_log(f"[INPUT ->] {text}\n")
        return jsonify({"code": 200, "message": msg})
    else:
        return jsonify({"code": 400, "message": msg}), 400

@bnp_bp.route("/bnp/download", methods=["POST"])
def api_bnp_download():
    data = request.get_json(silent=True) or request.form.to_dict() or request.args.to_dict()
    url = data.get("url", "")
    if not url:
        return jsonify({"code": 400, "message": "缺少小说链接 (url)"}), 400
    
    ctrl = get_bnp_controller()
    _cancel_waiting_timer()
    
    success, msg = ctrl.download_novel(url)
    if success:
        _add_log(f"[INPUT ->] {url} (下载小说)\n")
        return jsonify({"code": 200, "message": msg})
    else:
        return jsonify({"code": 400, "message": msg}), 400

@bnp_bp.route("/bnp/volume", methods=["POST"])
def api_bnp_volume():
    data = request.get_json(silent=True) or request.form.to_dict() or request.args.to_dict()
    volume_id = data.get("volume_id", "")
    if not volume_id:
        return jsonify({"code": 400, "message": "缺少分卷编号 (volume_id)"}), 400
    
    ctrl = get_bnp_controller()
    success, msg = ctrl.select_volume(str(volume_id))
    if success:
        _add_log(f"[INPUT ->] {volume_id} (选择分卷)\n")
        return jsonify({"code": 200, "message": msg})
    else:
        return jsonify({"code": 400, "message": msg}), 400

@bnp_bp.route("/bnp/title_config", methods=["POST"])
def api_bnp_title_config():
    data = request.get_json(silent=True) or request.form.to_dict() or request.args.to_dict()
    include_title = data.get("include_title", True)
    if isinstance(include_title, str):
        include_title = include_title.lower() in ["true", "1", "yes"]
        
    ctrl = get_bnp_controller()
    success, msg = ctrl.choose_chapter_title_config(include_title)
    if success:
        val_str = "1 (是)" if include_title else "2 (否)"
        _add_log(f"[INPUT ->] {val_str} (章节标题配置)\n")
        return jsonify({"code": 200, "message": msg})
    else:
        return jsonify({"code": 400, "message": msg}), 400

@bnp_bp.route("/bnp/epubs", methods=["GET"])
def api_bnp_epubs():
    ctrl = get_bnp_controller()
    epubs = ctrl.get_all_epub_files()
    file_list = [{"name": os.path.basename(p), "path": p} for p in epubs]
    return jsonify({"code": 200, "data": file_list})

@bnp_bp.route("/bnp/move_epubs", methods=["POST", "GET"])
def api_bnp_move_epubs():
    ctrl = get_bnp_controller()
    count, msg = ctrl.move_epubs_to_output_folder()
    _add_log(f"[系统] {msg}\n")
    return jsonify({"code": 200, "count": count, "message": msg})
