"""What search engines and link previews read in the page head."""
import json
from html import unescape

from django import template
from django.conf import settings
from django.templatetags.static import static
from django.utils.html import format_html, format_html_join, strip_tags
from django.utils.safestring import mark_safe
from django.utils.text import Truncator

register = template.Library()

SITE_NAME = "CodeArena"
# Other projects are called CodeArena too, and Google won't show one site name for two sites; it falls
# back to these, the domain last (its site-name guide).
ALTERNATE_NAMES = ["CodeArena.uz", "codearena.uz"]
SITE_DESCRIPTION = ("O‘zbek tilida dasturlash: masalalar yeching, mavzulab kurslarda o‘rganing, "
                    "reytingli musobaqalarda bellashing. Kodingiz serverda shu zahoti testlanadi.")

# staff tools and one person's own pages; robots.txt keeps crawlers out of them too
_PRIVATE_NAMESPACES = {"moderation", "integrity", "classroom", "submissions"}
_JSON_IN_SCRIPT = {ord("<"): "\\u003C", ord(">"): "\\u003E", ord("&"): "\\u0026"}


@register.filter
def plain(html: str, length: int = 155) -> str:
    """Rendered markdown as one line of text for a meta description (about what a result shows)."""
    return Truncator(" ".join(unescape(strip_tags(html)).split())).chars(length)


def _plain_page(request) -> str:
    """The page number of a plain paginated list past its first page, else ""."""
    page = request.GET.get("page", "")
    return page if page.isdigit() and page != "1" and set(request.GET) == {"page"} else ""


@register.simple_tag(takes_context=True)
def canonical_url(context) -> str:
    """This page's address without filters or tracking: the path, plus the page of a plain paginated
    list (a filtered list's page 2 is another list's, so filtered views all point at the list itself)."""
    request = context["request"]
    page = _plain_page(request)
    return request.build_absolute_uri(request.path) + (f"?page={page}" if page else "")


@register.simple_tag(takes_context=True)
def page_suffix(context) -> str:
    """" — 2-sahifa" in the title of a plain list's later pages, so they don't share the first page's."""
    page = _plain_page(context["request"])
    return f" — {page}-sahifa" if page else ""


@register.simple_tag(takes_context=True)
def robots_meta(context) -> str:
    """The default robots meta: staff and personal pages stay out of the index; elsewhere a result may
    show the page's picture large. A page that should stay out says so in its own {% block robots %}."""
    match = getattr(context.get("request"), "resolver_match", None)
    return "noindex" if match and match.namespace in _PRIVATE_NAMESPACES else "max-image-preview:large"


@register.simple_tag
def site_description() -> str:
    return SITE_DESCRIPTION


@register.simple_tag
def verification_meta() -> str:
    """The site-ownership tags of Google Search Console and Yandex Webmaster, when their codes are set."""
    return format_html_join("", '<meta name="{}" content="{}">',
                            ((name, code) for name, code in settings.SITE_VERIFICATION.items() if code))


class CaptureNode(template.Node):
    def __init__(self, nodelist, name):
        self.nodelist, self.name = nodelist, name

    def render(self, context):
        # the body is already escaped; only the line breaks and indentation of its template go
        context[self.name] = mark_safe(" ".join(self.nodelist.render(context).split()))
        return ""


@register.tag
def capture(parser, token):
    """{% capture name %}…{% endcapture %} renders its body once into `name`, so the title and the
    description fill their own tags and the Open Graph ones from the same blocks."""
    bits = token.split_contents()
    if len(bits) != 2:
        raise template.TemplateSyntaxError("{% capture %} takes one variable name")
    nodelist = parser.parse(("endcapture",))
    parser.delete_first_token()
    return CaptureNode(nodelist, bits[1])


def _ld(data: dict) -> str:
    """A JSON-LD block; <, > and & are escaped so no text can close the script early."""
    return format_html('<script type="application/ld+json">{}</script>',
                       mark_safe(json.dumps(data, ensure_ascii=False).translate(_JSON_IN_SCRIPT)))


@register.simple_tag(takes_context=True)
def site_jsonld(context) -> str:
    """The home page's WebSite (the site name Google shows over a result) and Organization (its logo)."""
    request = context["request"]
    home = request.build_absolute_uri("/")
    site = {"@context": "https://schema.org", "@type": "WebSite", "name": SITE_NAME,
            "alternateName": ALTERNATE_NAMES, "url": home, "inLanguage": "uz", "description": SITE_DESCRIPTION}
    org = {"@context": "https://schema.org", "@type": "Organization", "name": SITE_NAME, "url": home,
           "logo": request.build_absolute_uri(static("img/icon-512.png")), "description": SITE_DESCRIPTION}
    if settings.SITE_SAME_AS:
        org["sameAs"] = settings.SITE_SAME_AS
    return _ld(site) + _ld(org)


@register.simple_tag(takes_context=True)
def breadcrumbs_jsonld(context, *trail) -> str:
    """BreadcrumbList from name, path pairs, the section first and this page last: the trail desktop
    results show in place of the bare address."""
    request = context["request"]
    return _ld({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": n, "name": str(name), "item": request.build_absolute_uri(path)}
        for n, (name, path) in enumerate(zip(trail[::2], trail[1::2]), 1)]})


@register.simple_tag(takes_context=True)
def profile_jsonld(context, person, description="") -> str:
    """ProfilePage for a user's page, under the handle the page itself leads with. No real name and no
    photo: students are known here by their handles, and robots.txt keeps avatars out of image search."""
    request = context["request"]
    entity = {"@type": "Person", "name": person.username, "identifier": str(person.pk),
              "url": request.build_absolute_uri(request.path)}
    if description:
        entity["description"] = unescape(str(description))
    return _ld({"@context": "https://schema.org", "@type": "ProfilePage", "mainEntity": entity,
                "dateCreated": person.date_joined.isoformat(timespec="seconds")})
