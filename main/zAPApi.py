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
    if not html_content:
        return {"resources": [], "raw_html": ""}
    resources = []
    try:
        items = re.findall(r'<section[^>]*class="[^"]*resource-merged-item[^"]*"[^>]*>(.*?)</section>', html_content, re.DOTALL | re.IGNORECASE)
        if not items:
            items = re.findall(r'<section[^>]*class="[^"]*resource-card[^"]*resource-merged-item[^"]*"[^>]*>(.*?)</section>', html_content, re.DOTALL | re.IGNORECASE)

        for item_html in items:
            res_item = {}
            heading_match = re.search(r'<div[^>]*class="[^"]*resource-heading[^"]*"[^>]*>(.*?)</div>', item_html, re.DOTALL | re.IGNORECASE)
            name = "未知资源"
            if heading_match:
                span_match = re.search(r'<span[^>]*>(.*?)</span>', heading_match.group(1), re.DOTALL | re.IGNORECASE)
                if span_match:
                    name = re.sub(r'<[^>]+>', '', span_match.group(1)).strip()
                else:
                    name = re.sub(r'<[^>]+>', '', heading_match.group(1)).strip()
            res_item["name"] = name

            img_match = re.search(r'<img[^>]*src="([^"]+)"', item_html, re.DOTALL | re.IGNORECASE)
            if img_match:
                src = img_match.group(1)
                basename = os.path.basename(src.split('?')[0])
                if basename:
                    res_item["icon"] = f"/ap/file/{basename}"
                    try:
                        icon_url = f"http://127.0.0.1:22267/{basename}" if src.startswith("./") or not src.startswith("http") else src
                        req = urllib.request.Request(icon_url, headers={"User-Agent": "Mozilla/5.0"})
                        with urllib.request.urlopen(req, timeout=2) as resp:
                            if resp.status == 200:
                                icon_data = resp.read()
                                icon_path = os.path.join(AP_DIR, basename)
                                with open(icon_path, "wb") as f_icon:
                                    f_icon.write(icon_data)
                    except Exception as e:
                        logger.warning("下载图标 {} 失败: {}", basename, e)

            val_match = re.search(r'<div[^>]*class="[^"]*resource-value[^"]*"[^>]*>(.*?)</div>', item_html, re.DOTALL | re.IGNORECASE)
            current_val, max_val = 0, 0
            if val_match:
                val_html = val_match.group(1)
                spans = re.findall(r'<span[^>]*>(.*?)</span>', val_html, re.DOTALL | re.IGNORECASE)
                nums = []
                for s in spans:
                    cleaned = re.sub(r'<[^>]+>', '', s).strip()
                    if cleaned:
                        nums.append(cleaned)
                if len(nums) >= 2:
                    current_val = re.sub(r'[^\d]', '', nums[0])
                    max_val = re.sub(r'[^\d]', '', nums[1])
                    current_val = int(current_val) if current_val else 0
                    max_val = int(max_val) if max_val else 0
                elif len(nums) == 1:
                    cleaned_num = re.sub(r'[^\d]', '', nums[0])
                    current_val = int(cleaned_num) if cleaned_num else 0
            res_item["current"] = current_val
            res_item["max"] = max_val

            foot_match = re.search(r'<div[^>]*class="[^"]*resource-foot[^"]*"[^>]*>(.*?)</div>', item_html, re.DOTALL | re.IGNORECASE)
            time_str = ""
            if foot_match:
                time_str = re.sub(r'<[^>]+>', '', foot_match.group(1)).strip()
            ts, formatted_time = parse_relative_or_absolute_time(time_str)
            res_item["time_str"] = time_str
            res_item["timestamp"] = ts
            res_item["formatted_time"] = formatted_time

            resources.append(res_item)

        return {"resources": resources, "raw_html": html_content}
    except Exception as e:
        logger.error("解析仪表盘 HTML 异常: {}", e)
        return {"resources": [], "raw_html": html_content, "error": str(e)}

def parse_tasks_html(html_content):
    if not html_content:
        return {"tasks": [], "raw_html": ""}
    return {"tasks": [], "raw_html": html_content}

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
    return os.path.join(AP_DIR, "screenshot.png")

@ap_bp.route("/main/ap/set3", methods=["POST"])
@ap_bp.route("/ap/set3", methods=["POST"])
def handle_ap_set3():
    """接收并保存 Base64 截图"""
    try:
        req_data = _collect_request_dict()
        b64_data = req_data.get("image") or req_data.get("base64") or req_data.get("data")
        if not b64_data and request.is_json:
            j = request.get_json(silent=True)
            if j:
                b64_data = j.get("image") or j.get("base64") or j.get("data")
        if not b64_data:
            b64_data = request.form.get("image") or request.form.get("base64") or request.data.decode("utf-8", errors="ignore")

        if b64_data:
            import base64
            if "base64," in b64_data:
                b64_data = b64_data.split("base64,")[1]
            img_bytes = base64.b64decode(b64_data.strip())
            with open(get_screenshot_path(), "wb") as f:
                f.write(img_bytes)
            return format_response({"status": "ok", "message": "截图保存成功", "url": "/ap/file/screenshot.png"}, 200)
        return format_response({"status": "error", "message": "缺少图片数据"}, 400)
    except Exception as e:
        return format_response({"status": "error", "message": str(e)}, 500)

@ap_bp.route("/main/ap/get3", methods=["GET"])
@ap_bp.route("/ap/get3", methods=["GET"])
def handle_ap_get3():
    """获取最新截图信息及访问链接"""
    path = get_screenshot_path()
    exists = os.path.exists(path)
    return format_response({
        "status": "ok",
        "exists": exists,
        "screenshot_url": "/ap/file/screenshot.png" if exists else "",
        "updated_at": datetime.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M:%S") if exists else ""
    }, 200)
