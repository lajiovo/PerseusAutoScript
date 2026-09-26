import os
import json
from flask import Blueprint, jsonify, send_from_directory

lk_cache_viewer_bp = Blueprint("lk_cache_viewer_server", __name__, url_prefix="/lkvapi")

# 定义 lk cache 基础路径v
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LK_CACHE_BASE = os.path.join(CURRENT_DIR, "lkcache")
WEBASSETS_DIR = os.path.join(CURRENT_DIR, "webassets")

@lk_cache_viewer_bp.route("/lkcache/images", methods=["GET"])
def get_all_lkcache_images():
    """获取所有缓存书籍及插图列表（兼容前端 lkcachceviewer.html 的全局遍历或直接调用）"""
    books_dir = os.path.join(LK_CACHE_BASE, "books")
    result_images = []
    
    if os.path.exists(books_dir):
        for b_id in os.listdir(books_dir):
            b_path = os.path.join(books_dir, b_id)
            if not os.path.isdir(b_path):
                continue
            
            # 读取书籍元数据
            meta_path = os.path.join(b_path, "metadata.json")
            title = f"Book_{b_id}"
            author = "未知"
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                        title = meta.get("title", title)
                        author = meta.get("author", author)
                except Exception:
                    pass
            
            # 扫描 images_mapped 目录下的所有插图
            img_dir = os.path.join(b_path, "images_mapped")
            mapping_path = os.path.join(b_path, "image_address_mapping.json")
            mapping = {}
            if os.path.exists(mapping_path):
                try:
                    with open(mapping_path, "r", encoding="utf-8") as f:
                        mapping = json.load(f)
                except Exception:
                    mapping = {}
            
            # 反向映射哈希/原文件名
            reverse_mapping = {v: k for k, v in mapping.items()}

            if os.path.exists(img_dir):
                for f_name in sorted(os.listdir(img_dir)):
                    f_path = os.path.join(img_dir, f_name)
                    if os.path.isfile(f_path):
                        orig_url = reverse_mapping.get(f_name, "")
                        result_images.append({
                            "book_id": b_id,
                            "book_title": title,
                            "author": author,
                            "filename": f_name,
                            "url": f"/lkvapi/servercache/books/{b_id}/images_mapped/{f_name}",
                            "original_url": orig_url
                        })

    return jsonify({"status": "ok", "images": result_images})

@lk_cache_viewer_bp.route("/servercache/<path:filepath>", methods=["GET"])
def serve_lk_cache_files(filepath):
    """提供 lk cache 文件夹内静态文件（如图片等）的访问服务"""
    return send_from_directory(LK_CACHE_BASE, filepath)

@lk_cache_viewer_bp.route("/viewer", methods=["GET"])
def serve_lk_cache_viewer_page():
    """直接渲染/访问 lkcacheviewer.html 页面"""
    return send_from_directory(WEBASSETS_DIR, "lkcacheviewer.html")
