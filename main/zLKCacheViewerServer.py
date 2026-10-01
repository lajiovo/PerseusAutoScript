import os
import json
from flask import Blueprint, jsonify, send_from_directory

lk_cache_viewer_bp = Blueprint("lk_cache_viewer_server", __name__, url_prefix="/lkvapi")

# 定义 lk cache 基础路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LK_CACHE_BASE = os.path.join(CURRENT_DIR, "lkcache")
WEBASSETS_DIR = os.path.join(CURRENT_DIR, "webassets")

@lk_cache_viewer_bp.route("/books/all", methods=["GET"])
def get_all_books():
    """获取所有缓存的书籍列表"""
    books = []
    if os.path.exists(LK_CACHE_BASE):
        for book_folder in sorted(os.listdir(LK_CACHE_BASE)):
            b_path = os.path.join(LK_CACHE_BASE, book_folder)
            if not os.path.isdir(b_path):
                continue
            title = book_folder
            author = "未知"
            b_id = book_folder
            meta_path = os.path.join(b_path, "metadata.json")
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                        title = meta.get("title", title)
                        author = meta.get("author", author)
                        if "book_id" in meta:
                            b_id = str(meta.get("book_id"))
                except Exception:
                    pass
            books.append({
                "book_id": b_id,
                "title": title,
                "author": author,
                "folder": book_folder
            })
    return jsonify({"status": "ok", "books": books})

@lk_cache_viewer_bp.route("/book/<book_id>/images", methods=["GET"])
def get_book_images(book_id):
    """获取指定 book_id（或文件夹名）的插图列表"""
    result_images = []
    if os.path.exists(LK_CACHE_BASE):
        book_folders = sorted(os.listdir(LK_CACHE_BASE))
        target_b_path = None
        title = book_id
        author = "未知"
        
        for book_folder in book_folders:
            b_path = os.path.join(LK_CACHE_BASE, book_folder)
            if not os.path.isdir(b_path):
                continue
            b_id = book_folder
            meta_path = os.path.join(b_path, "metadata.json")
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                        if "book_id" in meta and str(meta.get("book_id")) == str(book_id):
                            target_b_path = b_path
                            title = meta.get("title", book_folder)
                            author = meta.get("author", author)
                            break
                except Exception:
                    pass
            if book_folder == str(book_id):
                target_b_path = b_path
                title = book_folder
                break
                
        if not target_b_path:
            # 尝试模糊匹配目录名
            for book_folder in book_folders:
                if str(book_id) in book_folder:
                    target_b_path = os.path.join(LK_CACHE_BASE, book_folder)
                    title = book_folder
                    break
        
        if target_b_path and os.path.exists(target_b_path):
            for root, dirs, files in os.walk(target_b_path):
                if os.path.basename(root) == "images_mapped":
                    rel_dir_from_base = os.path.relpath(root, LK_CACHE_BASE).replace("\\", "/")
                    for f_name in sorted(files):
                        if f_name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif')):
                            f_path = os.path.join(root, f_name)
                            if os.path.isfile(f_path) and os.path.getsize(f_path) > 0:
                                file_rel_path = f"{rel_dir_from_base}/{f_name}"
                                result_images.append({
                                    "book_id": book_id,
                                    "book_title": title,
                                    "author": author,
                                    "filename": f_name,
                                    "url": f"/lkvapi/servercache/{file_rel_path}",
                                    "original_url": ""
                                })
                                
    return jsonify({"status": "ok", "images": result_images})

@lk_cache_viewer_bp.route("/lkcache/images", methods=["GET"])
def get_all_lkcache_images():
    """获取所有缓存书籍及插图列表（兼容前端 lkcachceviewer.html 的全局遍历或直接调用）"""
    result_images = []
    
    print(f"[LKCacheViewer] 开始扫描 lkcache 基础路径: {LK_CACHE_BASE}")
    if os.path.exists(LK_CACHE_BASE):
        book_folders = sorted(os.listdir(LK_CACHE_BASE))
        print(f"[LKCacheViewer] 发现 lkcache 下的顶层条目共 {len(book_folders)} 个: {book_folders}")
        # 遍历 lkcache 下的各个书籍文件夹
        for book_folder in book_folders:
            b_path = os.path.join(LK_CACHE_BASE, book_folder)
            if not os.path.isdir(b_path):
                print(f"[LKCacheViewer] 跳过非目录条目: {book_folder}")
                continue
            
            print(f"[LKCacheViewer] 正在递归扫描书籍目录: {book_folder} (绝对路径: {b_path})")
            
            # 书籍名称即为文件夹名
            title = book_folder
            author = "未知"
            b_id = book_folder
            
            # 读取书籍元数据 metadata.json（如果存在）
            meta_path = os.path.join(b_path, "metadata.json")
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                        title = meta.get("title", title)
                        author = meta.get("author", author)
                        if "book_id" in meta:
                            b_id = str(meta.get("book_id"))
                    print(f"[LKCacheViewer] 成功读取书籍元数据: title={title}, author={author}, book_id={b_id}")
                except Exception as e:
                    print(f"[LKCacheViewer] 读取书籍元数据失败 ({meta_path}): {e}")
            else:
                print(f"[LKCacheViewer] 书籍目录下未发现 metadata.json: {meta_path}")
            
            # 严格适应 lkcache/<book-name>/ 的真实层级（包含子目录/分卷/分章节），递归查找所有的 images_mapped 文件夹及插图
            found_image_paths = set()
            book_images_count = 0
            
            for root, dirs, files in os.walk(b_path):
                rel_root = os.path.relpath(root, b_path)
                if rel_root != ".":
                    print(f"[LKCacheViewer]   - 递归扫描子目录: {rel_root} (子目录数: {len(dirs)}, 文件数: {len(files)})")
                
                if os.path.basename(root) == "images_mapped":
                    rel_dir_from_base = os.path.relpath(root, LK_CACHE_BASE).replace("\\", "/")
                    print(f"[LKCacheViewer]   > 发现 images_mapped 文件夹: {root}, 相对路径: {rel_dir_from_base}")
                    valid_files_in_folder = 0
                    for f_name in sorted(files):
                        if f_name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif')):
                            f_path = os.path.join(root, f_name)
                            if os.path.isfile(f_path) and os.path.getsize(f_path) > 0:
                                if f_path not in found_image_paths:
                                    found_image_paths.add(f_path)
                                    book_images_count += 1
                                    file_rel_path = f"{rel_dir_from_base}/{f_name}"
                                    result_images.append({
                                        "book_id": b_id,
                                        "book_title": title,
                                        "author": author,
                                        "filename": f_name,
                                        "url": f"/lkvapi/servercache/{file_rel_path}",
                                        "original_url": ""
                                    })
                                    valid_files_in_folder += 1
                    print(f"[LKCacheViewer]   > images_mapped 文件夹中有效插图数量: {valid_files_in_folder}")
            
            print(f"[LKCacheViewer] 书籍 [{title}] (ID: {b_id}) 递归扫描完成，共找到有效插图: {book_images_count} 张")
    else:
        print(f"[LKCacheViewer] 错误: lkcache 基础路径不存在: {LK_CACHE_BASE}")

    print(f"[LKCacheViewer] 整个 lkcache 扫描结束，总计找到插图: {len(result_images)} 张")
    return jsonify({"status": "ok", "images": result_images})

@lk_cache_viewer_bp.route("/servercache/<path:filepath>", methods=["GET"])
def serve_lk_cache_files(filepath):
    """提供 lk cache 文件夹内静态文件（如图片等）的访问服务"""
    return send_from_directory(LK_CACHE_BASE, filepath)

@lk_cache_viewer_bp.route("/viewer", methods=["GET"])
def serve_lk_cache_viewer_page():
    """直接渲染/访问 lkcacheviewer.html 页面"""
    return send_from_directory(WEBASSETS_DIR, "lkcacheviewer.html")
