import json
import os
import re
import time
import urllib.request
from playwright.sync_api import expect, sync_playwright

try:
    from zBarkCustom import PerseusErrorMsg, PerseusWarningMsg
    import zPerseusLogger
except ImportError:
    # Safe fallback if custom logger modules are not present
    def PerseusErrorMsg(msg, code=""): print(f"[ERROR] {code} {msg}")
    def PerseusWarningMsg(msg, code=""): print(f"[WARN] {code} {msg}")


def is_site_accessible(url="http://192.168.10.3:22267/"):
    """
    轻量级检查目标网页是否可访问
    """
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return response.status in (200, 301, 302, 401, 403)
    except Exception:
        return False


def wait_for_site_ready(url="http://192.168.10.3:22267/", max_wait_sec=180):
    """
    循环检查网页状态，在最长指定时间内等待网页在线。
    """
    if is_site_accessible(url):
        print(f"🌐 检测到 {url} 已在线。")
        return True

    print(f"⌛ 未检测到网页服务 ({url}) 在线，等待恢复中...")

    start_time = time.time()
    while time.time() - start_time < max_wait_sec:
        elapsed = int(time.time() - start_time)
        print(f"⏳ 正在等待网页响应...（已等待 {elapsed} 秒 / 最多 {max_wait_sec} 秒）")

        if is_site_accessible(url):
            print("🎉 检测到网页已恢复在线状态！")
            return True

        time.sleep(3)

    print("🚨 错误：超时网页无响应，任务终止。")
    return False


def fix_and_load_storage(json_path):
    """
    读取并修正 auth.json 的格式问题，确保所有的 localStorage value 都是字符串。
    """
    if not os.path.exists(json_path):
        return None

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "origins" in data:
            for origin in data["origins"]:
                if "localStorage" in origin:
                    for item in origin["localStorage"]:
                        if not isinstance(item.get("value"), str):
                            item["value"] = json.dumps(
                                item["value"], ensure_ascii=False
                            )

        return data
    except Exception as e:
        print(f"解析 auth.json 失败: {e}")
        return None


def post_data_to_endpoint(url: str, payload_dict: dict) -> bool:
    """
    通用的 HTTP POST 请求提交工具
    """
    try:
        req_data = json.dumps(payload_dict).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            print(f"✅ 数据成功提交至 {url}，响应状态码: {resp.status}")
            return True
    except Exception as e:
        print(f"⚠️ 提交至 {url} 失败: {e}")
        return False


def check_is_in_instance(page) -> bool:
    """
    核对是否在实例页面（检查是否存在 <div class="overview-page">）
    """
    try:
        overview_elem = page.locator(".overview-page")
        return overview_elem.is_visible()
    except Exception:
        return False


def nav_to_home(page):
    """
    ①函数前往主页：点击 <a href="#/" data-discover="true">主页</a>
    简称: home
    """
    try:
        print("🏠 正在前往主页...")
        home_btn = page.locator('a[href="#/"]').filter(has_text="主页").first
        if not home_btn.is_visible():
            home_btn = page.locator('a[href="#/"]').first
        
        home_btn.wait_for(state="visible", timeout=5000)
        home_btn.click(force=True)
        page.wait_for_timeout(1000)
        print("✅ 已点击前往主页")
        return True, "0001", "前往主页成功"
    except Exception as e:
        msg = f"前往主页失败: {e}"
        print(f"⚠️ {msg}")
        return False, "0002", msg


def nav_to_instance(page):
    """
    ②函数前往实例页：先前往主页，再点击实例卡片
    <a class="instance-card panel" href="#/i/alas/overview" ...> 后确认出现 <div class="overview-page">
    简称: instance
    """
    try:
        print("🖥️ 正在前往实例页...")
        # 步骤 1: 先前往主页
        nav_to_home(page)
        
        # 步骤 2: 点击实例卡片
        instance_card = page.locator('a.instance-card[href="#/i/alas/overview"], a[href="#/i/alas/overview"]').first
        instance_card.wait_for(state="visible", timeout=5000)
        instance_card.click(force=True)

        # 步骤 3: 确认出现 overview-page
        overview_page = page.locator(".overview-page")
        overview_page.wait_for(state="visible", timeout=8000)
        print("✅ 已成功跳转至实例页并确认包含 <div class=\"overview-page\">")
        return True, "0003", "前往实例页成功"
    except Exception as e:
        msg = f"前往实例页失败: {e}"
        print(f"⚠️ {msg}")
        return False, "0004", msg


def ensure_instance_page(page):
    """
    位置检查与自动跳转：核对是否在实例页面，否则先跳转至实例页
    """
    if check_is_in_instance(page):
        print("📍 当前已在实例页面。")
        return True
    print("📍 当前不在实例页面，正自动跳转至实例页...")
    success, _, _ = nav_to_instance(page)
    return success


def check_updates(page):
    """
    ③函数检查更新：检查 <a class="update-notice sidebar-update-notice" href="#/updater"...><span>新</span></a>
    如果有那么点击它，然后会跳转到 updater 页，暂时不做处理。
    简称: check_update
    """
    try:
        print("🔍 正在检查更新...")
        update_notice = page.locator('a.update-notice[href="#/updater"], a[href="#/updater"]').first
        if update_notice.is_visible():
            print("📢 检测到新版本更新提示，点击跳转至更新页...")
            update_notice.click(force=True)
            page.wait_for_timeout(1000)
            return True, "0005", "发现新版本并已点击跳转至 Updater 页面"
        else:
            print("✨ 未检测到新版本更新提示。")
            return True, "0006", "未发现新版本"
    except Exception as e:
        msg = f"检查更新执行异常: {e}"
        print(f"⚠️ {msg}")
        return False, "0007", msg


def get_resource_list(page):
    """
    ④函数获取资源列表：在实例页面，向 127.0.0.1:25566/main/ap/set 提交
    <section class="resource-card resource-merged"...> 的全部内容
    简称: get_resources
    """
    try:
        ensure_instance_page(page)
        print("📦 正在获取资源列表...")
        resource_sec = page.locator("section.resource-card").first
        resource_sec.wait_for(state="visible", timeout=5000)
        resource_html = resource_sec.evaluate("el => el.outerHTML")

        # 提交到 127.0.0.1:25566/main/ap/set
        target_url = "http://127.0.0.1:25566/main/ap/set"
        if post_data_to_endpoint(target_url, {"html": resource_html}):
            return True, "0008", "获取并提交资源列表成功"
        else:
            return False, "0009", "资源列表接口提交失败"
    except Exception as e:
        msg = f"获取资源列表异常: {e}"
        print(f"⚠️ {msg}")
        return False, "0010", msg


def get_task_list(page):
    """
    ⑤函数获取任务列表：在实例页面，向 127.0.0.1:25566/main/ap/set2 提交
    <aside class="right-rail" id="right-rail-menu" aria-label="调度与任务">
    简称: get_tasks
    """
    try:
        ensure_instance_page(page)
        print("📋 正在获取任务列表...")
        task_rail = page.locator('#right-rail-menu, aside.right-rail[aria-label*="调度"]').first
        task_rail.wait_for(state="visible", timeout=5000)
        task_html = task_rail.evaluate("el => el.outerHTML")

        # 提交到 127.0.0.1:25566/main/ap/set2
        target_url = "http://127.0.0.1:25566/main/ap/set2"
        if post_data_to_endpoint(target_url, {"html": task_html}):
            return True, "0011", "获取并提交任务列表成功"
        else:
            return False, "0012", "任务列表接口提交失败"
    except Exception as e:
        msg = f"获取任务列表异常: {e}"
        print(f"⚠️ {msg}")
        return False, "0013", msg


def start_scheduler(page):
    """
    ⑥函数启动调度器：在实例页面，点击
    <button class="button scheduler-toggle primary">启动调度器</button>
    直到出现 <button class="button scheduler-toggle danger">停止运行</button>
    简称: start
    """
    try:
        ensure_instance_page(page)
        print("⚡ 正在检查调度器状态...")
        
        stop_btn = page.locator("button.scheduler-toggle.danger").filter(has_text="停止运行")
        if stop_btn.is_visible():
            print("▶️ 调度器当前已处于运行状态（显示停止运行按钮）。")
            return True, "0014", "调度器已在运行状态"

        start_btn = page.locator("button.scheduler-toggle.primary").filter(has_text="启动调度器")
        start_btn.wait_for(state="visible", timeout=5000)
        print("🚀 点击【启动调度器】按钮...")
        start_btn.click(force=True)

        # 等待直到出现停止运行按钮
        stop_btn.wait_for(state="visible", timeout=10000)
        print("🎉 确认调度器已切换为【停止运行】状态！")
        return True, "0015", "成功启动调度器"
    except Exception as e:
        msg = f"启动调度器失败: {e}"
        print(f"⚠️ {msg}")
        return False, "0016", msg


def get_screenshot(page):
    """
    ⑦函数获取截图：在实例页面，点击
    <button type="button" role="tab"...>截图</button>
    等待获取 <a class="text-button" download="alas-screenshot.jpg"...>保存截图</a> 的 base64 图片，
    提交到 127.0.0.1:25566/main/ap/set3
    简称: get_screenshot
    """
    try:
        ensure_instance_page(page)
        print("📸 正在触发页面截图...")
        
        # 点击截图标签按钮
        screenshot_btn = page.locator('button[role="tab"]').filter(has_text="截图").first
        if not screenshot_btn.is_visible():
            screenshot_btn = page.locator("button").filter(has_text="截图").first
        
        screenshot_btn.wait_for(state="visible", timeout=5000)
        screenshot_btn.click(force=True)

        # 等待带有 base64 图片的保存截图 <a> 元素
        download_link = page.locator('a[download="alas-screenshot.jpg"], a.text-button[download]').first
        download_link.wait_for(state="visible", timeout=12000)
        
        base64_data = download_link.get_attribute("href")
        if not base64_data:
            return False, "0017", "未能从截图链接获取到 base64 内容"

        print(f"🖼️ 成功捕获 Base64 图片数据 (长度: {len(base64_data)})，提交至 /main/ap/set3...")
        
        target_url = "http://127.0.0.1:25566/main/ap/set3"
        if post_data_to_endpoint(target_url, {"image": base64_data}):
            return True, "0018", "获取并提交截图成功"
        else:
            return False, "0019", "截图接口提交失败"
    except Exception as e:
        msg = f"获取截图过程出现异常: {e}"
        print(f"⚠️ {msg}")
        return False, "0020", msg


def main(
    headless: bool = True,
    task_list: list = None,
    base_url: str = "http://192.168.10.3:22267/",
):
    """
    任务简称对照表：
    - 'home': 前往主页 (①)
    - 'instance': 前往实例页 (②)
    - 'check_update': 检查更新 (③)
    - 'get_resources': 获取资源列表 (④)
    - 'get_tasks': 获取任务列表 (⑤)
    - 'start': 启动调度器 (⑥)
    - 'get_screenshot': 获取截图 (⑦)

    默认任务顺序: 前往主页 -> 前往实例页 -> 启动调度器 -> 获取资源列表 -> 获取任务列表
    """
    if task_list is None:
        task_list = ["home", "instance", "start", "get_resources", "get_tasks"]

    if not wait_for_site_ready(base_url, max_wait_sec=180):
        return [False, [[False, "0000", f"错误：目标网址 {base_url} 无法访问"]]]

    task_results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)

        current_dir = os.path.dirname(os.path.abspath(__file__))
        auth_json_path = os.path.join(current_dir, "auth.json")

        storage_data = fix_and_load_storage(auth_json_path)
        if storage_data:
            print("🔐 正在加载 auth.json 登录凭证...")
            context = browser.new_context(storage_state=storage_data)
        else:
            print("ℹ️ 未在同目录下找到有效 auth.json，使用全新上下文打开...")
            context = browser.new_context()

        page = context.new_page()

        try:
            print(f"🚀 打开目标页面: {base_url}")
            page.goto(base_url, timeout=30000)
            page.wait_for_load_state("domcontentloaded")
        except Exception as load_err:
            print(f"🚨 打开网页异常: {load_err}")
            browser.close()
            return [False, [[False, "0000", f"页面打开失败: {load_err}"]]]

        # 执行任务列表
        for task in task_list:
            task_key = task.lower().strip()
            print(f"\n--- 📋 执行任务项: [{task_key}] ---")

            if task_key == "home":
                success, code, msg = nav_to_home(page)
                task_results.append([success, code, msg])

            elif task_key == "instance":
                success, code, msg = nav_to_instance(page)
                task_results.append([success, code, msg])

            elif task_key == "check_update":
                success, code, msg = check_updates(page)
                task_results.append([success, code, msg])

            elif task_key == "get_resources":
                success, code, msg = get_resource_list(page)
                task_results.append([success, code, msg])

            elif task_key == "get_tasks":
                success, code, msg = get_task_list(page)
                task_results.append([success, code, msg])

            elif task_key == "start":
                success, code, msg = start_scheduler(page)
                task_results.append([success, code, msg])

            elif task_key == "get_screenshot":
                success, code, msg = get_screenshot(page)
                task_results.append([success, code, msg])

            else:
                msg = f"未知的任务简称: {task}"
                print(f"⚠️ {msg}")
                task_results.append([False, "0099", msg])

        if not headless:
            page.wait_for_timeout(2000)

        browser.close()

    is_all_success = all(item[0] for item in task_results)
    return [is_all_success, task_results]


if __name__ == "__main__":
    # 默认按顺序执行：前往主页 -> 前往实例页 -> 启动调度器 -> 获取资源列表 -> 获取任务列表
    # 如需额外任务可添加 'get_screenshot' 或 'check_update'
    default_tasks = ["home", "instance", "start", "get_resources", "get_tasks"]
    
    result = main(
        headless=False,
        task_list=default_tasks,
        base_url="http://192.168.10.3:22267/"
    )
    
    print("\n" + "="*40)
    print("📊 最终运行结果总结:")
    print(f"整体执行是否成功: {result[0]}")
    print("详细任务日志:")
    for res in result[1]:
        print(f"  - 状态: {'SUCCESS' if res[0] else 'FAILED'} | 编号: {res[1]} | 信息: {res[2]}")
    print("="*40)