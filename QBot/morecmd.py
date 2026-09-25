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
        
        # 资源监控相关指令：ap, ziyuan, 监控, 资源
        if lower_cmd in ("ap", "ziyuan", "监控", "资源"):
            return self._get_resource_status()
            
        # 任务状态相关指令：task, tasks, 任务, 状态
        if lower_cmd in ("task", "tasks", "任务", "状态"):
            return self._get_task_status()

        # 综合统计相关指令：统计, status, botstatus, stats
        if lower_cmd in ("统计", "status", "botstatus", "stats"):
            return self._get_comprehensive_stats()

        # 截图查看相关指令：截图, screenshot, shot, pic
        if lower_cmd in ("截图", "screenshot", "shot", "pic"):
            return self._get_screenshot()
            
        # 未匹配到相关指令
        return None

    def _get_screenshot(self):
        """请求本地 /main/ap/get3 获取最新截图，下载并返回图文消息结构 (msg_type=7)"""
        try:
            url = f"{self.api_base_url}/main/ap/get3"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("exists"):
                    screenshot_url = f"{self.api_base_url}{data.get('screenshot_url')}"
                    updated_at = data.get("updated_at", "未知时间")
                    
                    img_resp = requests.get(screenshot_url, timeout=10)
                    if img_resp.status_code == 200:
                        os.makedirs("temp_images", exist_ok=True)
                        import hashlib
                        file_hash = hashlib.md5(img_resp.content).hexdigest()
                        file_path = os.path.join("temp_images", f"shot_{file_hash}.png")
                        with open(file_path, "wb") as f:
                            f.write(img_resp.content)
                        
                        return {
                            "msg_type": 7,
                            "file_path": file_path,
                            "content": f"🖼️ 【Alas 实时运行截图】(更新于 {updated_at})"
                        }
                return "🖼️ 暂无可用截图缓存。"
            else:
                return f"❌ 获取截图状态失败 (HTTP {resp.status_code})"
        except Exception as e:
            return f"❌ 获取截图异常: {str(e)}"

    def _get_comprehensive_stats(self):
        """请求本地 /main/stats/get 获取 zOnepush 与 QBot 的综合统计数据并格式化展示"""
        try:
            url = f"{self.api_base_url}/main/stats/get"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                z_stats = data.get("zOnepush", {})
                b_stats = data.get("qbot", {})

                lines = ["📈 【综合统计与运行状态】"]
                lines.append(f"• 自动化检查次数: {z_stats.get('auto_check_count', 0)} 次")
                lines.append(f"• Push 处理次数: {z_stats.get('push_handle_count', 0)} 次")
                lines.append(f"• 累计运行时长: {z_stats.get('total_runtime_hours', 0)} 小时 ({z_stats.get('total_runtime_seconds', 0)}秒)")

                if b_stats and b_stats.get("status") == "success":
                    lines.append(f"\n🤖 【Bot 运行统计】")
                    lines.append(f"• 消息总通量: {b_stats.get('total_messages', 0)} 条")
                    lines.append(f"• 回复量: {b_stats.get('reply_count', 0)} 条")
                    lines.append(f"• 处理量: {b_stats.get('processed_count', 0)} 次")
                    lines.append(f"• 活跃群聊数: {b_stats.get('active_groups_count', 0)} 个")
                else:
                    lines.append(f"\n🤖 【Bot 运行统计】: 离线或未连接")

                return "\n".join(lines)
            else:
                return f"❌ 获取综合统计失败 (HTTP {resp.status_code})"
        except Exception as e:
            return f"❌ 获取综合统计异常: {str(e)}"

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
