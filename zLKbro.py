import asyncio
import os
import json
import hashlib
import re
import html
import time
from datetime import datetime
from urllib.parse import urljoin
from playwright.async_api import async_playwright
import requests
import urllib3

from zConfig import get_config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 繁转简支持
cc_converter = None
try:
    import opencc
    try:
        cc_converter = opencc.OpenCC('t2s')
    except Exception:
        cc_converter = opencc.OpenCC('t2s.json')
except Exception:
    try:
        import zhconv
        cc_converter = "zhconv"
    except Exception:
        cc_converter = None

def convert_t2s(text: str, enabled: bool = True) -> str:
    if not text or not enabled:
        return text
    if cc_converter == "zhconv":
        try:
            import zhconv
            return zhconv.convert(text, 'zh-cn')
        except Exception:
            return text
    elif cc_converter:
        try:
            return cc_converter.convert(text)
        except Exception:
            return text
    return text

def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", name)

def get_url_hash(url: str) -> str:
    return hashlib.md5(url.encode("utf-8")).hexdigest()

class LKbro:
    def __init__(self, headless=True):
        self.headless = headless
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.user_data_dir = os.path.join(self.current_dir, "brocache")
        self.download_dir = os.path.join(self.current_dir, "browser_downloads")
        os.makedirs(self.download_dir, exist_ok=True)
        
        self.server_cache_dir = os.path.join(self.current_dir, "servercache", "lk")
        os.makedirs(os.path.join(self.server_cache_dir, "books"), exist_ok=True)
        os.makedirs(os.path.join(self.server_cache_dir, "bookshelf"), exist_ok=True)

        self.domain = "https://www.lightnovel.fun"
        self.proxy = get_config("proxy.socks") or get_config("proxy.http")
        self.auth_file = os.path.join(self.current_dir, "auth_lk.json")

        self.playwright = None
        self.browser_context = None
        self.page = None
        self._running = False
        self._lock = asyncio.Lock()

    async def start(self, headless=None):
        async with self._lock:
            if headless is not None:
                self.headless = headless

            if self._running and self.browser_context:
                return
            
            win_w, win_h = 1536, 864
            pos_x, pos_y = 192, 108
            view_w, view_h = win_w, win_h - 80

            self.playwright = await async_playwright().start()
            proxy_config = {"server": self.proxy} if self.proxy else None

            self.browser_context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=self.user_data_dir,
                headless=self.headless,
                args=[
                    f"--window-size={win_w},{win_h}",
                    f"--window-position={pos_x},{pos_y}",
                    "--force-device-scale-factor=1",
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--ignore-certificate-errors",
                ],
                ignore_default_args=["--enable-automation"],
                viewport={"width": view_w, "height": view_h},
                proxy=proxy_config,
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
                device_scale_factor=1,
                is_mobile=True,
                has_touch=True,
                locale="ja-JP",
                extra_http_headers={
                    "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7,zh-CN;q=0.6"
                },
                timezone_id="Asia/Tokyo",
                geolocation={"latitude": 35.6762, "longitude": 139.6503},
                permissions=["geolocation", "clipboard-read", "clipboard-write"],
                accept_downloads=True,
                downloads_path=self.download_dir
            )

            await self.browser_context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            if os.path.exists(self.auth_file):
                try:
                    with open(self.auth_file, "r", encoding="utf-8") as f:
                        cookies = json.load(f)
                        await self.browser_context.add_cookies(cookies)
                except Exception:
                    pass

            self.page = self.browser_context.pages[0] if self.browser_context.pages else await self.browser_context.new_page()
            self._running = True

    async def close(self):
        async with self._lock:
            if not self._running:
                return
            try:
                if self.browser_context:
                    cookies = await self.browser_context.cookies()
                    with open(self.auth_file, "w", encoding="utf-8") as f:
                        json.dump(cookies, f, ensure_ascii=False, indent=2)
                    await self.browser_context.close()
                if self.playwright:
                    await self.playwright.stop()
            except Exception:
                pass
            finally:
                self._running = False
                self.browser_context = None
                self.page = None

    def is_running(self):
        return self._running

    async def scroll_and_collect_bookshelf(self, target_url="https://www.lightnovel.fun/category/lightnovel", max_scrolls=50, progress_callback=None):
        """向下滚动书架，检测到新的书籍元素加入，继续下滑，直到无新书籍或达到最大上限"""
        await self.start()
        books_shelf_dir = os.path.join(self.server_cache_dir, "bookshelf")
        os.makedirs(books_shelf_dir, exist_ok=True)

        if progress_callback:
            progress_callback(0, f"正在访问书架页面: {target_url}")

        await self.page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
        await self.page.wait_for_timeout(2000)

        collected_books = {}
        shelf_json_path = os.path.join(books_shelf_dir, "bookshelf.json")
        if os.path.exists(shelf_json_path):
            try:
                with open(shelf_json_path, "r", encoding="utf-8") as f:
                    old_list = json.load(f)
                    for item in old_list:
                        collected_books[item["book_id"]] = item
            except Exception:
                pass

        consecutive_no_new = 0
        current_scroll = 0

        while current_scroll < max_scrolls:
            if not self._running:
                break
            
            current_scroll += 1
            html_content = await self.page.content()
            books = self._parse_bookshelf_html(html_content)

            new_found_this_turn = 0
            for b in books:
                if b["book_id"] not in collected_books:
                    collected_books[b["book_id"]] = b
                    new_found_this_turn += 1

            if progress_callback:
                progress_callback(
                    int((current_scroll / max_scrolls) * 100),
                    f"第 {current_scroll} 次下滑，本轮新增 {new_found_this_turn} 本，总计 {len(collected_books)} 本"
                )

            # 如果检测到新加入元素，重置无新元素计数器
            if new_found_this_turn > 0:
                consecutive_no_new = 0
            else:
                consecutive_no_new += 1

            # 连续 3 次下滑均无任何新书籍加入，说明已到达底部
            if consecutive_no_new >= 3:
                break

            # 往下滚动
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
            await self.page.wait_for_timeout(2000)

            # 每获取一轮就增量写盘，保证数据不丢
            with open(shelf_json_path, "w", encoding="utf-8") as f:
                json.dump(list(collected_books.values()), f, ensure_ascii=False, indent=2)

        bookshelf_list = list(collected_books.values())
        with open(shelf_json_path, "w", encoding="utf-8") as f:
            json.dump(bookshelf_list, f, ensure_ascii=False, indent=2)

        return bookshelf_list

    async def collect_current_page(self, progress_callback=None):
        """窗口模式/已有页面下：直接抓取当前页面中显示的内容（支持书架或书籍详情）"""
        if not self._running or not self.page:
            await self.start()

        if progress_callback:
            progress_callback(10, "正在读取浏览器当前活动页面...")

        current_url = self.page.url
        html_content = await self.page.content()

        # 1. 若当前是书架/列表类页面
        books = self._parse_bookshelf_html(html_content)
        if books:
            books_shelf_dir = os.path.join(self.server_cache_dir, "bookshelf")
            os.makedirs(books_shelf_dir, exist_ok=True)
            shelf_json_path = os.path.join(books_shelf_dir, "bookshelf.json")
            collected_books = {}
            if os.path.exists(shelf_json_path):
                try:
                    with open(shelf_json_path, "r", encoding="utf-8") as f:
                        for item in json.load(f):
                            collected_books[item["book_id"]] = item
                except Exception:
                    pass
            for b in books:
                collected_books[b["book_id"]] = b
            with open(shelf_json_path, "w", encoding="utf-8") as f:
                json.dump(list(collected_books.values()), f, ensure_ascii=False, indent=2)
            if progress_callback:
                progress_callback(100, f"已从当前页提取 {len(books)} 本书架书籍")
            return {"type": "bookshelf", "count": len(books), "url": current_url}

        # 2. 若当前是具体某一本书籍详情页 /book/xxx
        match = re.search(r'/book/(\d+)', current_url)
        if match:
            book_id = match.group(1)
            if progress_callback:
                progress_callback(50, f"识别到书籍详情页 ID: {book_id}，正在解析详情...")
            meta, cat = await self.get_book_detail_and_catalog(book_id, progress_callback)
            return {"type": "book", "book_id": book_id, "meta": meta, "catalog": cat, "url": current_url}

        return {"type": "unknown", "message": "当前页面未能匹配到书籍或书架结构", "url": current_url}

    def _parse_bookshelf_html(self, html_content):
        books = []
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        cards = soup.select("article.category-book-card")
        for card in cards:
            a_tag = card.select_one("a")
            if not a_tag:
                continue
            href = a_tag.get("href", "")
            match = re.search(r'/book/(\d+)', href)
            if not match:
                continue
            book_id = match.group(1)

            img_tag = card.select_one("img.pc-book-cover-img")
            cover_url = img_tag.get("src", "") if img_tag else ""
            alt_text = img_tag.get("alt", "") if img_tag else ""

            h3_tag = card.select_one("h3")
            title = h3_tag.get_text(strip=True) if h3_tag else alt_text

            meta_spans = card.select(".category-book-meta span")
            meta_info = [s.get_text(strip=True) for s in meta_spans]
            update_time = meta_info[1] if len(meta_info) > 1 else (meta_info[0] if meta_info else "")

            tag_spans = card.select(".category-book-tags span")
            tags = [s.get_text(strip=True) for s in tag_spans]

            books.append({
                "book_id": book_id,
                "title": convert_t2s(title, True),
                "cover_url": cover_url,
                "update_time": update_time,
                "tags": [convert_t2s(t, True) for t in tags],
                "url": urljoin(self.domain, href)
            })
        return books

    async def get_book_detail_and_catalog(self, book_id: str, progress_callback=None):
        await self.start()
        url = f"{self.domain}/cn/book/{book_id}"
        if progress_callback:
            progress_callback(10, f"正在访问书籍页面: {url}")

        await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await self.page.wait_for_timeout(1500)

        for _ in range(3):
            await self.page.evaluate("window.scrollBy(0, 800)")
            await self.page.wait_for_timeout(500)

        html_content = await self.page.content()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')

        title = f"Book_{book_id}"
        h1 = soup.select_one(".detail-info h1, h1")
        if h1:
            title = h1.get_text(strip=True)

        author = "未知"
        for span in soup.select(".detail-info-line span"):
            text = span.get_text()
            if "作者" in text:
                strong = span.select_one("strong")
                if strong:
                    author = strong.get_text(strip=True)
                    break

        cover_url = ""
        img_el = soup.select_one(".pc-book-cover-img, .detail-cover img")
        if img_el:
            cover_url = img_el.get("src", "")

        volumes_data = []
        tab_buttons = soup.select(".volume-tabs .volume-tab, .volume-tab")
        
        if tab_buttons:
            tab_locator = self.page.locator(".volume-tabs .volume-tab, .volume-tab")
            count = await tab_locator.count()
            for i in range(count):
                try:
                    tab = tab_locator.nth(i)
                    v_title = await tab.get_attribute("title") or await tab.inner_text()
                    v_title = v_title.strip() if v_title else f"第{i+1}卷"
                    
                    await tab.scroll_into_view_if_needed()
                    await tab.click(force=True)
                    await self.page.wait_for_timeout(1000)

                    c_links = await self.page.query_selector_all(".chapter-grid a, .chapter-grid .chapter, a[href*='/reader/']")
                    chapters = []
                    seen = set()
                    for cl in c_links:
                        href = await cl.get_attribute("href")
                        if not href or "reader" not in href:
                            continue
                        full_u = urljoin(self.domain, href)
                        if full_u in seen:
                            continue
                        seen.add(full_u)
                        ch_title = (await cl.inner_text()).strip() or "无标题"
                        
                        ch_id_match = re.search(r'/reader/\d+/(\d+)', full_u)
                        ch_id = ch_id_match.group(1) if ch_id_match else hashlib.md5(full_u.encode()).hexdigest()[:8]

                        chapters.append({
                            "chapter_id": ch_id,
                            "title": convert_t2s(ch_title, True),
                            "url": full_u,
                            "downloaded": False
                        })
                    volumes_data.append({
                        "vol_id": f"vol_{i+1}",
                        "vol_title": convert_t2s(v_title, True),
                        "fetched": len(chapters) > 0,
                        "chapters": chapters
                    })
                except Exception:
                    pass

        if not volumes_data:
            c_links = soup.select("a[href*='/reader/']")
            chapters = []
            seen = set()
            for cl in c_links:
                href = cl.get("href", "")
                full_u = urljoin(self.domain, href)
                if full_u in seen:
                    continue
                seen.add(full_u)
                ch_title = cl.get_text(strip=True) or "无标题"
                ch_id_match = re.search(r'/reader/\d+/(\d+)', full_u)
                ch_id = ch_id_match.group(1) if ch_id_match else hashlib.md5(full_u.encode()).hexdigest()[:8]
                chapters.append({
                    "chapter_id": ch_id,
                    "title": convert_t2s(ch_title, True),
                    "url": full_u,
                    "downloaded": False
                })
            if chapters:
                volumes_data.append({
                    "vol_id": "vol_1",
                    "vol_title": "正文卷",
                    "fetched": True,
                    "chapters": chapters
                })

        book_dir = os.path.join(self.server_cache_dir, "books", str(book_id))
        os.makedirs(book_dir, exist_ok=True)
        img_dir = os.path.join(book_dir, "images_mapped")
        os.makedirs(img_dir, exist_ok=True)

        mapping_file_path = os.path.join(book_dir, "image_address_mapping.json")
        image_mapping_records = {}
        if os.path.exists(mapping_file_path):
            try:
                with open(mapping_file_path, "r", encoding="utf-8") as f:
                    image_mapping_records = json.load(f)
            except Exception:
                pass

        if cover_url:
            cover_full_url = urljoin(self.domain, html.unescape(cover_url))
            cover_hash = get_url_hash(cover_full_url)
            ext = ".jpg"
            if ".png" in cover_full_url.lower():
                ext = ".png"
            elif ".webp" in cover_full_url.lower():
                ext = ".webp"
            cover_filename = f"cover_{cover_hash}{ext}"
            cover_path = os.path.join(img_dir, cover_filename)
            if not os.path.exists(cover_path) or os.path.getsize(cover_path) == 0:
                try:
                    resp = requests.get(cover_full_url, headers={"Referer": self.domain}, timeout=15, verify=False)
                    if resp.status_code == 200:
                        with open(cover_path, "wb") as f:
                            f.write(resp.content)
                except Exception:
                    pass
            image_mapping_records[cover_full_url] = cover_filename

        metadata = {
            "book_id": str(book_id),
            "title": convert_t2s(title, True),
            "author": convert_t2s(author, True),
            "cover_url": cover_url,
            "updated_at": datetime.now().isoformat()
        }

        with open(os.path.join(book_dir, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        catalog_path = os.path.join(book_dir, "catalog.json")
        existing_catalog = {}
        if os.path.exists(catalog_path):
            try:
                with open(catalog_path, "r", encoding="utf-8") as f:
                    existing_catalog = json.load(f)
            except Exception:
                pass

        custom_sort = existing_catalog.get("custom_sort", [])
        
        catalog_data = {
            "book_id": str(book_id),
            "volumes": volumes_data,
            "custom_sort": custom_sort
        }
        with open(catalog_path, "w", encoding="utf-8") as f:
            json.dump(catalog_data, f, ensure_ascii=False, indent=2)

        with open(mapping_file_path, "w", encoding="utf-8") as f:
            json.dump(image_mapping_records, f, ensure_ascii=False, indent=2)

        return metadata, catalog_data

    async def redownload_images(self, book_id: str, progress_callback=None):
        """手动重新下载插图及封面"""
        book_dir = os.path.join(self.server_cache_dir, "books", str(book_id))
        mapping_file_path = os.path.join(book_dir, "image_address_mapping.json")
        if not os.path.exists(mapping_file_path):
            return False

        with open(mapping_file_path, "r", encoding="utf-8") as f:
            mapping = json.load(f)

        img_dir = os.path.join(book_dir, "images_mapped")
        os.makedirs(img_dir, exist_ok=True)

        total = len(mapping)
        idx = 0
        for url, filename in mapping.items():
            idx += 1
            if progress_callback:
                progress_callback(int(idx / total * 100), f"重新下载插图: {filename}")
            try:
                resp = requests.get(url, headers={"Referer": self.domain}, timeout=15, verify=False)
                if resp.status_code == 200:
                    with open(os.path.join(img_dir, filename), "wb") as f:
                        f.write(resp.content)
            except Exception:
                pass
        return True

    async def crawl_chapter(self, book_id: str, chapter_url: str, vol_name: str, chapter_title: str, progress_callback=None):
        await self.start()
        if progress_callback:
            progress_callback(50, f"正在爬取章节: {chapter_title}")

        await self.page.goto(chapter_url, wait_until="domcontentloaded", timeout=45000)
        await self.page.wait_for_timeout(1000)

        try:
            read_more = self.page.locator(".read-more, .expand-btn, .show-more")
            if await read_more.count() > 0:
                await read_more.first.click(force=True)
                await self.page.wait_for_timeout(500)
        except Exception:
            pass

        content_el = await self.page.query_selector(".reader-text, .chapter-content, #article-content")
        if not content_el:
            content_el = await self.page.query_selector("body")

        html_raw = await content_el.inner_html()
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_raw, 'html.parser')

        for tag in soup(["script", "style", "iframe", "nav", "header", "footer"]):
            tag.decompose()

        book_dir = os.path.join(self.server_cache_dir, "books", str(book_id))
        vol_dir = os.path.join(book_dir, sanitize_filename(vol_name))
        img_dir = os.path.join(book_dir, "images_mapped")
        os.makedirs(vol_dir, exist_ok=True)
        os.makedirs(img_dir, exist_ok=True)

        mapping_file_path = os.path.join(book_dir, "image_address_mapping.json")
        image_mapping_records = {}
        if os.path.exists(mapping_file_path):
            try:
                with open(mapping_file_path, "r", encoding="utf-8") as f:
                    image_mapping_records = json.load(f)
            except Exception:
                pass

        paragraphs_and_images = []
        image_mapping = {}

        elements = soup.find_all(['p', 'div', 'img'])
        for el in elements:
            if el.name == 'img' or el.find('img'):
                img_tags = [el] if el.name == 'img' else el.find_all('img')
                for img in img_tags:
                    src = img.get('src') or img.get('data-src')
                    if not src:
                        continue
                    full_img_url = urljoin(self.domain, html.unescape(src))
                    img_hash = get_url_hash(full_img_url)
                    ext = ".jpg"
                    if ".png" in full_img_url.lower():
                        ext = ".png"
                    elif ".webp" in full_img_url.lower():
                        ext = ".webp"
                    
                    img_filename = f"{img_hash}{ext}"
                    img_path = os.path.join(img_dir, img_filename)

                    if not os.path.exists(img_path) or os.path.getsize(img_path) == 0:
                        try:
                            resp = requests.get(full_img_url, headers={"Referer": self.domain}, timeout=15, verify=False)
                            if resp.status_code == 200:
                                with open(img_path, "wb") as f:
                                    f.write(resp.content)
                        except Exception:
                            pass

                    image_mapping[img_hash] = img_filename
                    image_mapping_records[full_img_url] = img_filename

                    paragraphs_and_images.append({
                        "type": "image",
                        "url": full_img_url,
                        "hash": img_hash,
                        "file": img_filename
                    })
            else:
                text = el.get_text(strip=True)
                if text and len(text) > 0:
                    paragraphs_and_images.append({
                        "type": "text",
                        "content": convert_t2s(text, True)
                    })

        chapter_data = {
            "title": convert_t2s(chapter_title, True),
            "url": chapter_url,
            "paragraphs": paragraphs_and_images,
            "image_mapping": image_mapping
        }

        ch_json_path = os.path.join(vol_dir, f"{sanitize_filename(chapter_title)}.json")
        with open(ch_json_path, "w", encoding="utf-8") as f:
            json.dump(chapter_data, f, ensure_ascii=False, indent=2)

        with open(mapping_file_path, "w", encoding="utf-8") as f:
            json.dump(image_mapping_records, f, ensure_ascii=False, indent=2)

        return chapter_data

    async def crawl_all_chapters(self, book_id: str, progress_callback=None):
        metadata, catalog = await self.get_book_detail_and_catalog(book_id, progress_callback)
        volumes = catalog.get("volumes", [])
        
        total_chapters = sum(len(v["chapters"]) for v in volumes)
        current_count = 0

        for v in volumes:
            vol_name = v["vol_title"]
            for ch in v["chapters"]:
                current_count += 1
                if progress_callback:
                    progress_callback(int(current_count / total_chapters * 100), f"正在爬取 [{vol_name}] {ch['title']}")
                await self.crawl_chapter(book_id, ch["url"], vol_name, ch["title"])
                ch["downloaded"] = True
            v["fetched"] = True

        book_dir = os.path.join(self.server_cache_dir, "books", str(book_id))
        with open(os.path.join(book_dir, "catalog.json"), "w", encoding="utf-8") as f:
            json.dump(catalog, f, ensure_ascii=False, indent=2)

        return True
