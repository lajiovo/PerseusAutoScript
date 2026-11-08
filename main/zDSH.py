
import os
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit

from zConfig import get_config


# ============================================================
# 配置
# ============================================================

DSH_EXE = Path(get_config("dsh.exe"))

STOP_TIMEOUT = 10

# 需要清理的进程命令行特征
DSH_PROCESS_PATTERN = r"DeepSeek Harness"


# ============================================================
# 代理配置
# ============================================================

def setup_proxy():
    """
    读取代理配置，并为 DSH 及其子进程配置代理环境变量。
    """

    proxy = get_config("proxy.http")

    if not proxy:
        raise RuntimeError(
            "未配置 proxy.http"
        )

    proxy = str(proxy).strip()
    parsed = urlsplit(proxy)

    if parsed.scheme.lower() not in ("http", "https"):
        raise ValueError(
            f"不支持的代理协议：{proxy}"
        )

    if not parsed.hostname or not parsed.port:
        raise ValueError(
            f"代理地址无效：{proxy}"
        )

    env = os.environ.copy()

    # --------------------------------------------------------
    # HTTP / HTTPS 代理
    # --------------------------------------------------------

    env["HTTP_PROXY"] = proxy
    env["HTTPS_PROXY"] = proxy
    env["ALL_PROXY"] = proxy

    env["http_proxy"] = proxy
    env["https_proxy"] = proxy
    env["all_proxy"] = proxy

    # --------------------------------------------------------
    # Node.js 环境代理支持
    # --------------------------------------------------------

    env["NODE_USE_ENV_PROXY"] = "1"

    # --------------------------------------------------------
    # 清理不兼容的 npm 代理变量
    # --------------------------------------------------------

    env.pop("npm_config_http_proxy", None)
    env.pop("npm_config_https_proxy", None)

    # --------------------------------------------------------
    # 本地地址不走代理
    # --------------------------------------------------------

    no_proxy = "localhost,127.0.0.1,::1"

    env["NO_PROXY"] = no_proxy
    env["no_proxy"] = no_proxy

    print("=" * 60)
    print("[DSH] Proxy configuration")
    print(f"[DSH] HTTP_PROXY  : {proxy}")
    print(f"[DSH] HTTPS_PROXY : {proxy}")
    print(f"[DSH] ALL_PROXY   : {proxy}")
    print(f"[DSH] NODE_PROXY  : Enabled")
    print(f"[DSH] NO_PROXY    : {no_proxy}")
    print("=" * 60)

    return env


# ============================================================
# 清理旧进程
# ============================================================

def stop_existing_dsh():
    """
    查找并结束已有的 DeepSeek Harness 进程。

    通过 PowerShell 获取进程路径和命令行，
    使用 taskkill /T 结束进程树。
    """

    print("[DSH] Checking existing processes...")

    script = r"""
$processes = Get-CimInstance Win32_Process |
    Where-Object {
        $_.ExecutablePath -and
        $_.ExecutablePath -like '*DeepSeek Harness.exe'
    }

foreach ($p in $processes) {
    Write-Host "[DSH] Stopping PID $($p.ProcessId)"

    & taskkill.exe /PID $p.ProcessId /T /F 2>$null |
        Out-Null
}
"""

    try:
        subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script
            ],
            check=False,
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        time.sleep(1)

        print("[DSH] Process cleanup completed.")

    except subprocess.TimeoutExpired:
        raise RuntimeError(
            "[DSH] Process cleanup timed out."
        )

    except Exception as e:
        print(f"[DSH] Process cleanup error: {e}")
        raise


# ============================================================
# 启动 DSH
# ============================================================

def start_dsh():
    """
    直接启动 DeepSeek Harness.exe。

    不启动网页版。
    不使用 npx。
    不经过 npm。
    """

    print("\n[DSH] Launcher version: DIRECT_EXE_V1")
    print("[DSH] Starting launcher...")

    # 1. 检查 EXE
    if not DSH_EXE.is_file():
        raise FileNotFoundError(
            f"找不到程序：{DSH_EXE}"
        )

    # 2. 清理旧进程
    stop_existing_dsh()

    # 3. 设置代理环境
    env = setup_proxy()

    # 4. 显示启动信息
    print("[DSH] Starting DeepSeek Harness.exe")
    print(f"[DSH] Executable: {DSH_EXE}")
    print(f"[DSH] Working directory: {DSH_EXE.parent}")
    print("[DSH] Web mode: Disabled")
    print("[DSH] Proxy environment: Injected")

    try:
        # 5. 直接启动 EXE
        process = subprocess.Popen(
            [str(DSH_EXE)],
            cwd=str(DSH_EXE.parent),
            env=env,
            shell=False,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )

        print(f"[DSH] Started PID: {process.pid}")

        # 6. 等待主进程退出
        return_code = process.wait()

        print(
            f"[DSH] DeepSeek Harness exited "
            f"with code: {return_code}"
        )

    except KeyboardInterrupt:
        print("\n[DSH] Launcher interrupted.")

    except Exception as e:
        print(f"[DSH] Startup error: {e}")
        raise


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":

    try:
        start_dsh()

    except Exception as e:
        print(f"\n[FATAL] {e}")

    finally:
        print("\n[DSH] Launcher terminated.")
