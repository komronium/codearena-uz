"""Builds locale/en/LC_MESSAGES/django.po and .mo from the sources (no gettext binaries needed: polib).
  python tools/i18n_build.py              extract msgids, merge tools/i18n_en.json, write .po/.mo, report what is missing
  python tools/i18n_build.py --todo 150   print the next 150 untranslated msgids (numbered) to translate
msgids come from {% trans %}, {% blocktrans %}, {% jt %} in templates and _t()/_tl()/gettext() in Python."""
import ast
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

import polib

ROOT = Path(__file__).resolve().parent.parent
SKIP = {".venv", "venv", "node_modules", "staticfiles"}
TR = ROOT / "tools" / "i18n_en.json"
KINDS: dict = {}  # msgid -> where it is looked up from: "trans" (a template literal: % is doubled), "block", "plain"


def unq(s: str) -> str:
    return re.sub(r"\\(.)", r"\1", s)


def template_ids(path: Path, text: str):
    for m in re.finditer(r"\{%\s*(?:trans|translate)\s+(\"((?:[^\"\\]|\\.)*)\"|'((?:[^'\\]|\\.)*)')", text):
        yield unq(m.group(2) if m.group(2) is not None else m.group(3)), "trans"
    for m in re.finditer(r"[=\s(]_\((\"((?:[^\"\\]|\\.)*)\"|'((?:[^'\\]|\\.)*)')\)", text):
        yield unq(m.group(2) if m.group(2) is not None else m.group(3)), "trans"
    for m in re.finditer(r"\{%\s*jt\s+(\"((?:[^\"\\]|\\.)*)\"|'((?:[^'\\]|\\.)*)')", text):
        yield unq(m.group(2) if m.group(2) is not None else m.group(3)), "plain"
    for m in re.finditer(r"\{%\s*(?:blocktrans|blocktranslate)\b[^%]*%\}(.*?)\{%\s*end(?:blocktrans|blocktranslate)\s*%\}", text, re.S):
        body = m.group(1)
        body = re.sub(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}", lambda v: "%(" + v.group(1) + ")s", body.replace("%", "%%"))
        yield body, "block"


def python_ids(path: Path, text: str):
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and n.args and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
            f = n.func
            name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
            if name in ("_t", "_tl", "gettext", "gettext_lazy"):
                yield n.args[0].value, "plain"


def extract() -> "OrderedDict[str, list]":
    ids: "OrderedDict[str, list]" = OrderedDict()
    import os
    files = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP and d not in (".git", "static", "media", "work", "locale", "__pycache__")]
        files += [Path(dirpath) / f for f in filenames if f.endswith((".html", ".py"))]
    for path in sorted(files):
        rel = str(path.relative_to(ROOT))
        if path.name == "tests.py" or "/migrations/" in rel or rel.startswith("tools/"):
            continue
        text = path.read_text(encoding="utf-8")
        gen = template_ids(path, text) if path.suffix == ".html" else python_ids(path, text)
        for msgid, kind in gen:
            if msgid.strip():
                ids.setdefault(msgid, []).append(rel)
                KINDS.setdefault(msgid, set()).add(kind)
    return ids


def shape(s: str):
    """What a translation must keep: placeholders and tags."""
    return (sorted(re.findall(r"%\([a-z_0-9]+\)s", s)), sorted(re.findall(r"\{[a-z_0-9]+\}", s)),
            sorted(re.findall(r"\$\{[^}]*\}", s)), sorted(re.findall(r"</?[A-Za-z][A-Za-z0-9]*", s)))  # tag names: an attribute inside a tag may be translated


def main():
    ids = extract()
    tr = json.loads(TR.read_text(encoding="utf-8")) if TR.exists() else {}
    if "--todo" in sys.argv:
        n = int(sys.argv[sys.argv.index("--todo") + 1])
        todo = [m for m in ids if m not in tr]
        for i, m in enumerate(todo[:n]):
            print(f"{i}\t{m}")
        print(f"# {len(todo)} untranslated of {len(ids)}", file=sys.stderr)
        return
    if "--apply" in sys.argv:  # stdin: "index<TAB>English" lines against the current --todo order
        todo = [m for m in ids if m not in tr]
        n = 0
        for line in sys.stdin.read().splitlines():
            if not line.strip():
                continue
            idx, _, en = line.partition("\t")
            if not en.strip() or not idx.isdigit() or int(idx) >= len(todo):
                continue
            msgid = todo[int(idx)]
            if shape(msgid) != shape(en):
                print("SHAPE MISMATCH, skipped:", idx, msgid[:80], "=>", en[:80]); continue
            tr[msgid] = en; n += 1
        TR.write_text(json.dumps(tr, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
        print(f"applied {n}; {len([m for m in ids if m not in tr])} left")
        return
    po = polib.POFile()
    po.metadata = {"Project-Id-Version": "CodeArena", "Language": "en", "MIME-Version": "1.0",
                   "Content-Type": "text/plain; charset=UTF-8", "Content-Transfer-Encoding": "8bit"}
    missing = bad = 0
    for msgid, refs in ids.items():
        msgstr = tr.get(msgid, "")
        if msgstr and shape(msgid) != shape(msgstr):
            print("SHAPE MISMATCH:", msgid[:90], "=>", msgstr[:90]); bad += 1; msgstr = ""
        if not msgstr:
            missing += 1
        forms = []  # a template literal is looked up with its % doubled, Python and {% jt %} as written
        kinds = KINDS.get(msgid, {"plain"})
        if "trans" in kinds:
            forms.append((msgid.replace("%", "%%"), msgstr.replace("%", "%%")))
        if kinds - {"trans"}:
            forms.append((msgid, msgstr))
        forms = list(dict.fromkeys(forms))
        for mid, mstr in forms:
            po.append(polib.POEntry(msgid=mid, msgstr=mstr, occurrences=[(r, "") for r in refs[:2]]))
    out = ROOT / "locale" / "en" / "LC_MESSAGES"
    out.mkdir(parents=True, exist_ok=True)
    po.save(str(out / "django.po"))
    po.save_as_mofile(str(out / "django.mo"))
    stale = [m for m in tr if m not in ids]
    print(f"{len(ids)} msgids, {len(ids) - missing} translated, {missing} missing, {bad} shape errors, {len(stale)} stale translations")


if __name__ == "__main__":
    main()
