import os
import sys
import json
import shutil
import threading
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

# 导入配置模块 zConfig
try:
    from zConfig import get_config
except ImportError:
    # 备用容错：如果未找到 zConfig，提供默认回调
    def get_config(key: str, default=None):
        print(f"[警告] 无法导入 zConfig，使用默认配置 {key}")
        return default


def parse_cline_json_line(line_str: str) -> str:
    """
    解析 Cline CLI 输出的 NDJSON 单行并转换为人类易读的结构化日志
    """
    line_str = line_str.strip()
    if not line_str or not (line_str.startswith("{") and line_str.endswith("}")):
        return line_str

    try:
        data = json.loads(line_str)
        msg_type = data.get("type")

        # 1. 钩子与代理启动事件
        if msg_type == "hook_event":
            hook_name = data.get("hookEventName", "")
            task_id = data.get("taskId", "")
            return f"⚙️ [系统事件] Agent 已启动 (Task ID: {task_id})"

        # 2. 迭代轮次事件
        elif msg_type == "agent_event":
            evt = data.get("event", {})
            evt_type = evt.get("type", "")
            if evt_type == "iteration_start":
                iter_num = evt.get("iteration", 1)
                return f"🔄 [迭代开始] 正在进行第 {iter_num} 轮 AI 推理与决策..."
            return f"🤖 [Agent 状态] {evt_type}"

        # 3. 对话 / 思考 / 命令执行事件
        elif msg_type == "say" or "say" in data:
            say_type = data.get("say") or data.get("sayType")
            text = data.get("text") or data.get("content") or ""

            if say_type == "task":
                return f"📋 [接收任务] {text}"
            elif say_type == "text":
                return f"💬 [AI 回复]:\n{text}"
            elif say_type in ("thought", "reasoning"):
                return f"🧠 [AI 思考中]: {text}"
            elif say_type == "command":
                return f"⚡ [准备执行终端命令]: {text}"
            elif say_type == "tool":
                return f"🛠️ [准备使用工具]: {text}"
            elif say_type == "completion_result":
                return f"✅ [任务完成]: {text}"
            return f"💬 [{say_type}]: {text}"

        # 4. 任务结果完成事件
        elif msg_type == "completion_result":
            return f"✅ [任务完成]: {data.get('text', '已成功处理')}"

    except Exception:
        pass

    return line_str


class ClineRunner:
    """Cline CLI 接口封装类"""

    def __init__(self, project_dir: str = "."):
        self.project_dir = Path(project_dir).resolve()
        self.process = None
        self.is_cancelled = False

    def stop_task(self):
        """强制终止当前正在运行的 Cline 子进程"""
        self.is_cancelled = True
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass
            try:
                self.process.kill()
            except Exception:
                pass

    def get_cline_cmd(self) -> str:
        """动态查找 cline / cline.cmd 的可执行路径"""
        # 1. 系统 PATH 中查找
        path = shutil.which("cline")
        if path:
            return path
        
        # 2. Windows 平台特有的 npm 全局路径检查
        if sys.platform == "win32":
            appdata = os.environ.get("APPDATA", "")
            npm_cline = Path(appdata) / "npm" / "cline.cmd"
            if npm_cline.exists():
                return str(npm_cline)

        return "cline"

    def get_proxy_server(self) -> str:
        """从 zConfig 获取代理配置"""
        proxy = get_config("proxy.http")
        if not proxy:
            return ""
        # 补全协议前缀
        if not (proxy.startswith("http://") or proxy.startswith("https://") or proxy.startswith("socks5://")):
            proxy = f"http://{proxy}"
        return proxy

    def run_task(
        self,
        prompt: str,
        auto_approve: bool = True,
        plan_mode: bool = False,
        provider: str = "",
        model: str = "",
        api_key: str = "",
        thinking: str = "omitted",
        timeout: int = 0,
        session_id: str = "",
        system_prompt: str = "",
        format_json_log: bool = True,
        log_callback=None
    ) -> dict:
        """
        执行 Cline 任务接口，支持 CLI 参数扩展与日志格式化
        """
        def log(msg: str):
            if log_callback:
                log_callback(msg)
            else:
                print(msg)

        if not self.project_dir.exists():
            log(f"[错误] 项目路径不存在: {self.project_dir}")
            return {"success": False, "error": "项目路径不存在"}

        # 1. 获取 zConfig 中的代理设置
        proxy_server = self.get_proxy_server()
        env = os.environ.copy()

        if proxy_server:
            env["HTTP_PROXY"] = proxy_server
            env["HTTPS_PROXY"] = proxy_server
            env["ALL_PROXY"] = proxy_server
            log(f"[代理] 已挂载代理地址: {proxy_server}")
        else:
            log("[代理] 未检测到 proxy.http 配置，将直连运行")

        cline_exec = self.get_cline_cmd()
        
        # 针对 Cline CLI 的单字/单词 Prompt 特殊处理
        clean_prompt = prompt.strip()
        if clean_prompt and " " not in clean_prompt and "\t" not in clean_prompt and "\n" not in clean_prompt:
            clean_prompt = clean_prompt + " "

        # 参数选项列表
        args = ["--json"]

        if plan_mode:
            args.append("-p")
        if auto_approve:
            args.extend(["--auto-approve", "true"])
        else:
            args.extend(["--auto-approve", "false"])
        if provider.strip():
            args.extend(["-P", provider.strip()])
        if model.strip():
            args.extend(["-m", model.strip()])
        if api_key.strip():
            args.extend(["-k", api_key.strip()])
        if thinking and thinking != "omitted":
            args.extend(["--thinking", thinking])
        if timeout > 0:
            args.extend(["-t", str(timeout)])
        if session_id.strip():
            args.extend(["--id", session_id.strip()])
        if system_prompt.strip():
            args.extend(["-s", system_prompt.strip()])

        # 提示词 Prompt 作为最后一个参数追加
        args.append(clean_prompt)

        # 在 Windows 环境下使用 cmd.exe /c
        if sys.platform == "win32" and cline_exec.lower().endswith((".cmd", ".bat")):
            cmd = ["cmd.exe", "/c", cline_exec] + args
        else:
            cmd = [cline_exec] + args

        log(f"[工作区] {self.project_dir}")
        log(f"[执行路径] {cline_exec}")
        log(f"[指令] {prompt}\n" + "-" * 50)

        self.is_cancelled = False
        try:
            process = subprocess.Popen(
                cmd,
                cwd=str(self.project_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                env=env,
                bufsize=1,
                shell=False
            )
            self.process = process

            stdout_lines = []
            # 实时读取标准输出
            for line in iter(process.stdout.readline, ''):
                if self.is_cancelled:
                    break
                raw_line = line.rstrip("\r\n")
                stdout_lines.append(line)
                
                # 根据配置决定输出原始 JSON 还是人性化格式文本
                if format_json_log:
                    formatted_msg = parse_cline_json_line(raw_line)
                    if formatted_msg:
                        log(formatted_msg)
                else:
                    log(raw_line)

            process.stdout.close()
            stderr_out = process.stderr.read()
            process.stderr.close()
            process.wait()

            if self.is_cancelled:
                log("\n🛑 [中断] 任务已被用户手动强行终止！")
                return {"success": False, "error": "任务被用户手动终止"}

            raw_stdout = "".join(stdout_lines)

            if process.returncode == 0:
                log("\n[成功] 任务完成！")
                try:
                    return {"success": True, "data": json.loads(raw_stdout)}
                except json.JSONDecodeError:
                    return {"success": True, "data": raw_stdout}
            else:
                log(f"\n[失败] 退出码: {process.returncode}")
                if stderr_out:
                    log(f"错误信息: {stderr_out}")
                return {"success": False, "error": stderr_out or "执行失败"}

        except FileNotFoundError:
            err_msg = "未找到 cline 命令行工具，请确保 `npm install -g cline` 已安装并加入 PATH"
            log(f"[错误] {err_msg}")
            return {"success": False, "error": err_msg}
        except Exception as e:
            log(f"[异常] {e}")
            return {"success": False, "error": str(e)}


class ClineGUI:
    """Tkinter 界面类"""

    def __init__(self, root):
        self.root = root
        self.root.title("Cline AI 自动化任务控制器 (CLI 2.0+ Full Options)")
        self.root.geometry("820x720")
        self.root.minsize(700, 520)

        self.current_runner = None
        self.init_ui()

    def init_ui(self):
        # 顶部基础配置区域
        frame_config = ttk.LabelFrame(self.root, text=" 基础配置 ", padding=10)
        frame_config.pack(fill="x", padx=10, pady=5)
        frame_config.columnconfigure(1, weight=1)

        # 项目路径
        ttk.Label(frame_config, text="项目路径:").grid(row=0, column=0, sticky="w", pady=2)
        self.entry_path = ttk.Entry(frame_config)
        self.entry_path.insert(0, os.getcwd())
        self.entry_path.grid(row=0, column=1, sticky="ew", padx=5, pady=2)

        # 代理显示
        ttk.Label(frame_config, text="读取代理:").grid(row=1, column=0, sticky="w", pady=2)
        proxy_val = get_config("proxy.http", "未配置/未导入")
        self.lbl_proxy = ttk.Label(frame_config, text=str(proxy_val), foreground="gray")
        self.lbl_proxy.grid(row=1, column=1, sticky="w", padx=5, pady=2)

        # 高级参数配置区域
        frame_adv = ttk.LabelFrame(self.root, text=" 高级 CLI 参数设置 ", padding=10)
        frame_adv.pack(fill="x", padx=10, pady=5)
        frame_adv.columnconfigure(1, weight=1)
        frame_adv.columnconfigure(3, weight=1)

        # 运行模式 & 自动批准
        self.var_mode = tk.StringVar(value="act")
        ttk.Label(frame_adv, text="运行模式:").grid(row=0, column=0, sticky="w", pady=2)
        frame_mode = ttk.Frame(frame_adv)
        frame_mode.grid(row=0, column=1, sticky="w", padx=5, pady=2)
        ttk.Radiobutton(frame_mode, text="Act 模式 (自动改代码)", variable=self.var_mode, value="act").pack(side="left", padx=2)
        ttk.Radiobutton(frame_mode, text="Plan 模式 (-p 架构规划)", variable=self.var_mode, value="plan").pack(side="left", padx=2)

        self.var_auto_approve = tk.BooleanVar(value=True)
        self.chk_approve = ttk.Checkbutton(
            frame_adv, text="自动批准修改 (--auto-approve)", variable=self.var_auto_approve
        )
        self.chk_approve.grid(row=0, column=2, columnspan=2, sticky="w", padx=5, pady=2)

        # Provider (-P) & Model (-m)
        ttk.Label(frame_adv, text="Provider (-P):").grid(row=1, column=0, sticky="w", pady=2)
        self.entry_provider = ttk.Entry(frame_adv)
        self.entry_provider.grid(row=1, column=1, sticky="ew", padx=5, pady=2)

        ttk.Label(frame_adv, text="Model (-m):").grid(row=1, column=2, sticky="w", pady=2)
        self.entry_model = ttk.Entry(frame_adv)
        self.entry_model.insert(0, "")
        self.entry_model.grid(row=1, column=3, sticky="ew", padx=5, pady=2)

        # Reasoning Effort (--thinking) & Timeout (-t)
        ttk.Label(frame_adv, text="思考深度 (--thinking):").grid(row=2, column=0, sticky="w", pady=2)
        self.combo_thinking = ttk.Combobox(
            frame_adv, values=["omitted", "none", "low", "medium", "high", "xhigh"], state="readonly"
        )
        self.combo_thinking.current(0)
        self.combo_thinking.grid(row=2, column=1, sticky="ew", padx=5, pady=2)

        ttk.Label(frame_adv, text="超时时间 (s) (-t):").grid(row=2, column=2, sticky="w", pady=2)
        self.entry_timeout = ttk.Entry(frame_adv)
        self.entry_timeout.insert(0, "0")
        self.entry_timeout.grid(row=2, column=3, sticky="ew", padx=5, pady=2)

        # Session ID (--id) & Key Override (-k)
        ttk.Label(frame_adv, text="恢复 Session ID (--id):").grid(row=3, column=0, sticky="w", pady=2)
        self.entry_session_id = ttk.Entry(frame_adv)
        self.entry_session_id.grid(row=3, column=1, sticky="ew", padx=5, pady=2)

        ttk.Label(frame_adv, text="API Key 覆盖 (-k):").grid(row=3, column=2, sticky="w", pady=2)
        self.entry_key = ttk.Entry(frame_adv, show="*")
        self.entry_key.grid(row=3, column=3, sticky="ew", padx=5, pady=2)

        # 日志格式美化开关
        self.var_format_log = tk.BooleanVar(value=True)
        self.chk_format_log = ttk.Checkbutton(
            frame_adv, text="美化 JSON 实时日志 (推荐开启)", variable=self.var_format_log
        )
        self.chk_format_log.grid(row=4, column=0, columnspan=2, sticky="w", padx=5, pady=2)

        # 中部 Prompt 区域
        frame_prompt = ttk.LabelFrame(self.root, text=" 任务 Prompt ", padding=10)
        frame_prompt.pack(fill="x", padx=10, pady=5)

        self.txt_prompt = tk.Text(frame_prompt, height=4, font=("Microsoft YaHei", 9))
        self.txt_prompt.insert("1.0", "你好")
        self.txt_prompt.pack(fill="x")

        # 按钮控制区
        frame_btn = ttk.Frame(self.root, padding=5)
        frame_btn.pack(fill="x", padx=10)

        self.btn_run = ttk.Button(frame_btn, text="开始执行任务", command=self.start_task_thread)
        self.btn_run.pack(side="right", padx=5)

        self.btn_stop = ttk.Button(frame_btn, text="停止任务", command=self.stop_task, state="disabled")
        self.btn_stop.pack(side="right", padx=5)

        # 底部日志控制台
        frame_log = ttk.LabelFrame(self.root, text=" 运行日志 ", padding=10)
        frame_log.pack(fill="both", expand=True, padx=10, pady=5)

        self.txt_log = scrolledtext.ScrolledText(
            frame_log, state="disabled", font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4"
        )
        self.txt_log.pack(fill="both", expand=True)

    def append_log(self, text: str):
        """线程安全的日志输出"""
        def _write():
            self.txt_log.config(state="normal")
            self.txt_log.insert("end", text + "\n")
            self.txt_log.see("end")
            self.txt_log.config(state="disabled")
        
        self.root.after(0, _write)

    def stop_task(self):
        """点击停止任务按钮时的触发逻辑"""
        if self.current_runner:
            self.append_log("🛑 [系统提示] 正在发送终止信号，强行停止 Agent 任务...")
            self.current_runner.stop_task()
            self.btn_stop.config(state="disabled")

    def start_task_thread(self):
        """开启新线程运行任务，防止 GUI 卡死"""
        prompt = self.txt_prompt.get("1.0", "end").strip()
        project_dir = self.entry_path.get().strip()

        if not prompt:
            messagebox.showwarning("提示", "请输入 Prompt 任务描述！")
            return

        try:
            timeout_val = int(self.entry_timeout.get().strip() or "0")
        except ValueError:
            messagebox.showwarning("提示", "超时时间必须为数字（秒）！")
            return

        kwargs = {
            "project_dir": project_dir,
            "prompt": prompt,
            "auto_approve": self.var_auto_approve.get(),
            "plan_mode": (self.var_mode.get() == "plan"),
            "provider": self.entry_provider.get().strip(),
            "model": self.entry_model.get().strip(),
            "api_key": self.entry_key.get().strip(),
            "thinking": self.combo_thinking.get(),
            "timeout": timeout_val,
            "session_id": self.entry_session_id.get().strip(),
            "format_json_log": self.var_format_log.get()
        }

        self.btn_run.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.txt_log.config(state="normal")
        self.txt_log.delete("1.0", "end")
        self.txt_log.config(state="disabled")

        # 启动工作线程
        threading.Thread(
            target=self._run_task_worker,
            kwargs=kwargs,
            daemon=True
        ).start()

    def _run_task_worker(
        self,
        project_dir: str,
        prompt: str,
        auto_approve: bool,
        plan_mode: bool,
        provider: str,
        model: str,
        api_key: str,
        thinking: str,
        timeout: int,
        session_id: str,
        format_json_log: bool
    ):
        try:
            # 实例化 ClineRunner 接口并保存实例指针
            self.current_runner = ClineRunner(project_dir=project_dir)
            self.current_runner.run_task(
                prompt=prompt,
                auto_approve=auto_approve,
                plan_mode=plan_mode,
                provider=provider,
                model=model,
                api_key=api_key,
                thinking=thinking,
                timeout=timeout,
                session_id=session_id,
                format_json_log=format_json_log,
                log_callback=self.append_log
            )
        finally:
            # 清空 runner 并恢复按钮状态
            self.current_runner = None
            self.root.after(0, lambda: (
                self.btn_run.config(state="normal"),
                self.btn_stop.config(state="disabled")
            ))


if __name__ == "__main__":
    root = tk.Tk()
    app = ClineGUI(root)
    root.mainloop()