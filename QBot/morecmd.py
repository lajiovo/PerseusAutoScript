import requests
import json
import os

class MoreCommandSystem:
    """
    实现对刚才新解析的资源及任务状态内容的数据读取和指令处理（例如通过命令或API查询资源监控与任务状态）。
    """
    def __init__(self, data_mgr=None):
        self.data_mgr = data_mgr
        # 默认本地 OnePush 服务端口为 25566，可通过配置调整
        self.api_base_url = "http://127.0.0.1:25566"

    def handle_command(self, cmd: str, parts: list, sender_openid: str):
        """
        前置指令分发。如果匹配到相关指令（如 ap、ziyuan、task、tasks、监控、状态等），
        则处理并返回结果（支持字符串或返回带 msg_type 的 dict）。
        如果未匹配到相关指令，则返回 None，由 QBot 继续按原样分发给 game.py。
        """
        lower_cmd = cmd.lower()
        
        # 资源监控相关指令：ap, ziyuan, 监控
        if lower_cmd in ("ap", "ziyuan", "监控", "资源"):
            return self._get_resource_status()
            
        # 任务状态相关指令：task, tasks, 任务, 状态
        if lower_cmd in ("task", "tasks", "任务", "状态"):
            return self._get_task_status()
            
        # 未匹配到相关指令
        return None

    def _get_resource_status(self):
        """请求本地 /main/ap/get 获取资源监控数据并格式化展示"""
        try:
            url = f"{self.api_base_url}/main/ap/get"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                resources = data.get("resources", [])
                updated_at = data.get("updated_at", "未知时间")
                
                if not resources:
                    return f"📊 【资源监控状态】\n暂无资源监控数据。\n更新时间: {updated_at}"
                
                lines = [f"📊 【资源监控状态】(更新于 {updated_at})"]
                for item in resources:
                    name = item.get("name", "未知资源")
                    amount = item.get("amount", "0")
                    time_str = item.get("formatted_time") or item.get("time_text", "未知")
                    lines.append(f"• {name}: {amount} (时间: {time_str})")
                
                return "\n".join(lines)
            else:
                return f"❌ 获取资源监控失败 (HTTP {resp.status_code})"
        except Exception as e:
            return f"❌ 获取资源监控异常: {str(e)}"

    def _get_task_status(self):
        """请求本地 /main/ap/get2 获取任务状态数据并格式化展示"""
        try:
            url = f"{self.api_base_url}/main/ap/get2"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                running = data.get("running", [])
                queued = data.get("queued", [])
                waiting = data.get("waiting", [])
                updated_at = data.get("updated_at", "未知时间")
                
                lines = [f"⚙️ 【任务状态总览】(更新于 {updated_at})"]
                
                lines.append(f"\n🚀 运行中任务 ({len(running)}):")
                if running:
                    for t in running:
                        lines.append(f"  - {t.get('title')} [{t.get('formatted_time')}]")
                else:
                    lines.append("  (无)")
                    
                lines.append(f"\n📦 队列中任务 ({len(queued)}):")
                if queued:
                    for t in queued:
                        lines.append(f"  - {t.get('title')} [{t.get('formatted_time')}]")
                else:
                    lines.append("  (无)")
                    
                lines.append(f"\n⏳ 等待中任务 ({len(waiting)}):")
                if waiting:
                    for t in waiting:
                        lines.append(f"  - {t.get('title')} [{t.get('formatted_time')}]")
                else:
                    lines.append("  (无)")
                    
                return "\n".join(lines)
            else:
                return f"❌ 获取任务状态失败 (HTTP {resp.status_code})"
        except Exception as e:
            return f"❌ 获取任务状态异常: {str(e)}"
