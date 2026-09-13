import asyncio
import threading
import uuid
import time
import os
import json
from zLKbro import LKbro
from zLKepub import generate_epub_for_book

class LKApiManager:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._start_loop, daemon=True)
        self._thread.start()

        future = asyncio.run_coroutine_threadsafe(self._async_init(), self.loop)
        future.result()

        self.tasks = {}

    def _start_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def _async_init(self):
        self.bro = LKbro(headless=True)

    def get_bro_status(self):
        return {
            "running": self.bro.is_running(),
            "headless": self.bro.headless
        }

    def set_browser_state_sync(self, action: str, headless: bool = None):
        future = asyncio.run_coroutine_threadsafe(self.set_browser_state(action, headless), self.loop)
        return future.result()

    async def set_browser_state(self, action: str, headless: bool = None):
        if action == "start":
            if headless is not None:
                self.bro.headless = headless
            if not self.bro.is_running():
                await self.bro.start()
        elif action == "close":
            if self.bro.is_running():
                await self.bro.close()
        return self.get_bro_status()

    def get_task_list(self):
        return list(self.tasks.values())

    def get_task(self, task_id):
        return self.tasks.get(task_id)

    def cancel_task(self, task_id):
        task = self.tasks.get(task_id)
        if task and task["status"] in ["pending", "running"]:
            task["status"] = "cancelled"
            task["message"] = "任务已被用户强制终止"
            return True
        return False

    def add_task_sync(self, action, kwargs):
        future = asyncio.run_coroutine_threadsafe(self.add_task(action, kwargs), self.loop)
        return future.result()

    async def add_task(self, action, kwargs):
        task_id = str(uuid.uuid4())[:8]
        task_item = {
            "task_id": task_id,
            "action": action,
            "status": "pending",
            "progress": 0,
            "message": "等待执行",
            "created_at": time.time(),
            "error": None,
            "result": None
        }
        self.tasks[task_id] = task_item
        self.loop.create_task(self._run_task_worker(task_id, action, kwargs))
        return task_id

    async def _run_task_worker(self, task_id, action, kwargs):
        task = self.tasks[task_id]
        task["status"] = "running"
        
        def progress_cb(pct, msg):
            if task["status"] == "cancelled":
                raise Exception("任务已中止")
            task["progress"] = pct
            task["message"] = msg

        try:
            if action == "bookshelf":
                url = kwargs.get("url", "https://www.lightnovel.fun/category/lightnovel")
                max_scrolls = kwargs.get("max_scrolls", 50)
                res = await self.bro.scroll_and_collect_bookshelf(target_url=url, max_scrolls=max_scrolls, progress_callback=progress_cb)
                task["result"] = f"成功抓取书架书籍 {len(res)} 本"
            elif action == "collect_current_page":
                res = await self.bro.collect_current_page(progress_callback=progress_cb)
                task["result"] = res
            elif action == "book_detail":
                book_id = kwargs.get("book_id")
                metadata, catalog = await self.bro.get_book_detail_and_catalog(book_id, progress_callback=progress_cb)
                task["result"] = metadata
            elif action == "crawl_all":
                book_id = kwargs.get("book_id")
                await self.bro.crawl_all_chapters(book_id, progress_callback=progress_cb)
                task["result"] = "全书章节爬取完成"
            elif action == "redownload_images":
                book_id = kwargs.get("book_id")
                await self.bro.redownload_images(book_id, progress_callback=progress_cb)
                task["result"] = "插图重新下载完成"
            elif action == "epub":
                book_id = kwargs.get("book_id")
                selected_vols = kwargs.get("selected_volumes")
                sort_mode = kwargs.get("chapter_sort", "default")
                task["progress"] = 50
                task["message"] = "正在生成 EPUB..."
                epubs = generate_epub_for_book(book_id, selected_volumes=selected_vols, chapter_sort=sort_mode)
                task["result"] = epubs
            else:
                raise ValueError(f"未知操作类型: {action}")

            if task["status"] != "cancelled":
                task["status"] = "completed"
                task["progress"] = 100
                task["message"] = "任务执行成功"
        except Exception as e:
            if task["status"] != "cancelled":
                task["status"] = "failed"
                task["error"] = str(e)
                task["message"] = f"任务出错: {e}"

# 全局单例
lk_api = LKApiManager()
