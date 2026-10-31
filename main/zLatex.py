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

    def parse_latex(self, latex_str: str) -> list:
        """主解析入口，返回极简 JSON 节点"""
        latex_str = latex_str.strip()
        # 处理 \ce{...} 化学方程式
        if latex_str.startswith(r'\ce{') and latex_str.endswith('}'):
            chem_body = latex_str[4:-1]
            return self._parse_chemical(chem_body)
            
        tokens = self.tokenize(latex_str)
        nodes, _ = self._parse_tokens(tokens, 0)
        
        if len(nodes) == 1:
            return nodes[0]
        return ["r"] + nodes

    def _parse_tokens(self, tokens, index, stop_tokens=None):
        """递归解析 Token 序列（精简 AST 格式）"""
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
                children.append(["f", num, den])
                continue
                
            elif tok == r'\sqrt':
                index += 1
                body, index = self._parse_group(tokens, index)
                children.append(["sq", body])
                continue
                
            elif tok == r'\begin{cases}':
                index += 1
                cases_nodes, index = self._parse_cases(tokens, index)
                children.append(["c"] + cases_nodes)
                continue
                
            elif tok == '^':
                index += 1
                sup_node, index = self._parse_group(tokens, index)
                if children:
                    prev = children.pop()
                    children.append(["sup_g", prev, sup_node])
                else:
                    children.append(["sup", sup_node])
                continue
                
            elif tok == '_':
                index += 1
                sub_node, index = self._parse_group(tokens, index)
                if children:
                    prev = children.pop()
                    children.append(["sub_g", prev, sub_node])
                else:
                    children.append(["sub", sub_node])
                continue
                
            elif tok in ('{', '('):
                close_char = '}' if tok == '{' else ')'
                index += 1
                sub_nodes, index = self._parse_tokens(tokens, index, stop_tokens={close_char})
                if index < n and tokens[index] == close_char:
                    index += 1
                if tok == '(':
                    children.append(["r", ["t", "("]] + sub_nodes + [["t", ")"]])
                else:
                    children.append(["r"] + sub_nodes)
                continue
            # 假设这里是处理以 \ 开头的 LaTeX 命令的分支
            elif tok == r'\vec':
                index += 1
                if index < n:
                    next_tok = tokens[index]
                    # 检查后面是带大括号 \vec{a} 还是单个字符 \vec a
                    if next_tok == '{':
                        index += 1
                        sub_nodes, index = self._parse_tokens(tokens, index, stop_tokens={'}'})
                        if index < n and tokens[index] == '}':
                            index += 1
                        # 如果大括号里只有一个节点，直接作为 vec 的参数；否则用 ["r", ...] 包装
                        content = sub_nodes[0] if len(sub_nodes) == 1 else ["r"] + sub_nodes
                    else:
                        # 单个 token（例如字母 a）
                        content = ["t", next_tok]
                        index += 1
                    
                    children.append(["vec", content])
                continue
                
            # 符号与文本替换
            val = self.symbol_map.get(tok, tok)
            if val:
                children.append(["t", val])
            index += 1
            
        return children, index

    def _parse_group(self, tokens, index):
        """解析单组 {} 或单个字符"""
        if index >= len(tokens):
            return ["t", ""], index
            
        if tokens[index] == '{':
            index += 1
            nodes, index = self._parse_tokens(tokens, index, stop_tokens={'}'})
            if index < len(tokens) and tokens[index] == '}':
                index += 1
            if len(nodes) == 1:
                return nodes[0], index
            return ["r"] + nodes, index
        else:
            tok = tokens[index]
            val = self.symbol_map.get(tok, tok)
            return ["t", val], index + 1

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
            cases.append(["r"] + line_nodes)
        return cases, index

    def _parse_chemical(self, chem_str):
        import re
        
        # 升级版正则：完美兼容 ->[点燃]（单括号在上方）, <=>[高温][催化剂]（双括号上下）, 以及 \xlongequal{\Delta}
        arrow_pattern = re.compile(
            r'(\\xlongequal|\\xleftrightarrow|->|<=>|=)'
            r'(?:'
                r'\{([^}]*)\}'                  # 大括号形式，如 \xlongequal{\Delta} -> top
                r'(?:\[([^]]*)\])?'             # 后续可选的 [bottom]
              r'|'
                r'\[([^]]*)\]'                  # 第一个中括号，如 ->[点燃] -> 默认在 top
                r'(?:\[([^]]*)\])?'             # 第二个可选的中括号，如 [bottom]
            r')?'
        )
        
        parts = []
        last_idx = 0
        for match in arrow_pattern.finditer(chem_str):
            start, end = match.span()
            if start > last_idx:
                parts.append(chem_str[last_idx:start].strip())
            
            arrow_type = match.group(1)
            
            # 精准解析上下条件
            top_c, bot_c = None, None
            if match.group(2) is not None:  # 匹配到 {top}
                top_c = match.group(2)
                bot_c = match.group(3)
            elif match.group(4) is not None:  # 匹配到 [bracket1] -> 对应 top
                top_c = match.group(4)
                bot_c = match.group(5)      # 可选的第二个中括号对应 bottom
            
            # 标准化箭头符号
            arrow_symbol = "→"
            if "<=>" in arrow_type or "\\xleftrightarrow" in arrow_type:
                arrow_symbol = "⇌"
            elif "=" in arrow_type:
                arrow_symbol = "＝"
            elif "\\xlongequal" in arrow_type:
                arrow_symbol = "══"
                
            parts.append({
                "type": "chem_arrow_full",
                "symbol": arrow_symbol,
                "top": top_c,
                "bottom": bot_c
            })
            last_idx = end
            
        if last_idx < len(chem_str):
            parts.append(chem_str[last_idx:].strip())
            
        seq_nodes = []
        for p in parts:
            if isinstance(p, dict):
                top_node = self.parse_latex(p["top"]) if p["top"] else None
                bot_node = self.parse_latex(p["bottom"]) if p["bottom"] else None
                seq_nodes.append(["chem_a", p["symbol"], top_node, bot_node])
            elif p:
                seq_nodes.extend(self._parse_chem_formula_tokens(p))
                
        return ["chem_seq", seq_nodes]

    def _parse_chem_formula_tokens(self, formula_str):
        """严谨的化学式分词：仅按两边带空格的 ' + ' 分割反应物，保留离子电荷如 H+、Cu^{2+}"""
        tokens = []
        import re
        
        # 仅按“两侧有空白”的加号进行切分（例如 "A + B"），绝不切分 "H+" 或 "Fe3+"
        raw_parts = re.split(r'\s+\+\s+', formula_str)
        
        for i, part in enumerate(raw_parts):
            part = part.strip()
            if not part:
                continue
            
            # 如果不是第一项，说明中间有一个反应物分隔的 " + "
            if i > 0:
                tokens.append(["t", " + "])
                
            # 替换气体/沉淀符号
            t_clean = part.replace('^', '↑').replace('v', '↓')
            
            # 检查是否包含大括号或上下标（如 Fe^{3+}, SO4^{2-} 等）
            if '{' in t_clean or '^' in t_clean or '_' in t_clean:
                sub_ast = self.parse_latex(f"${t_clean}$")
                if sub_ast[0] == "t":
                    tokens.append(["t", t_clean])
                else:
                    tokens.append(sub_ast)
            else:
                tokens.append(["t", t_clean])
                
        return tokens

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
                current_page_nodes.append(["m", ast_node])
                current_char_count += 30
            else:
                current_page_nodes.append(["txt", tok])
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
                kind = item[0]
                if kind == "txt":
                    text_val = item[1].strip()
                    if text_val:
                        lbl = tk.Label(
                            self.scroll_frame, text=text_val, fg="#e0e0e0", bg="#181818",
                            font=self.font_main, justify="left", wraplength=340
                        )
                        lbl.pack(anchor="w", pady=2, padx=5)
                elif kind == "m":
                    ast = item[1]
                    c_widget = tk.Canvas(self.scroll_frame, bg="#222222", highlightthickness=1, highlightbackground="#444444")
                    c_widget.pack(anchor="w", pady=6, padx=8)
                    
                    self._draw_ast_node(c_widget, ast, x=8, y=10)
                    
                    c_widget.update_idletasks()
                    bbox = c_widget.bbox("all")
                    if bbox:
                        c_widget.config(width=bbox[2] + 8, height=bbox[3] + 8)

    def _draw_ast_node(self, cv, node, x, y):
        """递归绘制极简 AST 节点并返回占用的 (width, height)"""
        if not node or not isinstance(node, list):
            return 0, 18

        ntype = node[0]

        # 1. 普通文本 ["t", "val"]
        if ntype == "t":
            val = node[1] if len(node) > 1 else ""
            item_id = cv.create_text(x, y, text=val, fill="#4fc3f7", font=self.font_main, anchor="nw")
            bbox = cv.bbox(item_id)
            if not bbox:
                return 0, 18
            return bbox[2] - bbox[0], bbox[3] - bbox[1]

        # 2. 横向排列 ["r", child1, child2, ...]
        elif ntype == "r":
            curr_x = x
            max_h = 0
            for child in node[1:]:
                w, h = self._draw_ast_node(cv, child, curr_x, y)
                curr_x += w + 2
                max_h = max(max_h, h)
            return curr_x - x, max_h

        # 3. 分式 ["f", num_node, den_node]
        elif ntype == "f":
            num_node = node[1]
            den_node = node[2]

            w_num, h_num = self._measure_node(cv, num_node)
            w_den, h_den = self._measure_node(cv, den_node)

            width = max(w_num, w_den) + 8
            line_y = y + h_num + 3

            self._draw_ast_node(cv, num_node, x + (width - w_num) / 2, y)
            cv.create_line(x, line_y, x + width, line_y, fill="#ffffff", width=2)
            self._draw_ast_node(cv, den_node, x + (width - w_den) / 2, line_y + 4)

            return width, h_num + h_den + 8

        # 4. 根号 ["sq", content_node]
        elif ntype == "sq":
            content = node[1]
            w_in, h_in = self._measure_node(cv, content)

            cv.create_text(x, y, text="√", fill="#ffb74d", font=self.font_main, anchor="nw")
            cv.create_line(x + 10, y + 2, x + 14 + w_in, y + 2, fill="#ffb74d", width=2)
            self._draw_ast_node(cv, content, x + 12, y + 4)

            return w_in + 14, h_in + 4

        # 5. 上标 / 下标 ["sup_g", base, sup] / ["sub_g", base, sub]
        elif ntype in ("sup_group", "sub_group", "sup_g", "sub_g"):
            base = node[1]
            w_b, h_b = self._draw_ast_node(cv, base, x, y)

            target = node[2] if len(node) > 2 else None
            if not target:
                return w_b, h_b

            if ntype in ("sup_group", "sup_g"):
                w_s, h_s = self._draw_ast_node_subfont(cv, target, x + w_b, y - 6)
            else:
                w_s, h_s = self._draw_ast_node_subfont(cv, target, x + w_b, y + h_b - 6)

            return w_b + w_s, max(h_b, h_s)

        # 6. 化学方程式序列 ["chem_seq", ...] 或 ["chem_eq", ...]
        elif ntype in ("chem_seq", "chem_eq"):
            curr_x = x
            max_h = 18
            for child in node[1:]:
                if not isinstance(child, list):
                    continue
                c_type = child[0]
                
                # 如果是带条件的化学箭头: ["chem_a", symbol, top_node, bot_node]
                if c_type == "chem_a":
                    symbol = child[1]
                    top_node = child[2] if len(child) > 2 else None
                    bot_node = child[3] if len(child) > 3 else None

                    # 渲染上方条件 (如 \Delta)
                    top_w = 0
                    if top_node:
                        tw, th = self._draw_ast_node_subfont(cv, top_node, curr_x + 4, y - 12)
                        top_w = tw

                    # 渲染箭头符号
                    item_id = cv.create_text(curr_x, y, text=f" {symbol} ", fill="#ffb74d", font=self.font_main, anchor="nw")
                    bbox = cv.bbox(item_id)
                    w = (bbox[2] - bbox[0]) if bbox else 30

                    # 渲染下方条件
                    if bot_node:
                        self._draw_ast_node_subfont(cv, bot_node, curr_x + 4, y + 16)

                    curr_x += max(w, top_w) + 6
                    max_h = max(max_h, 26)
                else:
                    # 普通化学式片段（如分子式、离子、加号等）
                    w, h = self._draw_ast_node(cv, child, curr_x, y)
                    curr_x += w + 2
                    max_h = max(max_h, h)
            return curr_x - x, max_h

        # 7. 向量符号: ["vec", content_node]
        elif ntype == "vec":
            content = node[1]
            # 递归绘制内部的主体（如 a 或 \vec{a})
            w_in, h_in = self._draw_ast_node(cv, content, x, y + 4)
            
            # 在上方画一个小箭头顶杠
            cv.create_line(x, y, x + w_in, y, fill="#ffb74d", width=1.5)
            # 画箭头的小尖角
            cv.create_line(x + w_in - 3, y - 2, x + w_in, y, fill="#ffb74d", width=1.5)
            cv.create_line(x + w_in - 3, y + 2, x + w_in, y, fill="#ffb74d", width=1.5)
            
            return w_in, h_in + 4

        return 10, 18

    def _draw_ast_node_subfont(self, cv, node, x, y):
        """小字号渲染上下标"""
        if isinstance(node, list) and node[0] == "t":
            item_id = cv.create_text(x, y, text=node[1], fill="#e0e0e0", font=self.font_sub, anchor="nw")
            bbox = cv.bbox(item_id)
            return (bbox[2] - bbox[0], bbox[3] - bbox[1]) if bbox else (0, 10)
        return self._draw_ast_node(cv, node, x, y)

    def _measure_node(self, cv, node):
        """测量极简节点尺寸"""
        dummy_x, dummy_y = -1000, -1000
        if not node or not isinstance(node, list):
            return 20, 18
            
        ntype = node[0]
        if ntype == "t":
            val = node[1] if len(node) > 1 else ""
            item_id = cv.create_text(dummy_x, dummy_y, text=val, font=self.font_main, anchor="nw")
            bbox = cv.bbox(item_id)
            cv.delete(item_id)
            return (bbox[2] - bbox[0], bbox[3] - bbox[1]) if bbox else (10, 18)
        elif ntype == "r":
            total_w, max_h = 0, 0
            for c in node[1:]:
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