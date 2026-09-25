import json
from pathlib import Path
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from ebooklib import epub
import requests

# 根目录与基础配置
BASE_DIR = Path(__file__).parent
CACHE_BASE_DIR = BASE_DIR / "servercache" / "inovel"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def sanitize_filename(name):
    """清理非法的标准文件名/目录名字符"""
    return re.sub(r'[\\/*?:"<>|]', "_", name).strip()


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
        if self.log_callback:
            self.log_callback(message)
        else:
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
        """
        source_input = source_input.strip()
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

    def export(self, source_input, download_images=True):
        # 1. 准备 XML 缓存与路径结构
        cached_xml_path, novel_dir, book_title = self.prepare_xml_source(
            source_input
        )

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

        # 导出 EPUB 到同目录
        out_name = f"{book_title}.epub"
        out_path = BASE_DIR / out_name
        self.log(f"\n💾 正在生成 EPUB 文件: {out_path.name}")
        epub.write_epub(out_path, book, {})
        self.log(f"✨ 导出成功！保存位置: {out_path.resolve()}\n")


# ==========================================
# Tkinter GUI 界面
# ==========================================
class AppGUI:

    def __init__(self, root):
        self.root = root
        self.root.title("轻小说 XML 转 EPUB 工具")
        self.root.geometry("680x520")

        # 界面控件变量
        self.source_var = tk.StringVar(value="feed.xml")
        self.download_img_var = tk.BooleanVar(value=True)

        self._build_ui()

    def _build_ui(self):
        frame_top = ttk.LabelFrame(self.root, text="源 XML 设置", padding=10)
        frame_top.pack(fill="x", padx=10, pady=5)

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
            frame_input, text="浏览...", command=self._browse_file
        )
        btn_browse.pack(side="right")

        # 选项
        frame_opts = ttk.Frame(self.root, padding=(10, 5))
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

        # 日志输出区域
        frame_log = ttk.LabelFrame(self.root, text="运行日志", padding=10)
        frame_log.pack(fill="both", expand=True, padx=10, pady=5)

        self.txt_log = tk.Text(frame_log, wrap="word", font=("Consolas", 9))
        self.txt_log.pack(fill="both", expand=True)

    def _browse_file(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("XML 文件", "*.xml"), ("所有文件", "*.*")]
        )
        if file_path:
            self.source_var.set(file_path)

    def log_to_ui(self, message):
        self.txt_log.insert(tk.END, message + "\n")
        self.txt_log.see(tk.END)
        self.root.update_idletasks()

    def _start_process(self):
        source = self.source_var.get().strip()
        if not source:
            messagebox.showwarning("提示", "请输入 URL 链接或选择 XML 文件！")
            return

        self.txt_log.delete("1.0", tk.END)
        exporter = NovelEpubExporter(log_callback=self.log_to_ui)

        try:
            exporter.export(
                source_input=source,
                download_images=self.download_img_var.get(),
            )
            messagebox.showinfo("完成", "EPUB 转换并导出成功！")
        except Exception as e:
            self.log_to_ui(f"\n❌ 发生错误: {e}")
            messagebox.showerror("错误", f"转换失败:\n{e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = AppGUI(root)
    root.mainloop()