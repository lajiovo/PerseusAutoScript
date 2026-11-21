import win32gui
import win32process
import win32api
import win32con
import psutil
import pytesseract
from PIL import ImageGrab
import time
import re
import os
import ctypes
from datetime import datetime
from collections import defaultdict

# ==================== 基础配置 ====================
# 如果 Tesseract 没有加入系统 PATH，请在此指定你的绝对路径
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# 目标进程名与窗口标题关键词
TARGET_PROCESS = "alas-launcher.exe"  
TARGET_TITLE_KEYWORD = "AzurPilot"    

# 窗口标题黑名单（过滤后台组件、托盘、助手等）
WINDOW_BLACKLIST = {"siw", "helper", "background"} 

# 窗口最小尺寸过滤（宽高小于此数值的窗口将被直接跳过）
MIN_WIDTH = 100   
MIN_HEIGHT = 100  

# DPI 缩放系数 (125% 对应 1.25, 150% 对应 1.5)
DPI_SCALE = 1.25 
# ==================================================

def save_screenshot(screenshot):
    """用来调试的"""
    # 保存调试截图
    debug_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug")
    os.makedirs(debug_dir, exist_ok=True)
    filename = f"ocr_{datetime.now():%Y%m%d_%H%M%S_%f}.png"
    screenshot.save(os.path.join(debug_dir, filename))

def contains_keyword(lines, keyword, field="text"):
    """检查指定字段是否包含关键词（支持 str / list）"""
    keywords = [keyword] if isinstance(keyword, str) else keyword

    return any(
        kw in str(line.get(field, ""))
        for line in lines
        for kw in keywords
    )

def parse_and_merge_ocr_data(data):
    """
    解析并合并 OCR 识别到的文本行，同时保留每行整体的位置 bounding box。
    返回格式：[ {'text': '完整行文本', 'x': min_x, 'y': avg_y, 'w': width, 'h': height, 'items': [原始词块]}, ... ]
    """
    items = []
    
    # 1. 提取所有有效文本及坐标
    for i in range(len(data['text'])):
        text = data['text'][i].strip()
        conf = int(data['conf'][i])
        if not text or conf <= 0:
            continue
        x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
        items.append({'text': text, 'x': x, 'y': y, 'w': w, 'h': h, 'conf': conf})
        
    if not items:
        print("未检测到有效文本。")
        return []

    # 2. 首先按纵坐标 y 从上到下排序
    items = sorted(items, key=lambda item: item['y'])
    
    # 3. 动态行聚类：垂直差在 18 像素以内的归为同一行
    lines = []
    current_line = [items[0]]
    
    for item in items[1:]:
        ref_y = current_line[0]['y']
        if abs(item['y'] - ref_y) < 18:  # 阈值（可根据字体大小微调）
            current_line.append(item)
        else:
            lines.append(current_line)
            current_line = [item]
    lines.append(current_line)
    
    print("\n" + "=" * 50)
    print(" 📜 优化聚类后的完整文本行：")
    print("=" * 50)
    
    merged_lines = []
    for line_items in lines:
        # 同一行内按横坐标 x 从左到右排序
        sorted_line = sorted(line_items, key=lambda item: item['x'])
        merged_text = "".join([item['text'] for item in sorted_line])
        
        min_x = sorted_line[0]['x']
        max_x = sorted_line[-1]['x'] + sorted_line[-1]['w']
        avg_y = sum(item['y'] for item in sorted_line) // len(sorted_line)
        max_h = max(item['h'] for item in sorted_line)
        
        print(f"行 (y~{avg_y:3d}): 【 {merged_text} 】\t(区域: x: {min_x} ~ {max_x})")
        merged_lines.append({
            'text': merged_text,
            'x': min_x,
            'y': avg_y,
            'w': max_x - min_x,
            'h': max_h,
            'items': sorted_line
        })
        
    print("=" * 50)
    return merged_lines


def click_at(x, y):
    """模拟鼠标在指定的屏幕绝对像素坐标处进行点击"""
    try:
        # 移动光标
        win32api.SetCursorPos((int(x), int(y)))
        time.sleep(0.1)
        # 按下并释放左键
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.05)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        print(f"  👆 已点击屏幕坐标: ({int(x)}, {int(y)})")
    except Exception as e:
        print(f"  ❌ 点击失败: {e}")

# ============================================================
# DPI 坐标处理
# ============================================================

def enable_dpi_awareness():
    """
    尽可能让当前进程使用 Per-Monitor DPI Awareness。
    必须尽量在程序创建窗口之前调用。
    """
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return True
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
            return True
        except Exception:
            return False


# ============================================================
# 统一窗口截图函数
# ============================================================

def capture_window(hwnd, debugmode=False, save=True):
    """
    使用物理屏幕坐标获取窗口截图。
    返回：(screenshot, (left, top, right, bottom))
    """

    try:
        if not win32gui.IsWindow(hwnd):
            return None, None

        # 获取窗口真实屏幕坐标
        rect = win32gui.GetWindowRect(hwnd)
        left, top, right, bottom = map(int, rect)

        width = right - left
        height = bottom - top

        if width <= 0 or height <= 0:
            return None, None

        # 使用物理屏幕坐标截图
        screenshot = ImageGrab.grab(
            bbox=(left, top, right, bottom),
            all_screens=True
        )

        if debugmode:
            print(
                f"📸 截图坐标：{left},{top},{right},{bottom}"
            )
            print(
                f"📐 窗口尺寸：{width}x{height} "
                f"| 实际截图：{screenshot.width}x{screenshot.height}"
            )

            if save:
                save_screenshot(screenshot)

        return screenshot, (left, top, right, bottom)

    except Exception as e:
        print(f"❌ 截图失败：{e}")
        return None, None


# ============================================================
# 统一 OCR 识别函数
# ============================================================

def recognize_window(hwnd, debugmode=False, lang="eng"):
    screenshot, bbox = capture_window(
        hwnd,
        debugmode=debugmode
    )

    if screenshot is None:
        return None, [], None

    try:
        data = pytesseract.image_to_data(
            screenshot,
            lang=lang,
            output_type=pytesseract.Output.DICT
        )

        merged_lines = parse_and_merge_ocr_data(data)

        return screenshot, merged_lines, bbox

    except Exception as e:
        print(f"❌ OCR 异常：{e}")
        return screenshot, [], bbox


# ============================================================
# 窗口更新检测及自动点击
# ============================================================

def check_and_click_updater(
    trigger_keyword=["isavailable", "发现新版本"],
    button_keyword=["Updatelauncher", "CUpdate", "更新启动器"],
    prepare_keyword=["Preparingruntimeenvironment", "正在准备运行环境"],
    updating_keyword=["Updating", "启动器更新中"],
    debugmode: bool = False
):
    """
    检查目标窗口是否出现启动器更新提示。

    检测到更新提示后：
        1. OCR 寻找更新按钮。
        2. 点击更新按钮。
        3. 重新截图并 OCR 验证更新状态。
        4. 检测到更新中后最小化窗口。

    返回：
        True  : 正常运行或成功进入更新状态
        False : 更新操作失败
        0     : 未找到有效窗口
    """

    enable_dpi_awareness()

    valid_windows = []

    # --------------------------------------------------------
    # 1. 枚举并筛选目标窗口
    # --------------------------------------------------------

    def enum_windows_callback(hwnd, extra):

        if not win32gui.IsWindowVisible(hwnd):
            return

        title = win32gui.GetWindowText(hwnd).strip()

        if not title:
            return

        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)

            width = right - left
            height = bottom - top

            _, pid = win32process.GetWindowThreadProcessId(hwnd)

            proc = psutil.Process(pid)
            pname = proc.name().lower()

        except Exception:
            return

        # 进程过滤
        if pname != TARGET_PROCESS.lower():
            return

        # 标题过滤
        if TARGET_TITLE_KEYWORD.lower() not in title.lower():
            return

        # 黑名单过滤
        if any(
            black.lower() in title.lower()
            for black in WINDOW_BLACKLIST
        ):
            print(f"  [跳过黑名单] 标题：{title}")
            return

        # 最小尺寸过滤
        if width < MIN_WIDTH or height < MIN_HEIGHT:
            print(
                f"  [跳过尺寸过小] "
                f"标题：{title}，尺寸：{width}x{height}"
            )
            return

        valid_windows.append({
            "hwnd": hwnd,
            "title": title,
            "pid": pid,
            "pname": pname,
            "bbox": (left, top, right, bottom)
        })

    win32gui.EnumWindows(enum_windows_callback, None)

    if not valid_windows:
        print(
            f"未找到符合条件的窗口！"
            f"进程：{TARGET_PROCESS}，"
            f"标题关键词：{TARGET_TITLE_KEYWORD}"
        )
        return 0

    print(
        f"✅ 成功精准锁定 {len(valid_windows)} 个目标窗口：\n"
        + "=" * 65
    )

    total_clicked = 0

    # --------------------------------------------------------
    # 2. 逐个处理目标窗口
    # --------------------------------------------------------

    for idx, win in enumerate(valid_windows, 1):

        print(f"\n【目标窗口 {idx}】")
        print(f"  - 窗口标题：{win['title']}")
        print(
            f"  - 所属进程：{win['pname']} "
            f"(PID: {win['pid']})"
        )

        hwnd = win["hwnd"]

        if not win32gui.IsWindow(hwnd):
            print(f"  [跳过] 窗口句柄失效：{hwnd}")
            continue

        # ----------------------------------------------------
        # 3. 恢复窗口
        # ----------------------------------------------------

        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.3)

            if not win32gui.IsWindow(hwnd):
                continue

            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.5)

        except Exception as e:
            print(f"  [提示] 窗口激活失败：{e}")
            continue

        # ----------------------------------------------------
        # 4. 初次 OCR 检测
        # ----------------------------------------------------

        merged_lines = []

        for attempt in range(1, 3):

            print(f"🔍 正在执行 OCR 检测 ({attempt}/2)...")

            screenshot, merged_lines, screenshot_bbox = recognize_window(
                hwnd,
                debugmode=debugmode,
                lang="eng"
            )

            if screenshot is None:
                print("⚠️ 截图失败")

                if attempt < 2:
                    time.sleep(0.5)
                    continue

                break

            # 检测准备运行环境
            if contains_keyword(
                merged_lines,
                prepare_keyword
            ):
                print(
                    f"✅ 窗口 [{win['title']}] "
                    f"检测到正在准备运行环境"
                )
                return True

            # 原代码中 AzurPilot 检测被强制设置为 True，
            # 因此保留原来的跳过行为。
            break

        if not merged_lines:
            print("⚠️ OCR 未获取到有效文本")

        # ----------------------------------------------------
        # 5. 检测更新提示
        # ----------------------------------------------------

        has_update_notice = contains_keyword(
            merged_lines,
            trigger_keyword
        )

        if not has_update_notice:
            print(
                f"ℹ️ 窗口 [{win['title']}] "
                f"未检测到更新提示信息"
            )
            continue

        print(
            f"⚠️ 窗口 [{win['title']}] "
            f"检测到启动器更新提示"
        )

        # --------------------------------------------------------
        # 寻找更新按钮
        # --------------------------------------------------------

        btn_line = None

        for line in merged_lines:
            if contains_keyword([line], button_keyword):
                btn_line = line
                break

        # 获取当前截图对应的窗口坐标
        screenshot, _, screenshot_bbox = recognize_window(
            hwnd,
            debugmode=debugmode,
            lang="eng"
        )

        if screenshot_bbox is None:
            print("❌ 无法获取当前窗口截图坐标")
            return False

        left, top, right, bottom = screenshot_bbox

        if not btn_line:
            have_btn = False
            print("⚠️ OCR 未识别到更新按钮，使用备用坐标")

            # 截图内部相对坐标
            relative_x = 1170
            relative_y = 771

            # 转换为屏幕绝对坐标
            screen_click_x = left + relative_x
            screen_click_y = top + relative_y

            print(
                f"🎯 备用点击：相对坐标 "
                f"({relative_x}, {relative_y})"
            )

        else:
            have_btn = True
            print(f"🎯 识别按钮：【{btn_line['text']}】")

            # OCR 截图内部坐标
            relative_x = btn_line["x"] + btn_line["w"] / 2
            relative_y = btn_line["y"] + btn_line["h"] / 2

            # 转换为屏幕绝对坐标
            screen_click_x = left + relative_x
            screen_click_y = top + relative_y

        print(
            f"🖱️ 最终屏幕绝对点击坐标："
            f"({screen_click_x:.1f}, {screen_click_y:.1f})"
        )

        # ----------------------------------------------------
        # 8. 最多重试三次
        # ----------------------------------------------------

        max_retries = 3

        for click_attempt in range(1, max_retries + 1):

            print(
                f"  👉 第 {click_attempt}/{max_retries} "
                f"次尝试点击..."
            )

            if debugmode:
                print("  🧪 调试模式：跳过实际点击")
            else:
                if click_attempt == 1:
                    click_at(
                        screen_click_x,
                        screen_click_y
                    )
                    print(f"click{screen_click_x},{screen_click_y}")
                else:
                    print("..不要再点了啦(✿◡‿◡)..")

            total_clicked += 1

            time.sleep(1.0)

            # ------------------------------------------------
            # 9. 更新状态复检
            # ------------------------------------------------

            try:

                if not win32gui.IsWindow(hwnd):
                    print("❌ 更新状态校验失败：窗口已关闭")
                    continue

                # 尝试激活窗口，但激活失败不影响后续截图
                try:
                    if win32gui.IsWindow(hwnd):
                        if win32gui.IsIconic(hwnd):
                            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

                        win32gui.SetForegroundWindow(hwnd)
                        time.sleep(0.5)

                except Exception as e:
                    print(f"⚠️ 窗口激活失败，不影响后续状态校验：{e}")

                # 直接进行截图和 OCR
                try:
                    screenshot_retry, merged_lines_retry, screenshot_bbox_retry = recognize_window(
                        hwnd,
                        debugmode=debugmode,
                        lang="chi_sim+eng"
                    )

                    if screenshot_retry is None:
                        print("⚠️ 状态校验截图失败")
                        continue

                    is_updating = contains_keyword(
                        merged_lines_retry,
                        updating_keyword
                    )

                    if is_updating:
                        print("⏳ 检测到启动器更新中，正在最小化窗口...")

                        win32gui.ShowWindow(
                            hwnd,
                            win32con.SW_MINIMIZE
                        )

                        return True

                    save_screenshot(screenshot_retry)
                    
                    print("⚠️ 未检测到启动器更新中")

                except Exception as e:
                    print(f"❌ 状态校验异常：{e}")

                if screenshot_retry is None:
                    print("⚠️ 更新状态截图失败")
                    continue

                # 注意：这里必须使用 merged_lines_retry
                is_updating = contains_keyword(
                    merged_lines_retry,
                    updating_keyword
                )

                if is_updating:

                    print(
                        "⏳ 检测到启动器更新中，"
                        "正在最小化窗口..."
                    )

                    win32gui.ShowWindow(
                        hwnd,
                        win32con.SW_MINIMIZE
                    )

                    return True

                print("⚠️ 未检测到启动器更新中")

            except Exception as e:
                print(f"❌ 状态校验异常：{e}")

        # ----------------------------------------------------
        # 10. 三次点击失败
        # ----------------------------------------------------

        print(
            f"❌ 已达到最大重试次数 "
            f"({max_retries} 次)，"
            f"仍未能进入更新状态。"
        )

        return False

    return True



if __name__ == "__main__":
    check_and_click_updater(debugmode=True)
    # check_and_click_updater()