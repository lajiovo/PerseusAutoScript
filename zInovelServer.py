import os
import re
import json
import threading
from pathlib import Path
from flask import Blueprint, request, jsonify, send_from_directory
from ziNovel import get_cached_novels, export_novel, CACHE_BASE_DIR, BASE_DIR,OUTPUTDIR,convert_source_url

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

@inovel_bp.route("/books", methods=["GET"])
def list_inovel_books():
    """获取所有已缓存的书籍列表（带封面、插图列表、XML路径等）"""
    raw_novels = get_cached_novels()
    result = []

    for item in raw_novels:
        folder_path = Path(item["folder_path"])
        book_title = item["title"]
        
        # 查找封面
        cover_url = ""
        local_cover = ""
        images_dir = folder_path / "images"
        images_json_path = folder_path / "images.json"
        
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
            "local_cover": local_cover,
            "images": images_list,
            "has_epub": has_epub,
            "epub_url": epub_url,
            "image_count": len(images_list)
        })

    return jsonify({"status": "ok", "books": result})

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
