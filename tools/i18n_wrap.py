"""One-off helper that put the Uzbek strings of the templates under {% trans %} / {% blocktrans %} (Uzbek is the msgid,
English the translation). Usage: python tools/i18n_wrap.py [--write] [files...]; collects the msgids into
tools/i18n_msgids.json. Run it again after adding templates: wrapped text is skipped, new text gets wrapped."""
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INLINE = {"a", "b", "i", "em", "strong", "span", "code", "small", "kbd", "sub", "sup", "mark", "abbr", "u", "time", "bdi", "br", "s", "q", "cite", "var", "samp"}
ATTRS = ("title", "aria-label", "placeholder", "alt", "aria-description", "data-confirm", "data-empty", "data-label",
         "data-title", "data-text", "data-copy-done", "label", "content_")
LETTER = re.compile(r"[A-Za-zʻʼ‘’ʹ'ЁёА-я]")
SKIP_BLOCKS = {"comment": "endcomment", "blocktrans": "endblocktrans", "blocktranslate": "endblocktranslate"}


def tokenize(src: str):
    """Yield (kind, text): kind in text, var, tag (template block tag), tcomment, html (a tag), hcomment, raw (script/style)."""
    i, n = 0, len(src)
    buf = []

    def flush():
        if buf:
            yield "text", "".join(buf)
            buf.clear()

    while i < n:
        c = src[i]
        if src.startswith("{#", i):
            j = src.find("#}", i)
            j = n if j < 0 else j + 2
            yield from flush(); yield "tcomment", src[i:j]; i = j
        elif src.startswith("{%", i):
            j = src.find("%}", i); j = n if j < 0 else j + 2
            tag = src[i:j]
            name = tag[2:-2].strip().split(None, 1)[0] if tag[2:-2].strip() else ""
            if name in SKIP_BLOCKS:
                m = re.compile(r"\{%\s*" + SKIP_BLOCKS[name] + r"\s*%\}").search(src, j)
                j = m.end() if m else n
                yield from flush(); yield "tcomment", src[i:j]; i = j
            else:
                yield from flush(); yield "tag", tag; i = j
        elif src.startswith("{{", i):
            j = src.find("}}", i); j = n if j < 0 else j + 2
            yield from flush(); yield "var", src[i:j]; i = j
        elif src.startswith("<!--", i):
            j = src.find("-->", i); j = n if j < 0 else j + 3
            yield from flush(); yield "hcomment", src[i:j]; i = j
        elif c == "<" and re.match(r"</?[A-Za-z]", src[i:i + 3]):
            # scan to the closing > outside quotes and template constructs
            j, q = i + 1, ""
            while j < n:
                if src.startswith("{%", j):
                    e = src.find("%}", j); j = (n if e < 0 else e + 2); continue
                if src.startswith("{{", j):
                    e = src.find("}}", j); j = (n if e < 0 else e + 2); continue
                ch = src[j]
                if q:
                    if ch == q:
                        q = ""
                elif ch in "\"'":
                    q = ch
                elif ch == ">":
                    j += 1
                    break
                j += 1
            html = src[i:j]
            m = re.match(r"<(script|style)\b", html, re.I)
            if m and not html.endswith("/>"):
                e = re.compile(r"</" + m.group(1) + r"\s*>", re.I).search(src, j)
                j = e.end() if e else n
                yield from flush(); yield "raw", src[i:j]; i = j
            else:
                yield from flush(); yield "html", html; i = j
        else:
            buf.append(c); i += 1
    yield from flush()


def tag_name(html: str) -> str:
    m = re.match(r"</?\s*([A-Za-z][A-Za-z0-9-]*)", html)
    return m.group(1).lower() if m else ""


def is_inline(html: str) -> bool:
    name = tag_name(html)
    if name not in INLINE or "{%" in html or "{{" in html:
        return False
    if name == "i" and "data-lucide" in html:
        return False
    return True


def quote_lit(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def ws(s: str) -> str:
    return re.sub(r"\s+", " ", s)


class Wrapper:
    def __init__(self):
        self.ids: "OrderedDict[str, set]" = OrderedDict()
        self.review: list[str] = []

    def add(self, msgid: str, ref: str):
        self.ids.setdefault(msgid, set()).add(ref)

    # ---- a run of text / vars / inline tags -> one trans or blocktrans -----------------------------------------
    def wrap_run(self, run: list, ref: str) -> str:
        """run: [(kind, text)] with kind in text/var/html. Returns the template text (the original when nothing to translate)."""
        orig = "".join(t for _, t in run)
        # leading/trailing: whitespace, closing inline tags at the start and opening ones at the end stay outside
        lo, hi = 0, len(run)
        while lo < hi and (run[lo][0] == "html" and run[lo][1].startswith("</") or run[lo][0] == "text" and not run[lo][1].strip()):
            lo += 1
        while hi > lo and (run[hi - 1][0] == "html" and not run[hi - 1][1].startswith("</") or run[hi - 1][0] == "text" and not run[hi - 1][1].strip()):
            hi -= 1
        # trim until the inline tags balance: a closer at the end or an opener at the start belongs to the outside;
        # an opening tag at the start whose closer ends the run is peeled off as well (a wrapping <span> or <a>)
        def pairs(seq):
            stack, match, bad = [], {}, set()
            for idx, (k, t) in enumerate(seq):
                if k != "html":
                    continue
                if t.startswith("</"):
                    for sidx in range(len(stack) - 1, -1, -1):
                        if tag_name(seq[stack[sidx]][1]) == tag_name(t):
                            match[stack[sidx]] = idx; del stack[sidx:]
                            break
                    else:
                        bad.add(idx)
                elif not t.endswith("/>") and tag_name(t) != "br":
                    stack.append(idx)
            return match, bad | set(stack)
        while True:
            seq = run[lo:hi]
            match, bad = pairs(seq)
            if seq and 0 in bad and seq[0][0] == "html":
                lo += 1
            elif seq and (len(seq) - 1) in bad and seq[-1][0] == "html":
                hi -= 1
            elif seq and match.get(0) == len(seq) - 1:
                lo += 1; hi -= 1
            else:
                break
            while lo < hi and run[lo][0] == "text" and not run[lo][1].strip():
                lo += 1
            while hi > lo and run[hi - 1][0] == "text" and not run[hi - 1][1].strip():
                hi -= 1
        core = run[lo:hi]
        if not core:
            return orig
        if not any(k == "text" and LETTER.search(re.sub(r"&[a-z]+;|&#\d+;", "", t)) for k, t in core):
            return orig
        head = "".join(t for _, t in run[:lo])
        tail = "".join(t for _, t in run[hi:])
        # whitespace at the very start/end of the core text stays outside too
        first, last = core[0], core[-1]
        lead_ws = trail_ws = ""
        if first[0] == "text":
            m = re.match(r"\s+", first[1])
            if m:
                lead_ws = m.group(0); core[0] = ("text", first[1][m.end():])
        if last[0] == "text":
            m = re.search(r"\s+$", core[-1][1])
            if m:
                trail_ws = m.group(0); core[-1] = ("text", core[-1][1][:m.start()])
        has_var = any(k == "var" for k, _ in core)
        if not has_var:
            text = ws("".join(t for _, t in core))
            self.add(text, ref)
            return f"{head}{lead_ws}{{% trans {quote_lit(text)} %}}{trail_ws}{tail}"
        withs, names, parts, msgid = [], {}, [], []
        for k, t in core:
            if k == "var":
                expr = t[2:-2].strip()
                key = expr
                if key not in names:
                    base = re.sub(r"[^A-Za-z0-9_]+", "_", expr.split("|")[0]).strip("_").lower() or "v"
                    if not re.match(r"[a-z_]", base):
                        base = "v" + base
                    name, k2 = base, 1
                    while name in names.values():
                        k2 += 1; name = f"{base}{k2}"
                    names[key] = name
                    withs.append(f"{name}={expr}")
                parts.append("{{ %s }}" % names[key])
                msgid.append("%%(%s)s" % names[key])
            else:
                parts.append(ws(t) if k == "text" else ws(t))
                msgid.append(ws(t).replace("%", "%%"))
        # collapse to single spaces across pieces
        body = re.sub(r"\s+", " ", "".join(parts))
        mid = re.sub(r"\s+", " ", "".join(msgid))
        self.add(mid, ref)
        return f"{head}{lead_ws}{{% blocktrans with {' '.join(withs)} %}}{body}{{% endblocktrans %}}{trail_ws}{tail}"

    # ---- attributes ---------------------------------------------------------------------------------------------
    def wrap_attrs(self, html: str, ref: str) -> str:
        def repl(m):
            name, q, val = m.group(1), m.group(2), m.group(3)
            if name.lower() not in ATTRS and not (name.lower() == "value" and re.search(r"type=[\"'](submit|button)", html)):
                return m.group(0)
            if "{%" in val:
                # an attribute with if/else inside: each literal piece between the template constructs is wrapped alone
                inner = "'" if q == '"' else '"'
                pieces = []
                for pk, pt in tokenize(val):
                    if pk == "text" and LETTER.search(re.sub(r"&[a-z]+;|&#\d+;", "", pt)):
                        lead = re.match(r"\s*", pt).group(0); tail = re.search(r"\s*$", pt).group(0)
                        core = ws(pt.strip())
                        self.add(core, ref)
                        lit = inner + core.replace("\\", "\\\\").replace(inner, "\\" + inner) + inner
                        pieces.append(f"{lead}{{% trans {lit} %}}{tail}")
                    else:
                        pieces.append(pt)
                return f"{name}={q}{''.join(pieces)}{q}"
            if not LETTER.search(re.sub(r"\{\{.*?\}\}|&[a-z]+;", "", val)):
                return m.group(0)
            if "{{" in val:
                withs, names, body, mid = [], {}, "", ""
                pos = 0
                for vm in re.finditer(r"\{\{(.*?)\}\}", val):
                    expr = vm.group(1).strip()
                    if expr not in names:
                        base = re.sub(r"[^A-Za-z0-9_]+", "_", expr.split("|")[0]).strip("_").lower() or "v"
                        if not re.match(r"[a-z_]", base):
                            base = "v" + base
                        vname, k2 = base, 1
                        while vname in names.values():
                            k2 += 1; vname = f"{base}{k2}"
                        names[expr] = vname
                        withs.append(f"{vname}={expr}")
                    lit = val[pos:vm.start()]
                    body += lit + "{{ %s }}" % names[expr]; mid += lit.replace("%", "%%") + "%%(%s)s" % names[expr]
                    pos = vm.end()
                body += val[pos:]; mid += val[pos:].replace("%", "%%")
                if '"' in body or "'" in body and q == "'":
                    self.review.append(f"{ref}: quote in attribute {m.group(0)[:100]}")
                    return m.group(0)
                mid = ws(mid)
                self.add(mid, ref)
                return f'{name}={q}{{% blocktrans with {" ".join(withs)} %}}{ws(body)}{{% endblocktrans %}}{q}'
            text = ws(val.strip())
            self.add(text, ref)
            inner = "'" if q == '"' else '"'
            lit = inner + text.replace("\\", "\\\\").replace(inner, "\\" + inner) + inner
            return f"{name}={q}{{% trans {lit} %}}{q}"
        return re.sub(r"\b([A-Za-z][A-Za-z-]*)=([\"'])((?:\{\{.*?\}\}|\{%.*?%\}|(?!\2).)*)\2", repl, html, flags=re.S)

    # ---- a file ---------------------------------------------------------------------------------------------------
    def process(self, src: str, ref: str) -> str:
        out, run = [], []

        def flush():
            if run:
                out.append(self.wrap_run(list(run), ref))
                run.clear()

        for kind, text in tokenize(src):
            if kind in ("text", "var"):
                run.append((kind, text))
            elif kind == "html":
                if is_inline(text):
                    run.append(("html", text))
                else:
                    flush(); out.append(self.wrap_attrs(text, ref))
            else:
                flush()
                if kind == "raw" and LETTER.search(re.sub(r"<[^>]*>", "", text)):
                    self.review.append(f"{ref}: script/style block")
                out.append(text)
        flush()
        return "".join(out)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    write = "--write" in sys.argv
    files = [Path(a) for a in args] or sorted(p for p in ROOT.glob("**/*.html") if not {"node_modules", ".venv", "venv"} & set(p.parts) and "templates" in p.parts)
    w = Wrapper()
    changed = 0
    for f in files:
        f = f if f.is_absolute() else ROOT / f
        src = f.read_text(encoding="utf-8")
        new = w.process(src, str(f.relative_to(ROOT)))
        if new != src:
            changed += 1
            if write:
                f.write_text(new, encoding="utf-8")
    store = ROOT / "tools" / "i18n_msgids.json"
    prev = json.loads(store.read_text(encoding="utf-8")) if store.exists() else {}
    for k, v in w.ids.items():
        prev.setdefault(k, sorted(v))
    store.write_text(json.dumps(prev, ensure_ascii=False, indent=0), encoding="utf-8")
    (ROOT / "tools" / "i18n_review.txt").write_text("\n".join(w.review), encoding="utf-8")
    print(f"{len(files)} files, {changed} changed, {len(w.ids)} msgids, {len(w.review)} to review")


if __name__ == "__main__":
    main()
