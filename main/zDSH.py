
import os
import shutil
import subprocess
from pathlib import Path

from zConfig import get_config


def setup_proxy():
    """读取代理配置，设置子进程环境变量。"""
    proxy = get_config("proxy.http")

    if not proxy:
        raise RuntimeError("未配置 proxy.http")

    env = os.environ.copy()
    env["HTTP_PROXY"] = proxy
    env["HTTPS_PROXY"] = proxy
    env["ALL_PROXY"] = proxy
    env["NO_PROXY"] = "localhost,127.0.0.1,::1"

    print(f"[DSH] Proxy: {proxy}")
    return env


def find_npx():
    """定位 Windows 下的 npx.cmd。"""

    # 优先从 PATH 查找
    npx = shutil.which("npx.cmd") or shutil.which("npx")

    if npx:
        return npx

    # 常见 Node.js 安装位置
    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "nodejs" / "npx.cmd",

        Path(os.environ.get("APPDATA", ""))
        / "npm" / "npx.cmd",
    ]

    for path in candidates:
        if path.is_file():
            return str(path)

    raise FileNotFoundError(
        "找不到 npx.cmd，请检查 Node.js 是否安装及 PATH 配置。"
    )


def start_dsh():
    """启动 DeepSeek Harness Web UI。"""

    env = setup_proxy()
    npx = find_npx()

    print(f"[DSH] npx: {npx}")
    print("[DSH] Starting DeepSeek Harness...")
    print("[DSH] Web UI: http://127.0.0.1:3080")

    command = f'"{npx}" @deepseek-ai/dsh web'

    try:
        subprocess.run(
            command,
            env=env,
            shell=True,
            check=False
        )

    except KeyboardInterrupt:
        print("\n[DSH] Interrupted.")

    except Exception as e:
        print(f"[DSH] Startup error: {e}")
        raise


if __name__ == "__main__":
    start_dsh()
