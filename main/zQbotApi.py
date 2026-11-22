import os
import sys
import subprocess
import threading
import json
import urllib.request
import requests
from flask import Blueprint, request, Response
from zPerseusLogger import logger
from zConfig import get_config
from zBarkCustom import PerseusErrorMsg

# 创建 QBot 相关的 Blueprint，不设置 url_prefix 以完美保留原有的绝对路径路由
qbot_bp = Blueprint('qbot_bp', __name__)

# QBot 相关配置
PYTHONW_PATH = get_config("pushserver.qbot.pythonw_path")
QBOT_SCRIPT_PATH = get_config("pushserver.qbot.script_path")
QBOT_IDENTIFIER = get_config("pushserver.qbot.identifier")

QBOTSTOP = False

# 目标转发的基础地址
TARGET_BASE_URL = "http://127.0.0.1:25567/bot"

def format_response(result_data, status_code=200):
    """统一构建 JSON 响应"""
    if isinstance(result_data, (dict, list)):
        body = json.dumps(result_data, ensure_ascii=False)
    else:
        body = str(result_data)
    return body, status_code, {"Content-Type": "application/json"}

def kill_qbot_process():
    """查找并精准查杀带有识别标记的 QBot 进程（彻底无弹窗）"""
    if not sys.platform.startswith("win"):
        return

    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE
        creationflags = subprocess.CREATE_NO_WINDOW

        ps_command = f'Get-CimInstance Win32_Process | Where-Object {{ $_.CommandLine -like "*{QBOT_IDENTIFIER}*" }} | Select-Object -ExpandProperty ProcessId'
        
        proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_command],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startupinfo,
            creationflags=creationflags,
            text=True
        )
        output, _ = proc.communicate()

        if output and output.strip():
            pids = output.strip().splitlines()
            for pid in pids:
                pid = pid.strip()
                if pid.isdigit():
                    logger.info("🧹 找到指定的 QBot 进程 (PID: {})，正在静默结束...", pid)
                    subprocess.run(
                        ["taskkill", "/F", "/PID", pid],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        startupinfo=startupinfo,
                        creationflags=creationflags
                    )
            import time
            time.sleep(0.5)
        else:
            logger.info("🔍 未检测到正在运行的 QBot 目标进程。")
    except Exception as e:
        logger.warning("⚠️ 清理 QBot 进程时发生异常: {}", e)

def start_qbot_process():
    """先精准清理，然后使用 pythonw 无窗口启动 QBot"""
    try:
        kill_qbot_process()
    except Exception as e:
        logger.error("❌ 清理旧进程时发生错误: {}", e)

    if not os.path.exists(PYTHONW_PATH):
        logger.error("❌ 未找到 pythonw.exe 路径: {}", PYTHONW_PATH)
        raise FileNotFoundError(f"未找到 pythonw.exe 路径: {PYTHONW_PATH}")
    if not os.path.exists(QBOT_SCRIPT_PATH):
        logger.error("❌ 未找到脚本文件路径: {}", QBOT_SCRIPT_PATH)
        raise FileNotFoundError(f"未找到脚本文件路径: {QBOT_SCRIPT_PATH}")

    try:
        cmd = [PYTHONW_PATH, QBOT_SCRIPT_PATH, QBOT_IDENTIFIER]
        working_dir = os.path.dirname(QBOT_SCRIPT_PATH)

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        creationflags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS

        logger.info("🚀 正在使用 pythonw 后台静默启动 QBot: {}", QBOT_SCRIPT_PATH)
        subprocess.Popen(
            cmd,
            cwd=working_dir,
            startupinfo=startupinfo,
            creationflags=creationflags,
            close_fds=True
        )
    except Exception as e:
        logger.error("❌ 启动 QBot 进程失败: {}", e)

def is_bot_online():
    try:
        response = requests.get("http://127.0.0.1:25567/ping", timeout=0.1)
        if response.status_code == 200:
            data = response.json()
            return data.get("message") is True
    except Exception:
        pass
    return False

# ==================== QBot 路由注册 ====================

@qbot_bp.route("/qbot/start", methods=["GET", "POST"])
@qbot_bp.route("/qbot/restart", methods=["GET", "POST"])
@qbot_bp.route("/main/qbot/start", methods=["GET", "POST"])
@qbot_bp.route("/main/qbot/restart", methods=["GET", "POST"])
def handle_bot_start():
    """接收 /qbot/start 请求：先杀死旧的 QBot 进程，再用 pythonw 后台无窗口拉起"""
    try:
        global QBOTSTOP
        QBOTSTOP = False
        start_qbot_process()
        return format_response({
            "status": "ok", 
            "message": "QBot 启动成功（已完成启动前旧进程清理，无窗口运行中）"
        }, 200)
    except Exception as e:
        logger.error("❌ QBot 启动失败: {}", e)
        return format_response({
            "status": "error", 
            "message": f"QBot 启动失败: {str(e)}"
        }, 500)

@qbot_bp.route("/qbot/forcestop", methods=["GET", "POST"])
@qbot_bp.route("/main/qbot/forcestop", methods=["GET", "POST"])
def qbotfstop():
    global QBOTSTOP
    """接收 /qbot/forcestop 请求"""
    QBOTSTOP = True
    kill_qbot_process()
    return format_response({
        "status": "ok", 
        "message": "已强制结束QBOT进程"
    }, 200)

@qbot_bp.route("/qbot/shutdown", methods=["GET", "POST"])
@qbot_bp.route("/main/qbot/shutdown", methods=["GET", "POST"])
def handle_bot_shutdown():
    """接收 /qbot/shutdown 请求：精准结束 QBot 进程"""
    PerseusErrorMsg("", "收到 bot/shutdown 请求：将结束 QBot 进程")
    try:
        kill_qbot_process()
        return format_response({
            "status": "ok", 
            "message": "QBot 进程已精准清理/关闭"
        }, 200)
    except Exception as e:
        logger.error("❌ QBot 查杀关闭失败: {}", e)
        return format_response({
            "status": "error", 
            "message": f"QBot 查杀失败: {str(e)}"
        }, 500)

@qbot_bp.route("/bot", defaults={"subpath": ""}, methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
@qbot_bp.route("/bot/<path:subpath>", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
def proxy_bot(subpath):
    target_url = f"{TARGET_BASE_URL}/{subpath}" if subpath else TARGET_BASE_URL
    headers = {key: value for key, value in request.headers if key.lower() != 'host'}
    
    try:
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=request.get_data(),
            cookies=request.cookies,
            params=request.args,
            allow_redirects=False,
            timeout=30
        )
        
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        response_headers = [
            (name, value) for name, value in resp.raw.headers.items() 
            if name.lower() not in excluded_headers
        ]
        
        return Response(resp.content, resp.status_code, response_headers)
        
    except requests.exceptions.RequestException as e:
        return {"error": f"Proxy error: {str(e)}"}, 500

@qbot_bp.route("/main/bot/get", methods=["GET"])
def handle_main_bot_get():
    """请求本地 http://127.0.0.1:25567/bot/status/get 获取 QBot 统计并返回给前端"""
    try:
        req = urllib.request.Request("http://127.0.0.1:25567/bot/status/get", method="GET")
        with urllib.request.urlopen(req, timeout=0.2) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
            return format_response(data, resp.status)
    except Exception as e:
        return format_response({
            "status": "error",
            "message": f"获取 QBot 状态失败: {str(e)}"
        }, 502)
