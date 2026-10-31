import re
import json
import tkinter as tk
from tkinter import ttk

class LaTeXASTParser:
    """
    LaTeX & Chemical Formula AST Parser for Smartwatch LVGL Rendering Engine.
    Converts LaTeX expressions into structural JSON AST nodes (fraction, sqrt, sub, sup, cases, chem, etc.).
    """
    
    def __init__(self):
        # 常见符号替换表，直接映射为适合手表单行显示的 Unicode 符号
        self.symbol_map = {
            r'\pm': '±', r'\mp': '∓', r'\times': '×', r'\div': '÷',
            r'\cdot': '·', r'\leq': '≤', r'\ge': '≥', r'\geq': '≥', r'\neq': '≠',
            r'\approx': '≈', r'\infty': '∞', r'\Delta': 'Δ', r'\pi': 'π',
            r'\alpha': 'α', r'\beta': 'β', r'\theta': 'θ', r'\mu': 'μ',
            r'\to': '→', r'\iff': '⇔', r'\sum': '∑', r'\int': '∫',
            r'\lim': 'lim', r'\ln': 'ln', r'\log': 'log', r'\sin': 'sin',
            r'\cos': 'cos', r'\tan': 'tan', r'\quad': ' ', r'\vert': '|',
            r'\vec': 'vec', r'\displaystyle': '', r'\text': ''
        }

    def tokenize(self, expr: str):
        """将 LaTeX 字符串切分为 Token 列表"""
        tokens = []
        i = 0
        n = len(expr)
        
        while i < n:
            ch = expr[i]
            
            # 跳过注释与额外空格（保留必要分割符）
            if ch == '%':
                while i < n and expr[i] != '\n':
                    i += 1
                continue
            if ch in ' \t\n\r':
                i += 1
                continue
                
            # 命令字识别 (例如 \dfrac, \ce, \sqrt)
            if ch == '\\':
                start = i
                i += 1
                if i < n and not expr[i].isalpha():
                    # 像 \, 或 \| 这种非字母转义
                    i += 1
                else:
                    while i < n and expr[i].isalpha():
                        i += 1
                tokens.append(expr[start:i])
                continue
                
            # 上下标与成对符号
            if ch in '{}[]()^_=+-*/|,!&':
                tokens.append(ch)
                i += 1
                continue
                
            # 数字或连续字母文本
            start = i
            while i < n and not expr[i].isalpha() and not expr[i].isdigit() and expr[i] not in r'\%{}[]()^_=+-*/|,!&\s':
                i += 1
            if start == i:
                start = i
                while i < n and (expr[i].isalnum() or expr[i] in '.:'):
                    i += 1
            tokens.append(expr[start:i])
            
        return tokens

    def parse_latex(self, latex_str: str) -> dict:
        """主解析入口"""
        latex_str = latex_str.strip()
        # 处理 \ce{...} 化学方程式
        if latex_str.startswith(r'\ce{') and latex_str.endswith('}'):
            chem_body = latex_str[4:-1]
            return self._parse_chemical(chem_body)
            
        tokens = self.tokenize(latex_str)
        nodes, _ = self._parse_tokens(tokens, 0)
        
        if len(nodes) == 1:
            return nodes[0]
        return {"type": "row", "children": nodes}

    def _parse_tokens(self, tokens, index, stop_tokens=None):
        """递归解析 Token 序列"""
        if stop_tokens is None:
            stop_tokens = set()
            
        children = []
        n = len(tokens)
        
        while index < n:
            tok = tokens[index]
            
            if tok in stop_tokens:
                break
                
            # 处理宏命令
            if tok in (r'\dfrac', r'\frac'):
                index += 1
                num, index = self._parse_group(tokens, index)
                den, index = self._parse_group(tokens, index)
                children.append({"type": "frac", "num": num, "den": den})
                continue
                
            elif tok == r'\sqrt':
                index += 1
                body, index = self._parse_group(tokens, index)
                children.append({"type": "sqrt", "content": body})
                continue
                
            elif tok == r'\begin{cases}':
                index += 1
                cases_nodes, index = self._parse_cases(tokens, index)
                children.append({"type": "cases", "items": cases_nodes})
                continue
                
            elif tok == '^':
                index += 1
                sup_node, index = self._parse_group(tokens, index)
                # 如果上一个节点是文字，则转换为上标扩展
                if children:
                    prev = children.pop()
                    children.append({"type": "sup_group", "base": prev, "sup": sup_node})
                else:
                    children.append({"type": "sup", "content": sup_node})
                continue
                
            elif tok == '_':
                index += 1
                sub_node, index = self._parse_group(tokens, index)
                if children:
                    prev = children.pop()
                    children.append({"type": "sub_group", "base": prev, "sub": sub_node})
                else:
                    children.append({"type": "sub", "content": sub_node})
                continue
                
            elif tok in ('{', '('):
                close_char = '}' if tok == '{' else ')'
                index += 1
                sub_nodes, index = self._parse_tokens(tokens, index, stop_tokens={close_char})
                if index < n and tokens[index] == close_char:
                    index += 1
                if tok == '(':
                    children.append({"type": "row", "children": [{"type": "text", "val": "("}] + sub_nodes + [{"type": "text", "val": ")"}]})
                else:
                    children.append({"type": "row", "children": sub_nodes})
                continue
                
            # 符号与文本替换
            val = self.symbol_map.get(tok, tok)
            if val:
                children.append({"type": "text", "val": val})
            index += 1
            
        return children, index

    def _parse_group(self, tokens, index):
        """解析单组 {} 或单个字符"""
        if index >= len(tokens):
            return {"type": "text", "val": ""}, index
            
        if tokens[index] == '{':
            index += 1
            nodes, index = self._parse_tokens(tokens, index, stop_tokens={'}'})
            if index < len(tokens) and tokens[index] == '}':
                index += 1
            if len(nodes) == 1:
                return nodes[0], index
            return {"type": "row", "children": nodes}, index
        else:
            tok = tokens[index]
            val = self.symbol_map.get(tok, tok)
            return {"type": "text", "val": val}, index + 1

    def _parse_cases(self, tokens, index):
        """解析条件分支 \\begin{cases}"""
        cases = []
        while index < len(tokens):
            if tokens[index] == r'\end{cases}':
                index += 1
                break
            line_nodes, index = self._parse_tokens(tokens, index, stop_tokens={r'\\', r'\end{cases}'})
            if index < len(tokens) and tokens[index] == r'\\':
                index += 1
            cases.append({"type": "row", "children": line_nodes})
        return cases, index

    def _parse_chemical(self, chem_str: str) -> dict:
        """解析 \ce{...} 化学方程式与反应条件（增强通用匹配与容错）"""
        # 修复正则: 避免 \x 被正则解释器误判为十六进制转义
        pattern = r'(\\xlongequal|\\xleftrightarrow|->|<=>|=)(?:\[(.*?)\])?(?:\[(.*?)\])?'
        parts = re.split(pattern, chem_str)
        
        nodes = []
        i = 0
        while i < len(parts):
            chunk = parts[i]
            if chunk:
                # 简单解析离子/沉淀/气体符号与上下标
                cleaned = chunk.replace('^', '↑').replace('v', '↓').strip()
                nodes.append({"type": "chem_text", "val": cleaned})
            
            # 如果匹配到了化学反应箭头/等号
            if i + 1 < len(parts) and parts[i+1] in ('->', '<=>', '=', r'\xlongequal', r'\xleftrightarrow'):
                arrow_type = parts[i+1]
                cond1 = parts[i+2] if i+2 < len(parts) else None
                cond2 = parts[i+3] if i+3 < len(parts) else None
                
                arrow_symbol = "⇄" if arrow_type in ('<=>', r'\xleftrightarrow') else ("=" if arrow_type == '=' else "→")
                nodes.append({
                    "type": "chem_arrow",
                    "arrow": arrow_symbol,
                    "top_condition": cond1,
                    "bottom_condition": cond2
                })
                i += 3
            i += 1
            
        return {"type": "chem_equation", "children": nodes}

    def parse_markdown(self, md_text: str) -> list:
        """从 Markdown 中剥离并解析所有的文本段落与 LaTeX 公式"""
        pages = []
        tokens = re.split(r'(\$\$.*?\$\$|\$.*?\$|\\ce\{.*?\})', md_text, flags=re.DOTALL)
        
        current_page_nodes = []
        current_char_count = 0
        
        for tok in tokens:
            if not tok:
                continue
            tok_strip = tok.strip()
            
            is_block = tok_strip.startswith('$$') and tok_strip.endswith('$$')
            is_inline = tok_strip.startswith('$') and tok_strip.endswith('$')
            is_ce = tok_strip.startswith(r'\ce{') and tok_strip.endswith('}')
            
            if is_block or is_inline or is_ce:
                if is_block:
                    raw_latex = tok_strip[2:-2]
                elif is_inline:
                    raw_latex = tok_strip[1:-1]
                else:
                    raw_latex = tok_strip
                    
                ast_node = self.parse_latex(raw_latex)
                current_page_nodes.append({"kind": "math", "ast": ast_node, "raw": raw_latex})
                current_char_count += 30
            else:
                current_page_nodes.append({"kind": "text", "content": tok})
                current_char_count += len(tok)
                
            if current_char_count >= 400:
                pages.append(current_page_nodes)
                current_page_nodes = []
                current_char_count = 0
                
        if current_page_nodes:
            pages.append(current_page_nodes)
            
        return pages

# ========== 二、 Tkinter 按钮触发与双栏 AST 展现引擎 ==========

class ASTRendererTk(tk.Frame):
    """
    Tkinter Canvas AST 渲染器
    提供按键渲染 + AST JSON 结构对比查看 + LVGL 模拟排版
    """
    def __init__(self, master):
        super().__init__(master, bg="#121212")
        self.pack(fill=tk.BOTH, expand=True)

        self.parser = LaTeXASTParser()

        # 上半部分：输入的文本框容器 + 渲染按钮
        top_frame = tk.Frame(self, bg="#1e1e1e")
        top_frame.pack(fill="x", padx=10, pady=5)

        lbl_input = tk.Label(top_frame, text="Markdown / LaTeX 输入框:", fg="#81c784", bg="#1e1e1e", font=("Consolas", 10, "bold"))
        lbl_input.pack(anchor="w", padx=5, pady=2)

        self.txt_input = tk.Text(top_frame, height=5, bg="#262626", fg="#ffffff", insertbackground="white", font=("Consolas", 10), wrap="word")
        self.txt_input.pack(fill="x", padx=5, pady=2)
        
        # 取消 KeyRelease 绑定，改为点击按钮渲染
        btn_render = tk.Button(
            top_frame, text="▶ 渲染 AST 与排版", bg="#2e7d32", fg="#ffffff",
            activebackground="#388e3c", activeforeground="#ffffff",
            font=("Consolas", 10, "bold"), command=self.update_render, cursor="hand2"
        )
        btn_render.pack(anchor="e", padx=5, pady=4)

        # 默认填充测试文本
        default_text = r"""代数：$x=\dfrac{-b\pm\sqrt{b^2-4ac}}{2a}$
化学：\ce{N2 + 3H2 <=>[高温高压][催化剂] 2NH3}
方程式：\ce{2KMnO4 \xlongequal{\Delta} K2MnO4 + MnO2 + O2 ^}"""
        self.txt_input.insert("1.0", default_text)

        # 下半部分：左右分栏容器（左侧: 手表模拟预览，右侧: AST JSON 结果）
        bottom_paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg="#121212", sashwidth=4, sashrelief=tk.RAISED)
        bottom_paned.pack(fill="both", expand=True, padx=10, pady=5)

        # ---------------- 左栏：LVGL 手表预览 ----------------
        left_frame = tk.Frame(bottom_paned, bg="#121212")
        lbl_preview = tk.Label(left_frame, text="手表端 LVGL 模拟渲染区域:", fg="#4fc3f7", bg="#121212", font=("Consolas", 10, "bold"))
        lbl_preview.pack(anchor="w", padx=5, pady=(2, 0))

        render_container = tk.Frame(left_frame, bg="#121212")
        render_container.pack(fill="both", expand=True, pady=5)

        self.canvas = tk.Canvas(render_container, bg="#181818", highlightthickness=1, highlightbackground="#333333")
        self.scrollbar = ttk.Scrollbar(render_container, orient="vertical", command=self.canvas.yview)
        self.scroll_frame = tk.Frame(self.canvas, bg="#181818")

        self.scroll_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        bottom_paned.add(left_frame)

        # ---------------- 右栏：AST JSON 展示区 ----------------
        right_frame = tk.Frame(bottom_paned, bg="#121212")
        lbl_ast = tk.Label(right_frame, text="生成 AST 树 JSON 结构:", fg="#ffb74d", bg="#121212", font=("Consolas", 10, "bold"))
        lbl_ast.pack(anchor="w", padx=5, pady=(2, 0))

        ast_container = tk.Frame(right_frame, bg="#121212")
        ast_container.pack(fill="both", expand=True, pady=5)

        self.txt_ast = tk.Text(ast_container, bg="#1c1c1c", fg="#b0bec5", insertbackground="white", font=("Consolas", 9), wrap="none")
        ast_scroll_y = ttk.Scrollbar(ast_container, orient="vertical", command=self.txt_ast.yview)
        ast_scroll_x = ttk.Scrollbar(ast_container, orient="horizontal", command=self.txt_ast.xview)
        
        self.txt_ast.configure(yscrollcommand=ast_scroll_y.set, xscrollcommand=ast_scroll_x.set)

        ast_scroll_y.pack(side="right", fill="y")
        ast_scroll_x.pack(side="bottom", fill="x")
        self.txt_ast.pack(side="left", fill="both", expand=True)

        bottom_paned.add(right_frame)

        self.font_main = ("Consolas", 12)
        self.font_sub = ("Consolas", 9)

        # 首次手动加载渲染
        self.update_render()

    def update_render(self):
        """重新解析并刷新界面组件及 AST JSON 展示"""
        # 清空已有控件与 JSON 树
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        self.txt_ast.delete("1.0", tk.END)

        raw_md = self.txt_input.get("1.0", tk.END)
        parsed_pages = self.parser.parse_markdown(raw_md)
        
        # 更新 AST JSON 文本面板
        ast_json_str = json.dumps(parsed_pages, indent=2, ensure_ascii=False)
        self.txt_ast.insert("1.0", ast_json_str)

        # 更新 Canvas 模拟渲染
        self._render_page(parsed_pages)

    def _render_page(self, page_data):
        """遍历页节点进行混合渲染"""
        for page in page_data:
            for item in page:
                kind = item.get("kind")
                if kind == "text":
                    text_val = item["content"].strip()
                    if text_val:
                        lbl = tk.Label(
                            self.scroll_frame, text=text_val, fg="#e0e0e0", bg="#181818",
                            font=self.font_main, justify="left", wraplength=340
                        )
                        lbl.pack(anchor="w", pady=2, padx=5)
                elif kind == "math":
                    ast = item["ast"]
                    c_widget = tk.Canvas(self.scroll_frame, bg="#222222", highlightthickness=1, highlightbackground="#444444")
                    c_widget.pack(anchor="w", pady=6, padx=8)
                    
                    self._draw_ast_node(c_widget, ast, x=8, y=10)
                    
                    c_widget.update_idletasks()
                    bbox = c_widget.bbox("all")
                    if bbox:
                        c_widget.config(width=bbox[2] + 8, height=bbox[3] + 8)

    def _draw_ast_node(self, cv, node, x, y):
        """递归绘制 AST 节点并返回占用的 (width, height)"""
        ntype = node.get("type")

        # 1. 普通文本 / 符号
        if ntype == "text":
            val = node.get("val", "")
            item_id = cv.create_text(x, y, text=val, fill="#4fc3f7", font=self.font_main, anchor="nw")
            bbox = cv.bbox(item_id)
            if not bbox:
                return 0, 18
            return bbox[2] - bbox[0], bbox[3] - bbox[1]

        # 2. 横向排列 (row)
        elif ntype == "row":
            curr_x = x
            max_h = 0
            for child in node.get("children", []):
                w, h = self._draw_ast_node(cv, child, curr_x, y)
                curr_x += w + 2
                max_h = max(max_h, h)
            return curr_x - x, max_h

        # 3. 分式 (frac)
        elif ntype == "frac":
            num_node = node.get("num")
            den_node = node.get("den")

            w_num, h_num = self._measure_node(cv, num_node)
            w_den, h_den = self._measure_node(cv, den_node)

            width = max(w_num, w_den) + 8
            line_y = y + h_num + 3

            self._draw_ast_node(cv, num_node, x + (width - w_num) / 2, y)
            cv.create_line(x, line_y, x + width, line_y, fill="#ffffff", width=2)
            self._draw_ast_node(cv, den_node, x + (width - w_den) / 2, line_y + 4)

            return width, h_num + h_den + 8

        # 4. 根号 (sqrt)
        elif ntype == "sqrt":
            content = node.get("content")
            w_in, h_in = self._measure_node(cv, content)

            cv.create_text(x, y, text="√", fill="#ffb74d", font=self.font_main, anchor="nw")
            cv.create_line(x + 10, y + 2, x + 14 + w_in, y + 2, fill="#ffb74d", width=2)
            self._draw_ast_node(cv, content, x + 12, y + 4)

            return w_in + 14, h_in + 4

        # 5. 上标 / 下标组合
        elif ntype in ("sup_group", "sub_group"):
            base = node.get("base")
            w_b, h_b = self._draw_ast_node(cv, base, x, y)

            if ntype == "sup_group":
                target = node.get("sup")
                w_s, h_s = self._draw_ast_node_subfont(cv, target, x + w_b, y - 4)
            else:
                target = node.get("sub")
                w_s, h_s = self._draw_ast_node_subfont(cv, target, x + w_b, y + h_b - 8)

            return w_b + w_s, max(h_b, h_s)

        # 6. 化学反应式 (chem_equation)
        elif ntype == "chem_equation":
            curr_x = x
            for child in node.get("children", []):
                ctype = child.get("type")
                if ctype == "chem_text":
                    item_id = cv.create_text(curr_x, y, text=child["val"], fill="#81c784", font=self.font_main, anchor="nw")
                    bbox = cv.bbox(item_id)
                    w = (bbox[2] - bbox[0]) if bbox else 10
                    curr_x += w + 4
                elif ctype == "chem_arrow":
                    top_cond = child.get("top_condition") or ""
                    arrow_str = f"── {child['arrow']} ──"
                    if top_cond:
                        cv.create_text(curr_x + 5, y - 10, text=top_cond, fill="#ff8a65", font=self.font_sub, anchor="nw")
                    cv.create_text(curr_x, y, text=arrow_str, fill="#ffb74d", font=self.font_main, anchor="nw")
                    curr_x += 65
            return curr_x - x, 24

        return 10, 18

    def _draw_ast_node_subfont(self, cv, node, x, y):
        """小字号渲染上下标"""
        if node.get("type") == "text":
            item_id = cv.create_text(x, y, text=node.get("val", ""), fill="#e0e0e0", font=self.font_sub, anchor="nw")
            bbox = cv.bbox(item_id)
            return (bbox[2] - bbox[0], bbox[3] - bbox[1]) if bbox else (0, 10)
        return self._draw_ast_node(cv, node, x, y)

    def _measure_node(self, cv, node):
        """测量节点尺寸"""
        dummy_x, dummy_y = -1000, -1000
        if node.get("type") == "text":
            item_id = cv.create_text(dummy_x, dummy_y, text=node.get("val", ""), font=self.font_main, anchor="nw")
            bbox = cv.bbox(item_id)
            cv.delete(item_id)
            return (bbox[2] - bbox[0], bbox[3] - bbox[1]) if bbox else (10, 18)
        elif node.get("type") == "row":
            total_w, max_h = 0, 0
            for c in node.get("children", []):
                w, h = self._measure_node(cv, c)
                total_w += w + 2
                max_h = max(max_h, h)
            return total_w, max_h
        return 20, 18


# ========== 三、 主入口与界面拉起 ==========
if __name__ == '__main__':
    root = tk.Tk()
    root.title("Redmi Watch 6 - 点击渲染 & AST 树结构调试器")
    root.geometry("820x640") # 扩大宽度以适应左右分栏
    root.configure(bg="#121212")

    app = ASTRendererTk(root)
    root.mainloop()