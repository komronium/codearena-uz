"""One-off helper: put the Uzbek string literals of the Python sources under gettext (Uzbek is the msgid).
Constants inside function bodies become _t("...") (gettext, per request), everywhere else _tl("...") (lazy).
f-strings made of simple names/attributes become _t("... {x} ...").format(x=...). Usage: python tools/i18n_wrap_py.py [--write].
Appends the msgids to tools/i18n_msgids.json. Skips tests, migrations, management commands, quiz_bank, places, countries."""
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UZ = re.compile(r"[‘’ʻ]|\b(ta|va|uchun|bilan|qayta|urinib|natija|qator|masala|yuborish|keyin|hali|xato|vaqt|kerak|bo‘lsin|kuni|yoki|bor|yo‘q|ko‘ring|tanlang|yozing|noto|boshqa|foydalanuvchi)\b", re.I)
SKIP = ("quiz_bank", "places", "countries", "/migrations/", "management/", "tests.py", "conftest")


def collect():
    for f in sorted(ROOT.glob("apps/**/*.py")):
        s = str(f)
        if not any(k in s for k in SKIP):
            yield f


def main():
    write = "--write" in sys.argv
    store = ROOT / "tools" / "i18n_msgids.json"
    ids = json.loads(store.read_text(encoding="utf-8")) if store.exists() else {}
    changed = manual = 0
    todo = []
    for f in collect():
        src = f.read_text(encoding="utf-8")
        if "gettext" in src and "_tl(" in src:
            continue  # already done
        tree = ast.parse(src)
        lines = src.split("\n")
        parents = {}
        for n in ast.walk(tree):
            for c in ast.iter_child_nodes(n):
                parents[c] = n
        docs = set()
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.Module, ast.AsyncFunctionDef)) and n.body and isinstance(n.body[0], ast.Expr) \
                    and isinstance(n.body[0].value, ast.Constant):
                docs.add(n.body[0].value)

        def in_function_body(node):
            cur = node
            while cur in parents:
                p = parents[cur]
                if isinstance(p, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                    body = p.body if isinstance(p.body, list) else [p.body]
                    if any(cur is b for b in body):
                        return True
                    return False  # decorator / default argument: runs at import
                cur = p
            return False

        edits = []  # (start_line, start_col, end_line, end_col, replacement)
        used_t = used_tl = False
        seen_f = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.JoinedStr) and n not in seen_f:
                consts = [v for v in n.values if isinstance(v, ast.Constant)]
                if not any(UZ.search(c.value) for c in consts):
                    continue
                for sub in ast.walk(n):
                    seen_f.add(sub)
                if parents.get(n) is not None and isinstance(parents[n], ast.FormattedValue):
                    continue
                ok, parts, kw = True, [], []
                for v in n.values:
                    if isinstance(v, ast.Constant):
                        if "{" in v.value or "}" in v.value:
                            ok = False
                        parts.append(v.value)
                    elif isinstance(v, ast.FormattedValue) and v.conversion == -1 and v.format_spec is None:
                        expr = ast.get_source_segment(src, v.value)
                        name = re.sub(r"[^A-Za-z0-9_]+", "_", expr).strip("_").lower() or "v"
                        name = ("x" + name) if name[0].isdigit() else name
                        if "\n" in expr or len(name) > 30:
                            ok = False
                        parts.append("{" + name + "}")
                        if all(k[0] != name for k in kw):
                            kw.append((name, expr))
                    else:
                        ok = False
                if not ok or not in_function_body(n) or n.lineno != n.end_lineno:
                    todo.append(f"{f.relative_to(ROOT)}:{n.lineno}: f-string")
                    continue
                msgid = "".join(parts)
                ids.setdefault(msgid, [str(f.relative_to(ROOT))])
                call = '_t(%s)' % json.dumps(msgid, ensure_ascii=False)
                if kw:
                    call += ".format(%s)" % ", ".join(f"{k}={e}" for k, e in kw)
                edits.append((n.lineno, n.col_offset, n.end_lineno, n.end_col_offset, call)); used_t = True
        for n in ast.walk(tree):
            if n in seen_f or not (isinstance(n, ast.Constant) and isinstance(n.value, str)) or n in docs:
                continue
            if len(n.value) <= 3 or not UZ.search(n.value) or isinstance(parents.get(n), ast.JoinedStr):
                continue
            p = parents.get(n)
            if isinstance(p, ast.Call) and isinstance(p.func, ast.Name) and p.func.id in ("_t", "_tl", "gettext", "gettext_lazy"):
                continue  # already translated
            if isinstance(p, (ast.Dict,)) and n in p.keys:
                todo.append(f"{f.relative_to(ROOT)}:{n.lineno}: dict key"); continue
            if isinstance(p, ast.Compare):
                todo.append(f"{f.relative_to(ROOT)}:{n.lineno}: comparison"); continue
            lazy = not in_function_body(n)
            fn = "_tl" if lazy else "_t"
            used_tl |= lazy; used_t |= not lazy
            seg = ast.get_source_segment(src, n)
            ids.setdefault(n.value, [str(f.relative_to(ROOT))])
            edits.append((n.lineno, n.col_offset, n.end_lineno, n.end_col_offset, f"{fn}({seg})"))
        if not edits:
            continue
        changed += 1
        if write:
            # apply bottom-up on a byte-offset-free line/col basis (cols are utf-8 byte offsets)
            blines = [l.encode("utf-8") for l in lines]
            for sl, sc, el, ec, rep in sorted(edits, key=lambda e: (e[0], e[1]), reverse=True):
                head = blines[sl - 1][:sc]; tail = blines[el - 1][ec:]
                blines[sl - 1:el] = [head + rep.encode("utf-8") + tail]
            text = b"\n".join(blines).decode("utf-8")
            names = [n for n, u in (("gettext as _t", used_t), ("gettext_lazy as _tl", used_tl)) if u]
            imp = "from django.utils.translation import " + ", ".join(names)
            tree2 = ast.parse(text)
            last = 0
            for node in tree2.body:
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    last = node.end_lineno
                elif last and not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)):
                    break
            tl = text.split("\n")
            tl.insert(last, imp)
            f.write_text("\n".join(tl), encoding="utf-8")
    store.write_text(json.dumps(ids, ensure_ascii=False, indent=0), encoding="utf-8")
    (ROOT / "tools" / "i18n_py_todo.txt").write_text("\n".join(todo), encoding="utf-8")
    print(f"{changed} files, {len(todo)} left for hand work")


if __name__ == "__main__":
    main()
