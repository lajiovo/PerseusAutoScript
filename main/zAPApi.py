import os
import json
import re
import urllib.request
import datetime
from flask import Blueprint, request, send_from_directory, abort
from zPerseusLogger import logger

ap_bp = Blueprint("ap_bp", __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AP_DIR = os.path.join(BASE_DIR, "servercache", "ap")
os.makedirs(AP_DIR, exist_ok=True)

def collect_request_dict():
    msg_dict = {}
    msg_dict.update(request.args.to_dict())
    msg_dict.update(request.form.to_dict())
    if request.is_json:
        json_data = request.get_json(silent=True)
        if json_data and isinstance(json_data, dict):
            msg_dict.update(json_data)
    return msg_dict

def get_ap_html_path():
    return os.path.join(AP_DIR, "dashboard.html")

def get_dashboard_json_path():
    return os.path.join(AP_DIR, "dashboard_data.json")

def get_tasks_json_path():
    return os.path.join(AP_DIR, "tasks_data.json")

def parse_relative_or_absolute_time(time_str):
    if not time_str:
        now_dt = datetime.datetime.now()
        return int(now_dt.timestamp() * 1000), now_dt.strftime("%Y-%m-%d %H:%M:%S")

    time_str = str(time_str).strip()
    now = datetime.datetime.now()

    abs_formats = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M"]
    for fmt in abs_formats:
        try:
            dt = datetime.datetime.strptime(time_str, fmt)
            return int(dt.timestamp() * 1000), dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue

    # 纯时间格式：14:28:15，使用今天的日期
    try:
        parsed_time = datetime.datetime.strptime(time_str, "%H:%M:%S")
        target_dt = now.replace(
            hour=parsed_time.hour,
            minute=parsed_time.minute,
            second=parsed_time.second,
            microsecond=0
        )
        return (
            int(target_dt.timestamp() * 1000),
            target_dt.strftime("%Y-%m-%d %H:%M:%S")
        )
    except ValueError:
        pass

    if "刚刚" in time_str or "just now" in time_str.lower():
        return int(now.timestamp() * 1000), now.strftime("%Y-%m-%d %H:%M:%S")

    match = re.search(r'(\d+)\s*(秒|分|小时|天|周|个月|年|s|m|h|d)', time_str, re.IGNORECASE)
    if match:
        val = int(match.group(1))
        unit = match.group(2)
        delta = datetime.timedelta(seconds=0)
        if unit in ('秒', 's'):
            delta = datetime.timedelta(seconds=val)
        elif unit in ('分', 'm'):
            delta = datetime.timedelta(minutes=val)
        elif unit in ('小时', 'h'):
            delta = datetime.timedelta(hours=val)
        elif unit in ('天', 'd'):
            delta = datetime.timedelta(days=val)
        elif unit in ('周',):
            delta = datetime.timedelta(weeks=val)
        elif unit in ('个月',):
            delta = datetime.timedelta(days=val * 30)
        elif unit in ('年',):
            delta = datetime.timedelta(days=val * 365)

        target_dt = now - delta
        return int(target_dt.timestamp() * 1000), target_dt.strftime("%Y-%m-%d %H:%M:%S")

    return int(now.timestamp() * 1000), now.strftime("%Y-%m-%d %H:%M:%S")


def parse_dashboard_html(html_content):
    """解析新版 ALAS 仪表盘资源 HTML"""
    import os
    import re
    import html as html_lib
    import urllib.request

    if not html_content:
        return {"resources": [], "raw_html": ""}

    resources = []

    def clean_text(value):
        """清理 HTML 标签、实体及空白字符"""
        value = re.sub(r"<[^>]+>", "", value or "")
        value = html_lib.unescape(value)
        return re.sub(r"\s+", " ", value).strip()

    def parse_number(value):
        """提取数值，支持千位分隔符"""
        number = re.sub(r"[^\d]", "", value or "")
        return int(number) if number else 0

    try:
        # ① 获取所有资源节点
        items = re.findall(
            r'<section\b(?=[^>]*\bclass=["\'][^"\']*\bresource-merged-item\b[^"\']*["\'])[^>]*>(.*?)</section>',
            html_content,
            re.DOTALL | re.IGNORECASE
        )

        for item_html in items:
            res_item = {
                "name": "未知资源",
                "current": 0,
                "max": None,
                "icon": None,
                "time_str": "",
                "timestamp": None,
                "formatted_time": None
            }

            # ② 资源名称
            heading_match = re.search(
                r'<div\b[^>]*\bclass=["\'][^"\']*\bresource-heading\b[^"\']*["\'][^>]*>(.*?)</div>',
                item_html,
                re.DOTALL | re.IGNORECASE
            )

            if heading_match:
                name_match = re.search(
                    r'<span\b[^>]*>(.*?)</span>',
                    heading_match.group(1),
                    re.DOTALL | re.IGNORECASE
                )

                if name_match:
                    res_item["name"] = clean_text(name_match.group(1))

            # ③ 资源图标
            img_match = re.search(
                r'<img\b[^>]*\bsrc=["\']([^"\']+)["\']',
                item_html,
                re.IGNORECASE
            )

            if img_match:
                src = html_lib.unescape(img_match.group(1))
                basename = os.path.basename(src.split("?")[0])

                if basename:
                    res_item["icon"] = f"/ap/file/{basename}"
                    icon_path = os.path.join(AP_DIR, basename)

                    if not os.path.exists(icon_path):
                        try:
                            # 相对路径默认从 ALAS WebUI 根目录获取
                            if src.startswith("./"):
                                icon_url = (
                                    f"http://127.0.0.1:22267/"
                                    f"{src[2:]}"
                                )
                            elif not src.startswith(("http://", "https://")):
                                icon_url = (
                                    f"http://127.0.0.1:22267/{src.lstrip('/')}"
                                )
                            else:
                                icon_url = src

                            req = urllib.request.Request(
                                icon_url,
                                headers={"User-Agent": "Mozilla/5.0"}
                            )

                            with urllib.request.urlopen(req, timeout=2) as resp:
                                if resp.status == 200:
                                    with open(icon_path, "wb") as f_icon:
                                        f_icon.write(resp.read())

                        except Exception as e:
                            logger.warning(
                                "下载图标 {} 失败: {}", basename, e
                            )

            
            # ④ 资源数值
            current_val = 0
            max_val = None

            value_match = re.search(
                r'<div\b[^>]*\bclass=["\'][^"\']*\bresource-value\b[^"\']*["\'][^>]*>(.*?)</div>',
                item_html,
                re.DOTALL | re.IGNORECASE
            )

            if value_match:
                value_html = value_match.group(1)

                # 优先提取 resource-value-content 内部的第一个数字 span
                current_match = re.search(
                    r'<span\b[^>]*>([\d,]+)</span>',
                    value_html,
                    re.IGNORECASE
                )

                if current_match:
                    current_val = parse_number(current_match.group(1))

                # 提取最大值，兼容没有 small 的资源
                max_match = re.search(
                    r'<small\b[^>]*>(.*?)</small>',
                    value_html,
                    re.DOTALL | re.IGNORECASE
                )

                if max_match:
                    max_val = parse_number(clean_text(max_match.group(1)))

            res_item["current"] = current_val
            res_item["max"] = max_val


            # ⑤ 更新时间
            foot_match = re.search(
                r'<div\b[^>]*\bclass=["\'][^"\']*\bresource-foot\b[^"\']*["\'][^>]*>(.*?)</div>',
                item_html,
                re.DOTALL | re.IGNORECASE
            )

            if foot_match:
                time_str = clean_text(foot_match.group(1))
                res_item["time_str"] = time_str

                ts, formatted_time = parse_relative_or_absolute_time(
                    time_str
                )

                res_item["timestamp"] = ts
                res_item["formatted_time"] = formatted_time

            resources.append(res_item)

        return {
            "resources": resources,
            "raw_html": html_content
        }

    except Exception as e:
        logger.exception("解析仪表盘 HTML 异常")

        return {
            "resources": resources,
            "raw_html": html_content,
            "error": str(e)
        }


def parse_tasks_html(html_content):
    """解析新版 ALAS 调度与任务列表 HTML"""

    if not html_content:
        return {
            "tasks": [],
            "groups": {
                "running": [],
                "pending": [],
                "waiting": []
            },
            "raw_html": ""
        }

    result = {
        "tasks": [],
        "groups": {
            "running": [],
            "pending": [],
            "waiting": []
        },
        "raw_html": html_content
    }

    try:
        # 直接匹配所有的任务节点（无论是否在 rail-queue-group 内）
        task_pattern = re.compile(
            r'<a\b([^>]*\bclass=["\'][^"\']*?\btask\b[^"\']*["\'][^>]*)>(.*?)</a>',
            re.DOTALL | re.IGNORECASE
        )
        
        matches = list(re.finditer(task_pattern, html_content))
        if not matches:
            # 兼容 rail-task-item
            task_pattern = re.compile(
                r'<a\b([^>]*\bclass=["\'][^"\']*?\brail-task-item\b[^"\']*["\'][^>]*)>(.*?)</a>',
                re.DOTALL | re.IGNORECASE
            )
            matches = list(re.finditer(task_pattern, html_content))

        for task_match in matches:
            task_attrs = task_match.group(1)
            task_html = task_match.group(2)

            # 任务 ID
            id_match = re.search(
                r'data-task=["\']([^"\']*)["\']',
                task_attrs,
                re.IGNORECASE
            )
            task_id = id_match.group(1) if id_match else ""

            # 任务名称
            name_match = re.search(
                r'<strong[^>]*>(.*?)</strong>',
                task_html,
                re.DOTALL | re.IGNORECASE
            )
            task_name = ""
            if name_match:
                task_name = re.sub(r'<[^>]+>', '', name_match.group(1)).strip()

            # 任务时间
            time_match = re.search(
                r'<small[^>]*>(.*?)</small>',
                task_html,
                re.DOTALL | re.IGNORECASE
            )
            time_str = ""
            if time_match:
                time_str = re.sub(r'<[^>]+>', '', time_match.group(1)).strip()

            # 任务状态与分组推断
            status = "waiting"
            status_text = "等待中"
            group_type = "waiting"
            group_name = "等待中"

            state_match = re.search(
                r'<span\b([^>]*\bclass=["\'][^"\']*?\btask-state\b[^"\']*["\'][^>]*)>(.*?)</span>',
                task_html,
                re.DOTALL | re.IGNORECASE
            )

            if state_match:
                state_attrs = state_match.group(1)
                state_text_raw = re.sub(r'<[^>]+>', '', state_match.group(2)).strip()
                if state_text_raw:
                    status_text = state_text_raw

                if "running" in state_attrs.lower() or "运行" in status_text or "进行" in status_text:
                    status = "running"
                    group_type = "running"
                    group_name = "运行中"
                elif "pending" in state_attrs.lower() or "queued" in state_attrs.lower() or "待" in status_text or "排队" in status_text:
                    status = "pending"
                    group_type = "pending"
                    group_name = "待运行"
                else:
                    status = "waiting"
                    group_type = "waiting"
                    group_name = "等待中"

            ts, formatted_time = parse_relative_or_absolute_time(time_str)

            task = {
                "id": task_id,
                "name": task_name,
                "time_str": time_str,
                "timestamp": ts,
                "formatted_time": formatted_time,
                "status": status,
                "status_text": status_text,
                "group": group_type,
                "group_name": group_name
            }

            result["tasks"].append(task)
            if group_type in result["groups"]:
                result["groups"][group_type].append(task)
            else:
                result["groups"]["waiting"].append(task)

        return result

    except Exception as e:
        logger.error("解析任务 HTML 异常: {}", e)
        result["error"] = str(e)
        return result

def format_response(data, status_code=200):
    return data, status_code

@ap_bp.route("/main/ap/set", methods=["POST"])
@ap_bp.route("/ap/set", methods=["POST"])
def handle_ap_set():
    try:
        req_data = {}
        if request.is_json:
            req_data = request.get_json(silent=True) or {}
        else:
            req_data = request.form.to_dict()

        html_content = req_data.get("html")
        if not html_content and request.data:
            html_content = request.data.decode("utf-8", errors="ignore")

        if html_content:
            with open(get_ap_html_path(), "w", encoding="utf-8") as f:
                f.write(html_content)
            parsed_data = parse_dashboard_html(html_content)
            with open(get_dashboard_json_path(), "w", encoding="utf-8") as f:
                json.dump(parsed_data, f, ensure_ascii=False, indent=2)
            return format_response({"status": "ok", "message": "仪表盘 HTML 解析并保存成功", "data": parsed_data}, 200)
        return format_response({"status": "error", "message": "缺少 html 内容"}, 400)
    except Exception as e:
        logger.error("handle_ap_set 异常: {}", e)
        return format_response({"status": "error", "message": str(e)}, 500)

@ap_bp.route("/main/ap/set2", methods=["POST"])
@ap_bp.route("/ap/set2", methods=["POST"])
def handle_ap_set2():
    try:
        req_data = {}
        if request.is_json:
            req_data = request.get_json(silent=True) or {}
        else:
            req_data = request.form.to_dict()

        html_content = req_data.get("html")
        if not html_content and request.data:
            html_content = request.data.decode("utf-8", errors="ignore")

        if html_content:
            parsed_data = parse_tasks_html(html_content)
            with open(get_tasks_json_path(), "w", encoding="utf-8") as f:
                json.dump(parsed_data, f, ensure_ascii=False, indent=2)
            return format_response({"status": "ok", "message": "任务状态 HTML 解析并保存成功", "data": parsed_data}, 200)
        return format_response({"status": "error", "message": "缺少 html 内容"}, 400)
    except Exception as e:
        logger.error("handle_ap_set2 异常: {}", e)
        return format_response({"status": "error", "message": str(e)}, 500)

@ap_bp.route("/main/ap/reparse", methods=["GET", "POST"])
@ap_bp.route("/ap/reparse", methods=["GET", "POST"])
def handle_ap_reparse():
    """重新从缓存的 HTML 文件及 tasks_data.json 中的 raw_html 解析资源和任务数据"""
    try:
        results = {}
        
        # 1. 重新解析仪表盘/资源 HTML (来自 dashboard.html)
        html_path = get_ap_html_path()
        if os.path.exists(html_path):
            with open(html_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            parsed_dashboard = parse_dashboard_html(html_content)
            with open(get_dashboard_json_path(), "w", encoding="utf-8") as f:
                json.dump(parsed_dashboard, f, ensure_ascii=False, indent=2)
            results["dashboard"] = "success"
        else:
            results["dashboard"] = "dashboard.html not found"

        # 2. 重新解析任务 HTML (优先从 tasks_data.json 的 raw_html 读取，其次从 dashboard.html 或 tasks.html)
        tasks_json_path = get_tasks_json_path()
        tasks_content = ""
        if os.path.exists(tasks_json_path):
            try:
                with open(tasks_json_path, "r", encoding="utf-8") as f:
                    t_json = json.load(f)
                    if isinstance(t_json, dict) and t_json.get("raw_html"):
                        tasks_content = t_json.get("raw_html")
            except Exception:
                pass

        if not tasks_content:
            tasks_html_path = os.path.join(AP_DIR, "tasks.html")
            target_tasks_html = tasks_html_path if os.path.exists(tasks_html_path) else html_path
            if os.path.exists(target_tasks_html):
                with open(target_tasks_html, "r", encoding="utf-8") as f:
                    tasks_content = f.read()

        if tasks_content:
            parsed_tasks = parse_tasks_html(tasks_content)
            with open(tasks_json_path, "w", encoding="utf-8") as f:
                json.dump(parsed_tasks, f, ensure_ascii=False, indent=2)
            results["tasks"] = "success"
        else:
            results["tasks"] = "tasks html not found"

        return format_response({"status": "ok", "message": "重新解析完成", "results": results}, 200)
    except Exception as e:
        logger.error("handle_ap_reparse 异常: {}", e)
        return format_response({"status": "error", "message": str(e)}, 500)

@ap_bp.route("/main/ap/get", methods=["GET"])
@ap_bp.route("/ap/get", methods=["GET"])
def handle_ap_get():
    try:
        if os.path.exists(get_dashboard_json_path()):
            with open(get_dashboard_json_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
            return format_response({"status": "ok", "data": data}, 200)
        return format_response({"status": "ok", "data": {"resources": []}}, 200)
    except Exception as e:
        return format_response({"status": "error", "message": str(e)}, 500)

@ap_bp.route("/main/ap/get2", methods=["GET"])
@ap_bp.route("/ap/get2", methods=["GET"])
def handle_ap_get2():
    try:
        if os.path.exists(get_tasks_json_path()):
            with open(get_tasks_json_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
            return format_response({"status": "ok", "data": data}, 200)
        return format_response({"status": "ok", "data": {"tasks": []}}, 200)
    except Exception as e:
        return format_response({"status": "error", "message": str(e)}, 500)

@ap_bp.route("/main/ap/file/<path:filename>", methods=["GET"])
@ap_bp.route("/ap/file/<path:filename>", methods=["GET"])
def serve_ap_file(filename):
    try:
        return send_from_directory(AP_DIR, filename)
    except Exception as e:
        return abort(404)

def get_screenshot_path():
    return os.path.join(AP_DIR, "alas-screenshot.jpg")

@ap_bp.route("/main/ap/set3", methods=["POST"])
@ap_bp.route("/ap/set3", methods=["POST"])
def handle_ap_set3():
    """接收并保存 Base64 截图"""
    try:
        print("[AP_SET3] 开始处理截图请求")

        # ① 获取请求数据
        req_data = collect_request_dict()
        print(f"[AP_SET3] 请求数据类型: {type(req_data).__name__}")

        b64_data = (
            req_data.get("image")
            or req_data.get("base64")
            or req_data.get("data")
        )

        if not b64_data and request.is_json:
            j = request.get_json(silent=True)
            if j:
                b64_data = (
                    j.get("image")
                    or j.get("base64")
                    or j.get("data")
                )

        if not b64_data:
            b64_data = (
                request.form.get("image")
                or request.form.get("base64")
                or request.data.decode("utf-8", errors="ignore")
            )

        if not b64_data:
            print("[AP_SET3] 缺少图片数据")
            return format_response({
                "status": "error",
                "message": "缺少图片数据"
            }, 400)

        # ② 处理 Base64
        import base64

        if isinstance(b64_data, bytes):
            b64_data = b64_data.decode("utf-8")

        if "base64," in b64_data:
            b64_data = b64_data.split("base64,", 1)[1]

        print(f"[AP_SET3] Base64 长度: {len(b64_data)}")

        img_bytes = base64.b64decode(b64_data.strip(), validate=True)

        print(f"[AP_SET3] 图片解码成功，大小: {len(img_bytes)} bytes")

        # ③ 保存图片
        save_path = get_screenshot_path()
        print(f"[AP_SET3] 保存路径: {save_path}")

        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        with open(save_path, "wb") as f:
            f.write(img_bytes)

        print("[AP_SET3] 截图保存成功")

        return format_response({
            "status": "ok",
            "message": "截图保存成功",
            "url": "/ap/file/alas-screenshot.jpg"
        }, 200)

    except Exception as e:
        import traceback
        traceback.print_exc()

        return format_response({
            "status": "error",
            "message": str(e)
        }, 500)

@ap_bp.route("/main/ap/get3", methods=["GET"])
@ap_bp.route("/ap/get3", methods=["GET"])
def handle_ap_get3():
    """获取最新截图信息及访问链接"""
    path = get_screenshot_path()
    exists = os.path.exists(path)

    return format_response({
        "status": "ok",
        "exists": exists,
        "screenshot_url": "/ap/file/alas-screenshot.jpg" if exists else "",
        "updated_at": datetime.datetime.fromtimestamp(
            os.path.getmtime(path)
        ).strftime("%Y-%m-%d %H:%M:%S") if exists else ""
    }, 200)
