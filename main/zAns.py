import re
import json

def parse_latex_to_ast(latex_str):
    """
    将 LaTeX 公式字符串解析为简单的 AST 结构树 (fraction, sqrt, sup, sub, text)
    """
    latex_str = latex_str.strip()
    # 处理分数 \frac{num}{den}
    frac_match = re.search(r'\\frac\{([^}]+)\}\{([^}]+)\}', latex_str)
    if frac_match:
        return {
            "type": "fraction",
            "numerator": parse_latex_to_ast(frac_match.group(1)),
            "denominator": parse_latex_to_ast(frac_match.group(2))
        }
    
    # 处理根号 \sqrt{content}
    sqrt_match = re.search(r'\\sqrt\{([^}]+)\}', latex_str)
    if sqrt_match:
        return {
            "type": "sqrt",
            "content": parse_latex_to_ast(sqrt_match.group(1))
        }
    
    # 处理上标 / 下标如 base^sup 或 base_sub
    sup_match = re.search(r'([a-zA-Z0-9\+\-\*\/]+)\^([a-zA-Z0-9\+\-\*\/\{\}]+)', latex_str)
    if sup_match:
        return {
            "type": "sup",
            "base": {"type": "text", "value": sup_match.group(1)},
            "sup": parse_latex_to_ast(sup_match.group(2).replace('{','').replace('}',''))
        }

    sub_match = re.search(r'([a-zA-Z0-9\+\-\*\/]+)_([a-zA-Z0-9\+\-\*\/\{\}]+)', latex_str)
    if sub_match:
        return {
            "type": "sub",
            "base": {"type": "text", "value": sub_match.group(1)},
            "sub": parse_latex_to_ast(sub_match.group(2).replace('{','').replace('}',''))
        }

    return {
        "type": "text",
        "value": latex_str
    }

def process_markdown_and_latex(raw_text):
    """
    解析原始 Markdown 文本，提取行内 ($...$) 和块级 ($$...$$) LaTeX 公式并转为 AST，
    同时将文本分块切页（每页 300-500 字）。
    """
    # 替换 LaTeX 为占位符或节点
    # 简单按段落切分
    paragraphs = raw_text.split('\n\n')
    nodes = []
    
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        # 检查是否是标题
        if p.startswith('# '):
            nodes.append({"type": "h1", "value": p[2:].strip()})
        elif p.startswith('## '):
            nodes.append({"type": "h2", "value": p[3:].strip()})
        elif p.startswith('### '):
            nodes.append({"type": "h3", "value": p[4:].strip()})
        else:
            # 提取 LaTeX 公式
            # 查找所有 $...$ 或 $$...$$
            parts = []
            pattern = re.compile(r'(\$\$[\s\S]*?\$\$|\$[^\$]+?\$|[^\$\n]+)')
            matches = pattern.findall(p)
            for m in matches:
                if m.startswith('$$') and m.endswith('$$'):
                    latex_content = m[2:-2].strip()
                    parts.append({
                        "type": "formula_block",
                        "ast": parse_latex_to_ast(latex_content)
                    })
                elif m.startswith('$') and m.endswith('$'):
                    latex_content = m[1:-1].strip()
                    parts.append({
                        "type": "formula_inline",
                        "ast": parse_latex_to_ast(latex_content)
                    })
                else:
                    if m.strip():
                        parts.append({
                            "type": "text",
                            "value": m.strip()
                        })
            nodes.append({
                "type": "paragraph",
                "children": parts
            })

    # 分页算法：每页约 350 字
    pages = []
    current_page_nodes = []
    current_char_count = 0
    target_page_chars = 350

    for node in nodes:
        node_str = json.dumps(node, ensure_ascii=False)
        node_len = len(node_str)
        if current_char_count + node_len > target_page_chars and current_page_nodes:
            pages.append(current_page_nodes)
            current_page_nodes = [node]
            current_char_count = node_len
        else:
            current_page_nodes.append(node)
            current_char_count += node_len

    if current_page_nodes:
        pages.append(current_page_nodes)

    if not pages:
        pages = [[]]

    return {
        "total_pages": len(pages),
        "pages": pages
    }
