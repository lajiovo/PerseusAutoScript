import os
import json
import time
import base64
import threading
import queue
import re
import sys
import requests
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from pathlib import Path
from urllib.parse import urljoin
from ebooklib import epub
from playwright.sync_api import sync_playwright

# 路径常量定义
BASE_CACHE_DIR = Path("servercache/lnlcache")
BOOKSHELF_DIR = BASE_CACHE_DIR / "bookshelf"
BOOKSHELF_COVER_DIR = BOOKSHELF_DIR / "cover"
BOOKS_DIR = BASE_CACHE_DIR / "books"

BOOKSHELF_COVER_DIR.mkdir(parents=True, exist_ok=True)
BOOKS_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://www.linovelib.com"

def safe_filename(name):
    """移除文件名中的非法字符"""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def download_image(url, save_path, referer=BASE_URL):
    """通用的网络图片下载函数"""
    if not url.startswith("http"):
        url = urljoin(BASE_URL, url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": referer,
        "Accept-Language": "zh-CN,zh;q=0.9"
    }
    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(response.content)
            return True
        else:
            print(f"[警告] 图片下载 HTTP 状态码异常: {response.status_code} ({url})")
    except Exception as e:
        print(f"[错误] 下载图片失败 {url}: {e}")
    return False


class PlaywrightWorker(threading.Thread):
    """
    Playwright 后台工作线程，负责处理所有的浏览器交互操作。
    包含 Cloudflare 人机验证识别与自动等待机制。
    """
    def __init__(self, task_queue, result_queue):
        super().__init__()
        self.task_queue = task_queue
        self.result_queue = result_queue
        self.daemon = True
        self.browser = None
        self.context = None
        self.page = None

    def run(self):
        with sync_playwright() as p:
            print("[系统] 启动 Chromium/Chrome 引擎中...")
            
            # 创建持久化缓存目录保存 Cookie 和 Session，避免反复验证
            user_data_dir = BASE_CACHE_DIR / "user_data"
            user_data_dir.mkdir(parents=True, exist_ok=True)
            
            launch_args = {
                "user_data_dir": str(user_data_dir),
                "headless": False,
                "ignore_default_args": ["--enable-automation"],
                "args": [
                    '--disable-blink-features=AutomationControlled',
                    '--disable-infobars',
                    '--disable-dev-shm-usage',
                    '--start-maximized'
                ],
                "viewport": None
            }
            
            try:
                # 优先调起本地安装的官方 Google Chrome，通过率远高于 Playwright 自带 Chromium
                print("[系统] 尝试调用本地真实 Google Chrome 浏览器...")
                self.context = p.chromium.launch_persistent_context(channel="chrome", **launch_args)
            except Exception as e:
                print(f"[提示] 未检测到本地 Chrome ({e})，回退到 Playwright 默认 Chromium...")
                self.context = p.chromium.launch_persistent_context(**launch_args)
            
            # 深入注入脚本抹除自动化特征
            self.context.add_init_script("""
                // 擦除实例与原型链上的 webdriver 标记
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                try {
                    delete Object.getPrototypeOf(navigator).webdriver;
                } catch(e) {}
                
                // 补充标准 Chrome 运行时对象
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };
                
                // 伪装标准语言与插件列表
                Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en-US', 'en']});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                
                // 绕过 Permissions API 检测
                if (window.navigator.permissions) {
                    const origQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (params) => (
                        params.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        origQuery(params)
                    );
                }
            """)
            
            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
            print("[系统] 浏览器后台线程加载完成，持久化 Session 已激活。")
            
            while True:
                task = self.task_queue.get()
                if task is None or task.get('action') == 'quit':
                    print("[系统] 收到退出指令，关闭浏览器...")
                    break
                
                try:
                    self.handle_task(task)
                except Exception as e:
                    print(f"[错误] 执行任务失败 [{task.get('action')}]: {e}")
                    self.result_queue.put({"status": "error", "task": task, "error": str(e)})
                finally:
                    self.task_queue.task_done()
            
            self.context.close()

    def wait_for_cf_pass(self, selector, timeout=180):
        """
        检测页面是否有人机验证/Cloudflare 防护。
        若发现验证，暂停脚本干扰，等待用户在浏览器界面中手动点击完成。
        """
        start = time.time()
        notified = False
        while time.time() - start < timeout:
            try:
                # 检查目标元素是否存在，如果存在则说明已成功突破防护
                if self.page.query_selector(selector):
                    if notified:
                        print("[日志] ✅ 人机验证已成功通过，继续执行后续任务...")
                    return True

                title = self.page.title()
                
                # 仅通过页面标题快速判断，避免频繁读取 content() 干扰 Cloudflare 脚本运行
                if any(k in title for k in ["Just a moment", "验证", "Cloudflare", "安全检查", "cf-challenge"]):
                    if not notified:
                        print("\n" + "="*50)
                        print("[提示] ⚠️ 检测到 Cloudflare / 人机验证防护！")
                        print("[提示] 👉 请直接在弹出的 Chrome 浏览器窗口中用鼠标手动点击完成验证。")
                        print("[提示] 💡 注意：脚本已暂停任何后台点击干扰，手动通过后将自动恢复运行。")
                        print("="*50 + "\n")
                        notified = True
                    
                    time.sleep(2)
                else:
                    time.sleep(1)
            except Exception:
                time.sleep(1)
                
        print(f"[错误] 等待页面元素 '{selector}' 超时，请确认网络连接或手动通过验证。")
        return False

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
        page_num = task.get('page', 1)
        url = f"{BASE_URL}/wenku/" if page_num == 1 else f"{BASE_URL}/wenku/lastupdate_0_0_0_0_0_0_0_{page_num}_0.html"
        print(f"[日志] 正在访问书库页面 (第 {page_num} 页): {url}")
        
        self.page.goto(url, wait_until="domcontentloaded")
        
        # 等待并通过人机验证
        if not self.wait_for_cf_pass('.store_collist'):
            self.result_queue.put({"status": "fail", "action": "store_mode", "reason": "验证失败或页面超时"})
            return

        books_data = []
        book_elements = self.page.query_selector_all('.store_collist .bookbox')
        print(f"[日志] 找到 {len(book_elements)} 本书籍，解析数据中...")
        
        for el in book_elements:
            try:
                a_tag = el.query_selector('.bookname a')
                href = a_tag.get_attribute('href')
                book_id = href.split('/')[-1].replace('.html', '')
                title = a_tag.inner_text().strip()
                
                img_tag = el.query_selector('.bookimg img')
                cover_url = img_tag.get_attribute('data-original') or img_tag.get_attribute('src')
                
                info_spans = el.query_selector_all('.bookilnk span')
                info_text = [span.inner_text().strip() for span in info_spans]
                
                intro_tag = el.query_selector('.bookintro')
                intro = intro_tag.inner_text().strip() if intro_tag else ""
                
                tags_tag = el.query_selector('.bookupdate b')
                tags = tags_tag.inner_text().strip().split() if tags_tag else []
                
                cover_path = BOOKSHELF_COVER_DIR / f"{book_id}.jpg"
                if not cover_path.exists():
                    download_image(cover_url, cover_path, referer=url)
                
                books_data.append({
                    "book_id": book_id,
                    "title": title,
                    "cover_url": cover_url,
                    "local_cover": str(cover_path),
                    "info": info_text,
                    "intro": intro,
                    "tags": tags
                })
            except Exception as e:
                print(f"[错误] 解析单本条目出错: {e}")
                continue
        
        store_file = BOOKSHELF_DIR / "store.json"
        existing_data = []
        if store_file.exists():
            try:
                with open(store_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except Exception:
                existing_data = []
        
        existing_map = {b['book_id']: b for b in existing_data}
        for b in books_data:
            existing_map[b['book_id']] = b
                
        with open(store_file, 'w', encoding='utf-8') as f:
            json.dump(list(existing_map.values()), f, ensure_ascii=False, indent=4)
            
        print(f"[日志] 书库第 {page_num} 页抓取成功，保存 {len(books_data)} 条记录。")
        self.result_queue.put({"status": "success", "action": "store_mode", "page": page_num, "count": len(books_data)})

    def do_book_info(self, task):
        book_id = task['book_id']
        book_dir = BOOKS_DIR / str(book_id)
        book_dir.mkdir(parents=True, exist_ok=True)
        
        info_url = f"{BASE_URL}/novel/{book_id}.html"
        print(f"[日志] 获取书籍详情 (ID: {book_id}): {info_url}")
        self.page.goto(info_url, wait_until="domcontentloaded")
        
        if not self.wait_for_cf_pass('.book-name'):
            self.result_queue.put({"status": "fail", "action": "book_info", "book_id": book_id})
            return
        
        title = self.page.inner_text('.book-name').strip()
        cover_tag = self.page.query_selector('.book-img img')
        cover_url = cover_tag.get_attribute('src') if cover_tag else ""
        
        author_tag = self.page.query_selector('.au-name a')
        author = author_tag.inner_text().strip() if author_tag else "未知"
        
        translator_tag = self.page.query_selector('.tr-name a')
        translator = translator_tag.inner_text().strip() if translator_tag else "无"
        
        desc_tag = self.page.query_selector('.book-dec')
        description = desc_tag.inner_text().strip() if desc_tag else ""
        
        cover_path = book_dir / "cover.jpg"
        if not cover_path.exists() and cover_url:
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
            
        catalog_url = f"{BASE_URL}/novel/{book_id}/catalog"
        print(f"[日志] 正在抓取书籍目录: {catalog_url}")
        self.page.goto(catalog_url, wait_until="domcontentloaded")
        
        self.wait_for_cf_pass('.volume')
        
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
            
        print(f"[日志] 《{title}》 目录解析成功，包含 {len(catalog)} 卷。")
        self.result_queue.put({"status": "success", "action": "book_info", "book_id": book_id, "title": title})

    def do_chapter(self, task):
        book_id = str(task['book_id'])
        vol_title = safe_filename(task['vol_title'])
        chap_title = safe_filename(task['chap_title'])
        url_path = task['url']
        
        chap_url = urljoin(BASE_URL, url_path)
        vol_dir = BOOKS_DIR / book_id / vol_title
        img_dir = vol_dir / "img"
        img_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"[日志] 正在下载章节: {vol_title} -> {chap_title}")
        self.page.goto(chap_url, wait_until="domcontentloaded")
        
        if not self.wait_for_cf_pass('#TextContent'):
            self.result_queue.put({"status": "fail", "action": "chapter", "chap_title": chap_title})
            return
        
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(0.8)
        
        content_elements = self.page.query_selector_all('#TextContent > *, #hidden-images img')
        chapter_data = []
        img_counter = 1
        
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
            
            if 'dag' in class_name:
                continue
                
            if tag_name in ['p', 'br']:
                text = el.inner_text().strip()
                if text:
                    chapter_data.append({"type": "text", "content": text})
                    
            elif tag_name == 'img':
                src = el.get_attribute('data-src') or el.get_attribute('src')
                if not src or "sloading.svg" in src:
                    continue
                    
                img_name = f"{chap_title}_{img_counter}.jpg"
                img_path = img_dir / img_name
                
                base64_data = el.evaluate(canvas_extractor_js)
                if base64_data and base64_data.startswith("data:image"):
                    header, encoded = base64_data.split(",", 1)
                    with open(img_path, "wb") as f:
                        f.write(base64.b64decode(encoded))
                else:
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
            
        print(f"[日志] 章节完成: {chap_title} (包含 {img_counter-1} 张插图)")
        self.result_queue.put({
            "status": "success", 
            "action": "chapter", 
            "book_id": book_id, 
            "chap_title": chap_title
        })


class LNL:
    """LNL 主控制类，管理异步队列与 EPUB 制作"""
    def __init__(self):
        self.task_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.worker = PlaywrightWorker(self.task_queue, self.result_queue)
        self.worker.start()

    def wait_for_result(self):
        return self.result_queue.get()

    def get_store(self, page=1):
        self.task_queue.put({"action": "store_mode", "page": page})
        return self.wait_for_result()

    def get_book_info(self, book_id):
        self.task_queue.put({"action": "book_info", "book_id": book_id})
        return self.wait_for_result()

    def download_chapter(self, book_id, vol_title, chap_title, url):
        self.task_queue.put({
            "action": "chapter",
            "book_id": book_id,
            "vol_title": vol_title,
            "chap_title": chap_title,
            "url": url
        })
        return self.wait_for_result()

    def make_epub(self, book_id, output_path=None):
        book_dir = BOOKS_DIR / str(book_id)
        if not (book_dir / "metadata.json").exists() or not (book_dir / "catalog.json").exists():
            print(f"[错误] 书籍 {book_id} 的元数据或目录不存在，无法打包！")
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
        
        cover_path = Path(meta.get("local_cover"))
        if cover_path.exists():
            with open(cover_path, "rb") as f:
                book.set_cover("cover.jpg", f.read())

        spine = ['nav']
        toc = []
        
        style = 'p { text-indent: 2em; line-height: 1.6; } img { max-width: 100%; text-align: center; display: block; margin: 10px auto; }'
        default_css = epub.EpubItem(uid="style_default", file_name="style/default.css", media_type="text/css", content=style)
        book.add_item(default_css)

        for vol_idx, vol in enumerate(catalog):
            vol_title = safe_filename(vol["volume_title"])
            vol_dir = book_dir / vol_title
            
            vol_toc = (epub.Section(vol_title), [])
            
            for chap_idx, chap in enumerate(vol["chapters"]):
                chap_title = safe_filename(chap["title"])
                chap_json_path = vol_dir / f"{chap_title}.json"
                
                if not chap_json_path.exists():
                    continue
                    
                with open(chap_json_path, "r", encoding="utf-8") as f:
                    chap_data = json.load(f)
                
                html_content = f"<h1>{chap_title}</h1>\n"
                
                for item in chap_data:
                    if item["type"] == "text":
                        html_content += f"<p>{item['content']}</p>\n"
                    elif item["type"] == "image":
                        local_img_rel = item["local_path"]
                        local_img_abs = BASE_CACHE_DIR / local_img_rel
                        
                        if local_img_abs.exists():
                            epub_img_name = f"images/v{vol_idx}_c{chap_idx}_{local_img_abs.name}"
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
                                    pass
                                
                            html_content += f'<div style="text-align: center;"><img src="{epub_img_name}" alt="illustration"/></div>\n'
                
                chapter_item = epub.EpubHtml(title=chap_title, file_name=f"c_{vol_idx}_{chap_idx}.xhtml", lang='zh-CN')
                chapter_item.content = html_content
                chapter_item.add_item(default_css)
                
                book.add_item(chapter_item)
                spine.append(chapter_item)
                vol_toc[1].append(chapter_item)
            
            if vol_toc[1]:
                toc.append(vol_toc)

        book.toc = toc
        book.spine = spine
        
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        if output_path is None:
            output_path = f"{safe_filename(meta.get('title', book_id))}.epub"
            
        print(f"[打包] 正在打包生成 EPUB 文件: {output_path}...")
        epub.write_epub(output_path, book, {})
        print(f"[打包] ✅ EPUB 打包成功！文件名: {output_path}")
        return True

    def close(self):
        self.task_queue.put({"action": "quit"})
        self.worker.join()


class ThreadSafeRedirector:
    """线程安全的标准输出重定向器，实时写日志到 Tkinter"""
    def __init__(self, widget, root):
        self.widget = widget
        self.root = root

    def write(self, text):
        self.root.after(0, self._write, text)

    def _write(self, text):
        try:
            self.widget.configure(state="normal")
            self.widget.insert("end", text)
            self.widget.see("end")
            self.widget.configure(state="disabled")
        except Exception:
            pass

    def flush(self):
        pass


class LNLApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LNL 轻小说下载助手 v2.0")
        self.root.geometry("820x600")
        
        self.create_widgets()
        
        sys.stdout = ThreadSafeRedirector(self.log_text, self.root)
        sys.stderr = ThreadSafeRedirector(self.log_text, self.root)
        
        print("[初始化] 正在启动后台自动化浏览器，请稍候...")
        threading.Thread(target=self.init_lnl, daemon=True).start()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def init_lnl(self):
        self.lnl = LNL()
        print("[初始化] LNL 引擎启动成功！可以开始操作。")
        self.root.after(0, self.refresh_bookshelf)

    def create_widgets(self):
        # 选项卡控件
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # 选项卡 1：主控制台
        self.tab_console = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_console, text="📋 控制台与任务")

        # 选项卡 2：书架管理
        self.tab_bookshelf = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_bookshelf, text="📚 简易书架")

        self.setup_console_tab()
        self.setup_bookshelf_tab()

    def setup_console_tab(self):
        input_frame = ttk.LabelFrame(self.tab_console, text="参数输入", padding=10)
        input_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(input_frame, text="书库页码:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.page_var = tk.StringVar(value="1")
        ttk.Entry(input_frame, textvariable=self.page_var, width=10).grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        
        ttk.Label(input_frame, text="书籍 ID:").grid(row=0, column=2, padx=(20, 5), pady=5, sticky=tk.W)
        self.bookid_var = tk.StringVar(value="5354")
        ttk.Entry(input_frame, textvariable=self.bookid_var, width=15).grid(row=0, column=3, padx=5, pady=5, sticky=tk.W)

        btn_frame = ttk.Frame(self.tab_console, padding=5)
        btn_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(btn_frame, text="抓取书库页", command=self.do_get_store).grid(row=0, column=0, padx=5)
        ttk.Button(btn_frame, text="获取书籍信息与目录", command=self.do_get_info).grid(row=0, column=1, padx=5)
        ttk.Button(btn_frame, text="下载测试(前2章)", command=self.do_download_test).grid(row=0, column=2, padx=5)
        ttk.Button(btn_frame, text="下载整本书籍", command=self.do_download_full).grid(row=0, column=3, padx=5)
        ttk.Button(btn_frame, text="生成 EPUB", command=self.do_epub).grid(row=0, column=4, padx=5)

        log_frame = ttk.LabelFrame(self.tab_console, text="运行日志输出", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(log_frame, state="disabled", height=18)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def setup_bookshelf_tab(self):
        top_bar = ttk.Frame(self.tab_bookshelf)
        top_bar.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(top_bar, text="刷新书架列表", command=self.refresh_bookshelf).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_bar, text="把选中项设为主ID", command=self.select_book_from_shelf).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_bar, text="一键打包选中书为 EPUB", command=self.epub_selected_shelf).pack(side=tk.LEFT, padx=5)

        # 树状列表展现书架
        columns = ("book_id", "title", "author", "tags", "download_status")
        self.shelf_tree = ttk.Treeview(self.tab_bookshelf, columns=columns, show="headings", height=18)
        
        self.shelf_tree.heading("book_id", text="书籍 ID")
        self.shelf_tree.heading("title", text="书名")
        self.shelf_tree.heading("author", text="作者/信息")
        self.shelf_tree.heading("tags", text="标签")
        self.shelf_tree.heading("download_status", text="本地状态")

        self.shelf_tree.column("book_id", width=80, anchor="center")
        self.shelf_tree.column("title", width=200, anchor="w")
        self.shelf_tree.column("author", width=180, anchor="w")
        self.shelf_tree.column("tags", width=180, anchor="w")
        self.shelf_tree.column("download_status", width=100, anchor="center")

        scrollbar = ttk.Scrollbar(self.tab_bookshelf, orient=tk.VERTICAL, command=self.shelf_tree.yview)
        self.shelf_tree.configure(yscroll=scrollbar.set)

        self.shelf_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def refresh_bookshelf(self):
        """扫描 store.json 和 books 目录更新简易书架"""
        for item in self.shelf_tree.get_children():
            self.shelf_tree.delete(item)

        books_map = {}

        # 1. 扫描 store.json 历史
        store_file = BOOKSHELF_DIR / "store.json"
        if store_file.exists():
            try:
                with open(store_file, "r", encoding="utf-8") as f:
                    store_data = json.load(f)
                    for b in store_data:
                        bid = b.get("book_id")
                        books_map[bid] = {
                            "book_id": bid,
                            "title": b.get("title", "未知"),
                            "author": " / ".join(b.get("info", [])[:2]),
                            "tags": " ".join(b.get("tags", [])),
                            "status": "未下载"
                        }
            except Exception as e:
                print(f"[错误] 读取 store.json 失败: {e}")

        # 2. 扫描本地已缓存的书籍目录
        if BOOKS_DIR.exists():
            for b_dir in BOOKS_DIR.iterdir():
                if b_dir.is_dir():
                    bid = b_dir.name
                    meta_file = b_dir / "metadata.json"
                    status = "已抓目录"
                    if list(b_dir.glob("*/*.json")):
                        status = "已下载部分章节"

                    if meta_file.exists():
                        try:
                            with open(meta_file, "r", encoding="utf-8") as f:
                                meta = json.load(f)
                                books_map[bid] = {
                                    "book_id": bid,
                                    "title": meta.get("title", "未知"),
                                    "author": meta.get("author", "未知"),
                                    "tags": meta.get("description", "")[:20] + "...",
                                    "status": status
                                }
                        except Exception:
                            pass
                    else:
                        if bid not in books_map:
                            books_map[bid] = {
                                "book_id": bid,
                                "title": f"书籍_{bid}",
                                "author": "未知",
                                "tags": "-",
                                "status": status
                            }

        # 填入 Treeview
        for bid, item in books_map.items():
            self.shelf_tree.insert("", "end", values=(
                item["book_id"],
                item["title"],
                item["author"],
                item["tags"],
                item["status"]
            ))

    def select_book_from_shelf(self):
        selected = self.shelf_tree.selection()
        if not selected:
            messagebox.showinfo("提示", "请先在列表中选中一本书籍")
            return
        item_values = self.shelf_tree.item(selected[0], "values")
        book_id = item_values[0]
        self.bookid_var.set(book_id)
        self.notebook.select(self.tab_console)
        print(f"[操作] 已将选择的书籍 ID ({book_id}) 加载至主控制台。")

    def epub_selected_shelf(self):
        selected = self.shelf_tree.selection()
        if not selected:
            messagebox.showinfo("提示", "请先在列表中选中一本书籍")
            return
        book_id = self.shelf_tree.item(selected[0], "values")[0]
        self.bookid_var.set(book_id)
        self.do_epub()

    def run_task(self, target):
        if not hasattr(self, 'lnl'):
            print("[错误] Playwright 尚未初始化完成，请稍后再试。")
            return
        threading.Thread(target=target, daemon=True).start()

    def do_get_store(self):
        page_str = self.page_var.get().strip()
        if not page_str.isdigit():
            print("[错误] 页码必须为数字！")
            return
        def task():
            print(f"\n--- 抓取书库列表 (第 {page_str} 页) ---")
            res = self.lnl.get_store(int(page_str))
            print("抓取结果:", res)
            self.root.after(0, self.refresh_bookshelf)
        self.run_task(task)

    def do_get_info(self):
        book_id = self.bookid_var.get().strip()
        if not book_id:
            print("[错误] 请输入书籍 ID！")
            return
        def task():
            print(f"\n--- 抓取书籍信息 ({book_id}) ---")
            res = self.lnl.get_book_info(book_id)
            print("抓取结果:", res)
            self.root.after(0, self.refresh_bookshelf)
        self.run_task(task)

    def do_download_test(self):
        book_id = self.bookid_var.get().strip()
        if not book_id:
            print("[错误] 请输入书籍 ID！")
            return
        def task():
            print(f"\n--- 开始下载测试章节 (前2章) ({book_id}) ---")
            book_dir = BOOKS_DIR / book_id
            cat_file = book_dir / "catalog.json"
            if not cat_file.exists():
                print("[提示] 目录数据不存在，自动先获取书籍目录...")
                self.lnl.get_book_info(book_id)
                
            if not cat_file.exists():
                print("[错误] 无法获取该书目录，中断操作。")
                return
                
            with open(cat_file, "r", encoding="utf-8") as f:
                catalog = json.load(f)
            if catalog and catalog[0].get("chapters"):
                vol_title = catalog[0]["volume_title"]
                for chap in catalog[0]["chapters"][:2]:
                    self.lnl.download_chapter(
                        book_id=book_id,
                        vol_title=vol_title,
                        chap_title=chap["title"],
                        url=chap["url"]
                    )
                print("测试下载完成。")
                self.root.after(0, self.refresh_bookshelf)
            else:
                print("[错误] 目录数据为空。")
        self.run_task(task)

    def do_download_full(self):
        book_id = self.bookid_var.get().strip()
        if not book_id:
            print("[错误] 请输入书籍 ID！")
            return
        def task():
            print(f"\n--- 开始全本书籍全章节下载 ({book_id}) ---")
            book_dir = BOOKS_DIR / book_id
            cat_file = book_dir / "catalog.json"
            if not cat_file.exists():
                print("[提示] 目录数据不存在，自动先获取书籍目录...")
                self.lnl.get_book_info(book_id)
                
            if not cat_file.exists():
                print("[错误] 无法获取该书目录，中断下载。")
                return
                
            with open(cat_file, "r", encoding="utf-8") as f:
                catalog = json.load(f)
                
            for vol in catalog:
                vol_title = vol["volume_title"]
                for chap in vol["chapters"]:
                    self.lnl.download_chapter(
                        book_id=book_id,
                        vol_title=vol_title,
                        chap_title=chap["title"],
                        url=chap["url"]
                    )
            print(f"《{book_id}》 全书下载完毕！")
            self.root.after(0, self.refresh_bookshelf)
        self.run_task(task)

    def do_epub(self):
        book_id = self.bookid_var.get().strip()
        if not book_id:
            print("[错误] 请输入书籍 ID！")
            return
        def task():
            print(f"\n--- 开始打包 EPUB ({book_id}) ---")
            self.lnl.make_epub(book_id)
        self.run_task(task)

    def on_closing(self):
        if messagebox.askokcancel("退出", "确定要退出程序吗？"):
            print("[退出] 清理线程与浏览器...")
            if hasattr(self, 'lnl'):
                threading.Thread(target=self.lnl.close, daemon=True).start()
            self.root.after(800, self.root.destroy)

if __name__ == "__main__":
    root = tk.Tk()
    app = LNLApp(root)
    root.mainloop()