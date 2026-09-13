import os
import json
from flask import Blueprint, request, jsonify, send_from_directory
from zLKapi import lk_api

lk_bp = Blueprint("lk_server", __name__, url_prefix="/lkapi")

@lk_bp.route("/status", methods=["GET"])
def get_status():
    return jsonify({
        "status": "ok",
        "browser": lk_api.get_bro_status(),
        "tasks": lk_api.get_task_list()
    })

@lk_bp.route("/servercache/<path:filepath>", methods=["GET"])
def serve_lk_servercache(filepath):
    """直接提供 servercache/lk 下文件静态访问，支持前端直接渲染本地缓存封面与插图"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    cache_base = os.path.join(current_dir, "servercache", "lk")
    return send_from_directory(cache_base, filepath)

@lk_bp.route("/browser", methods=["POST"])
def manage_browser():
    data = request.get_json(silent=True) or request.form.to_dict() or request.args.to_dict()
    action = data.get("action", "start")
    headless = data.get("headless")
    if headless is not None:
        if isinstance(headless, str):
            headless = headless.lower() in ("true", "1", "yes")
        else:
            headless = bool(headless)

    status = lk_api.set_browser_state_sync(action, headless)
    return jsonify({"status": "ok", "browser": status})

@lk_bp.route("/tasks", methods=["GET"])
def list_tasks():
    return jsonify({
        "status": "ok",
        "tasks": lk_api.get_task_list()
    })

@lk_bp.route("/tasks/<task_id>", methods=["GET"])
def get_task_detail(task_id):
    task = lk_api.get_task(task_id)
    if not task:
        return jsonify({"status": "error", "message": "任务不存在"}), 404
    return jsonify({"status": "ok", "task": task})

@lk_bp.route("/tasks/<task_id>/cancel", methods=["POST"])
def cancel_task(task_id):
    success = lk_api.cancel_task(task_id)
    if success:
        return jsonify({"status": "ok", "message": "任务已中止"})
    return jsonify({"status": "error", "message": "无法中止任务或任务不存在"}), 400

@lk_bp.route("/bookshelf", methods=["POST", "GET"])
def bookshelf_action():
    data = request.get_json(silent=True) or request.form.to_dict() or request.args.to_dict()
    url = data.get("url", "https://www.lightnovel.fun/category/lightnovel")
    max_scrolls = int(data.get("max_scrolls", 50))
    
    task_id = lk_api.add_task_sync("bookshelf", {"url": url, "max_scrolls": max_scrolls})
    return jsonify({"status": "ok", "task_id": task_id, "message": "书架滚动抓取任务已创建"})

@lk_bp.route("/collect_current_page", methods=["POST", "GET"])
def collect_current_page_action():
    task_id = lk_api.add_task_sync("collect_current_page", {})
    return jsonify({"status": "ok", "task_id": task_id, "message": "爬取当前页面任务已创建"})

@lk_bp.route("/book/<book_id>/detail", methods=["GET", "POST"])
def get_book_detail(book_id):
    task_id = lk_api.add_task_sync("book_detail", {"book_id": book_id})
    return jsonify({"status": "ok", "task_id": task_id, "message": "书籍详情解析任务已创建"})

@lk_bp.route("/book/<book_id>/crawl", methods=["POST"])
def crawl_book(book_id):
    task_id = lk_api.add_task_sync("crawl_all", {"book_id": book_id})
    return jsonify({"status": "ok", "task_id": task_id, "message": "全书爬取任务已创建"})

@lk_bp.route("/book/<book_id>/crawl_selected", methods=["POST"])
def crawl_selected_chapters(book_id):
    data = request.get_json(silent=True) or {}
    chapter_urls = data.get("chapter_urls", [])
    task_id = lk_api.add_task_sync("crawl_selected", {"book_id": book_id, "chapter_urls": chapter_urls})
    return jsonify({"status": "ok", "task_id": task_id, "message": "选中章节爬取任务已创建"})

@lk_bp.route("/book/<book_id>/redownload_images", methods=["POST"])
def redownload_book_images(book_id):
    task_id = lk_api.add_task_sync("redownload_images", {"book_id": book_id})
    return jsonify({"status": "ok", "task_id": task_id, "message": "重新下载插图任务已创建"})

@lk_bp.route("/book/<book_id>/epub", methods=["POST"])
def make_epub(book_id):
    data = request.get_json(silent=True) or {}
    selected_vols = data.get("selected_volumes")
    chapter_sort = data.get("chapter_sort", "default")

    task_id = lk_api.add_task_sync("epub", {
        "book_id": book_id,
        "selected_volumes": selected_vols,
        "chapter_sort": chapter_sort
    })
    return jsonify({"status": "ok", "task_id": task_id, "message": "EPUB 打包任务已创建"})

@lk_bp.route("/bookshelf/data", methods=["GET"])
def get_bookshelf_data():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    shelf_path = os.path.join(current_dir, "servercache", "lk", "bookshelf", "bookshelf.json")
    if os.path.exists(shelf_path):
        with open(shelf_path, "r", encoding="utf-8") as f:
            return jsonify({"status": "ok", "books": json.load(f)})
    return jsonify({"status": "ok", "books": []})

@lk_bp.route("/books/all", methods=["GET"])
def get_all_cached_books():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    books_dir = os.path.join(current_dir, "servercache", "lk", "books")
    result = []

    if os.path.exists(books_dir):
        for b_id in os.listdir(books_dir):
            b_path = os.path.join(books_dir, b_id)
            if not os.path.isdir(b_path):
                continue
            meta_path = os.path.join(b_path, "metadata.json")
            cat_path = os.path.join(b_path, "catalog.json")

            title = f"Book_{b_id}"
            author = "未知"
            cover_url = ""
            local_cover = ""
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        m = json.load(f)
                        title = m.get("title", title)
                        author = m.get("author", author)
                        cover_url = m.get("cover_url", cover_url)
                        local_cover = m.get("local_cover", "")
                except Exception:
                    pass
            
            if not local_cover and os.path.exists(os.path.join(b_path, "images_mapped")):
                # 查找是否存在 cover_* 文件
                for fname in os.listdir(os.path.join(b_path, "images_mapped")):
                    if fname.startswith("cover_"):
                        local_cover = f"/servercache/lk/books/{b_id}/images_mapped/{fname}"
                        break

            catalog_status = "no_catalog"
            download_status = "none"
            total_chapters = 0
            downloaded_chapters = 0

            if os.path.exists(cat_path):
                catalog_status = "has_catalog"
                try:
                    with open(cat_path, "r", encoding="utf-8") as f:
                        cat = json.load(f)
                        vols = cat.get("volumes", [])
                        for v in vols:
                            for ch in v.get("chapters", []):
                                total_chapters += 1
                                if ch.get("downloaded"):
                                    downloaded_chapters += 1
                except Exception:
                    pass

                if total_chapters > 0:
                    if downloaded_chapters == total_chapters:
                        download_status = "downloaded_all"
                    elif downloaded_chapters > 0:
                        download_status = "downloading"
                    else:
                        download_status = "not_downloaded"

            result.append({
                "book_id": b_id,
                "title": title,
                "author": author,
                "cover_url": cover_url,
                "local_cover": local_cover,
                "catalog_status": catalog_status,
                "download_status": download_status,
                "total_chapters": total_chapters,
                "downloaded_chapters": downloaded_chapters
            })

    return jsonify({"status": "ok", "books": result})

@lk_bp.route("/book/<book_id>/catalog", methods=["GET"])
def get_book_catalog(book_id):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    cat_path = os.path.join(current_dir, "servercache", "lk", "books", str(book_id), "catalog.json")
    if os.path.exists(cat_path):
        with open(cat_path, "r", encoding="utf-8") as f:
            return jsonify({"status": "ok", "catalog": json.load(f)})
    return jsonify({"status": "error", "message": "目录不存在，请先获取书籍详情"}), 404

@lk_bp.route("/book/<book_id>/custom_sort", methods=["POST"])
def save_custom_sort(book_id):
    data = request.get_json(silent=True) or {}
    custom_sort = data.get("custom_sort", [])
    current_dir = os.path.dirname(os.path.abspath(__file__))
    cat_path = os.path.join(current_dir, "servercache", "lk", "books", str(book_id), "catalog.json")
    if os.path.exists(cat_path):
        with open(cat_path, "r", encoding="utf-8") as f:
            cat = json.load(f)
        cat["custom_sort"] = custom_sort
        with open(cat_path, "w", encoding="utf-8") as f:
            json.dump(cat, f, ensure_ascii=False, indent=2)
        return jsonify({"status": "ok", "message": "自定义排序已保存"})
    return jsonify({"status": "error", "message": "目录文件不存在"}), 404

@lk_bp.route("/book/<book_id>/images", methods=["GET"])
def get_book_images(book_id):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    img_dir = os.path.join(current_dir, "servercache", "lk", "books", str(book_id), "images_mapped")
    mapping_path = os.path.join(current_dir, "servercache", "lk", "books", str(book_id), "image_address_mapping.json")

    images = []
    mapping = {}
    if os.path.exists(mapping_path):
        try:
            with open(mapping_path, "r", encoding="utf-8") as f:
                mapping = json.load(f)
        except Exception:
            pass

    if os.path.exists(img_dir):
        for f in os.listdir(img_dir):
            if os.path.isfile(os.path.join(img_dir, f)):
                orig_url = ""
                for u, fname in mapping.items():
                    if fname == f:
                        orig_url = u
                        break
                images.append({
                    "filename": f,
                    "url": f"/servercache/lk/books/{book_id}/images_mapped/{f}",
                    "original_url": orig_url
                })
    return jsonify({"status": "ok", "images": images})

@lk_bp.route("/book/<book_id>/chapter_content", methods=["GET"])
def get_chapter_content(book_id):
    vol_name = request.args.get("vol")
    ch_title = request.args.get("ch")
    if not vol_name or not ch_title:
        return jsonify({"status": "error", "message": "缺少分卷或章节名称"}), 400

    from zLKbro import sanitize_filename
    current_dir = os.path.dirname(os.path.abspath(__file__))
    ch_json_path = os.path.join(
        current_dir, "servercache", "lk", "books", str(book_id),
        sanitize_filename(vol_name), f"{sanitize_filename(ch_title)}.json"
    )

    if os.path.exists(ch_json_path):
        with open(ch_json_path, "r", encoding="utf-8") as f:
            return jsonify({"status": "ok", "chapter": json.load(f)})
    return jsonify({"status": "error", "message": "章节内容尚未爬取"}), 404
