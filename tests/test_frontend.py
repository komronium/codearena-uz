"""The front end is self-hosted: frontend/build.mjs builds static/css, static/vendor,
static/fonts and templates/_importmap.html, and those outputs are committed."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from django.contrib.staticfiles import finders

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
TEMPLATES = sorted((ROOT / "templates").rglob("*.html"))


def test_templates_load_no_third_party_scripts_or_styles():
    """A CDN that is slow or blocked for a student must not leave the page unstyled."""
    offenders = [f"{t.relative_to(ROOT)}: {m.group(0)}" for t in TEMPLATES
                 for m in re.finditer(r'<(?:script|link)\b[^>]*\b(?:src|href)="https?://[^"]+"', t.read_text())]
    assert not offenders, "\n".join(offenders)


def test_every_static_path_in_templates_exists():
    missing = [f"{t.relative_to(ROOT)}: {path}" for t in TEMPLATES
               for path in re.findall(r"""\{% static ['"]([^'"]+)['"] %\}""", t.read_text())
               if finders.find(path) is None]
    assert not missing, "\n".join(missing)


@pytest.mark.skipif(shutil.which("node") is None or not (FRONTEND / "node_modules").is_dir(),
                    reason="needs Node and `npm ci` in frontend/")
def test_committed_build_matches_the_templates():
    """A class added to a template, or an icon, only exists once the CSS is rebuilt."""
    r = subprocess.run(["node", "build.mjs", "--check"], cwd=FRONTEND, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr or r.stdout


def test_tier_colours_are_not_used_raw_as_text():
    """Several tier colours fail contrast as text (Pupil green is 3.3:1 on white); text goes
    through .ca-tier-ink, which mixes the tier toward the theme's ink."""
    raw = re.compile(r"(?<![-\w])color:\s*(?:\{\{[^}]*(?:tier_color|t\.color)[^}]*\}\}|var\(--tier\))")
    sources = [*TEMPLATES, FRONTEND / "src" / "app.css"]
    offenders = [f"{p.relative_to(ROOT)}: {m.group(0)}" for p in sources for m in raw.finditer(p.read_text())]
    assert not offenders, "\n".join(offenders)
