import os
import re
import tempfile
import logging
from ebooklib import epub
import patoolib
import docx  # 用于处理 .docx 文件

# 抑制 patool 的冗余提示
logging.getLogger('patool').setLevel(logging.ERROR)


def print_directory_tree(startpath):
    """
    打印解压后的目录树状结构
    """
    print(f"\n[TREE] 解压后的文件结构:")
    for root, dirs, files in os.walk(startpath):
        level = root.replace(startpath, '').count(os.sep)
        indent = '│   ' * (level)
        folder_name = os.path.basename(root) if os.path.basename(root) else "."
        print(f"{indent}├── 📁 {folder_name}/")
        sub_indent = '│   ' * (level + 1)
        for f in sorted(files):
            ext = os.path.splitext(f)[1].lower()
            if ext in ('.txt', '.docx'):
                icon = "📄"
            elif ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'):
                icon = "🖼️ "
            else:
                icon = "📎"
            print(f"{sub_indent}├── {icon} {f}")
    print()


def read_txt_content(txt_path):
    """
    尝试多种常见编码读取 TXT 内容，防止乱码
    """
    encodings = ['utf-8', 'gbk', 'gb2312', 'utf-16', 'big5']
    for enc in encodings:
        try:
            with open(txt_path, 'r', encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()


def read_docx_content(docx_path):
    """
    读取 DOCX 文件并将其内容转化为纯文本
    """
    try:
        doc = docx.Document(docx_path)
        full_text = []
        for para in doc.paragraphs:
            if para.text.strip():
                full_text.append(para.text.strip())
        return '\n\n'.join(full_text)
    except Exception as e:
        print(f"[WARNING] 读取 DOCX 文件失败 {os.path.basename(docx_path)}: {e}")
        return ""


def parse_text_to_chapters(content, default_title="正文"):
    """
    解析文本内容，按“第XX章”等关键字分割章节
    """
    if not content.strip():
        return [(default_title, "（本章内容为空）")]

    chapter_pattern = re.compile(
        r'^(?:\s*|\n*)(第[0-9一二三四五六七八九十百千万]+[章卷节部].*|Chapter\s+[0-9]+.*)$',
        re.MULTILINE
    )

    matches = list(chapter_pattern.finditer(content))
    chapters = []

    if not matches:
        chapters.append((default_title, content))
        return chapters

    if matches[0].start() > 0:
        preface = content[:matches[0].start()].strip()
        if preface:
            chapters.append((f"{default_title} - 前言", preface))

    for i, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[start:end].strip()
        chapters.append((title, body))

    return chapters


def rar_to_epub(rar_path, output_epub_path):
    """
    深度递归解压 RAR 并处理所有子文件夹中的图片、TXT 和 DOCX 文件
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"[INFO] 正在处理: {os.path.basename(rar_path)}...")
        
        try:
            patoolib.extract_archive(rar_path, outdir=temp_dir, verbosity=-1)
        except Exception as e:
            print(f"[ERROR] 解压失败 {os.path.basename(rar_path)}: {e}")
            return

        # 打印文件结构树
        print_directory_tree(temp_dir)

        text_files = []  # 存 txt 和 docx 文件
        image_files = []
        image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')

        # 遍历所有子文件夹，搜寻文本和图片
        for root, _, files in os.walk(temp_dir):
            for file in files:
                full_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()
                if ext in ('.txt', '.docx'):
                    # 过滤 Word 临时文件（以 ~$ 开头的文件）
                    if not file.startswith('~$'):
                        text_files.append(full_path)
                elif ext in image_extensions:
                    image_files.append(full_path)

        if not text_files:
            print(f"[WARNING] 跳过 {os.path.basename(rar_path)}：压缩包内部未找到 TXT 或 DOCX 文本文件。\n")
            return

        # 按路径和文件名自然排序
        text_files.sort()
        image_files.sort()

        # 创建 EPUB 书籍对象
        book = epub.EpubBook()
        book_title = os.path.splitext(os.path.basename(rar_path))[0]
        book.set_title(book_title)
        book.set_language('zh')

        spine = ['nav']
        toc = []

        # ==================== 1. 添加插图章节 ====================
        if image_files:
            illus_chapter = epub.EpubHtml(
                title='插图',
                file_name='illustrations.xhtml',
                lang='zh'
            )
            illus_content = ["<h1>插图</h1>"]

            for idx, img_path in enumerate(image_files):
                ext = os.path.splitext(img_path)[1].lower()
                img_name = f"img_{idx}{ext}"
                media_type = f"image/{'jpeg' if ext in ('.jpg', '.jpeg') else ext[1:]}"

                try:
                    with open(img_path, 'rb') as f:
                        epub_img = epub.EpubItem(
                            uid=f"image_{idx}",
                            file_name=f"images/{img_name}",
                            media_type=media_type,
                            content=f.read()
                        )
                        book.add_item(epub_img)

                    illus_content.append(
                        f'<div style="text-align: center; margin: 1em 0;">'
                        f'<img src="images/{img_name}" style="max-width: 100%; height: auto;" />'
                        f'</div>'
                    )
                except Exception as img_err:
                    print(f"[WARNING] 读取图片失败 {os.path.basename(img_path)}: {img_err}")

            illus_chapter.content = "".join(illus_content)
            book.add_item(illus_chapter)
            spine.append(illus_chapter)
            toc.append(illus_chapter)

        # ==================== 2. 处理所有 TXT / DOCX 文本 ====================
        global_chapter_idx = 1

        for doc_path in text_files:
            file_base_name = os.path.splitext(os.path.basename(doc_path))[0]
            ext = os.path.splitext(doc_path)[1].lower()

            if ext == '.docx':
                content = read_docx_content(doc_path)
            else:
                content = read_txt_content(doc_path)

            parsed_chapters = parse_text_to_chapters(content, default_title=file_base_name)

            for title, body in parsed_chapters:
                ch_item = epub.EpubHtml(
                    title=title,
                    file_name=f'chapter_{global_chapter_idx}.xhtml',
                    lang='zh'
                )
                paragraphs = body.split('\n')
                html_paragraphs = [f'<p>{p.strip()}</p>' for p in paragraphs if p.strip()]
                
                ch_item.content = f'<h2>{title}</h2>' + "".join(html_paragraphs)
                book.add_item(ch_item)
                spine.append(ch_item)
                toc.append(ch_item)

                global_chapter_idx += 1

        # ==================== 3. 组装并导出 EPUB ====================
        book.toc = toc
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = spine

        epub.write_epub(output_epub_path, book)
        print(f"[SUCCESS] ✅ 成功导出: {output_epub_path}\n")


def batch_convert():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    input_dir = os.path.join(base_dir, "rawrar")
    output_dir = os.path.join(base_dir, "Novels")

    if not os.path.exists(input_dir):
        os.makedirs(input_dir)
        print(f"已自动生成输入文件夹 '{input_dir}'，请将 RAR 放置在此文件夹后重新运行。")
        return

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    rar_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.rar')]

    if not rar_files:
        print(f"未在 '{input_dir}' 中找到任何 .rar 文件。")
        return

    print(f"共扫描到 {len(rar_files)} 个 RAR 文件，开始批量处理...\n")

    for file_name in rar_files:
        rar_path = os.path.join(input_dir, file_name)
        epub_name = os.path.splitext(file_name)[0] + ".epub"
        output_epub_path = os.path.join(output_dir, epub_name)

        try:
            rar_to_epub(rar_path, output_epub_path)
        except Exception as e:
            print(f"[ERROR] 处理 {file_name} 时出错: {e}\n")

    print("所有任务处理完毕！")


if __name__ == "__main__":
    batch_convert()