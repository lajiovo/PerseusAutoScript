import win32gui
import win32process
import win32api
import win32con
import psutil
import pytesseract
from PIL import ImageGrab
import time
import re
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


def check_and_click_updater(trigger_keyword="发现新版本", button_keyword="更新启动器"):
    """
    检查目标窗口中是否出现类似“发现新版本x.x.x,请先更新启动器”的提示，
    如果匹配成功，则自动寻找并点击按钮（如“C更新启动器”、“更新启动器”等）。
    首次点击后校验是否处于“启动器更新中”，若是则最小化窗口，否则重试点击。
    
    :param trigger_keyword: 提示框中的触发关键词（正则表达式或字符串）
    :param button_keyword: 需要点击的目标按钮文本关键词
    :return: 成功执行点击的次数
    """
    valid_windows = []

    def enum_windows_callback(hwnd, extra):
        # 1. 必须是可见窗口
        if not win32gui.IsWindowVisible(hwnd):
            return
            
        title = win32gui.GetWindowText(hwnd).strip()
        if not title:
            return
            
        # 2. 获取窗口坐标与尺寸
        rect = win32gui.GetWindowRect(hwnd)
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top
        
        # 3. 获取该窗口所属的进程名称和 PID
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid)
            pname = proc.name().lower()
        except Exception:
            pname = ""
            pid = 0

        # --- 严格过滤逻辑 ---
        if pname != TARGET_PROCESS.lower():
            return
            
        if TARGET_TITLE_KEYWORD.lower() not in title.lower():
            return
            
        if any(black in title.lower() for black in WINDOW_BLACKLIST):
            print(f"  [跳过黑名单] 标题: 「{title}」 (进程: {pname})")
            return
            
        if width < MIN_WIDTH or height < MIN_HEIGHT:
            print(f"  [跳过尺寸过小] 标题: 「{title}」 尺寸: {width}x{height}")
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
        print(f"未找到任何同时满足进程 '{TARGET_PROCESS}' 且标题包含 '{TARGET_TITLE_KEYWORD}' 的有效窗口！")
        return 0

    print(f"✅ 成功精准锁定 {len(valid_windows)} 个目标窗口：\n" + "=" * 65)
    total_clicked = 0

    for idx, win in enumerate(valid_windows, 1):
        print(f"\n【目标窗口 {idx}】")
        print(f"  - 窗口标题 : {win['title']}")
        print(f"  - 所属进程 : {win['pname']} (PID: {win['pid']})")
        print(f"  - 绝对坐标 : 左上角 {win['bbox'][:2]}, 宽高 {win['bbox'][2]-win['bbox'][0]}x{win['bbox'][3]-win['bbox'][1]}")
        print("-" * 65)

        hwnd = win['hwnd']
        
        if not win32gui.IsWindow(hwnd):
            print(f"  [跳过] 窗口句柄已失效或已被销毁: {hwnd}")
            continue

        # 1. 恢复最小化
        if win32gui.IsIconic(hwnd):
            try:
                win32gui.ShowWindow(hwnd, 9) # SW_RESTORE
                time.sleep(0.3)
            except Exception:
                pass

        # 2. 安全地尝试激活并置顶窗口
        try:
            if win32gui.IsWindow(hwnd):
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.5)
        except Exception as e:
            print(f"  [提示] 窗口置顶受限或已关闭，跳过此轮：{e}")
            continue

        # 3. 再次校验并实时获取最新坐标
        try:
            if not win32gui.IsWindow(hwnd):
                continue
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        except Exception:
            continue

        # DPI 坐标缩放计算
        real_left = int(left * DPI_SCALE)
        real_top = int(top * DPI_SCALE)
        real_right = int(right * DPI_SCALE)
        real_bottom = int(bottom * DPI_SCALE)

        # 进行 OCR 截屏识别与校验（包含 AzurPilot 缺失重试逻辑）
        azur_attempts = 0
        merged_lines = []
        while azur_attempts < 2:
            azur_attempts += 1
            # 截图并进行 OCR
            screenshot = ImageGrab.grab(bbox=(real_left, real_top, real_right, real_bottom))
            data = pytesseract.image_to_data(screenshot, lang='chi_sim+eng', output_type=pytesseract.Output.DICT)
            merged_lines = parse_and_merge_ocr_data(data)

            # 1. 如果结果中包含“正在准备运行环境”，直接返回 True
            if any("正在准备运行环境" in line['text'] for line in merged_lines):
                print(f"✅ 窗口 [{win['title']}] 检测到 '正在准备运行环境'，直接返回 True")
                return True

            # 检查是否有 AzurPilot 文本
            has_azurpilot = any("azurpilot" in line['text'].lower() for line in merged_lines)
            if has_azurpilot:
                break
            else:
                print(f"⚠️ 第 {azur_attempts}/2 次未在 OCR 结果中检测到 'AzurPilot'")
                if azur_attempts < 2:
                    print("  🔄 尝试重新置顶窗口并再次识别...")
                    try:
                        if win32gui.IsWindow(hwnd):
                            win32gui.SetForegroundWindow(hwnd)
                            time.sleep(0.5)
                            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                            real_left = int(left * DPI_SCALE)
                            real_top = int(top * DPI_SCALE)
                            real_right = int(right * DPI_SCALE)
                            real_bottom = int(bottom * DPI_SCALE)
                    except Exception as e:
                        print(f"  ❌ 重置窗口失败: {e}")

        # 如果尝试 2 次后仍未检测到 AzurPilot，返回 0
        if not any("azurpilot" in line['text'].lower() for line in merged_lines):
            print(f"❌ 尝试 2 次后仍未在 OCR 结果中检索到 'AzurPilot'，失败返回 0")
            return 0

        # 检查所有文本行中是否出现了更新提示
        has_update_notice = any(trigger_keyword in line['text'] for line in merged_lines)

        if has_update_notice:
            print(f"⚠️ 窗口 [{win['title']}] 检测到更新提示（匹配词: '{trigger_keyword}'）")

            # 寻找符合点击条件的按钮（可能包含噪声字符如 "C更新启动器"）
            btn_line = None
            for line in merged_lines:
                if button_keyword in line['text']:
                    btn_line = line
                    break

            if not btn_line:
                print(f"❌ 检测到更新提示，但未找到对应的按钮关键词: '{button_keyword}'")
                return False

            print(f"🎯 找到匹配按钮文本行: 【{btn_line['text']}】")

            # 计算在截图图片上的逻辑像素中心点
            btn_center_x_ocr = btn_line['x'] + btn_line['w'] / 2
            btn_center_y_ocr = btn_line['y'] + btn_line['h'] / 2

            # 换算为屏幕真实物理像素坐标（先加屏幕左上偏移，再除以 DPI 缩放回到物理屏幕点）
            screen_click_x = (real_left + btn_center_x_ocr) / DPI_SCALE
            screen_click_y = (real_top + btn_center_y_ocr) / DPI_SCALE

            # 重试最多3次点击
            max_retries = 3
            for attempt in range(1, max_retries + 1):
                print(f"  👉 第 {attempt}/{max_retries} 次尝试点击...")
                click_at(screen_click_x, screen_click_y)
                total_clicked += 1
                time.sleep(1.0)  # 等待更新状态响应与界面刷新

                # 再次截屏校验是否在更新中
                try:
                    if win32gui.IsWindow(hwnd):
                        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                        real_left = int(left * DPI_SCALE)
                        real_top = int(top * DPI_SCALE)
                        real_right = int(right * DPI_SCALE)
                        real_bottom = int(bottom * DPI_SCALE)
                        
                        screenshot_retry = ImageGrab.grab(bbox=(real_left, real_top, real_right, real_bottom))
                        data_retry = pytesseract.image_to_data(screenshot_retry, lang='chi_sim+eng', output_type=pytesseract.Output.DICT)
                        merged_lines_retry = parse_and_merge_ocr_data(data_retry)

                        # 判断是否存在“启动器更新中”
                        is_updating = any("启动器更新中" in l['text'] for l in merged_lines_retry)

                        if is_updating:
                            print(f"⏳ 检测到 '启动器更新中'，正在最小化窗口...")
                            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                            return True
                        else:
                            print(f"⚠️ 未检测到 '启动器更新中'。")
                except Exception as e:
                    print(f"  ❌ 状态校验异常: {e}")

            # 3次点击后仍未识别到“启动器更新中”
            print(f"❌ 已达到最大重试次数 ({max_retries} 次)，仍未能进入更新状态。")
            return False
        else:
            print(f"ℹ️ 窗口 [{win['title']}] 未检测到更新提示信息。")
            return True

    return True


if __name__ == "__main__":
    check_and_click_updater(trigger_keyword="发现新版本", button_keyword="更新启动器")