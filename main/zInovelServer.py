import os
import re
import json
import threading
from pathlib import Path
from flask import Blueprint, request, jsonify, send_from_directory
from ziNovel import get_cached_novels, export_novel, CACHE_BASE_DIR, BASE_DIR,OUTPUTDIR,convert_source_url,truncate_string,sanitize_path
import zBarkCustom

inovel_bp = Blueprint("inovel_server", __name__, url_prefix="/inovelapi")

# 全局任务状态或线程锁（防止并发导出冲突）
inovel_lock = threading.Lock()
inovel_current_task = {
    "book_title": None,
    "status": "idle",
    "message": ""
}

@inovel_bp.route("/status", methods=["GET"])
def get_inovel_status():
    """获取当前 inovel 后台异步导出任务状态"""
    with inovel_lock:
        return jsonify({
            "status": "ok",
            "task": inovel_current_task
        })

@inovel_bp.route("/servercache/<path:filepath>", methods=["GET"])
def serve_inovel_servercache(filepath):
    """直接提供 servercache/inovel 下文件静态访问（支持封面、插图等）"""
    return send_from_directory(CACHE_BASE_DIR, filepath)

def format_size(size_bytes):
    """格式化文件大小为友好的带单位字符串"""
    try:
        size_bytes = int(size_bytes)
    except Exception:
        return "0 B"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"

@inovel_bp.route("/books", methods=["GET"])
def list_inovel_books():
    """获取所有已缓存的书籍列表（带分页、封面、插图列表、XML大小等）"""
    raw_novels = get_cached_novels()
    
    # 获取分页参数
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 10))
    except ValueError:
        page = 1
        page_size = 10

    if page < 1: page = 1
    if page_size < 1: page_size = 10

    total_count = len(raw_novels)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    
    paginated_novels = raw_novels[start_idx:end_idx]
    result = []

    for item in paginated_novels:
        folder_path = Path(item["folder_path"])
        book_title = item["title"]
        
        # 查找封面
        local_cover = ""
        images_dir = folder_path / "images"
        images_json_path = folder_path / "images.json"
        xml_path_file = folder_path / "feed.xml"
        
        # 计算 feed.xml 文件大小
        xml_size_bytes = 0
        if xml_path_file.exists():
            try:
                xml_size_bytes = xml_path_file.stat().st_size
            except Exception:
                xml_size_bytes = 0

        image_mapping = {}
        if images_json_path.exists():
            try:
                image_mapping = json.loads(images_json_path.read_text(encoding="utf-8"))
            except Exception:
                image_mapping = {}

        # 收集所有插图列表
        images_list = []
        if images_dir.exists():
            for img_file in sorted(images_dir.iterdir()):
                if img_file.is_file():
                    rel_img_path = f"{book_title}/images/{img_file.name}"
                    images_list.append({
                        "filename": img_file.name,
                        "url": f"/inovelapi/servercache/{rel_img_path}"
                    })
                    if img_file.name.startswith("cover.") and not local_cover:
                        local_cover = f"/inovelapi/servercache/{rel_img_path}"

        # 如果没有找到 cover.*，看看 image_mapping 里有没有
        if not local_cover:
            for k, v in image_mapping.items():
                if "cover" in k.lower() or "cover" in v.lower():
                    local_cover = f"/inovelapi/servercache/{book_title}/{v}"
                    break

        # 检查是否已经导出过 EPUB
        epub_path = OUTPUTDIR / f"{book_title}.epub"
        has_epub = epub_path.exists()
        epub_url = f"/inovelapi/epub/{book_title}.epub" if has_epub else ""

        result.append({
            "title": book_title,
            "mtime": item["mtime"],
            "xml_path": item["xml_path"],
            "xml_size_bytes": xml_size_bytes,
            "xml_size_formatted": format_size(xml_size_bytes),
            "local_cover": local_cover,
            "images": images_list,
            "has_epub": has_epub,
            "epub_url": epub_url,
            "image_count": len(images_list)
        })

    return jsonify({
        "status": "ok",
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": (total_count + page_size - 1) // page_size if page_size > 0 else 1,
        "books": result
    })

@inovel_bp.route("/book/delete", methods=["POST", "DELETE"])
def delete_inovel_book():
    """删除指定的书籍目录及所有缓存文件（通过书名/目录名）"""
    data = request.get_json(silent=True) or request.form.to_dict() or request.args.to_dict()
    title = data.get("title") or data.get("book_title")
    if not title:
        return jsonify({"status": "error", "message": "缺少要删除的书籍标题(title)"}), 400

    target_dir = CACHE_BASE_DIR / sanitize_path(title)
    if not target_dir.exists():
        # 尝试遍历查找匹配名称的文件夹
        found = False
        if CACHE_BASE_DIR.exists():
            for folder in CACHE_BASE_DIR.iterdir():
                if folder.is_dir() and folder.name.lower() == title.lower():
                    target_dir = folder
                    found = True
                    break
        if not found:
            return jsonify({"status": "error", "message": f"未找到该书籍的缓存目录: {title}"}), 404

    try:
        import shutil
        shutil.rmtree(target_dir)
        # 同时检查并删除对应的 epub 文件（若存在）
        epub_file = OUTPUTDIR / f"{title}.epub"
        if epub_file.exists():
            epub_file.unlink()
        return jsonify({"status": "ok", "message": f"书籍《{title}》及其缓存已成功删除"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"删除书籍目录失败: {e}"}), 500

@inovel_bp.route("/book/xml", methods=["GET"])
def get_inovel_book_xml():
    """查看/获取指定书籍的 feed.xml 内容或文件"""
    title = request.args.get("title")
    if not title:
        return jsonify({"status": "error", "message": "缺少书籍标题(title)参数"}), 400

    target_xml = CACHE_BASE_DIR / title / "feed.xml"
    if not target_xml.exists():
        return jsonify({"status": "error", "message": f"未找到该书的 feed.xml 文件"}), 404

    return send_from_directory(target_xml.parent, "feed.xml", mimetype="application/xml")

@inovel_bp.route("/book/images", methods=["GET"])
def get_inovel_book_images():
    """获取某本书的插图列表 API"""
    title = request.args.get("title")
    if not title:
        return jsonify({"status": "error", "message": "缺少书籍标题(title)参数"}), 400

    folder_path = CACHE_BASE_DIR / title
    images_dir = folder_path / "images"
    images_list = []

    if images_dir.exists():
        for img_file in sorted(images_dir.iterdir()):
            if img_file.is_file():
                rel_img_path = f"{title}/images/{img_file.name}"
                images_list.append({
                    "filename": img_file.name,
                    "url": f"/inovelapi/servercache/{rel_img_path}"
                })

    return jsonify({"status": "ok", "title": title, "images": images_list, "count": len(images_list)})

@inovel_bp.route("/export", methods=["POST"])
def trigger_inovel_export():
    """下达下载/导出命令：通过 URL 或本地 XML 抓取/加载并生成 EPUB"""
    data = request.get_json(silent=True) or request.form.to_dict() or request.args.to_dict()
    raw_source = data.get("source")
    download_images = data.get("download_images", True)
    if isinstance(download_images, str):
        download_images = download_images.lower() in ("true", "1", "yes")

    if not raw_source:
        return jsonify({"status": "error", "message": "缺少 source 参数（XML URL 或本地文件路径）"}), 400

    source = convert_source_url(raw_source)

    with inovel_lock:
        if inovel_current_task["status"] == "running":
            return jsonify({"status": "warning", "message": "当前已有导出任务正在进行中，请稍候"})

        inovel_current_task["status"] = "running"
        inovel_current_task["message"] = f"正在处理源: {source}"
        inovel_current_task["book_title"] = None

    def background_export():
        logs = []
        def log_cb(msg):
            logs.append(msg)
            print(f"[ziNovel] {msg}")
            with inovel_lock:
                inovel_current_task["message"] = msg
        zBarkCustom.PerseusNotifyMsg("即将处理源：",str(truncate_string(source, head=2, tail=15)))
        try:
            out_path = export_novel(source_input=source, output_dir=OUTPUTDIR, download_images=download_images, log_callback=log_cb)
            with inovel_lock:
                inovel_current_task["status"] = "completed"
                inovel_current_task["message"] = f"导出成功: {out_path.name}"
        except Exception as e:
            print(f"[ziNovel Error] {e}")
            with inovel_lock:
                inovel_current_task["status"] = "error"
                inovel_current_task["message"] = str(e)

    threading.Thread(target=background_export, daemon=True).start()
    return jsonify({"status": "ok", "message": "后台已成功接收导出任务并开始执行"})

@inovel_bp.route("/epub/<path:filename>", methods=["GET"])
def download_inovel_epub(filename):
    """下载生成的 EPUB 文件"""
    return send_from_directory(OUTPUTDIR, filename, as_attachment=True)
