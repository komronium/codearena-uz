"""A page's critical CSS: just the rules the page uses (tools/critical_css.py measures them), inline in its head, with
the whole stylesheet fetched when the visitor first touches the page. The 300 KB stylesheet, which a page uses a
twentieth of, then stays out of the way of its first paint. If the critical file is missing or was made for another
version of app.css, the tag writes the ordinary stylesheet link, so a stale file can never leave a page unstyled."""
import hashlib
import re

from django import template
from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()
_cache: dict = {}

# the first real touch: a press, a key, a wheel, a scroll that moved the page, a mouse that moved. (A synthetic mouseover
# after layout, or a scroll to the top, is not one: nobody is looking at the page yet, and a crawler never does any.)
_LOADER = ('(function(){var d=0,u=%s,w=window;function g(){if(d)return;d=1;'
           'var l=document.createElement("link");l.rel="stylesheet";l.href=u;document.head.appendChild(l)}'
           '["pointerdown","keydown","touchstart","wheel"].forEach(function(e){w.addEventListener(e,g,{capture:true,once:true,passive:true})});'
           'w.addEventListener("mousemove",function(e){if(e.movementX||e.movementY)g()},{capture:true,passive:true});'
           'w.addEventListener("scroll",function(){if(w.scrollY>0)g()},{capture:true,passive:true});'
           'setTimeout(g,15000)})();')


def _critical(name: str) -> str | None:
    """The file's CSS if it was cut from the current app.css, else None (kept per process; a dev server re-reads it)."""
    if name in _cache and not settings.DEBUG:
        return _cache[name]
    css = None
    app, small = finders.find("css/app.css"), finders.find(f"css/critical-{name}.css")
    if app and small:
        with open(small, encoding="utf-8") as handle:
            text = handle.read()
        with open(app, "rb") as handle:
            current = hashlib.md5(handle.read()).hexdigest()[:12]
        # the file's urls are relative to /static/css/; inline they must name the files themselves (hashed ones in production)
        css = re.sub(r"url\(\.\./([^)]+)\)", lambda m: f"url({static(m.group(1))})", text) if text.startswith(f"/*app:{current}*/") else None
    _cache[name] = css
    return css


@register.simple_tag
def critical_css(name: str):
    full = static("css/app.css")
    css = _critical(name)
    if css is None:
        return format_html('<link rel="stylesheet" href="{}">', full)
    import json
    return format_html('<style>{}</style>\n  <script>{}</script>\n  <noscript><link rel="stylesheet" href="{}"></noscript>\n'
                       '  <link rel="prefetch" href="{}">',
                       mark_safe(css), mark_safe(_LOADER % json.dumps(full)), full, full)
