import os
import json
import time
import base64
import threading
import queue
import re
import requests
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from pathlib import Path
from urllib.parse import urljoin
from ebooklib import epub
from playwright.sync_api import sync_playwright

BASE_CACHE_DIR = Path("servercache/lnlcache")
BOOKSHELF_DIR = BASE_CACHE_DIR / "bookshelf"
BOOKSHELF_COVER_DIR = BOOKSHELF_DIR / "cover"
BOOKS_DIR = BASE_CACHE_DIR / "books"

# 确保基础目录存在
BOOKSHELF_COVER_DIR.mkdir(parents=True, exist_ok=True)
BOOKS_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://www.linovelib.com"

def safe_filename(name):
    """移除文件名中的非法字符"""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def download_image(url, save_path, referer=BASE_URL):
    """通用的图片下载函数（当 Canvas 提取失败时的后备方案）"""
    if not url.startswith("http"):
        url = urljoin(BASE_URL, url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
        "Referer": referer
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(response.content)
            return True
    except Exception as e:
        print(f"下载图片失败 {url}: {e}")
    return False

class PlaywrightWorker(threading.Thread):
    """
    Playwright 后台工作线程，负责处理所有的浏览器操作。
    通过 task_queue 接收任务，通过 result_queue 返回结果。
    """
    def __init__(self, task_queue, result_queue):
        super().__init__()
        self.task_queue = task_queue
        self.result_queue = result_queue
        self.daemon = True # 主线程退出时自动退出
        self.browser = None
        self.context = None
        self.page = None

    def run(self):
        with sync_playwright() as p:
            # 启动 Chrome，抹除常规自动化标记，无需代理
            self.browser = p.chromium.launch(
                headless=False, # 可以设置为 True 以无头模式运行
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-infobars'
                ]
            )
            self.context = self.browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
            )
            
            # 注入 JS 抹除 webdriver 标识
            self.context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            
            self.page = self.context.new_page()
            
            # 循环监听任务队列
            while True:
                task = self.task_queue.get()
                if task is None or task.get('action') == 'quit':
                    break
                
                try:
                    self.handle_task(task)
                except Exception as e:
                    self.result_queue.put({"status": "error", "task": task, "error": str(e)})
                finally:
                    self.task_queue.task_done()
            
            self.browser.close()

    def handle_task(self, task):
        action = task.get('action')
        if action == 'store_mode':
            self.do_store_mode(task)
        elif action == 'book_info':
            self.do_book_info(task)
        elif action == 'chapter':
            self.do_chapter(task)
        else:
            self.result_queue.put({"status": "error", "error": f"未知任务: {action}"})

    def do_store_mode(self, task):
        """爬取书库列表并保存到 store.json"""
        page_num = task.get('page', 1)
        # 根据请求构建分页 URL，如果是第一页直接访问
        if page_num == 1:
            url = f"{BASE_URL}/wenku/"
        else:
            url = f"{BASE_URL}/wenku/lastupdate_0_0_0_0_0_0_0_{page_num}_0.html"
            
        self.page.goto(url, wait_until="domcontentloaded")
        
        books_data = []
        # 等待列表加载
        self.page.wait_for_selector('.store_collist')
        
        # 获取所有书籍节点 (包括 fl 和 fr)
        book_elements = self.page.query_selector_all('.store_collist .bookbox')
        
        for el in book_elements:
            try:
                # 解析 URL (从中提取 bookid)
                a_tag = el.query_selector('.bookname a')
                href = a_tag.get_attribute('href')
                book_id = href.split('/')[-1].replace('.html', '')
                title = a_tag.inner_text().strip()
                
                # 解析封面
                img_tag = el.query_selector('.bookimg img')
                cover_url = img_tag.get_attribute('data-original') or img_tag.get_attribute('src')
                
                # 解析信息 (作者, 分类, 状态, 更新时间)
                info_spans = el.query_selector_all('.bookilnk span')
                info_text = [span.inner_text().strip() for span in info_spans]
                
                # 简介
                intro_tag = el.query_selector('.bookintro')
                intro = intro_tag.inner_text().strip() if intro_tag else ""
                
                # 标签
                tags_tag = el.query_selector('.bookupdate b')
                tags = tags_tag.inner_text().strip().split() if tags_tag else []
                
                # 处理封面下载
                cover_path = BOOKSHELF_COVER_DIR / f"{book_id}.jpg"
                if not cover_path.exists():
                    download_image(cover_url, cover_path, referer=url)
                
                book_dict = {
                    "book_id": book_id,
                    "title": title,
                    "cover_url": cover_url,
                    "local_cover": str(cover_path),
                    "info": info_text,
                    "intro": intro,
                    "tags": tags
                }
                books_data.append(book_dict)
            except Exception as e:
                print(f"解析列表书籍出错: {e}")
                continue
        
        # 追加/更新保存到 store.json
        store_file = BOOKSHELF_DIR / "store.json"
        existing_data = []
        if store_file.exists():
            with open(store_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        
        # 简单去重合并
        existing_ids = {b['book_id'] for b in existing_data}
        for b in books_data:
            if b['book_id'] not in existing_ids:
                existing_data.append(b)
                
        with open(store_file, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=4)
            
        self.result_queue.put({"status": "success", "action": "store_mode", "page": page_num, "count": len(books_data)})

    def do_book_info(self, task):
        """爬取书籍基本信息(metadata)及目录(catalog)"""
        book_id = task['book_id']
        book_dir = BOOKS_DIR / str(book_id)
        book_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. 抓取元数据
        info_url = f"{BASE_URL}/novel/{book_id}.html"
        self.page.goto(info_url, wait_until="domcontentloaded")
        
        title = self.page.inner_text('.book-name').strip()
        cover_tag = self.page.query_selector('.book-img img')
        cover_url = cover_tag.get_attribute('src')
        
        author_tag = self.page.query_selector('.au-name a')
        author = author_tag.inner_text().strip() if author_tag else "未知"
        
        translator_tag = self.page.query_selector('.tr-name a')
        translator = translator_tag.inner_text().strip() if translator_tag else "无"
        
        desc_tag = self.page.query_selector('.book-dec')
        description = desc_tag.inner_text().strip() if desc_tag else ""
        
        # 下载封面
        cover_path = book_dir / "cover.jpg"
        if not cover_path.exists():
            download_image(cover_url, cover_path, referer=info_url)
            
        metadata = {
            "book_id": book_id,
            "title": title,
            "author": author,
            "translator": translator,
            "description": description,
            "cover_url": cover_url,
            "local_cover": str(cover_path)
        }
        with open(book_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=4)
            
        # 2. 抓取目录
        catalog_url = f"{BASE_URL}/novel/{book_id}/catalog"
        self.page.goto(catalog_url, wait_until="domcontentloaded")
        
        catalog = []
        volumes = self.page.query_selector_all('.volume')
        
        for vol in volumes:
            vol_title_tag = vol.query_selector('.v-line a')
            if not vol_title_tag:
                continue
            vol_title = vol_title_tag.inner_text().strip()
            
            chapters = []
            chap_tags = vol.query_selector_all('.chapter-list li a')
            for c_tag in chap_tags:
                chap_title = c_tag.inner_text().strip()
                chap_href = c_tag.get_attribute('href')
                chapters.append({
                    "title": chap_title,
                    "url": chap_href
                })
            
            catalog.append({
                "volume_title": vol_title,
                "chapters": chapters
            })
            
        with open(book_dir / "catalog.json", "w", encoding="utf-8") as f:
            json.dump(catalog, f, ensure_ascii=False, indent=4)
            
        self.result_queue.put({"status": "success", "action": "book_info", "book_id": book_id, "title": title})

    def do_chapter(self, task):
        """获取章节正文和图片"""
        book_id = str(task['book_id'])
        vol_title = safe_filename(task['vol_title'])
        chap_title = safe_filename(task['chap_title'])
        url_path = task['url']
        
        chap_url = urljoin(BASE_URL, url_path)
        
        vol_dir = BOOKS_DIR / book_id / vol_title
        img_dir = vol_dir / "img"
        img_dir.mkdir(parents=True, exist_ok=True)
        
        self.page.goto(chap_url, wait_until="domcontentloaded")
        
        # 确保图片懒加载触发（稍微滚动一下）
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1) # 给定一点时间渲染懒加载
        
        content_elements = self.page.query_selector_all('#TextContent > *, #hidden-images img')
        
        chapter_data = []
        img_counter = 1
        
        # 提取 Canvas 数据的注入函数
        canvas_extractor_js = """
        (img) => {
            try {
                if (!img.complete || img.naturalWidth === 0) return null;
                let canvas = document.createElement('canvas');
                canvas.width = img.naturalWidth;
                canvas.height = img.naturalHeight;
                let ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0);
                return canvas.toDataURL('image/jpeg', 0.9);
            } catch(e) {
                return null;
            }
        }
        """

        for el in content_elements:
            tag_name = el.evaluate("el => el.tagName.toLowerCase()")
            class_name = el.get_attribute('class') or ""
            
            # 跳过广告块
            if 'dag' in class_name:
                continue
                
            if tag_name == 'p' or tag_name == 'br':
                text = el.inner_text().strip()
                if text:
                    chapter_data.append({"type": "text", "content": text})
                    
            elif tag_name == 'img':
                src = el.get_attribute('data-src') or el.get_attribute('src')
                if not src or "sloading.svg" in src:
                    continue # 跳过加载占位图
                    
                img_name = f"{chap_title}_{img_counter}.jpg"
                img_path = img_dir / img_name
                
                # 尝试用 Canvas 提取
                base64_data = el.evaluate(canvas_extractor_js)
                
                if base64_data and base64_data.startswith("data:image"):
                    # Canvas 提取成功
                    header, encoded = base64_data.split(",", 1)
                    with open(img_path, "wb") as f:
                        f.write(base64.b64decode(encoded))
                else:
                    # Canvas 失败或未渲染，回退到网络下载
                    download_image(src, img_path, referer=chap_url)
                
                chapter_data.append({
                    "type": "image", 
                    "original_url": src, 
                    "local_path": str(img_path.relative_to(BASE_CACHE_DIR))
                })
                img_counter += 1

        json_path = vol_dir / f"{chap_title}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(chapter_data, f, ensure_ascii=False, indent=4)
            
        self.result_queue.put({
            "status": "success", 
            "action": "chapter", 
            "book_id": book_id, 
            "chap_title": chap_title
        })

class LNL:
    """LNL 主控制类，负责管理队列、启动线程、封装上层API，以及生成 EPUB。"""
    
    def __init__(self):
        self.task_queue = queue.Queue()
        self.result_queue = queue.Queue()
        
        # 启动 Playwright 线程
        self.worker = PlaywrightWorker(self.task_queue, self.result_queue)
        self.worker.start()
        print("LNL Playwright 线程已启动...")

    def wait_for_result(self):
        """阻塞等待队列返回结果"""
        return self.result_queue.get()

    def get_store(self, page=1):
        """下达任务：抓取指定页码的商店列表"""
        print(f"请求抓取商店第 {page} 页...")
        self.task_queue.put({"action": "store_mode", "page": page})
        return self.wait_for_result()

    def get_book_info(self, book_id):
        """下达任务：抓取书籍信息及目录"""
        print(f"请求抓取书籍 {book_id} 的信息与目录...")
        self.task_queue.put({"action": "book_info", "book_id": book_id})
        return self.wait_for_result()

    def download_chapter(self, book_id, vol_title, chap_title, url):
        """下达任务：下载指定章节（内容与图片）"""
        print(f"请求下载章节: {vol_title} - {chap_title}...")
        self.task_queue.put({
            "action": "chapter",
            "book_id": book_id,
            "vol_title": vol_title,
            "chap_title": chap_title,
            "url": url
        })
        return self.wait_for_result()

    def make_epub(self, book_id, output_path=None):
        """
        利用已经缓存在本地的 json 和图片制作 EPUB。
        插图直接读取本地文件打包，不写入外部链接。
        """
        book_dir = BOOKS_DIR / str(book_id)
        if not (book_dir / "metadata.json").exists() or not (book_dir / "catalog.json").exists():
            print(f"书籍 {book_id} 的元数据或目录不存在，请先执行信息抓取。")
            return False

        with open(book_dir / "metadata.json", "r", encoding="utf-8") as f:
            meta = json.load(f)
        with open(book_dir / "catalog.json", "r", encoding="utf-8") as f:
            catalog = json.load(f)

        book = epub.EpubBook()
        book.set_identifier(str(book_id))
        book.set_title(meta.get("title", "Unknown Title"))
        book.set_language('zh-CN')
        book.add_author(meta.get("author", "Unknown Author"))
        
        # 设置封面
        cover_path = Path(meta.get("local_cover"))
        if cover_path.exists():
            with open(cover_path, "rb") as f:
                book.set_cover("cover.jpg", f.read())

        spine = ['nav']
        toc = []
        
        # 添加 CSS 样式
        style = 'p { text-indent: 2em; line-height: 1.5; } img { max-width: 100%; text-align: center; display: block; margin: 0 auto; }'
        default_css = epub.EpubItem(uid="style_default", file_name="style/default.css", media_type="text/css", content=style)
        book.add_item(default_css)

        # 遍历目录，读取缓存构建 HTML
        for vol_idx, vol in enumerate(catalog):
            vol_title = safe_filename(vol["volume_title"])
            vol_dir = book_dir / vol_title
            
            vol_toc = (epub.Section(vol_title), [])
            
            for chap_idx, chap in enumerate(vol["chapters"]):
                chap_title = safe_filename(chap["title"])
                chap_json_path = vol_dir / f"{chap_title}.json"
                
                if not chap_json_path.exists():
                    print(f"跳过未下载章节: {chap_title}")
                    continue
                    
                with open(chap_json_path, "r", encoding="utf-8") as f:
                    chap_data = json.load(f)
                
                # 构建章节 HTML 内容
                html_content = f"<h1>{chap_title}</h1>\n"
                
                for item in chap_data:
                    if item["type"] == "text":
                        html_content += f"<p>{item['content']}</p>\n"
                    elif item["type"] == "image":
                        local_img_rel = item["local_path"]  # e.g. books/5354/vol_name/img/xxx.jpg
                        local_img_abs = BASE_CACHE_DIR / local_img_rel
                        
                        if local_img_abs.exists():
                            # 在 epub 内部的路径定义
                            epub_img_name = f"images/v{vol_idx}_c{chap_idx}_{local_img_abs.name}"
                            
                            # 将本地图片以二进制形式添加到 EPUB Item
                            with open(local_img_abs, "rb") as img_f:
                                img_item = epub.EpubItem(
                                    uid=f"img_{vol_idx}_{chap_idx}_{local_img_abs.stem}",
                                    file_name=epub_img_name,
                                    media_type="image/jpeg",
                                    content=img_f.read()
                                )
                                try:
                                    book.add_item(img_item)
                                except ValueError:
                                    pass # Item already exists
                                
                            # 在 HTML 中引用内嵌的图片
                            html_content += f'<div style="text-align: center;"><img src="{epub_img_name}" alt="illustration"/></div>\n'
                
                # 创建 EpubHtml 对象
                chapter_item = epub.EpubHtml(title=chap_title, file_name=f"c_{vol_idx}_{chap_idx}.xhtml", lang='zh-CN')
                chapter_item.content = html_content
                chapter_item.add_item(default_css)
                
                book.add_item(chapter_item)
                spine.append(chapter_item)
                vol_toc[1].append(chapter_item)
            
            if vol_toc[1]: # 如果该卷下有成功下载的章节
                toc.append(vol_toc)

        book.toc = toc
        book.spine = spine
        
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        if output_path is None:
            output_path = f"{meta.get('title', book_id)}.epub"
            
        print(f"正在生成 EPUB 文件: {output_path}...")
        epub.write_epub(output_path, book, {})
        print("EPUB 生成成功！")
        return True

    def close(self):
        """关闭线程和浏览器"""
        self.task_queue.put({"action": "quit"})
        self.worker.join()

class ThreadSafeRedirector:
    """线程安全的标准输出重定向器，用于将控制台输出显示在 Tkinter 界面上"""
    def __init__(self, widget, root):
        self.widget = widget
        self.root = root

    def write(self, text):
        self.root.after(0, self._write, text)

    def _write(self, text):
        self.widget.configure(state="normal")
        self.widget.insert("end", text)
        self.widget.see("end")
        self.widget.configure(state="disabled")

    def flush(self):
        pass

class LNLApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LNL 下载器")
        self.root.geometry("650x450")
        
        self.create_widgets()
        
        # 重定向标准输出到文本框，由于在多线程环境中调用，需要保证线程安全
        import sys
        sys.stdout = ThreadSafeRedirector(self.log_text, self.root)
        sys.stderr = ThreadSafeRedirector(self.log_text, self.root)
        
        print("正在启动后台浏览器，请稍候...")
        # 异步初始化后台浏览器，避免阻塞 GUI 主线程
        threading.Thread(target=self.init_lnl, daemon=True).start()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def init_lnl(self):
        self.lnl = LNL()
        print("LNL App 启动成功，可以开始操作。")

    def create_widgets(self):
        input_frame = ttk.Frame(self.root, padding=10)
        input_frame.pack(fill=tk.X)
        
        ttk.Label(input_frame, text="书库页码:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.page_var = tk.StringVar(value="1")
        ttk.Entry(input_frame, textvariable=self.page_var, width=10).grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        
        ttk.Label(input_frame, text="书籍 ID:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.bookid_var = tk.StringVar(value="5354")
        ttk.Entry(input_frame, textvariable=self.bookid_var, width=15).grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        
        btn_frame = ttk.Frame(self.root, padding=10)
        btn_frame.pack(fill=tk.X)
        
        ttk.Button(btn_frame, text="获取书库列表", command=self.do_get_store).grid(row=0, column=0, padx=5)
        ttk.Button(btn_frame, text="获取书籍信息", command=self.do_get_info).grid(row=0, column=1, padx=5)
        ttk.Button(btn_frame, text="下载测试(前2章)", command=self.do_download).grid(row=0, column=2, padx=5)
        ttk.Button(btn_frame, text="生成 EPUB", command=self.do_epub).grid(row=0, column=3, padx=5)
        
        self.log_text = scrolledtext.ScrolledText(self.root, state="disabled", height=15)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

    def run_task(self, target):
        """通用任务运行器，开启后台线程避免 UI 假死"""
        if not hasattr(self, 'lnl'):
            print("错误: Playwright 尚未初始化完成，请稍后再试。")
            return
        threading.Thread(target=target, daemon=True).start()

    def do_get_store(self):
        page_str = self.page_var.get()
        if not page_str.isdigit():
            print("错误: 页码必须是数字")
            return
        def task():
            print(f"\n--- 抓取书库列表 (第 {page_str} 页) ---")
            res = self.lnl.get_store(int(page_str))
            print("抓取结果:", res)
        self.run_task(task)

    def do_get_info(self):
        book_id = self.bookid_var.get().strip()
        if not book_id:
            print("错误: 请输入书籍 ID")
            return
        def task():
            print(f"\n--- 抓取书籍信息 ({book_id}) ---")
            res = self.lnl.get_book_info(book_id)
            print("抓取结果:", res)
        self.run_task(task)

    def do_download(self):
        book_id = self.bookid_var.get().strip()
        if not book_id:
            print("错误: 请输入书籍 ID")
            return
        def task():
            print(f"\n--- 开始下载测试章节 ({book_id}) ---")
            book_dir = BOOKS_DIR / book_id
            cat_file = book_dir / "catalog.json"
            if not cat_file.exists():
                print("错误: 目录文件不存在，请先执行「获取书籍信息」。")
                return
            with open(cat_file, "r", encoding="utf-8") as f:
                catalog = json.load(f)
            if catalog and catalog[0].get("chapters"):
                vol_title = catalog[0]["volume_title"]
                for chap in catalog[0]["chapters"][:2]:
                    res = self.lnl.download_chapter(
                        book_id=book_id,
                        vol_title=vol_title,
                        chap_title=chap["title"],
                        url=chap["url"]
                    )
                    print(f"章节下载结果: {res}")
                print("测试下载结束。")
            else:
                print("错误: 目录数据为空。")
        self.run_task(task)

    def do_epub(self):
        book_id = self.bookid_var.get().strip()
        if not book_id:
            print("错误: 请输入书籍 ID")
            return
        def task():
            print(f"\n--- 开始打包 EPUB ({book_id}) ---")
            self.lnl.make_epub(book_id)
        self.run_task(task)

    def on_closing(self):
        if messagebox.askokcancel("退出", "确定要退出程序吗？"):
            print("正在清理后台资源并退出...")
            if hasattr(self, 'lnl'):
                # 后台通知 playwright 关闭
                threading.Thread(target=self.lnl.close, daemon=True).start()
            # 延时 1 秒后真正销毁窗体
            self.root.after(1000, self.root.destroy)

if __name__ == "__main__":
    root = tk.Tk()
    app = LNLApp(root)
    root.mainloop()