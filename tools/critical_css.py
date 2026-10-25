"""Measures which rules of static/css/app.css a page uses, in a real browser at many widths and in both themes, and
writes static/css/critical-<name>.css with just those (frontend/critical.mjs does the cutting). The landing page
inlines that file and loads the whole stylesheet only when the visitor first touches the page, which keeps the
~300 KB stylesheet off its way to the first paint. A page's critical file is used only while its first line names the
current app.css (apps/home/templatetags/critical.py): after a CSS change run this again; until then the page falls
back to the whole stylesheet in the head.

  needs: playwright (+ chromium) in the Python you run it with, a dev server on the demo data (as a guest), and
         npm ci in frontend/ (postcss)
  python tools/critical_css.py --base http://127.0.0.1:8765
"""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
# name -> (path to measure, the font families it uses)
PAGES = {"landing": ("/", ["Lato", "JetBrains Mono"])}
WIDTHS = [360, 412, 600, 768, 820, 1024, 1280, 1366, 1536, 1920]
THEMES = [("light", None), ("dark", None), ("light", "dark"), ("dark", "light")]  # (OS scheme, theme chosen on the site)


def open_hidden_parts(page) -> None:
    """Rules of what is closed (menus, dialogs) are not matched while it is display: none, so open each part once."""
    for selector in ("#theme-toggle", "[data-palette-open]", "[data-menu-open]", "#user-menu-toggle"):
        for button in page.query_selector_all(selector):
            if button.is_visible():
                button.evaluate("el => el.click()")  # a script click: a bar or a sheet over the button cannot intercept it
                page.wait_for_timeout(150)
                page.keyboard.press("Escape")
                page.evaluate("document.querySelectorAll('dialog[open]').forEach(d => d.close()); document.querySelectorAll('details[open]').forEach(d => d.open = false)")
    page.keyboard.press("?")  # the shortcuts dialog
    page.wait_for_timeout(150)
    page.keyboard.press("Escape")


def measure(base: str, path: str) -> list[int]:
    starts: set[int] = set()
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        for width in WIDTHS:
            for mobile in ([True, False] if width <= 820 else [False]):
                for scheme, chosen in THEMES + [("light", "reduce")]:
                    reduce = chosen == "reduce"
                    ctx = browser.new_context(viewport={"width": width, "height": 900}, color_scheme=scheme, is_mobile=mobile,
                                              has_touch=mobile, reduced_motion="reduce" if reduce else "no-preference")
                    if chosen and not reduce:
                        ctx.add_init_script(f"try {{ localStorage.setItem('ca-theme', '{chosen}'); }} catch (e) {{}}")
                    page = ctx.new_page()
                    cdp = ctx.new_cdp_session(page)
                    sheets: dict[str, str] = {}
                    cdp.on("CSS.styleSheetAdded", lambda e, s=sheets: s.__setitem__(e["header"]["styleSheetId"], e["header"]["sourceURL"]))
                    cdp.send("DOM.enable")
                    cdp.send("CSS.enable")
                    cdp.send("CSS.startRuleUsageTracking")
                    page.goto(base + path, wait_until="load")
                    page.wait_for_timeout(700)
                    open_hidden_parts(page)
                    usage = cdp.send("CSS.stopRuleUsageTracking")["ruleUsage"]
                    ids = {i for i, url in sheets.items() if "/css/app." in url}
                    starts |= {r["startOffset"] for r in usage if r["used"] and r["styleSheetId"] in ids}
                    ctx.close()
        browser.close()
    return sorted(starts)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8765", help="a DEBUG server, which serves static/css/app.css as it is")
    args = ap.parse_args()
    for name, (path, families) in PAGES.items():
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(measure(args.base, path), handle)
        subprocess.run(["node", "critical.mjs", handle.name, str(ROOT / f"static/css/critical-{name}.css"), *families],
                       cwd=ROOT / "frontend", check=True)
