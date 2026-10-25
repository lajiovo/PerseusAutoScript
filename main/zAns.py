import re
import json
import hashlib

class LaTeXParser:
    """
    高级 LaTeX 数学表达式及化学方程式 (\ce) 转换为树状 AST 结构。
    支持 \frac, \dfrac, \sqrt, 上标 ^, 下标 _, 极限 \lim, 积分 \int, 求和 \sum, 化学方程式 \ce 等。
    """
    @staticmethod
    def parse_expression(expr_str):
        expr_str = expr_str.strip()
        if not expr_str:
            return {"type": "text", "value": ""}

        # 1. 化学方程式 \ce{...}
        if expr_str.startswith(r"\ce{") and expr_str.endswith("}"):
            inner = expr_str[4:-1].strip()
            return {"type": "chemical", "value": inner}

        # 2. 极限 \lim_{...} ...
        if expr_str.startswith(r"\lim"):
            return {"type": "limit", "raw": expr_str}

        # 3. 积分 \int ...
        if expr_str.startswith(r"\int") or expr_str.startswith(r"\displaystyle\int"):
            return {"type": "integral", "raw": expr_str}

        # 4. 求和 \sum ...
        if expr_str.startswith(r"\sum"):
            return {"type": "summation", "raw": expr_str}

        # 5. 绝对值 \left| ... \right| 或 | ... |
        if expr_str.startswith(r"\left|") and expr_str.endswith(r"\right|"):
            inner = expr_str[6:-7].strip()
            return {"type": "abs", "content": LaTeXParser.parse_expression(inner)}
        if expr_str.startswith("|") and expr_str.endswith("|") and len(expr_str) > 2:
            inner = expr_str[1:-1].strip()
            return {"type": "abs", "content": LaTeXParser.parse_expression(inner)}

        # 6. 分式 \frac{num}{den} 或 \dfrac{num}{den}
        if expr_str.startswith(r"\frac") or expr_str.startswith(r"\dfrac"):
            offset = 5 if expr_str.startswith(r"\frac") else 6
            idx = offset
            while idx < len(expr_str) and expr_str[idx].isspace():
                idx += 1
            if idx < len(expr_str) and expr_str[idx] == '{':
                num_str, next_idx = LaTeXParser._extract_braces(expr_str, idx)
                while next_idx < len(expr_str) and expr_str[next_idx].isspace():
                    next_idx += 1
                if next_idx < len(expr_str) and expr_str[next_idx] == '{':
                    den_str, _ = LaTeXParser._extract_braces(expr_str, next_idx)
                    return {
                        "type": "fraction",
                        "numerator": LaTeXParser.parse_expression(num_str),
                        "denominator": LaTeXParser.parse_expression(den_str)
                    }

        # 7. 根号 \sqrt{content}
        if expr_str.startswith(r"\sqrt"):
            idx = 5
            while idx < len(expr_str) and expr_str[idx].isspace():
                idx += 1
            if idx < len(expr_str) and expr_str[idx] == '{':
                content_str, _ = LaTeXParser._extract_braces(expr_str, idx)
                return {
                    "type": "sqrt",
                    "content": LaTeXParser.parse_expression(content_str)
                }

        # 8. 上下标 (含 ^ 和 _)
        if '^' in expr_str or '_' in expr_str:
            parts = LaTeXParser._split_binary(expr_str)
            if len(parts) == 3:
                base, op, val = parts
                return {
                    "type": "sup" if op == '^' else "sub",
                    "base": LaTeXParser.parse_expression(base),
                    "value": LaTeXParser.parse_expression(val)
                }

        # 9. 连等式
        if '=' in expr_str and not expr_str.startswith('='):
            eq_parts = [p.strip() for p in expr_str.split('=')]
            if len(eq_parts) > 1:
                return {
                    "type": "equation_chain",
                    "parts": [LaTeXParser.parse_expression(p) for p in eq_parts]
                }

        return {"type": "text", "value": expr_str}

    @staticmethod
    def _extract_braces(s, start_idx):
        depth = 0
        i = start_idx
        while i < len(s):
            if s[i] == '{':
                depth += 1
            elif s[i] == '}':
                depth -= 1
                if depth == 0:
                    return s[start_idx+1:i], i+1
            i += 1
        return s[start_idx+1:], len(s)

    @staticmethod
    def _split_binary(s):
        for i, char in enumerate(s):
            if char in ('^', '_'):
                return s[:i].strip(), char, s[i+1:].strip()
        return [s]


class ZAnsProcessor:
    """
    处理 Markdown 与高级 LaTeX/化学方程式混合文本，并执行智能分页。
    """
    @staticmethod
    def process_content(raw_text, title="", category="数学"):
        lines = raw_text.split('\n')
        blocks = []
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith("%"):
                continue
            
            block_type = "paragraph"
            if line.startswith("# "):
                block_type = "h1"
                line = line[2:].strip()
            elif line.startswith("## "):
                block_type = "h2"
                line = line[3:].strip()
            elif line.startswith("### "):
                block_type = "h3"
                line = line[4:].strip()
            elif line.startswith("$$") and line.endswith("$$"):
                block_type = "block_math"
                line = line[2:-2].strip()

            parsed_inlines = ZAnsProcessor._parse_inlines_and_math(line)
            blocks.append({
                "block_type": block_type,
                "raw": line,
                "content": parsed_inlines,
                "length": len(line)
            })

        pages = []
        current_page_blocks = []
        current_page_len = 0
        target_page_len = 350

        for block in blocks:
            b_len = block["length"]
            if current_page_len + b_len > target_page_len and current_page_blocks:
                pages.append({
                    "page_index": len(pages) + 1,
                    "blocks": current_page_blocks
                })
                current_page_blocks = [block]
                current_page_len = b_len
            else:
                current_page_blocks.append(block)
                current_page_len += b_len

        if current_page_blocks:
            pages.append({
                "page_index": len(pages) + 1,
                "blocks": current_page_blocks
            })

        if not pages:
            pages.append({"page_index": 1, "blocks": []})

        ans_id = hashlib.md5(raw_text.encode('utf-8')).hexdigest()[:8]
        result = {
            "ans_id": ans_id,
            "id": ans_id,
            "title": title or "未命名解析",
            "category": category,
            "total_pages": len(pages),
            "pages": pages,
            "raw_text": raw_text
        }
        return result

    @staticmethod
    def _parse_inlines_and_math(text):
        tokens = []
        pattern = re.compile(r'\$(.*?)\$|\*\*(.*?)\*\*|([^\$\*]+)')
        matches = pattern.findall(text)
        
        for m_math, m_bold, m_plain in matches:
            if m_math:
                tokens.append({
                    "type": "inline_math",
                    "ast": LaTeXParser.parse_expression(m_math),
                    "raw": m_math
                })
            elif m_bold:
                tokens.append({
                    "type": "bold",
                    "value": m_bold
                })
            elif m_plain:
                tokens.append({
                    "type": "text",
                    "value": m_plain
                })
        return tokens
