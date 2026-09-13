import os
import json
import re
from ebooklib import epub

def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", name)

def generate_epub_for_book(book_id: str, output_dir: str = None, selected_volumes: list = None, chapter_sort: str = "default"):
    """
    提供对对应 bookid 自动合成可选章节或者部分章节的 epub 文件，
    支持排序章节，自动寻找对应插图，确保不把链接当插图。
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    server_cache_dir = os.path.join(current_dir, "servercache", "lk")
    book_dir = os.path.join(server_cache_dir, "books", str(book_id))

    if not os.path.exists(book_dir):
        raise FileNotFoundError(f"未找到 book_id [{book_id}] 的缓存目录")

    if not output_dir:
        output_dir = os.path.join(current_dir, "Novels2")
    os.makedirs(output_dir, exist_ok=True)

    metadata_path = os.path.join(book_dir, "metadata.json")
    meta = {}
    if os.path.exists(metadata_path):
        with open(metadata_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

    book_title = meta.get("title", f"Book_{book_id}")
    author = meta.get("author", "未知")

    catalog_path = os.path.join(book_dir, "catalog.json")
    if not os.path.exists(catalog_path):
        raise FileNotFoundError(f"未找到 book_id [{book_id}] 的目录文件 catalog.json")

    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    volumes = catalog.get("volumes", [])
    custom_sort = catalog.get("custom_sort", [])

    generated_epubs = []
    img_mapped_dir = os.path.join(book_dir, "images_mapped")

    for vol_idx, vol in enumerate(volumes):
        vol_title = vol.get("vol_title", f"第{vol_idx+1}卷")
        if selected_volumes and vol_title not in selected_volumes and vol.get("vol_id") not in selected_volumes:
            continue

        chapters = vol.get("chapters", [])
        if not chapters:
            continue

        if chapter_sort == "reverse":
            chapters = list(reversed(chapters))
        elif chapter_sort == "custom" and custom_sort:
            pass

        book = epub.EpubBook()
        book.set_identifier(f"lk-{book_id}-v{vol_idx+1}")
        book.set_title(f"{book_title} - {vol_title}")
        book.set_language("zh")
        book.add_author(author)

        cover_files = [f for f in os.listdir(img_mapped_dir) if f.startswith("cover_")] if os.path.exists(img_mapped_dir) else []
        if cover_files:
            cover_path = os.path.join(img_mapped_dir, cover_files[0])
            with open(cover_path, "rb") as f:
                cover_data = f.read()
            ext = os.path.splitext(cover_files[0])[1] or ".jpg"
            book.set_cover(f"cover{ext}", cover_data)

        epub_chapters = []
        vol_dir = os.path.join(book_dir, sanitize_filename(vol_title))

        for ch_idx, ch in enumerate(chapters):
            ch_title = ch.get("title", f"章节{ch_idx+1}")
            ch_json_filename = f"{sanitize_filename(ch_title)}.json"
            ch_json_path = os.path.join(vol_dir, ch_json_filename)

            text_htmls = []
            image_htmls = []
            ch_images = []

            if os.path.exists(ch_json_path):
                try:
                    with open(ch_json_path, "r", encoding="utf-8") as f:
                        ch_data = json.load(f)
                        items = ch_data.get("paragraphs", [])
                        for item in items:
                            if item.get("type") == "text":
                                text_htmls.append(f'<p class="ln-paragraph" style="text-indent:2em;">{item.get("content", "")}</p>')
                            elif item.get("type") == "image":
                                img_filename = item.get("file")
                                if img_filename:
                                    img_full_path = os.path.join(img_mapped_dir, img_filename)
                                    if os.path.exists(img_full_path) and os.path.getsize(img_full_path) > 0:
                                        ch_images.append((img_filename, img_full_path))
                                        image_htmls.append(f'<p style="text-align:center; margin: 15px 0;"><img src="images/{img_filename}" style="max-width:100%;height:auto;"/></p>')
                except Exception:
                    pass

            # 将插图重新排布在各章节之首，文本排在插图之后
            paragraphs_html = image_htmls + text_htmls
            if not paragraphs_html:
                paragraphs_html.append(f'<p>暂无内容或未爬取</p>')

            c_item = epub.EpubHtml(
                title=ch_title,
                file_name=f"chap_{ch_idx+1}.xhtml",
                lang="zh"
            )
            c_item.content = f"<h2>{ch_title}</h2>\n" + "\n".join(paragraphs_html)
            book.add_item(c_item)
            epub_chapters.append(c_item)

            for img_filename, img_full_path in ch_images:
                try:
                    with open(img_full_path, "rb") as f:
                        img_bytes = f.read()
                    media_type = "image/jpeg"
                    if img_filename.endswith(".png"):
                        media_type = "image/png"
                    elif img_filename.endswith(".webp"):
                        media_type = "image/webp"
                    elif img_filename.endswith(".gif"):
                        media_type = "image/gif"
                    
                    img_item = epub.EpubItem(
                        uid=re.sub(r'[^a-zA-Z0-9_\-]', '_', f"img_{img_filename}"),
                        file_name=f"images/{img_filename}",
                        media_type=media_type,
                        content=img_bytes
                    )
                    book.add_item(img_item)
                except Exception:
                    pass

        book.toc = tuple(epub_chapters)
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ["nav"] + epub_chapters

        out_name = f"{sanitize_filename(book_title)} - {sanitize_filename(vol_title)}.epub"
        out_path = os.path.join(output_dir, out_name)
        epub.write_epub(out_path, book)
        generated_epubs.append(out_path)

    return generated_epubs
