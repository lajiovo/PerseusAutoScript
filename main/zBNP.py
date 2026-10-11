import zPerseusLogger
import os
import sys
import time
import subprocess
import threading
import queue
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
    """
    def __init__(self, on_log_callback=None, on_stdout_callback=None, on_exit_callback=None):
        self.process = None
        self.stop_event = threading.Event()
        self.on_log_callback = on_log_callback
        self.on_stdout_callback = on_stdout_callback
        self.on_exit_callback = on_exit_callback
        self.is_running = False

    def start_process(self):
        """启动外部程序及其监听线程"""
        if self.is_running:
            return False, "程序已经在运行中！"

        if not os.path.exists(EXE_PATH):
            return False, f"未找到程序文件: {EXE_PATH}"

        self.stop_event.clear()
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

    def _tail_log_worker(self):
        """后台线程：实时监听 log 文件"""
        while not self.stop_event.is_set():
            if os.path.exists(LOG_PATH):
                break
            time.sleep(0.2)
            
        try:
            with open(LOG_PATH, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(0, os.SEEK_END)  # 从文件末尾或头部开始，可改为 SEEK_SET
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
            if self.on_exit_callback:
                self.on_exit_callback(returncode)

class BNPApp:
    """
    Tkinter 图艺界面主窗口
    """
    def __init__(self, root):
        self.root = root
        self.root.title("BNP 自动化控制中心")
        self.root.geometry("900x650")
        
        # 设置基础样式主题
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # 消息队列用于线程安全的 UI 交互
        self.queue = queue.Queue()

        # 初始化控制器
        self.controller = BNPController(
            on_log_callback=lambda msg: self.queue.put(("LOG", msg)),
            on_stdout_callback=lambda msg: self.queue.put(("STDOUT", msg)),
            on_exit_callback=lambda code: self.queue.put(("EXIT", code))
        )

        self.create_widgets()
        
        # 启动队列轮询定时器
        self.root.after(100, self.process_queue)

    def create_widgets(self):
        """构建界面组件"""
        # 顶部控制面板
        control_frame = ttk.LabelFrame(self.root, text=" 运行控制 ", padding=10)
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        self.btn_start = ttk.Button(control_frame, text="启动程序", command=self.handle_start)
        self.btn_start.pack(side=tk.LEFT, padx=5)

        self.btn_stop = ttk.Button(control_frame, text="终止程序", command=self.handle_stop, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=5)

        self.lbl_status = ttk.Label(control_frame, text="状态: 未运行", foreground="red")
        self.lbl_status.pack(side=tk.RIGHT, padx=5)

        # 中部日志与输出展示区
        log_frame = ttk.LabelFrame(self.root, text=" 实时控制台与日志 ", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.text_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, font=("Consolas", 10))
        self.text_area.pack(fill=tk.BOTH, expand=True)
        # 配置标签颜色
        self.text_area.tag_config("LOG", foreground="#0066cc")
        self.text_area.tag_config("STDOUT", foreground="#333333")
        self.text_area.tag_config("SYSTEM", foreground="#cc0000")

        # 底部指令输入区
        input_frame = ttk.LabelFrame(self.root, text=" 命令下发 ", padding=10)
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
            self.lbl_status.config(text="状态: 运行中", foreground="green")
            self.append_log(f"[系统] {msg}\n", "SYSTEM")
        else:
            messagebox.showerror("错误", msg)

    def handle_stop(self):
        """点击终止按钮"""
        self.controller.terminate_process()
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.lbl_status.config(text="状态: 已停止", foreground="red")
        self.append_log("[系统] 用户手动终止程序。\n", "SYSTEM")

    def handle_send_input(self):
        """点击发送按钮或回车输入"""
        cmd = self.entry_input.get()
        if not cmd.strip():
            return
        
        # 调用可以直接调用的函数发送输入
        success, msg = self.controller.send_input(cmd)
        if success:
            self.append_log(f"[INPUT ->] {cmd}\n", "SYSTEM")
            self.entry_input.delete(0, tk.END)
        else:
            messagebox.showwarning("提示", msg)

    def append_log(self, text, tag="STDOUT"):
        """向文本框安全追加内容"""
        print(text)
        self.text_area.insert(tk.END, text, tag)
        self.text_area.see(tk.END)

    def process_queue(self):
        """轮询后台线程放入队列的消息，安全更新 UI"""
        try:
            while True:
                msg_type, content = self.queue.get_nowait()
                if msg_type == "LOG":
                    self.append_log(content, "LOG")
                elif msg_type == "STDOUT":
                    self.append_log(content, "STDOUT")
                elif msg_type == "EXIT":
                    self.btn_start.config(state=tk.NORMAL)
                    self.btn_stop.config(state=tk.DISABLED)
                    self.lbl_status.config(text=f"状态: 已退出 (返回码 {content})", foreground="red")
                    self.append_log(f"\n[系统] 程序已退出，返回码: {content}\n", "SYSTEM")
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_queue)

if __name__ == "__main__":
    root = tk.Tk()
    app = BNPApp(root)
    root.mainloop()