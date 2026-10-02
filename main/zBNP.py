import zPerseusLogger
import os
import sys
import time
import subprocess
import threading
from zConfig import get_config

EXE_DIR = get_config("bnp.exe_dir")
EXE_PATH = os.path.join(EXE_DIR, get_config("bnp.exe_path"))
LOG_PATH = os.path.join(EXE_DIR, get_config("bnp.log_path"))

def tail_log(log_path, stop_event):
    """实时监听 log 文件"""
    print(f"[系统] 开始监听日志文件: {log_path}")
    
    while not stop_event.is_set():
        if os.path.exists(log_path):
            break
        time.sleep(0.2)
        
    try:
        # 改为 utf-8 编码读取日志
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            f.seek(0, os.SEEK_SET)
            while not stop_event.is_set():
                line = f.readline()
                if line:
                    print(f"[LOG] {line}", end='', flush=True)
                else:
                    time.sleep(0.2)
    except Exception as e:
        print(f"\n[系统] 读取日志异常: {e}")

def read_stdout(process, stop_event):
    """读取 exe 原生的标准输出"""
    try:
        # 使用 iter 按行读取 stdout
        for line in iter(process.stdout.readline, ''):
            if line:
                print(f"[STDOUT] {line}", end='', flush=True)
            if stop_event.is_set():
                break
    except Exception:
        pass

def input_thread(process, stop_event):
    """转发键盘输入给 exe"""
    while not stop_event.is_set() and process.poll() is None:
        try:
            user_input = sys.stdin.readline()
            if not user_input:
                break
            process.stdin.write(user_input)
            process.stdin.flush()
        except (IOError, ValueError):
            break

def main():
    if not os.path.exists(EXE_PATH):
        print(f"[错误] 未找到程序文件: {EXE_PATH}")
        return

    print(f"[系统] 正在启动程序: {EXE_PATH}")
    
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    process = subprocess.Popen(
        [EXE_PATH],
        cwd=EXE_DIR,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',        # 关键修正：修改为 utf-8
        errors='ignore',         # 忽略无法解码的异常字符
        bufsize=1,
        env=env
    )

    stop_event = threading.Event()

    # 1. 监听 log 文件
    log_worker = threading.Thread(target=tail_log, args=(LOG_PATH, stop_event), daemon=True)
    log_worker.start()

    # 2. 监听 exe 控制台输出
    stdout_worker = threading.Thread(target=read_stdout, args=(process, stop_event), daemon=True)
    stdout_worker.start()

    # 3. 转发键盘输入
    input_worker = threading.Thread(target=input_thread, args=(process, stop_event), daemon=True)
    input_worker.start()

    try:
        process.wait()
        print(f"\n[系统] 程序已退出，返回码: {process.returncode}")
    except KeyboardInterrupt:
        print("\n[系统] 手动终止程序...")
        process.terminate()
    finally:
        stop_event.set()

if __name__ == "__main__":
    main()