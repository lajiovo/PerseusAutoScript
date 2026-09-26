import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from ebooklib import epub
import requests

# 根目录与基础配置
BASE_DIR = Path(__file__).parent
OUTPUTDIR = BASE_DIR / "Novels"
CACHE_BASE_DIR = BASE_DIR / "servercache" / "inovel"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

def convert_source_url(source):
    """自动将页面链接转换为对应的 feed.xml 链接（若非 lnovel.animes.garden 则强转）"""
    source = source.strip()
    
    # 0. 如果已经带 lnovel.animes.garden 域名，直接返回
    if "lnovel.animes.garden" in source:
        return source

    # 1. 轻小说分卷页: .../novel/2960/vol_332998.html -> https://lnovel.animes.garden/bili/novel/2960/vol/332998/feed.xml
    m = re.search(r'/novel/(\d+)/vol_(\d+)\.html', source)
    if m:
        book_id, vol_id = m.groups()
        return f"https://lnovel.animes.garden/bili/novel/{book_id}/vol/{vol_id}/feed.xml"

    # 2. 轻小说章节内容页 (非分卷): .../novel/4649/287262.html -> 不需要转成 feed 列表
    if re.search(r'/novel/\d+/\d+\.html', source):
        return source
    if "/chapter/" in source:
        return source

    # 2. 轻小说丛书页: .../novel/4972.html -> https://lnovel.animes.garden/bili/novel/4972/feed.xml
    m = re.search(r'/novel/(\d+)\.html', source)
    if m:
        book_id = m.group(1)
        return f"https://lnovel.animes.garden/bili/novel/{book_id}/feed.xml"

    # 3. 排行榜索引页: .../top/monthvisit/1.html -> https://lnovel.animes.garden/bili/top/monthvisit/feed.xml
    m = re.search(r'/top/([^/]+)/', source)
    if m:
        top_type = m.group(1)
        return f"https://lnovel.animes.garden/bili/top/{top_type}/feed.xml"

    return source

def sanitize_filename(name):
    """清理非法的标准文件名/目录名字符"""
    return re.sub(r'[\\/*?:"<>|]', "_", name).strip()


def get_cached_novels():
    """扫描 servercache/inovel 目录，获取所有已缓存的书籍元数据"""
    novels = []
    if not CACHE_BASE_DIR.exists():
        return novels

    import datetime
    for folder in CACHE_BASE_DIR.iterdir():
        if folder.is_dir():
            xml_path = folder / "feed.xml"
            if xml_path.exists():
                mtime = xml_path.stat().st_mtime
                time_str = datetime.datetime.fromtimestamp(mtime).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                novels.append(
                    {
                        "title": folder.name,
                        "xml_path": str(xml_path),
                        "mtime": time_str,
                        "folder_path": str(folder),
                    }
                )
    return sorted(novels, key=lambda x: x["mtime"], reverse=True)


def get_novel_title_from_xml_content(content_bytes):
    """从 XML 二进制或字符串内容中快速解析出 channel -> title"""
    try:
        root = ET.fromstring(content_bytes)
        channel = root.find("channel")
        if channel is not None:
            title = channel.findtext("title", "").strip()
            if title:
                return sanitize_filename(title)
    except Exception:
        pass
    return "UnknownNovel"


class NovelEpubExporter:

    def __init__(self, log_callback=None):
        self.log_callback = log_callback

    def log(self, message):
        """打印日志，直接输出到控制台，避免 Tkinter UI 频繁刷新导致卡死"""
        print(message)

    def download_file(self, url):
        """下载网络文件并返回 bytes 和 Content-Type"""
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                return resp.content, resp.headers.get("Content-Type", "")
        except Exception as e:
            self.log(f"  [!] 下载失败 ({url}): {e}")
        return None, None

    def prepare_xml_source(self, source_input):
        """
        处理源 XML（URL 链接或本地文件路径），
        解析书名并缓存到 servercache/inovel/<书名>/feed.xml
        如果传入的 XML 是卷列表（即 item 里面的链接是 novel/feed.xml 或单个卷的链接，或者包含多个独立卷的 feed 链接），
        则进行嵌套解析或合并下载。
        """
        source_input = str(source_input).strip()
        xml_bytes = None

        if source_input.startswith("http://") or source_input.startswith(
            "https://"
        ):
            self.log(f"🌐 正在从链接获取 XML: {source_input}")
            xml_bytes, _ = self.download_file(source_input)
            if not xml_bytes:
                raise Exception("无法从提供的网络链接获取 XML 内容")
        else:
            local_path = Path(source_input)
            if not local_path.exists():
                raise Exception(f"未找到本地 XML 文件: {local_path}")
            self.log(f"📂 正在读取本地文件: {local_path}")
            xml_bytes = local_path.read_bytes()

        # 解析根节点以检查是否是卷列表 XML
        try:
            root = ET.fromstring(xml_bytes)
            channel = root.find("channel")
            if channel is not None:
                items = channel.findall("item")
                # 检查是否为卷列表（即每个 item 指向的是单独的 vol 链接或者包含 feed.xml 链接）
                vol_feed_urls = []
                for item in items:
                    link = item.findtext("link", "").strip()
                    # 尝试从 item 的 link、guid 或 content 中寻找链接
                    if not link:
                        guid = item.findtext("guid", "").strip()
                        if guid and guid.startswith("http"):
                            link = guid
                    
                    # 检查 encoded 内容中的 RSS 订阅链接
                    encoded = item.findtext("encoded", "")
                    if not encoded:
                        encoded = item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded", "")
                    
                    m_rss = re.search(r'href="([^"]+?/feed\.xml)"', encoded)
                    if m_rss:
                        vol_feed_urls.append(m_rss.group(1))
                    elif link:
                        converted = convert_source_url(link)
                        if converted and converted.endswith("/feed.xml"):
                            vol_feed_urls.append(converted)

                # 如果检测到了多个卷的 feed 链接（说明这是一个小说丛书/卷列表 feed.xml）
                if len(vol_feed_urls) > 1:
                    self.log(f"📚 检测到 XML 是卷列表，包含 {len(vol_feed_urls)} 个分卷/章节 feed，将开始嵌套依次下载并合并...")
                    
                    book_title = get_novel_title_from_xml_content(xml_bytes)
                    novel_cache_dir = CACHE_BASE_DIR / book_title
                    novel_cache_dir.mkdir(parents=True, exist_ok=True)
                    
                    # 创建一个新的合并 channel XML
                    new_root = ET.Element("rss", attrib=root.attrib)
                    new_channel = ET.SubElement(new_root, "channel")
                    
                    # 复制 channel 的基本元数据
                    for child in channel:
                        if child.tag != "item":
                            new_channel.append(child)
                    
                    # 依次下载每个分卷的 feed.xml 并将其 item 合并进来
                    for i, vol_url in enumerate(vol_feed_urls, 1):
                        self.log(f"  └─ [{i}/{len(vol_feed_urls)}] 正在下载分卷 feed: {vol_url}")
                        v_bytes, _ = self.download_file(vol_url)
                        if v_bytes:
                            try:
                                v_root = ET.fromstring(v_bytes)
                                v_channel = v_root.find("channel")
                                if v_channel is not None:
                                    for v_item in v_channel.findall("item"):
                                        new_channel.append(v_item)
                            except Exception as e:
                                self.log(f"    [!] 解析分卷 feed 失败: {e}")
                    
                    # 生成合并后的完整 XML 字节流
                    xml_bytes = ET.tostring(new_root, encoding="utf-8", xml_declaration=True)
        except Exception as e:
            self.log(f"  [!] 检查卷列表时发生异常（按常规处理）: {e}")

        # 解析书名
        book_title = get_novel_title_from_xml_content(xml_bytes)
        self.log(f"📖 识别到书名: {book_title}")

        # 确定缓存路径
        novel_cache_dir = CACHE_BASE_DIR / book_title
        novel_cache_dir.mkdir(parents=True, exist_ok=True)

        cached_xml_path = novel_cache_dir / "feed.xml"
        cached_xml_path.write_bytes(xml_bytes)
        self.log(f"💾 XML 已缓存至: {cached_xml_path.relative_to(BASE_DIR)}")

        return cached_xml_path, novel_cache_dir, book_title

    def export(self, source_input, output_dir=None, download_images=True):
        """
        核心导出逻辑
        :param source_input: 网络 URL 或本地 XML 文件路径
        :param output_dir: 自定义 EPUB 导出文件夹（可选，默认导出到 BASE_DIR）
        :param download_images: 是否下载并缓存插图
        :return: 生成的 EPUB 文件 Path 对象或列表
        """
        source_input = str(source_input).strip()
        xml_bytes = None

        # 1. 优先获取根 XML 判断是否为卷列表
        if source_input.startswith("http://") or source_input.startswith("https://"):
            self.log(f"🌐 正在从链接获取 XML: {source_input}")
            xml_bytes, _ = self.download_file(source_input)
            if not xml_bytes:
                raise Exception("无法从提供的网络链接获取 XML 内容")
        else:
            local_path = Path(source_input)
            if not local_path.exists():
                raise Exception(f"未找到本地 XML 文件: {local_path}")
            self.log(f"📂 正在读取本地文件: {local_path}")
            xml_bytes = local_path.read_bytes()

        # 检查是否为卷列表
        vol_feed_urls = []
        try:
            root = ET.fromstring(xml_bytes)
            channel = root.find("channel")
            if channel is not None:
                for item in channel.findall("item"):
                    link = item.findtext("link", "").strip()
                    if not link:
                        guid = item.findtext("guid", "").strip()
                        if guid and guid.startswith("http"):
                            link = guid
                    
                    encoded = item.findtext("encoded", "")
                    if not encoded:
                        encoded = item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded", "")
                    
                    m_rss = re.search(r'href="([^"]+?/feed\.xml)"', encoded)
                    if m_rss:
                        vol_feed_urls.append(m_rss.group(1))
                    elif link:
                        converted = convert_source_url(link)
                        if converted and converted.endswith("/feed.xml"):
                            vol_feed_urls.append(converted)
        except Exception as e:
            self.log(f"  [!] 解析 XML 检查卷列表异常: {e}")

        # 如果检测到了多个卷的 feed 链接，说明是卷列表，则依次为每个分卷单独创建文件夹、下载 XML 并调用 export_novel 导出
        if len(vol_feed_urls) > 1:
            self.log(f"📚 检测到 XML 是卷列表，包含 {len(vol_feed_urls)} 个分卷，将依次下载并独立导出...")
            exported_files = []
            for i, vol_url in enumerate(vol_feed_urls, 1):
                self.log(f"\n--- 处理第 {i}/{len(vol_feed_urls)} 个分卷: {vol_url} ---")
                try:
                    out_file = export_novel(
                        source_input=vol_url,
                        output_dir=output_dir,
                        download_images=download_images,
                        log_callback=self.log_callback
                    )
                    if out_file:
                        exported_files.append(out_file)
                except Exception as e:
                    self.log(f"  [!] 导出分卷失败 ({vol_url}): {e}")
            return exported_files

        # 否则按单本书常规逻辑导出
        cached_xml_path, novel_dir, book_title = self.prepare_xml_source(source_input)

        images_dir = novel_dir / "images"
        images_json_path = novel_dir / "images.json"

        # 2. 读取/初始化 images.json 缓存映射
        image_mapping = {}
        if images_json_path.exists():
            try:
                image_mapping = json.loads(
                    images_json_path.read_text(encoding="utf-8")
                )
            except Exception:
                image_mapping = {}

        # 3. 解析 XML 内容
        tree = ET.parse(cached_xml_path)
        root = tree.getroot()
        channel = root.find("channel")

        if channel is None:
            raise Exception("XML 缺少有效的 channel 节点")

        book_author = "未知作者"
        book_intro = channel.findtext("description", "").strip()

        # 初始化 EPUB
        book = epub.EpubBook()
        book.set_identifier(f"inovel-{hash(book_title)}")
        book.set_title(book_title)
        book.set_language("zh")

        # 尝试设置封面
        cover_url = ""
        image_node = channel.find("image")
        if image_node is not None:
            cover_url = image_node.findtext("url", "").strip()

        # 提取作者
        first_item = channel.find("item")
        if first_item is not None and first_item.findtext("author"):
            book_author = first_item.findtext("author").strip()
        book.add_author(book_author)

        # 样式定义
        style = """
        @namespace xhtml "http://www.w3.org/1999/xhtml";
        body { font-family: sans-serif, "PingFang SC", "Microsoft YaHei"; line-height: 1.6; padding: 0 5%; }
        h1, h2 { text-align: center; font-weight: bold; margin-top: 1.5em; margin-bottom: 1em; }
        p { text-indent: 2em; margin-top: 0.5em; margin-bottom: 0.5em; }
        .img-container { text-align: center; margin: 1em 0; }
        img { max-width: 100%; height: auto; }
        """
        default_css = epub.EpubItem(
            uid="style_nav",
            file_name="style/nav.css",
            media_type="text/css",
            content=style,
        )
        book.add_item(default_css)

        # 处理封面下载与缓存
        if cover_url and download_images:
            if cover_url not in image_mapping:
                images_dir.mkdir(parents=True, exist_ok=True)
                img_bytes, mime_type = self.download_file(cover_url)
                if img_bytes:
                    ext = mime_type.split("/")[-1] if mime_type else "jpg"
                    img_name = f"cover.{ext}"
                    local_img_path = images_dir / img_name
                    local_img_path.write_bytes(img_bytes)

                    rel_path = str(local_img_path.relative_to(novel_dir))
                    image_mapping[cover_url] = rel_path

            if cover_url in image_mapping:
                cover_local_full = novel_dir / image_mapping[cover_url]
                if cover_local_full.exists():
                    book.set_cover(
                        cover_local_full.name, cover_local_full.read_bytes()
                    )

        # 遍历处理章节
        items = channel.findall("item")
        epub_chapters = []
        epub_img_cache = {}  # 防止往 epub 里重复插入图片文件资源

        self.log(
            f"\n📚 开始处理 {len(items)} 个章节 (下载插图: {'是' if download_images else '否'})..."
        )

        for idx, item in enumerate(items, start=1):
            ch_title = item.findtext("title", f"第 {idx} 章").strip()
            raw_html = item.findtext("encoded", "")
            if not raw_html:
                raw_html = item.findtext(
                    "{http://purl.org/rss/1.0/modules/content/}encoded", ""
                )

            soup = BeautifulSoup(raw_html, "html.parser")

            # 处理文章内部插图
            for img in soup.find_all("img"):
                img_src = img.get("src")
                if not img_src:
                    continue

                if download_images:
                    images_dir.mkdir(parents=True, exist_ok=True)

                    # 1. 检查本地磁盘/JSON缓存
                    if img_src not in image_mapping or not (
                        novel_dir / image_mapping[img_src]
                    ).exists():
                        self.log(
                            f"  └─ 下载插图 [{idx}/{len(items)}]: {img_src}"
                        )
                        img_bytes, mime_type = self.download_file(img_src)
                        if img_bytes:
                            ext = (
                                mime_type.split("/")[-1] if mime_type else "jpg"
                            )
                            # 生成新文件名
                            img_filename = (
                                f"img_{len(image_mapping) + 1:03d}.{ext}"
                            )
                            local_path = images_dir / img_filename
                            local_path.write_bytes(img_bytes)

                            # 更新 mapping
                            rel_path = str(local_path.relative_to(novel_dir))
                            image_mapping[img_src] = rel_path
                            images_json_path.write_text(
                                json.dumps(
                                    image_mapping, indent=2, ensure_ascii=False
                                ),
                                encoding="utf-8",
                            )

                    # 2. 嵌入 EPUB 包内部
                    if img_src in image_mapping:
                        rel_img_path = image_mapping[img_src]
                        full_img_path = novel_dir / rel_img_path

                        if full_img_path.exists():
                            epub_img_filename = (
                                f"images/{full_img_path.name}"
                            )

                            if epub_img_filename not in epub_img_cache:
                                ext = full_img_path.suffix.lstrip(".")
                                mime = (
                                    f"image/{ext}" if ext != "jpg" else "image/jpeg"
                                )
                                epub_img = epub.EpubItem(
                                    uid=f"img_{len(epub_img_cache) + 1}",
                                    file_name=epub_img_filename,
                                    media_type=mime,
                                    content=full_img_path.read_bytes(),
                                )
                                book.add_item(epub_img)
                                epub_img_cache[epub_img_filename] = True

                            # 修改 HTML 内的引用路径
                            img["src"] = epub_img_filename

                # 为图片包一层居中 div
                wrapper = soup.new_tag("div", **{"class": "img-container"})
                img.wrap(wrapper)

            # 保存更新后的 json
            if download_images:
                images_json_path.write_text(
                    json.dumps(image_mapping, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )

            # 生成章节页面
            ch_filename = f"chap_{idx:03d}.xhtml"
            chapter_item = epub.EpubHtml(
                title=ch_title, file_name=ch_filename, lang="zh"
            )
            chapter_item.content = f"""
            <html>
            <head>
                <title>{ch_title}</title>
                <link rel="stylesheet" href="style/nav.css" type="text/css" />
            </head>
            <body>
                <h2>{ch_title}</h2>
                {str(soup)}
            </body>
            </html>
            """
            chapter_item.add_item(default_css)
            book.add_item(chapter_item)
            epub_chapters.append(chapter_item)

            self.log(f"  ✓ 章节完毕: {ch_title}")

        # 挂载目录结构
        book.toc = tuple(epub_chapters)
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ["nav"] + epub_chapters

        # 设置导出文件夹
        if output_dir:
            export_directory = Path(output_dir)
        else:
            export_directory = BASE_DIR

        export_directory.mkdir(parents=True, exist_ok=True)

        out_name = f"{book_title}.epub"
        out_path = export_directory / out_name

        self.log(f"\n💾 正在生成 EPUB 文件: {out_path.name}")
        epub.write_epub(out_path, book, {})
        self.log(f"✨ 导出成功！保存位置: {out_path.resolve()}\n")

        return out_path


def export_novel(source_input, output_dir=None, download_images=True, log_callback=None):
    """
    直接调用的快捷函数，无需 Tkinter 界面。
    
    示例:
    >>> from ziNovel import export_novel
    >>> export_novel("https://example.com/feed.xml", output_dir="./output")
    """
    exporter = NovelEpubExporter(log_callback=log_callback)
    return exporter.export(
        source_input=source_input,
        output_dir=output_dir,
        download_images=download_images,
    )


class AppGUI:

    def __init__(self, root):
        import tkinter as tk
        from tkinter import ttk

        self.root = root
        self.root.title("轻小说 XML 转 EPUB 工具")
        self.root.geometry("750x620")

        # 界面控件变量
        self.source_var = tk.StringVar(value="feed.xml")
        self.output_dir_var = tk.StringVar(value=str(OUTPUTDIR))
        self.download_img_var = tk.BooleanVar(value=True)
        self.search_var = tk.StringVar()
        self.cached_novels_data = []

        self._build_ui()
        self._refresh_library()

    def _build_ui(self):
        import tkinter as tk
        from tkinter import ttk

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(10, 5))

        # 选项卡 1：转换导出
        tab_convert = ttk.Frame(self.notebook)
        self.notebook.add(tab_convert, text=" 转换导出 ")

        # 选项卡 2：本地书库
        tab_library = ttk.Frame(self.notebook)
        self.notebook.add(tab_library, text=" 本地书库 ")

        # --- Tab 1 内容：源与导出设置 ---
        frame_top = ttk.LabelFrame(tab_convert, text="源 XML 设置", padding=10)
        frame_top.pack(fill="x", padx=5, pady=5)

        lbl_tip = ttk.Label(
            frame_top, text="请输入 XML 的网络 URL 或选择本地 feed.xml 文件："
        )
        lbl_tip.pack(anchor="w", pady=(0, 5))

        frame_input = ttk.Frame(frame_top)
        frame_input.pack(fill="x")

        entry_source = ttk.Entry(
            frame_input, textvariable=self.source_var, font=("Consolas", 10)
        )
        entry_source.pack(side="left", fill="x", expand=True, padx=(0, 5))

        btn_browse = ttk.Button(
            frame_input, text="浏览...", command=self._browse_source_file
        )
        btn_browse.pack(side="right")

        # 导出路径设置
        frame_export = ttk.LabelFrame(tab_convert, text="导出设置", padding=10)
        frame_export.pack(fill="x", padx=5, pady=5)

        lbl_out_tip = ttk.Label(frame_export, text="设置 EPUB 导出目标文件夹：")
        lbl_out_tip.pack(anchor="w", pady=(0, 5))

        frame_out_input = ttk.Frame(frame_export)
        frame_out_input.pack(fill="x")

        entry_out_dir = ttk.Entry(
            frame_out_input,
            textvariable=self.output_dir_var,
            font=("Consolas", 10),
        )
        entry_out_dir.pack(side="left", fill="x", expand=True, padx=(0, 5))

        btn_browse_dir = ttk.Button(
            frame_out_input, text="选择文件夹...", command=self._browse_output_dir
        )
        btn_browse_dir.pack(side="right")

        # 选项
        frame_opts = ttk.Frame(tab_convert, padding=(5, 5))
        frame_opts.pack(fill="x")

        chk_img = ttk.Checkbutton(
            frame_opts,
            text="下载并缓存插图 (创建/更新 images.json 映射)",
            variable=self.download_img_var,
        )
        chk_img.pack(side="left")

        btn_start = ttk.Button(
            frame_opts, text="开始转换", command=self._start_process
        )
        btn_start.pack(side="right")

        # --- Tab 2 内容：本地书库查询 ---
        frame_search = ttk.Frame(tab_library, padding=5)
        frame_search.pack(fill="x")

        ttk.Label(frame_search, text="搜索书名: ").pack(side="left")
        entry_search = ttk.Entry(
            frame_search, textvariable=self.search_var, font=("Consolas", 10)
        )
        entry_search.pack(side="left", fill="x", expand=True, padx=5)
        self.search_var.trace_add("write", lambda *args: self._filter_library())

        btn_refresh = ttk.Button(
            frame_search, text="刷新书库", command=self._refresh_library
        )
        btn_refresh.pack(side="right")

        # 书籍列表展示
        frame_tree = ttk.Frame(tab_library, padding=5)
        frame_tree.pack(fill="both", expand=True)

        columns = ("title", "mtime", "xml_path")
        self.tree_library = ttk.Treeview(
            frame_tree, columns=columns, show="headings", selectmode="browse"
        )
        self.tree_library.heading("title", text="书名")
        self.tree_library.heading("mtime", text="缓存时间")
        self.tree_library.heading("xml_path", text="缓存 XML 相对路径")

        self.tree_library.column("title", width=200, anchor="w")
        self.tree_library.column("mtime", width=140, anchor="center")
        self.tree_library.column("xml_path", width=320, anchor="w")

        scroll_y = ttk.Scrollbar(
            frame_tree, orient="vertical", command=self.tree_library.yview
        )
        self.tree_library.configure(yscrollcommand=scroll_y.set)

        self.tree_library.pack(side="left", fill="both", expand=True)
        scroll_y.pack(side="right", fill="y")

        # 书库操作按纽
        frame_lib_actions = ttk.Frame(tab_library, padding=5)
        frame_lib_actions.pack(fill="x")

        btn_select_as_source = ttk.Button(
            frame_lib_actions,
            text="载入并切至转换页",
            command=self._use_selected_as_source,
        )
        btn_select_as_source.pack(side="left", padx=(0, 5))

        btn_direct_export = ttk.Button(
            frame_lib_actions, text="直接导出选中书籍", command=self._export_selected
        )
        btn_direct_export.pack(side="left", padx=(0, 5))

        btn_open_folder = ttk.Button(
            frame_lib_actions, text="打开缓存文件夹", command=self._open_cache_folder
        )
        btn_open_folder.pack(side="right")

        # 底部公共运行日志输出区域
        frame_log = ttk.LabelFrame(self.root, text="运行日志", padding=10)
        frame_log.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.txt_log = tk.Text(frame_log, wrap="word", font=("Consolas", 9), height=8)
        self.txt_log.pack(fill="both", expand=True)

    def _refresh_library(self):
        """刷新本地缓存书库列表"""
        self.cached_novels_data = get_cached_novels()
        self._filter_library()

    def _filter_library(self):
        """根据输入的关键词过滤书库列表"""
        for item in self.tree_library.get_children():
            self.tree_library.delete(item)

        query = self.search_var.get().strip().lower()
        for book in self.cached_novels_data:
            if not query or query in book["title"].lower():
                self.tree_library.insert(
                    "",
                    "end",
                    values=(book["title"], book["mtime"], book["xml_path"]),
                )

    def _get_selected_novel_path(self):
        """获取 Treeview 中选中的书籍 XML 路径"""
        import tkinter.messagebox as messagebox

        selected_item = self.tree_library.selection()
        if not selected_item:
            messagebox.showwarning("提示", "请先在书库列表中选择一本书籍！")
            return None
        values = self.tree_library.item(selected_item[0], "values")
        return values[2] if len(values) >= 3 else None

    def _use_selected_as_source(self):
        """将选中的书籍 XML 设置为源并切换到转换面板"""
        xml_path = self._get_selected_novel_path()
        if xml_path:
            self.source_var.set(xml_path)
            self.notebook.select(0)

    def _export_selected(self):
        """直接导出选中的书籍为 EPUB"""
        xml_path = self._get_selected_novel_path()
        if xml_path:
            self.source_var.set(xml_path)
            self._start_process()

    def _open_cache_folder(self):
        """打开选中书籍的本地缓存文件夹"""
        import os
        import subprocess
        import sys
        import tkinter.messagebox as messagebox

        selected_item = self.tree_library.selection()
        if not selected_item:
            target_dir = CACHE_BASE_DIR
        else:
            xml_path = self.tree_library.item(selected_item[0], "values")[2]
            target_dir = Path(xml_path).parent

        if not target_dir.exists():
            target_dir.mkdir(parents=True, exist_ok=True)

        try:
            if sys.platform == "win32":
                os.startfile(target_dir)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(target_dir)])
            else:
                subprocess.Popen(["xdg-open", str(target_dir)])
        except Exception as e:
            messagebox.showerror("错误", f"无法打开文件夹: {e}")

    def _browse_source_file(self):
        from tkinter import filedialog

        file_path = filedialog.askopenfilename(
            filetypes=[("XML 文件", "*.xml"), ("所有文件", "*.*")]
        )
        if file_path:
            self.source_var.set(file_path)

    def _browse_output_dir(self):
        from tkinter import filedialog

        dir_path = filedialog.askdirectory()
        if dir_path:
            self.output_dir_var.set(dir_path)

    def log_to_ui(self, message):
        import tkinter as tk

        self.txt_log.insert(tk.END, message + "\n")
        self.txt_log.see(tk.END)
        self.root.update_idletasks()

    def _start_process(self):
        import tkinter as tk
        from tkinter import messagebox

        source = self.source_var.get().strip()
        out_dir = self.output_dir_var.get().strip()

        if not source:
            messagebox.showwarning("提示", "请输入 URL 链接或选择 XML 文件！")
            return

        self.txt_log.delete("1.0", tk.END)
        exporter = NovelEpubExporter(log_callback=self.log_to_ui)

        try:
            exported_file = exporter.export(
                source_input=source,
                output_dir=out_dir if out_dir else None,
                download_images=self.download_img_var.get(),
            )
            messagebox.showinfo("完成", f"EPUB 转换成功！\n保存至: {exported_file}")
        except Exception as e:
            self.log_to_ui(f"\n❌ 发生错误: {e}")
            messagebox.showerror("错误", f"转换失败:\n{e}")


def launch_gui():
    """启动图形界面"""
    import tkinter as tk

    root = tk.Tk()
    app = AppGUI(root)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()