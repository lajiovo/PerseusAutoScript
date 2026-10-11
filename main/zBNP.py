import os
import sys
import time
import subprocess
import threading
import queue
import re
import shutil
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

# 模拟配置获取（如无 zConfig 模块，提供默认兜底）
try:
    from zConfig import get_config
    EXE_DIR = get_config("bnp.exe_dir")
    EXE_PATH = os.path.join(EXE_DIR, get_config("bnp.exe_path"))
    LOG_PATH = os.path.join(EXE_DIR, get_config("bnp.log_path"))
except ImportError:
    # 默认当前目录测试用
    EXE_DIR = os.getcwd()
    EXE_PATH = os.path.join(EXE_DIR, "bnp.exe")
    LOG_PATH = os.path.join(EXE_DIR, "bnp.log")

class BNPController:
    """
    BNP 程序核心控制器：管理子进程、输入输出、日志监听，
    并通过线程安全队列将底层事件回调到 UI 界面。
    同时内置了针对 bili_novel_packer 的智能状态解析器。
    """
    def __init__(self, on_log_callback=None, on_stdout_callback=None, on_exit_callback=None, on_state_change=None):
        self.process = None
        self.stop_event = threading.Event()
        self.on_log_callback = on_log_callback
        self.on_stdout_callback = on_stdout_callback
        self.on_exit_callback = on_exit_callback
        self.on_state_change = on_state_change
        self.is_running = False

        # 进度与状态追踪属性
        self.current_state = "IDLE"  # IDLE, WAITING_URL, WAITING_VOLUME, WAITING_TITLE_CONFIG, DOWNLOADING, FINISHED
        self.book_title = ""
        self.book_author = ""
        self.volumes = []  # 存储解析出来的分卷列表: [{"id": "1", "name": "怪人的沙拉碗 1"}, ...]
        self._accumulator = "" # 用于多行文本累积分析

    def start_process(self):
        """启动外部程序及其监听线程"""
        if self.is_running:
            return False, "程序已经在运行中！"

        if not os.path.exists(EXE_PATH):
            return False, f"未找到程序文件: {EXE_PATH}"

        self.stop_event.clear()
        self.current_state = "STARTING"
        self.volumes.clear()
        self._accumulator = ""
        
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        try:
            self.process = subprocess.Popen(
                [EXE_PATH],
                cwd=EXE_DIR,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='ignore',
                bufsize=1,
                env=env
            )
            self.is_running = True

            # 启动后台工作线程
            threading.Thread(target=self._tail_log_worker, daemon=True).start()
            threading.Thread(target=self._read_stdout_worker, daemon=True).start()
            threading.Thread(target=self._monitor_exit_worker, daemon=True).start()

            return True, "程序启动成功"
        except Exception as e:
            self.is_running = False
            self.current_state = "IDLE"
            return False, f"启动失败: {str(e)}"

    def send_input(self, text):
        """
        直接调用的输入函数：向子进程的 stdin 发送文本命令
        """
        if not self.is_running or not self.process:
            return False, "程序未运行，无法发送输入"
        try:
            if not text.endswith('\n'):
                text += '\n'
            self.process.stdin.write(text)
            self.process.stdin.flush()
            return True, f"已发送: {text.strip()}"
        except Exception as e:
            return False, f"发送输入异常: {str(e)}"

    # ==================== 直接调用的高级控制函数 ====================
    def download_novel(self, url: str):
        """直接调用函数：开始下载指定链接的小说"""
        if self.current_state != "WAITING_URL":
            return False, f"当前状态 ({self.current_state}) 不允许直接输入链接"
        return self.send_input(url)

    def select_volume(self, volume_index: str):
        """直接调用函数：指定分卷编号进行下载"""
        if self.current_state != "WAITING_VOLUME":
            return False, f"当前状态 ({self.current_state}) 不允许选择分卷"
        return self.send_input(str(volume_index))

    def choose_chapter_title_config(self, include_title: bool):
        """直接调用函数：是否在每章开头添加章节标题 ('1' 代表是, '2' 代表否)"""
        if self.current_state != "WAITING_TITLE_CONFIG":
            return False, f"当前状态 ({self.current_state}) 不允许设置章节标题选项"
        val = "1" if include_title else "2"
        return self.send_input(val)

    def get_progress_info(self):
        """直接调用函数：获取目前的进展在哪一步及详细上下文"""
        return {
            "is_running": self.is_running,
            "state": self.current_state,
            "book_title": self.book_title,
            "book_author": self.book_author,
            "volumes": self.volumes
        }

    # ==================== 新增扩展函数 ① & ② ====================
    def get_all_epub_files(self):
        """
        额外函数①：获取 EXE_DIR 文件夹（以及递归子目录，或直接平级目录）内的所有 epub 文件名。
        返回包含文件绝对路径或文件名的列表。
        """
        epub_files = []
        try:
            if os.path.exists(EXE_DIR):
                for root, dirs, files in os.walk(EXE_DIR):
                    for file in files:
                        if file.lower().endswith('.epub'):
                            epub_files.append(os.path.join(root, file))
        except Exception as e:
            print(f"[系统] 扫描 epub 文件异常: {e}")
        return epub_files

    def move_epubs_to_output_folder(self):
        """
        额外函数②：将 EXE_DIR 内所有的 epub 文件移动到 get_config("bnp.output_floder") 
        绝对路径对应的文件夹。如果目标文件夹不存在则自动创建。
        返回 (成功数量, 错误信息/提示)
        """
        try:
            # 获取配置的目标输出文件夹
            output_dir = get_config("bnp.output_floder")
            if not output_dir:
                return 0, "未配置输出文件夹路径 (bnp.output_floder)"

            # 确保目标文件夹绝对路径存在
            if not os.path.isabs(output_dir):
                # 如果是相对路径，基于 EXE_DIR 解析
                output_dir = os.path.abspath(os.path.join(EXE_DIR, output_dir))

            if not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)

            epub_list = self.get_all_epub_files()
            if not epub_list:
                return 0, "未在程序目录中找到任何 .epub 文件"

            moved_count = 0
            for src_path in epub_list:
                if not os.path.exists(src_path):
                    continue
                file_name = os.path.basename(src_path)
                dest_path = os.path.join(output_dir, file_name)

                # 防止同名文件覆盖冲突，自动重命名或直接覆盖
                if os.path.exists(dest_path):
                    base, ext = os.path.splitext(file_name)
                    timestamp = int(time.time())
                    dest_path = os.path.join(output_dir, f"{base}_{timestamp}{ext}")

                shutil.move(src_path, dest_path)
                moved_count += 1

            return moved_count, f"成功移动 {moved_count} 个 epub 文件到: {output_dir}"
        except Exception as e:
            return 0, f"移动 epub 文件失败: {str(e)}"
    # ===============================================================

    def terminate_process(self):
        """终止子进程运行"""
        if not self.is_running or not self.process:
            return
        self.stop_event.set()
        try:
            self.process.terminate()
            self.process.wait(timeout=2)
        except Exception:
            try:
                self.process.kill()
            except Exception:
                pass
        self.is_running = False
        self.current_state = "IDLE"
        if self.on_state_change:
            self.on_state_change(self.current_state, "程序已手动终止")

    def _analyze_line(self, line):
        """
        智能状态解析引擎：逐行扫描输出，分析当前程序阶段、小说元数据及分卷列表
        """
        clean_line = line.strip()
        self._accumulator += line

        # 1. 检查是否在请求输入链接
        if "请输入链接(多个链接使用空格隔开):" in clean_line:
            self.current_state = "WAITING_URL"
            if self.on_state_change:
                self.on_state_change(self.current_state, "等待用户输入小说链接...")

        # 2. 检查书籍作者
        if "作者:" in clean_line and not self.book_author:
            pass

        # 3. 解析分卷行格式如: [ 1] 怪人的沙拉碗 1
        vol_match = re.search(r'\[\s*(\d+)\]\s+(.+)', clean_line)
        if vol_match and self.current_state in ["WAITING_URL", "WAITING_VOLUME"]:
            v_id = vol_match.group(1)
            v_name = vol_match.group(2).strip()
            # 排除非分卷选项（如选择全部 [ 0]）
            if v_id != "0":
                if not any(v['id'] == v_id for v in self.volumes):
                    self.volumes.append({"id": v_id, "name": v_name})

        # 4. 检查是否在请求选择分卷
        if "请选择要下载的分卷:" in clean_line:
            self.current_state = "WAITING_VOLUME"
            if self.on_state_change:
                self.on_state_change(self.current_state, f"已解析到 {len(self.volumes)} 个分卷，等待选择分卷...")

        # 5. 检查是否在请求是否添加章节标题
        if "是否在每章开头添加章节标题?" in clean_line:
            self.current_state = "WAITING_TITLE_CONFIG"
            if self.on_state_change:
                self.on_state_change(self.current_state, "等待选择是否添加章节标题...")

        # 6. 检查是否开始打包
        if "开始打包" in clean_line:
            self.current_state = "DOWNLOADING"
            if self.on_state_change:
                self.on_state_change(self.current_state, clean_line)

        # 7. 检查是否打包完成
        if "打包完成:" in clean_line:
            self.current_state = "FINISHED"
            if self.on_state_change:
                self.on_state_change(self.current_state, clean_line)

    def _tail_log_worker(self):
        """后台线程：实时监听 log 文件"""
        while not self.stop_event.is_set():
            if os.path.exists(LOG_PATH):
                break
            time.sleep(0.2)
            
        try:
            with open(LOG_PATH, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(0, os.SEEK_END)
                while not self.stop_event.is_set():
                    line = f.readline()
                    if line:
                        if self.on_log_callback:
                            self.on_log_callback(line)
                    else:
                        time.sleep(0.2)
        except Exception as e:
            if self.on_log_callback:
                self.on_log_callback(f"[系统] 读取日志异常: {e}\n")

    def _read_stdout_worker(self):
        """后台线程：读取 exe 原生标准输出"""
        try:
            for line in iter(self.process.stdout.readline, ''):
                if line:
                    self._analyze_line(line)
                    if self.on_stdout_callback:
                        self.on_stdout_callback(line)
                if self.stop_event.is_set():
                    break
        except Exception:
            pass

    def _monitor_exit_worker(self):
        """监控进程退出"""
        if self.process:
            returncode = self.process.wait()
            self.is_running = False
            self.stop_event.set()
            self.current_state = "IDLE"
            if self.on_exit_callback:
                self.on_exit_callback(returncode)

class BNPApp:
    """
    Tkinter 图形界面主窗口：集成状态可视化监控与便捷控制面板
    """
    def __init__(self, root):
        self.root = root
        self.root.title("BNP 自动化控制中心 (内置智能解析与文件管理)")
        self.root.geometry("1050x800")
        
        self.style = ttk.Style()
        self.style.theme_use('clam')

        self.queue = queue.Queue()

        # 初始化控制器并绑定状态改变回调
        self.controller = BNPController(
            on_log_callback=lambda msg: self.queue.put(("LOG", msg)),
            on_stdout_callback=lambda msg: self.queue.put(("STDOUT", msg)),
            on_exit_callback=lambda code: self.queue.put(("EXIT", code)),
            on_state_change=lambda state, desc: self.queue.put(("STATE", (state, desc)))
        )

        self.create_widgets()
        self.root.after(100, self.process_queue)

    def create_widgets(self):
        """构建现代风格界面组件"""
        # 1. 顶部：运行与状态监控面板
        top_frame = ttk.LabelFrame(self.root, text=" 运行控制与状态追踪 ", padding=10)
        top_frame.pack(fill=tk.X, padx=10, pady=10)

        btn_row = ttk.Frame(top_frame)
        btn_row.pack(fill=tk.X, pady=(0, 8))

        self.btn_start = ttk.Button(btn_row, text="启动程序", command=self.handle_start)
        self.btn_start.pack(side=tk.LEFT, padx=5)

        self.btn_stop = ttk.Button(btn_row, text="终止程序", command=self.handle_stop, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=5)

        # 新增：文件管理快捷按钮
        self.btn_scan_epub = ttk.Button(btn_row, text="扫描EPUB文件", command=self.handle_scan_epubs)
        self.btn_scan_epub.pack(side=tk.LEFT, padx=5)

        self.btn_move_epub = ttk.Button(btn_row, text="移动EPUB到输出目录", command=self.handle_move_epubs)
        self.btn_move_epub.pack(side=tk.LEFT, padx=5)

        self.lbl_status = ttk.Label(btn_row, text="状态: 未运行", font=("Arial", 10, "bold"), foreground="red")
        self.lbl_status.pack(side=tk.RIGHT, padx=5)

        # 状态机引导提示卡片
        self.lbl_guide = ttk.Label(top_frame, text="当前无活动进程，请点击上方“启动程序”。", font=("Arial", 10), foreground="#0066cc")
        self.lbl_guide.pack(fill=tk.X, padx=5)

        # 2. 中部：分卷交互快捷面板（当解析到分卷时动态展示）
        self.volume_frame = ttk.LabelFrame(self.root, text=" 快捷操作分卷面板（自动识别） ", padding=10)
        self.volume_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.vol_combobox = ttk.Combobox(self.volume_frame, state="readonly", width=40, font=("Arial", 10))
        self.vol_combobox.pack(side=tk.LEFT, padx=5)
        
        self.btn_dl_vol = ttk.Button(self.volume_frame, text="下载选中分卷", command=self.handle_quick_download_vol, state=tk.DISABLED)
        self.btn_dl_vol.pack(side=tk.LEFT, padx=5)

        self.btn_title_yes = ttk.Button(self.volume_frame, text="加章节标题(是)", command=lambda: self.handle_title_config(True), state=tk.DISABLED)
        self.btn_title_yes.pack(side=tk.LEFT, padx=5)

        self.btn_title_no = ttk.Button(self.volume_frame, text="不加章节标题(否)", command=lambda: self.handle_title_config(False), state=tk.DISABLED)
        self.btn_title_no.pack(side=tk.LEFT, padx=5)

        # 3. 中下部：日志与输出展示区
        log_frame = ttk.LabelFrame(self.root, text=" 实时控制台与日志 ", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.text_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, font=("Consolas", 10))
        self.text_area.pack(fill=tk.BOTH, expand=True)
        self.text_area.tag_config("LOG", foreground="#0066cc")
        self.text_area.tag_config("STDOUT", foreground="#333333")
        self.text_area.tag_config("SYSTEM", foreground="#cc0000")
        self.text_area.tag_config("HIGHLIGHT", foreground="#008800", font=("Consolas", 10, "bold"))

        # 4. 底部：通用自由指令输入区
        input_frame = ttk.LabelFrame(self.root, text=" 通用命令下发 (Stdin) ", padding=10)
        input_frame.pack(fill=tk.X, padx=10, pady=10)

        self.entry_input = ttk.Entry(input_frame, font=("Arial", 11))
        self.entry_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.entry_input.bind("<Return>", lambda event: self.handle_send_input())

        self.btn_send = ttk.Button(input_frame, text="发送指令", command=self.handle_send_input)
        self.btn_send.pack(side=tk.RIGHT)

    def handle_start(self):
        """点击启动按钮"""
        success, msg = self.controller.start_process()
        if success:
            self.btn_start.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.NORMAL)
            self.append_log(f"[系统] {msg}\n", "SYSTEM")
        else:
            messagebox.showerror("错误", msg)

    def handle_stop(self):
        """点击终止按钮"""
        self.controller.terminate_process()
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.lbl_status.config(text="状态: 已停止", foreground="red")
        self.lbl_guide.config(text="程序已终止。")
        self.append_log("[系统] 用户手动终止程序。\n", "SYSTEM")

    def handle_scan_epubs(self):
        """点击扫描 epub 文件按钮"""
        epubs = self.controller.get_all_epub_files()
        if epubs:
            file_names = [os.path.basename(p) for p in epubs]
            msg = f"在目录中找到 {len(epubs)} 个 EPUB 文件:\n" + "\n".join(file_names)
            messagebox.showinfo("扫描结果", msg)
            self.append_log(f"[系统] 扫描到 {len(epubs)} 个 EPUB 文件\n", "SYSTEM")
        else:
            messagebox.showinfo("扫描结果", "未在工作目录中找到任何 EPUB 文件。")

    def handle_move_epubs(self):
        """点击移动 epub 到输出目录按钮"""
        count, msg = self.controller.move_epubs_to_output_folder()
        if count > 0:
            messagebox.showinfo("成功", msg)
            self.append_log(f"[系统] {msg}\n", "SYSTEM")
        else:
            messagebox.showwarning("提示", msg)

    def handle_send_input(self):
        """点击发送按钮或回车输入"""
        cmd = self.entry_input.get()
        if not cmd.strip():
            return
        
        success, msg = self.controller.send_input(cmd)
        if success:
            self.append_log(f"[INPUT ->] {cmd}\n", "HIGHLIGHT")
            self.entry_input.delete(0, tk.END)
        else:
            messagebox.showwarning("提示", msg)

    def handle_quick_download_vol(self):
        """快捷面板：下载选中的分卷"""
        selection = self.vol_combobox.get()
        if not selection:
            messagebox.showwarning("提示", "请先选择一个分卷！")
            return
        match = re.search(r'\[(\d+)\]', selection)
        if match:
            v_id = match.group(1)
            success, msg = self.controller.select_volume(v_id)
            if success:
                self.append_log(f"[INPUT ->] {v_id} (快捷选择分卷)\n", "HIGHLIGHT")
            else:
                messagebox.showwarning("提示", msg)

    def handle_title_config(self, include_title):
        """快捷面板：设置章节标题选项"""
        success, msg = self.controller.choose_chapter_title_config(include_title)
        if success:
            val_str = "1 (是)" if include_title else "2 (否)"
            self.append_log(f"[INPUT ->] {val_str} (快捷选择章节标题)\n", "HIGHLIGHT")
        else:
            messagebox.showwarning("提示", msg)

    def append_log(self, text, tag="STDOUT"):
        """向文本框安全追加内容"""
        print(text)
        self.text_area.insert(tk.END, text, tag)
        self.text_area.see(tk.END)

    def update_state_ui(self, state, desc):
        """根据解析出来的状态更新 UI 提示与按钮可用性"""
        self.lbl_status.config(text=f"状态: {state}", foreground="green" if state != "IDLE" else "red")
        self.lbl_guide.config(text=f"【智能解析进度】{desc}")

        if state == "WAITING_URL":
            self.btn_dl_vol.config(state=tk.DISABLED)
            self.btn_title_yes.config(state=tk.DISABLED)
            self.btn_title_no.config(state=tk.DISABLED)
        elif state == "WAITING_VOLUME":
            vol_items = [f"[{v['id']}] {v['name']}" for v in self.controller.volumes]
            self.vol_combobox['values'] = vol_items
            if vol_items:
                self.vol_combobox.current(0)
            self.btn_dl_vol.config(state=tk.NORMAL)
        elif state == "WAITING_TITLE_CONFIG":
            self.btn_dl_vol.config(state=tk.DISABLED)
            self.btn_title_yes.config(state=tk.NORMAL)
            self.btn_title_no.config(state=tk.NORMAL)
        elif state in ["DOWNLOADING", "FINISHED"]:
            self.btn_dl_vol.config(state=tk.DISABLED)
            self.btn_title_yes.config(state=tk.DISABLED)
            self.btn_title_no.config(state=tk.DISABLED)
            if state == "FINISHED":
                # 打包完成后自动触发一次将文件移动到输出目录的静默或提醒
                pass

    def process_queue(self):
        """轮询后台线程放入队列的消息，安全更新 UI"""
        try:
            while True:
                msg_type, content = self.queue.get_nowait()
                if msg_type == "LOG":
                    self.append_log(content, "LOG")
                elif msg_type == "STDOUT":
                    self.append_log(content, "STDOUT")
                elif msg_type == "STATE":
                    state, desc = content
                    self.update_state_ui(state, desc)
                elif msg_type == "EXIT":
                    self.btn_start.config(state=tk.NORMAL)
                    self.btn_stop.config(state=tk.DISABLED)
                    self.lbl_status.config(text=f"状态: 已退出 (返回码 {content})", foreground="red")
                    self.lbl_guide.config(text=f"程序已退出，返回码: {content}")
                    self.append_log(f"\n[系统] 程序已退出，返回码: {content}\n", "SYSTEM")
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_queue)

if __name__ == "__main__":
    root = tk.Tk()
    app = BNPApp(root)
    root.mainloop()